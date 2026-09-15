import uuid

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from rest_framework.test import APIClient

from analysis.management.commands.seed_demo import DEMO_RESUME_ID
from analysis.models import Analysis, JobDescription
from resumes.models import Resume

pytestmark = pytest.mark.django_db

RESUME_TEXT = "Frontend developer. React, TypeScript, Redux, Node.js, PostgreSQL, Git, REST APIs."
FRONTEND_JD = (
    "Frontend Engineer. You will build UIs in React and TypeScript, write unit tests with Jest, "
    "and ship through CI/CD on AWS. Docker experience is a plus."
)
BACKEND_JD = (
    "Backend Engineer. Design REST APIs in Django and Python, model data in PostgreSQL, "
    "cache with Redis, and deploy with Docker on AWS."
)


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def resume():
    return Resume.objects.create(filename="resume.pdf", storage_key="resumes/x.pdf", extracted_text=RESUME_TEXT)


def analyze(client, resume_id, jd_text=FRONTEND_JD, **extra):
    payload = {"resume_id": str(resume_id), "jd_text": jd_text, **extra}
    return client.post("/api/analyze/", payload, format="json")


def assert_error(response, status_code, code):
    assert response.status_code == status_code, response.content
    body = response.json()
    assert set(body) == {"error"}
    assert body["error"]["code"] == code
    return body["error"]


# --- POST /api/analyze/ -------------------------------------------------------------

def test_analyze_returns_full_saved_analysis(client, resume):
    response = analyze(client, resume.id, title="Frontend Engineer", company="Acme")

    assert response.status_code == 201, response.content
    body = response.json()
    assert set(body) == {
        "id", "resume_id", "job_description", "overall_score", "similarity_score",
        "matched_skills", "missing_skills", "category_scores", "suggestions", "created_at",
    }
    assert body["resume_id"] == str(resume.id)
    assert body["job_description"]["title"] == "Frontend Engineer"
    assert 5 <= body["overall_score"] <= 97
    assert {"React", "TypeScript"} <= {skill["name"] for skill in body["matched_skills"]}
    assert "Docker" in {skill["name"] for skill in body["missing_skills"]}
    assert 3 <= len(body["suggestions"]) <= 5
    assert Analysis.objects.filter(id=body["id"]).exists()


def test_analyze_unknown_resume_is_404(client):
    assert_error(analyze(client, uuid.uuid4()), 404, "not_found")


def test_analyze_validates_input(client, resume):
    error = assert_error(analyze(client, resume.id, jd_text="too short"), 400, "validation_error")
    assert "jd_text" in error["fields"]
    error = assert_error(analyze(client, "nope"), 400, "validation_error")
    assert "resume_id" in error["fields"]


def test_analyze_is_throttled_at_20_per_hour(client, resume):
    for _attempt in range(20):
        assert analyze(client, resume.id).status_code == 201
    error = assert_error(analyze(client, resume.id), 429, "throttled")
    assert "available in" in error["message"]


# --- GET /api/analyses/ ---------------------------------------------------------------

def test_history_filters_by_resume_newest_first(client, resume):
    older = analyze(client, resume.id, title="Older").json()
    newer = analyze(client, resume.id, BACKEND_JD, title="Newer").json()
    other_resume = Resume.objects.create(filename="other.pdf", storage_key="k", extracted_text=RESUME_TEXT)
    analyze(client, other_resume.id)

    body = client.get(f"/api/analyses/?resume_id={resume.id}").json()

    assert body["count"] == 2
    assert [row["id"] for row in body["results"]] == [newer["id"], older["id"]]
    row = body["results"][0]
    assert set(row) == {
        "id", "resume_id", "job_description", "overall_score", "similarity_score",
        "matched_count", "missing_count", "created_at",
    }
    assert row["job_description"] == {"id": newer["job_description"]["id"], "title": "Newer", "company": ""}


def test_history_requires_a_valid_resume_id(client, resume):
    analyze(client, resume.id)
    assert_error(client.get("/api/analyses/"), 400, "validation_error")
    assert_error(client.get("/api/analyses/?resume_id=abc"), 400, "validation_error")


# --- GET / DELETE /api/analyses/<id>/ --------------------------------------------------

def test_analysis_detail_and_delete(client, resume):
    created = analyze(client, resume.id).json()

    detail = client.get(f"/api/analyses/{created['id']}/")
    assert detail.status_code == 200
    assert detail.json() == created

    assert client.delete(f"/api/analyses/{created['id']}/").status_code == 204
    assert not Analysis.objects.exists()
    assert not JobDescription.objects.exists()
    assert_error(client.get(f"/api/analyses/{created['id']}/"), 404, "not_found")


# --- GET /api/compare/ -------------------------------------------------------------------

def test_compare_is_table_shaped(client, resume):
    frontend = analyze(client, resume.id, FRONTEND_JD, title="Frontend").json()
    backend = analyze(client, resume.id, BACKEND_JD, title="Backend").json()

    body = client.get(f"/api/compare/?resume_id={resume.id}").json()

    assert body["resume"] == {"id": str(resume.id), "filename": "resume.pdf"}
    assert [column["analysis_id"] for column in body["columns"]] == [backend["id"], frontend["id"]]
    rows = {row["name"]: row["cells"] for row in body["rows"]}
    # Columns are [backend, frontend].
    assert rows["Docker"] == ["absent", "absent"]      # both JDs ask, resume lacks it
    assert rows["PostgreSQL"] == ["present", None]     # only the backend JD asks
    assert rows["React"] == [None, "present"]          # only the frontend JD asks
    # Skills asked for by both JDs sort before skills asked for by one.
    assert body["rows"][0]["cells"].count(None) == 0


def test_compare_requires_resume_id(client):
    assert_error(client.get("/api/compare/"), 400, "validation_error")
    assert_error(client.get(f"/api/compare/?resume_id={uuid.uuid4()}"), 404, "not_found")


# --- Cross-cutting -------------------------------------------------------------------------

def test_health(client):
    response = client.get("/api/health/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_root_returns_status(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "jobfit-api", "api": "/api/"}


def test_unknown_api_path_uses_error_shape(client):
    assert_error(client.get("/api/does-not-exist/"), 404, "not_found")


def test_unsafe_method_on_unknown_path_is_json_404_not_csrf_403():
    # enforce_csrf_checks makes the test client behave like a real browser.
    browser_like = APIClient(enforce_csrf_checks=True)
    assert_error(browser_like.delete("/api/resumes//"), 404, "not_found")
    assert_error(browser_like.post("/api/nope/", {}), 404, "not_found")


def test_method_not_allowed_uses_error_shape(client):
    assert_error(client.get("/api/analyze/"), 405, "method_not_allowed")


def test_cors_allows_configured_origin_only(client, settings):
    settings.CORS_ALLOWED_ORIGINS = ["http://localhost:5173"]
    allowed = client.get("/api/health/", HTTP_ORIGIN="http://localhost:5173")
    assert allowed["Access-Control-Allow-Origin"] == "http://localhost:5173"
    blocked = client.get("/api/health/", HTTP_ORIGIN="https://evil.example")
    assert "Access-Control-Allow-Origin" not in blocked


# --- seed_demo --------------------------------------------------------------------------------

def write_seed_dir(path):
    path.mkdir()
    (path / "demo_resume.txt").write_text(RESUME_TEXT)
    for name, jd in [("frontend", FRONTEND_JD), ("backend", BACKEND_JD), ("fullstack", FRONTEND_JD), ("sde_fresher", BACKEND_JD)]:
        (path / f"jd_{name}.txt").write_text(f"Title: {name}\nCompany: Example\n---\n{jd}\n")


def test_seed_demo_is_idempotent(tmp_path):
    seed_dir = tmp_path / "seed"
    write_seed_dir(seed_dir)

    call_command("seed_demo", seed_dir=str(seed_dir))
    call_command("seed_demo", seed_dir=str(seed_dir))

    resume = Resume.objects.get(id=DEMO_RESUME_ID)
    assert resume.storage_key == ""
    assert resume.analyses.count() == 4
    assert JobDescription.objects.count() == 4


def test_seed_demo_names_missing_files(tmp_path):
    with pytest.raises(CommandError, match="demo_resume.txt"):
        call_command("seed_demo", seed_dir=str(tmp_path))


# --- Demo resume is read-only -------------------------------------------------------------------

def test_demo_resume_cannot_be_analyzed_or_deleted(client, tmp_path):
    seed_dir = tmp_path / "seed"
    write_seed_dir(seed_dir)
    call_command("seed_demo", seed_dir=str(seed_dir))
    demo_analysis = Analysis.objects.filter(resume_id=DEMO_RESUME_ID).first()

    assert_error(analyze(client, DEMO_RESUME_ID), 403, "demo_read_only")
    assert_error(client.delete(f"/api/analyses/{demo_analysis.id}/"), 403, "demo_read_only")
    assert_error(client.delete(f"/api/resumes/{DEMO_RESUME_ID}/"), 403, "demo_read_only")
    assert Analysis.objects.filter(resume_id=DEMO_RESUME_ID).count() == 4

    # Reading it is fine: that's what "Try the demo" does.
    assert client.get(f"/api/resumes/{DEMO_RESUME_ID}/").status_code == 200
    assert client.get(f"/api/analyses/?resume_id={DEMO_RESUME_ID}").json()["count"] == 4


def test_matched_skills_carry_resume_spans(client, resume):
    body = analyze(client, resume.id).json()
    react = next(skill for skill in body["matched_skills"] if skill["name"] == "React")
    assert [RESUME_TEXT[start:end] for start, end in react["resume_spans"]] == ["React"]


def test_compare_marks_implied_skills_as_inferred(client):
    django_resume = Resume.objects.create(filename="django.pdf", storage_key="k", extracted_text="Built APIs with Django.")
    analyze(client, django_resume.id, "Backend role using Python and Django with PostgreSQL. " * 2)

    body = client.get(f"/api/compare/?resume_id={django_resume.id}").json()
    rows = {row["name"]: row["cells"] for row in body["rows"]}

    assert rows["Django"] == ["present"]
    assert rows["Python"] == ["inferred"]
    assert rows["PostgreSQL"] == ["absent"]
