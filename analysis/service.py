"""
Orchestration: the only module that touches extraction, storage, scoring and
the database together. The management command uses it now; the Phase 2 API
views will call the same functions.
"""

import logging
import uuid

from django.db import transaction

from analysis import corpus
from analysis.extractor import extract_text
from analysis.models import Analysis, JobDescription
from analysis.scorer import analyze_texts
from analysis.similarity import tokenize
from resumes.models import Resume
from storage import object_storage

logger = logging.getLogger(__name__)


def resume_storage_key(resume_id):
    # WHY key on the UUID, not the uploaded filename: filenames collide
    # ("resume.pdf" from every user) and can contain path characters.
    return f"resumes/{resume_id}.pdf"


def create_resume(filename, pdf_bytes):
    """Extract text, store the PDF, and save a Resume. Raises PDFExtractionError."""
    # WHY extract before uploading: a scanned or corrupt PDF raises here, so
    # we never store a file we are about to reject.
    extracted_text = extract_text(pdf_bytes)

    resume_id = uuid.uuid4()
    key = resume_storage_key(resume_id)
    object_storage.upload_file(key, pdf_bytes)

    try:
        return Resume.objects.create(
            id=resume_id,
            filename=filename,
            storage_key=key,
            extracted_text=extracted_text,
        )
    except Exception:
        # WHY clean up: storage and the database can't share a transaction. If
        # the row fails to save, nothing will ever reference the uploaded
        # object, so delete it instead of leaking an orphan in the bucket.
        logger.exception("Saving Resume failed; deleting uploaded object %s", key)
        object_storage.delete_file(key)
        raise


def run_analysis(resume, jd_text, title="", company=""):
    """
    Score a resume against JD text and save both the JD and the Analysis.

    Returns (analysis, result). The AnalysisResult also carries the score
    components (skill coverage, category balance) that aren't stored on the
    model, which the demo command prints as a breakdown.
    """
    # The JD being analysed isn't stored yet, so count it as one more document
    # for this analysis. The next corpus rebuild picks it up from the database.
    statistics = corpus.load().with_document(tokenize(jd_text))
    result = analyze_texts(resume.extracted_text, jd_text, corpus=statistics)

    # WHY atomic: a JobDescription without its Analysis is meaningless data
    # that would show up in no view. Either both rows exist or neither does.
    with transaction.atomic():
        job_description = JobDescription.objects.create(
            title=title,
            company=company,
            raw_text=jd_text,
        )
        analysis = save_analysis(resume, job_description, result)
    return analysis, result


def save_analysis(resume, job_description, result):
    """Persist an AnalysisResult. Shared by run_analysis and seed_demo."""
    return Analysis.objects.create(
        resume=resume,
        job_description=job_description,
        overall_score=result.overall_score,
        similarity_score=result.similarity_score,
        matched_skills=result.matched_skills,
        missing_skills=result.missing_skills,
        category_scores=result.category_scores,
        suggestions=result.suggestions,
    )
