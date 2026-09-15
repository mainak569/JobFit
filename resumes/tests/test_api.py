import io
import uuid

import pytest
from pypdf import PdfWriter
from rest_framework.test import APIClient

from analysis.models import Analysis, JobDescription
from analysis.service import run_analysis
from resumes.models import Resume

pytestmark = pytest.mark.django_db

JD_TEXT = "We need a React and TypeScript engineer comfortable with Docker, AWS and PostgreSQL."


@pytest.fixture
def client():
    return APIClient()


def upload(client, content, name="resume.pdf"):
    file = io.BytesIO(content)
    file.name = name
    return client.post("/api/resumes/", {"file": file}, format="multipart")


def assert_error(response, status_code, code):
    assert response.status_code == status_code, response.content
    body = response.json()
    assert set(body) == {"error"}
    assert body["error"]["code"] == code
    assert body["error"]["message"]
    return body["error"]


# --- POST /api/resumes/ ---------------------------------------------------------

def test_upload_extracts_stores_and_returns_preview(client, text_pdf, isolated_storage):
    response = upload(client, text_pdf)

    assert response.status_code == 201, response.content
    body = response.json()
    assert set(body) == {"id", "filename", "created_at", "text_length", "text_preview", "analysis_count"}
    assert body["filename"] == "resume.pdf"
    assert "React" in body["text_preview"]
    assert body["analysis_count"] == 0

    resume = Resume.objects.get(id=body["id"])
    assert (isolated_storage / resume.storage_key).read_bytes() == text_pdf


def test_upload_rejects_non_pdf_with_pdf_extension(client):
    error = assert_error(upload(client, b"MZ\x90\x00 this is an exe", name="resume.pdf"), 400, "validation_error")
    assert error["message"] == "file: The file is not a PDF."
    assert "file" in error["fields"]
    assert Resume.objects.count() == 0


def test_upload_rejects_files_over_5_mb(client):
    too_big = b"%PDF-1.4\n" + b"0" * (5 * 1024 * 1024)
    error = assert_error(upload(client, too_big), 400, "validation_error")
    assert "5 MB" in error["message"]


def test_upload_without_file_is_a_validation_error(client):
    assert_error(client.post("/api/resumes/", {}, format="multipart"), 400, "validation_error")


def test_upload_of_scanned_pdf_returns_422_and_stores_nothing(client, isolated_storage):
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    buffer = io.BytesIO()
    writer.write(buffer)

    error = assert_error(upload(client, buffer.getvalue()), 422, "scanned_pdf")
    assert "OCR" in error["message"]
    assert Resume.objects.count() == 0
    assert not isolated_storage.exists()


# --- No public list ---------------------------------------------------------------

def test_resumes_cannot_be_listed(client, text_pdf):
    upload(client, text_pdf)
    assert_error(client.get("/api/resumes/"), 405, "method_not_allowed")


# --- GET / DELETE /api/resumes/<id>/ ----------------------------------------------

def test_detail_includes_full_text(client, text_pdf):
    created = upload(client, text_pdf).json()
    body = client.get(f"/api/resumes/{created['id']}/").json()
    assert "unit tests in Jest" in body["extracted_text"]


def test_delete_removes_record_file_analyses_and_their_jds(client, text_pdf, isolated_storage):
    created = upload(client, text_pdf).json()
    resume = Resume.objects.get(id=created["id"])
    run_analysis(resume, JD_TEXT)
    stored_file = isolated_storage / resume.storage_key
    assert stored_file.exists()

    response = client.delete(f"/api/resumes/{created['id']}/")

    assert response.status_code == 204
    assert not Resume.objects.exists()
    assert not Analysis.objects.exists()
    assert not JobDescription.objects.exists()
    assert not stored_file.exists()


def test_delete_unknown_or_malformed_id_is_structured_404(client):
    assert_error(client.delete(f"/api/resumes/{uuid.uuid4()}/"), 404, "not_found")
    assert_error(client.delete("/api/resumes/not-a-uuid/"), 404, "not_found")


def test_storage_failure_returns_503_and_saves_nothing(client, text_pdf, monkeypatch):
    from storage import object_storage

    def failing_upload(key, data, content_type="application/pdf"):
        raise object_storage.StorageError("simulated outage")

    monkeypatch.setattr(object_storage, "upload_file", failing_upload)

    error = assert_error(upload(client, text_pdf), 503, "storage_unavailable")
    assert "try again" in error["message"]
    assert "simulated outage" not in error["message"]
    assert Resume.objects.count() == 0
