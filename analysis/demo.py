import uuid
from pathlib import Path

from django.conf import settings

# WHY a fixed UUID: the frontend's "Try the demo" button needs to find the demo
# resume on a cold visit without searching for it, and re-running seed_demo
# must replace these rows rather than add a second copy. A stable id does both.
# The frontend has the same value in src/lib/demo.js.
DEMO_RESUME_ID = uuid.UUID("00000000-0000-4000-8000-000000000001")

DEMO_JOB_DESCRIPTIONS = [
    ("jd_frontend.txt", uuid.UUID("00000000-0000-4000-8000-000000000101")),
    ("jd_backend.txt", uuid.UUID("00000000-0000-4000-8000-000000000102")),
    ("jd_fullstack.txt", uuid.UUID("00000000-0000-4000-8000-000000000103")),
    ("jd_sde_fresher.txt", uuid.UUID("00000000-0000-4000-8000-000000000104")),
]

HEADER_SEPARATOR = "---"


def default_seed_dir():
    return Path(settings.BASE_DIR) / "samples" / "seed"


def is_demo_resume(resume_id):
    return resume_id == DEMO_RESUME_ID


def parse_jd_file(path):
    """
    Return (title, company, text) from a seed JD file shaped like:

        Title: Frontend Engineer
        Company: Example Corp
        ---
        <job description text>

    Raises ValueError if the file doesn't follow that shape.
    """
    content = path.read_text(encoding="utf-8")
    if HEADER_SEPARATOR not in content:
        raise ValueError(f"{path.name}: missing the '---' line between the header and the JD text.")

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
        raise ValueError(f"{path.name}: the JD text after '---' is empty.")
    return title, company, text


def seed_job_description_texts(seed_dir=None):
    """[(job description id, text)] for every seed JD file that exists and parses."""
    seed_dir = seed_dir or default_seed_dir()
    texts = []
    for filename, jd_id in DEMO_JOB_DESCRIPTIONS:
        path = seed_dir / filename
        if not path.is_file():
            continue
        try:
            _title, _company, text = parse_jd_file(path)
        except ValueError:
            continue
        texts.append((jd_id, text))
    return texts
