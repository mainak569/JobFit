import uuid

# WHY a fixed UUID: the frontend's "Try the demo" button needs to find the demo
# resume on a cold visit without searching for it, and re-running seed_demo
# must replace these rows rather than add a second copy. A stable id does both.
# The frontend has the same value in src/lib/demo.js.
DEMO_RESUME_ID = uuid.UUID("00000000-0000-4000-8000-000000000001")


def is_demo_resume(resume_id):
    return resume_id == DEMO_RESUME_ID
