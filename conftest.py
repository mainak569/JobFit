import pytest
from django.core.cache import cache

from storage.object_storage import REQUIRED_STORAGE_SETTINGS


LOCAL_DATABASE_HOSTS = {"", "localhost", "127.0.0.1", "::1"}


@pytest.fixture(scope="session", autouse=True)
def refuse_remote_test_database():
    # WHY: pytest-django creates and drops a "test_<name>" database on whatever
    # server DATABASE_URL points at. When a local .env pointed at the
    # production Neon database, test runs did exactly that over the internet,
    # ran 100x slower, and once left a stray test database behind. Tests only
    # ever need a local server (CI uses a Postgres service on localhost).
    from django.conf import settings

    host = settings.DATABASES["default"].get("HOST") or ""
    if host not in LOCAL_DATABASE_HOSTS and not host.startswith("/"):
        pytest.exit(
            f"Refusing to run tests against the database server at {host!r}. "
            "Tests create and drop a test database, so point DATABASE_URL at a "
            "local Postgres (for example postgres:///jobfit) before running pytest.",
            returncode=2,
        )


@pytest.fixture(autouse=True)
def isolated_storage(settings, tmp_path):
    # WHY autouse: if a developer's .env has real storage credentials, tests
    # must never upload to or delete from the real bucket.
    for name in REQUIRED_STORAGE_SETTINGS:
        setattr(settings, name, "")
    settings.MEDIA_ROOT = tmp_path / "media"
    return settings.MEDIA_ROOT


@pytest.fixture(autouse=True)
def clear_throttle_cache():
    # Throttle counts live in the cache; without this, tests would share them.
    cache.clear()
    yield
    cache.clear()


def build_text_pdf(lines):
    """
    A minimal one-page PDF with real selectable text, written by hand so tests
    don't need a PDF-generation library. Object offsets in the xref table are
    computed as the bytes are written.
    """
    content = ["BT", "/F1 11 Tf", "14 TL", "72 740 Td"]
    for line in lines:
        escaped = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        content.append(f"({escaped}) Tj T*")
    content.append("ET")
    stream = "\n".join(content).encode("latin-1")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]

    output = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(output))
        output += str(number).encode() + b" 0 obj\n" + body + b"\nendobj\n"

    xref_position = len(output)
    output += b"xref\n0 " + str(len(objects) + 1).encode() + b"\n"
    output += b"0000000000 65535 f \n"
    for offset in offsets:
        output += f"{offset:010d} 00000 n \n".encode()
    output += b"trailer\n<< /Size " + str(len(objects) + 1).encode() + b" /Root 1 0 R >>\n"
    output += b"startxref\n" + str(xref_position).encode() + b"\n%%EOF\n"
    return bytes(output)


@pytest.fixture
def text_pdf():
    return build_text_pdf([
        "Asha Verma - Frontend Developer",
        "Skills: JavaScript, TypeScript, React, Redux, Node.js, PostgreSQL, Git",
        "Built a React dashboard with REST APIs and unit tests in Jest.",
    ])
