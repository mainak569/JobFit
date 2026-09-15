"""
Load the demo resume and four job descriptions, with analyses precomputed.

Expected files in the seed directory (default: samples/seed/):

    demo_resume.txt      plain resume text, contact details already removed
    jd_frontend.txt      \
    jd_backend.txt        |  each starts with a small header, then "---",
    jd_fullstack.txt      |  then the JD text:
    jd_sde_fresher.txt   /
                             Title: Frontend Engineer
                             Company: Example Corp
                             ---
                             <job description text>

Safe to run repeatedly: existing demo rows are replaced, not duplicated.
"""

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from analysis import corpus
from analysis.demo import DEMO_JOB_DESCRIPTIONS, DEMO_RESUME_ID, default_seed_dir, parse_jd_file
from analysis.models import JobDescription
from analysis.scorer import analyze_texts
from analysis.service import save_analysis
from resumes.models import Resume


class Command(BaseCommand):
    help = "Load the demo resume and four JDs with precomputed analyses (idempotent)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--seed-dir",
            default=str(default_seed_dir()),
            help="Directory containing demo_resume.txt and the four jd_*.txt files",
        )

    def handle(self, *args, **options):
        seed_dir = Path(options["seed_dir"])
        resume_path = seed_dir / "demo_resume.txt"
        expected = [resume_path] + [seed_dir / filename for filename, _id in DEMO_JOB_DESCRIPTIONS]
        missing = [path.name for path in expected if not path.is_file()]
        if missing:
            raise CommandError(f"Missing seed files in {seed_dir}: {', '.join(missing)}")

        resume_text = resume_path.read_text(encoding="utf-8").strip()
        job_descriptions = []
        for filename, jd_id in DEMO_JOB_DESCRIPTIONS:
            try:
                title, company, text = parse_jd_file(seed_dir / filename)
            except ValueError as exc:
                raise CommandError(str(exc)) from exc
            job_descriptions.append((jd_id, title, company, text))

        with transaction.atomic():
            Resume.objects.filter(id=DEMO_RESUME_ID).delete()
            JobDescription.objects.filter(id__in=[jd_id for _file, jd_id in DEMO_JOB_DESCRIPTIONS]).delete()

            # WHY no stored PDF (empty storage_key): the demo is public and the repo
            # is public. Seeding from text means no PDF with contact details is
            # ever committed or served; the UI only ever shows extracted text.
            resume = Resume.objects.create(
                id=DEMO_RESUME_ID,
                filename="demo_resume.pdf",
                storage_key="",
                extracted_text=resume_text,
            )

            stored = []
            for jd_id, title, company, text in job_descriptions:
                stored.append(JobDescription.objects.create(id=jd_id, title=title, company=company, raw_text=text))

            # Every seed JD is stored now, so the rebuilt corpus already counts
            # each of them; no with_document() needed when scoring them.
            statistics = corpus.rebuild()

            for job_description in stored:
                result = analyze_texts(resume_text, job_description.raw_text, corpus=statistics)
                save_analysis(resume, job_description, result)
                self.stdout.write(f"  {result.overall_score:>3}  {job_description}")

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded demo resume {DEMO_RESUME_ID} with 4 analyses "
                f"(IDF corpus: {statistics.document_count} job descriptions)."
            )
        )
