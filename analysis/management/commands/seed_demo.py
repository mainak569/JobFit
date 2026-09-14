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

import uuid
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from analysis.demo import DEMO_RESUME_ID
from analysis.models import JobDescription
from analysis.scorer import analyze_texts
from analysis.service import save_analysis
from resumes.models import Resume

# Fixed ids so re-running replaces rows instead of duplicating them; see analysis/demo.py.

DEMO_JOB_DESCRIPTIONS = [
    ("jd_frontend.txt", uuid.UUID("00000000-0000-4000-8000-000000000101")),
    ("jd_backend.txt", uuid.UUID("00000000-0000-4000-8000-000000000102")),
    ("jd_fullstack.txt", uuid.UUID("00000000-0000-4000-8000-000000000103")),
    ("jd_sde_fresher.txt", uuid.UUID("00000000-0000-4000-8000-000000000104")),
]

HEADER_SEPARATOR = "---"


def parse_jd_file(path):
    """Return (title, company, text) from a seed JD file."""
    content = path.read_text(encoding="utf-8")
    if HEADER_SEPARATOR not in content:
        raise CommandError(f"{path.name}: missing the '---' line between the header and the JD text.")

    header, text = content.split(HEADER_SEPARATOR, 1)
    title = ""
    company = ""
    for line in header.splitlines():
        key, _, value = line.partition(":")
        if key.strip().lower() == "title":
            title = value.strip()
        elif key.strip().lower() == "company":
            company = value.strip()

    text = text.strip()
    if not text:
        raise CommandError(f"{path.name}: the JD text after '---' is empty.")
    return title, company, text


class Command(BaseCommand):
    help = "Load the demo resume and four JDs with precomputed analyses (idempotent)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--seed-dir",
            default=str(Path(settings.BASE_DIR) / "samples" / "seed"),
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
        job_descriptions = [(jd_id, *parse_jd_file(seed_dir / filename)) for filename, jd_id in DEMO_JOB_DESCRIPTIONS]

        with transaction.atomic():
            Resume.objects.filter(id=DEMO_RESUME_ID).delete()
            JobDescription.objects.filter(id__in=[jd_id for _file, jd_id in DEMO_JOB_DESCRIPTIONS]).delete()

            # WHY no stored PDF (empty r2_key): the demo is public and the repo
            # is public. Seeding from text means no PDF with contact details is
            # ever committed or served; the UI only ever shows extracted text.
            resume = Resume.objects.create(
                id=DEMO_RESUME_ID,
                filename="demo_resume.pdf",
                r2_key="",
                extracted_text=resume_text,
            )

            for jd_id, title, company, text in job_descriptions:
                job_description = JobDescription.objects.create(id=jd_id, title=title, company=company, raw_text=text)
                result = analyze_texts(resume_text, text)
                save_analysis(resume, job_description, result)
                self.stdout.write(f"  {result.overall_score:>3}  {job_description}")

        self.stdout.write(self.style.SUCCESS(f"Seeded demo resume {DEMO_RESUME_ID} with 4 analyses."))
