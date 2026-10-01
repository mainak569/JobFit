import re

import pytest
from rest_framework.test import APIClient

from analysis.models import Analysis
from analysis.service import run_analysis
from interviews import llm
from interviews.models import InterviewMessage, InterviewSession
from resumes.models import Resume

pytestmark = pytest.mark.django_db

RESUME_TEXT = "Frontend developer. React, TypeScript, Redux, Node.js, PostgreSQL, GitHub, REST APIs. dev@example.com"
JD_TEXT = (
    "Frontend Engineer. You will build UIs in React and TypeScript, write unit tests with Jest, "
    "and ship through CI/CD on AWS. Docker experience is a plus. Strong Git skills."
)


class FakeAI:
    """
    Stands in for llm.chat_json. Writes numbered questions, follows up on the
    answers listed in follow_up_on, and gives every answer a 4. Runs the
    service's own validators, so their checks are exercised too.
    """

    def __init__(self):
        self.calls = []
        self.prompts = []
        self.follow_up_on = set()
        self.fail = False

    def __call__(self, messages, *, purpose, max_tokens, validate=None, transport=None):
        self.calls.append(purpose)
        content = messages[-1]["content"]
        self.prompts.append(content)
        if self.fail:
            raise llm.AIUnavailable("down")
        if purpose == "open":
            count = int(re.search(r"exactly (\d+) strings", content).group(1))
            reply = {"greeting": "Welcome!", "questions": [f"Question {n}?" for n in range(1, count + 1)]}
        elif purpose == "turn":
            answer = re.search(r"<answer>\n(.*)\n</answer>", content, re.S).group(1)
            follow_up = "Can you go deeper?" if answer in self.follow_up_on else None
            reply = {"follow_up": follow_up, "acknowledgement": "Thanks."}
        else:
            count = int(re.search(r"exactly (\d+) objects", content).group(1))
            reply = {
                "summary": "Good effort.",
                "questions": [
                    {"score": 4, "strengths": ["Clear"], "improvements": ["Add numbers"], "better_answer": "Outline."}
                    for _ in range(count)
                ],
            }
        return validate(reply) if validate else reply


@pytest.fixture
def ai(monkeypatch):
    fake = FakeAI()
    monkeypatch.setattr("interviews.service.llm.chat_json", fake)
    return fake


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def resume():
    return Resume.objects.create(filename="resume.pdf", storage_key="resumes/x.pdf", extracted_text=RESUME_TEXT)


@pytest.fixture
def analysis(resume):
    saved, _result = run_analysis(resume, JD_TEXT, title="Frontend Engineer", company="Acme")
    return saved


def start(client, **payload):
    return client.post("/api/interviews/", payload, format="json")


def answer(client, session, text):
    return client.post(
        f"/api/interviews/{session['id']}/answer/", {"text": text, "turn": session["turn"]}, format="json",
    )


def finish(client, session):
    return client.post(f"/api/interviews/{session['id']}/finish/", format="json")


def assert_error(response, status_code, code):
    assert response.status_code == status_code, response.content
    assert response.json()["error"]["code"] == code


# --- starting ----------------------------------------------------------------------

def test_start_from_analysis_plans_from_its_skills(client, ai, analysis):
    response = start(client, analysis_id=str(analysis.id))

    assert response.status_code == 201, response.content
    body = response.json()
    assert body["resume_id"] == str(analysis.resume_id)
    assert body["analysis_id"] == str(analysis.id)
    assert body["title"] == "Frontend Engineer at Acme"
    assert body["status"] == "in_progress"
    assert body["turn"] == 2
    assert [m["text"] for m in body["messages"]] == ["Welcome!", "Question 1?"]
    assert body["messages"][1]["question_index"] == 0
    assert ai.calls == ["open"]

    session = InterviewSession.objects.get(id=body["id"])
    focuses = [slot["focus"] for slot in session.plan]
    assert "React" in focuses
    assert "Docker" in focuses or "Jest" in focuses or "AWS" in focuses  # a gap from the analysis
    assert all(slot["question"] for slot in session.plan)
    # Contact details never reach the AI.
    assert "dev@example.com" not in ai.prompts[0]


def test_start_with_resume_and_pasted_jd(client, ai, resume):
    response = start(client, resume_id=str(resume.id), jd_text=JD_TEXT)

    assert response.status_code == 201, response.content
    assert response.json()["analysis_id"] is None
    # Nothing is saved as an analysis when starting directly.
    assert Analysis.objects.count() == 0


def test_start_with_role_preset_only(client, ai):
    response = start(client, role="backend")

    assert response.status_code == 201, response.content
    body = response.json()
    assert body["resume_id"] is None
    assert body["title"] == "Backend Engineer (Python)"
    assert "No resume was provided" in ai.prompts[0]


def test_start_with_resume_only(client, ai, resume):
    response = start(client, resume_id=str(resume.id))

    assert response.status_code == 201, response.content
    session = InterviewSession.objects.get(id=response.json()["id"])
    assert session.plan[0]["kind"] == "project"


@pytest.mark.parametrize("payload", [
    {},
    {"role": "astronaut"},
    {"role": "backend", "jd_text": JD_TEXT},
    {"jd_text": "too short"},
    {"resume_id": "not-a-uuid"},
])
def test_start_validates_input(client, ai, payload):
    assert_error(start(client, **payload), 400, "validation_error")
    assert ai.calls == []


def test_start_with_analysis_rejects_extra_fields(client, ai, analysis):
    assert_error(start(client, analysis_id=str(analysis.id), role="backend"), 400, "validation_error")


def test_start_unknown_analysis_or_resume_is_404(client, ai):
    assert_error(start(client, analysis_id="00000000-0000-4000-8000-00000000abcd"), 404, "not_found")
    assert_error(start(client, resume_id="00000000-0000-4000-8000-00000000abcd"), 404, "not_found")


def test_start_when_ai_is_down_saves_nothing(client, ai, resume):
    ai.fail = True

    assert_error(start(client, resume_id=str(resume.id)), 503, "ai_unavailable")
    assert InterviewSession.objects.count() == 0


def test_start_with_no_keys_configured_is_ai_unavailable(client, resume):
    # No fake: the real chat_json finds no configured provider.
    assert_error(start(client, resume_id=str(resume.id)), 503, "ai_unavailable")


def test_start_works_on_the_demo_resume(client, ai):
    from django.core.management import call_command

    from analysis.demo import DEMO_RESUME_ID

    call_command("seed_demo")
    demo_analysis = Analysis.objects.filter(resume_id=DEMO_RESUME_ID).first()

    response = start(client, analysis_id=str(demo_analysis.id))

    assert response.status_code == 201, response.content


def test_start_is_throttled_at_10_per_hour(client, ai):
    for _attempt in range(10):
        assert start(client, role="frontend").status_code == 201
    assert_error(start(client, role="frontend"), 429, "throttled")


# --- answering ---------------------------------------------------------------------

def test_full_interview_with_one_follow_up(client, ai, resume):
    session = start(client, role="frontend").json()
    question_count = session["question_count"]
    ai.follow_up_on = {"answer 1"}

    session = answer(client, session, "answer 1").json()
    # The follow-up comes before question 2, on the same question.
    assert session["messages"][-1] == {
        "order": 3, "speaker": "interviewer", "text": "Can you go deeper?", "question_index": 0, "is_follow_up": True,
    }
    assert session["current_question"] == 0

    calls_before = len(ai.calls)
    session = answer(client, session, "follow-up answer").json()
    # Answering a follow-up needs no AI call: the next question already exists.
    assert len(ai.calls) == calls_before
    assert session["messages"][-1]["text"] == "Question 2?"
    assert session["current_question"] == 1

    for number in range(2, question_count + 1):
        session = answer(client, session, f"answer {number}").json()

    assert session["questions_done"] is True
    assert session["messages"][-1]["question_index"] is None  # closing message
    assert_error(answer(client, session, "one more"), 409, "turn_conflict")

    report_session = finish(client, session).json()
    assert report_session["status"] == "completed"
    assert report_session["overall_score"] == 75  # all 4s on a 1-5 scale
    report = report_session["report"]
    assert report["summary"] == "Good effort."
    assert [q["index"] for q in report["questions"]] == list(range(question_count))
    assert report["questions"][0]["question"] == "Question 1?"
    # The follow-up and its answer went into the grading prompt.
    assert "Follow-up: Can you go deeper?" in ai.prompts[-1]
    assert ai.calls.count("report") == 1


def test_only_one_follow_up_per_question(client, ai):
    session = start(client, role="frontend").json()
    ai.follow_up_on = {"vague", "still vague"}

    session = answer(client, session, "vague").json()
    session = answer(client, session, "still vague").json()

    assert session["current_question"] == 1
    assert [m["is_follow_up"] for m in session["messages"]].count(True) == 2  # one question, one answer


def test_stale_turn_is_rejected_and_not_saved(client, ai):
    session = start(client, role="frontend").json()
    assert answer(client, session, "first click").status_code == 200

    assert_error(answer(client, session, "second click"), 409, "turn_conflict")
    assert InterviewMessage.objects.filter(text="second click").count() == 0


def test_answer_when_ai_is_down_saves_nothing(client, ai):
    session = start(client, role="frontend").json()
    ai.fail = True

    assert_error(answer(client, session, "my answer"), 503, "ai_unavailable")
    assert InterviewMessage.objects.filter(text="my answer").count() == 0


@pytest.mark.parametrize("text", ["", "   ", "x" * 4001])
def test_answer_validates_text(client, ai, text):
    session = start(client, role="frontend").json()
    assert_error(answer(client, session, text), 400, "validation_error")


def test_unknown_interview_is_404(client):
    assert_error(client.get("/api/interviews/00000000-0000-4000-8000-00000000abcd/"), 404, "not_found")
    assert_error(client.get("/api/interviews/not-a-uuid/"), 404, "not_found")


# --- finishing ---------------------------------------------------------------------

def test_finish_early_grades_only_answered_questions(client, ai):
    session = start(client, role="frontend").json()
    session = answer(client, session, "answer 1").json()
    session = answer(client, session, "answer 2").json()

    body = finish(client, session).json()

    assert [q["index"] for q in body["report"]["questions"]] == [0, 1]
    assert "exactly 2 objects" in ai.prompts[-1]


def test_finish_early_ignores_an_unanswered_follow_up(client, ai):
    session = start(client, role="frontend").json()
    ai.follow_up_on = {"vague"}
    session = answer(client, session, "vague").json()

    finish(client, session)

    assert "exactly 1 objects" in ai.prompts[-1]
    assert "Can you go deeper?" not in ai.prompts[-1]


def test_finish_without_answers_skips_the_ai(client, ai):
    session = start(client, role="frontend").json()

    body = finish(client, session).json()

    assert body["status"] == "completed"
    assert body["overall_score"] is None
    assert body["report"]["questions"] == []
    assert "report" not in ai.calls


def test_finish_twice_returns_the_same_report(client, ai):
    session = start(client, role="frontend").json()
    session = answer(client, session, "answer 1").json()
    first = finish(client, session).json()

    second = finish(client, session).json()

    assert second["report"] == first["report"]
    assert ai.calls.count("report") == 1
    assert_error(answer(client, second, "late"), 409, "interview_finished")


# --- deleting ----------------------------------------------------------------------

def test_delete_interview(client, ai):
    session = start(client, role="frontend").json()

    assert client.delete(f"/api/interviews/{session['id']}/").status_code == 204
    assert InterviewSession.objects.count() == 0
    assert InterviewMessage.objects.count() == 0


def test_deleting_the_resume_deletes_its_interviews(client, ai, resume):
    start(client, resume_id=str(resume.id))

    assert client.delete(f"/api/resumes/{resume.id}/").status_code == 204
    assert InterviewSession.objects.count() == 0


def test_deleting_the_analysis_keeps_the_interview(client, ai, analysis):
    session = start(client, analysis_id=str(analysis.id)).json()

    assert client.delete(f"/api/analyses/{analysis.id}/").status_code == 204
    assert client.get(f"/api/interviews/{session['id']}/").json()["analysis_id"] is None


def test_overall_score_maps_rubric_to_0_100():
    from interviews.service import overall_score

    assert overall_score([1, 1]) == 0
    assert overall_score([5]) == 100
    assert overall_score([3, 4]) == 62


# --- transcribing ------------------------------------------------------------------

def transcribe(client, session, data=b"OPUS-AUDIO", content_type="audio/webm"):
    from django.core.files.uploadedfile import SimpleUploadedFile

    audio = SimpleUploadedFile("answer.webm", data, content_type=content_type)
    return client.post(f"/api/interviews/{session['id']}/transcribe/", {"audio": audio}, format="multipart")


@pytest.fixture
def whisper(monkeypatch):
    calls = []

    def fake(audio, content_type, prompt="", transport=None):
        calls.append({"audio": audio, "content_type": content_type, "prompt": prompt})
        return "I would use Redux Toolkit."

    monkeypatch.setattr("interviews.views.speech.transcribe", fake)
    return calls


def test_transcribe_returns_text_and_saves_nothing(client, ai, whisper):
    session = start(client, role="frontend").json()

    response = transcribe(client, session)

    assert response.status_code == 200, response.content
    assert response.json() == {"text": "I would use Redux Toolkit."}
    assert whisper[0]["audio"] == b"OPUS-AUDIO"
    # The question being answered is passed as context.
    assert whisper[0]["prompt"] == "Question 1?"
    assert InterviewMessage.objects.filter(speaker="candidate").count() == 0


@pytest.mark.parametrize("data, content_type", [
    (b"", "audio/webm"),
    (b"x" * (5 * 1024 * 1024 + 1), "audio/webm"),
    (b"%PDF-1.4", "application/pdf"),
])
def test_transcribe_validates_audio(client, ai, whisper, data, content_type):
    session = start(client, role="frontend").json()

    assert_error(transcribe(client, session, data, content_type), 400, "validation_error")
    assert whisper == []


def test_transcribe_requires_a_file(client, ai, whisper):
    session = start(client, role="frontend").json()

    response = client.post(f"/api/interviews/{session['id']}/transcribe/", {}, format="multipart")

    assert_error(response, 400, "validation_error")


def test_transcribe_after_finishing_is_refused(client, ai, whisper):
    session = start(client, role="frontend").json()
    finish(client, session)

    assert_error(transcribe(client, session), 409, "interview_finished")


def test_transcribe_when_groq_is_down(client, ai, monkeypatch):
    def down(*args, **kwargs):
        raise llm.AIUnavailable("down")

    monkeypatch.setattr("interviews.views.speech.transcribe", down)
    session = start(client, role="frontend").json()

    response = transcribe(client, session)

    assert_error(response, 503, "ai_unavailable")
    assert "type your answer" in response.json()["error"]["message"]
