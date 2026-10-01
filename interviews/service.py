"""
Interview orchestration: planner, AI calls and database.

Each function makes at most one AI call, before its transaction, so a failed
call saves nothing and the client can just retry.
"""

import logging

from django.db import transaction

from analysis.matcher import find_skills
from analysis.scorer import analyze_texts
from interviews import llm, planner, prompts
from interviews.models import InterviewMessage, InterviewSession
from interviews.roles import load_role

logger = logging.getLogger(__name__)

CLOSING_MESSAGE = "That's all my questions. Thanks for your time, let's look at how it went."


class TurnConflict(Exception):
    pass


class InterviewFinished(Exception):
    pass


def _job_title(title, company):
    if title and company:
        return f"{title} at {company}"
    return title or company


def _plan_for(resume, analysis, jd_text):
    if analysis is not None:
        return planner.plan_from_match(analysis.matched_skills, analysis.missing_skills)
    if resume is not None and jd_text:
        # Not saved as an analysis; only the skill lists are needed.
        result = analyze_texts(resume.extracted_text, jd_text)
        return planner.plan_from_match(result.matched_skills, result.missing_skills)
    if resume is not None:
        return planner.plan_from_resume(find_skills(resume.extracted_text))
    return planner.plan_from_job(find_skills(jd_text))


def start_interview(resume=None, analysis=None, jd_text="", role=""):
    """Raises llm.AIUnavailable."""
    title = ""
    if analysis is not None:
        resume = analysis.resume
        jd_text = analysis.job_description.raw_text
        title = _job_title(analysis.job_description.title, analysis.job_description.company)
    elif role:
        title, jd_text = load_role(role)

    plan = _plan_for(resume, analysis, jd_text)
    resume_text = resume.extracted_text if resume is not None else ""
    opening = llm.chat_json(
        prompts.open_messages(title, plan, resume_text, jd_text),
        purpose="open",
        max_tokens=prompts.OPEN_MAX_TOKENS,
        validate=lambda reply: prompts.validate_open(reply, len(plan)),
    )
    for slot, question in zip(plan, opening["questions"]):
        slot["question"] = question

    with transaction.atomic():
        session = InterviewSession.objects.create(
            resume=resume,
            analysis=analysis,
            title=title[:255],
            jd_text=jd_text,
            plan=plan,
        )
        _add_message(session, 0, InterviewMessage.INTERVIEWER, opening["greeting"])
        _add_message(session, 1, InterviewMessage.INTERVIEWER, plan[0]["question"], question_index=0)
    return session


def _add_message(session, order, speaker, text, question_index=None, is_follow_up=False):
    return InterviewMessage.objects.create(
        session=session,
        order=order,
        speaker=speaker,
        text=text,
        question_index=question_index,
        is_follow_up=is_follow_up,
    )


def _check_turn(session, turn):
    if session.status == InterviewSession.COMPLETED:
        raise InterviewFinished()
    if session.questions_done or turn != session.messages.count():
        raise TurnConflict()


def submit_answer(session, text, turn):
    """`turn` is how many messages the client has seen; a stale one raises TurnConflict."""
    _check_turn(session, turn)
    index = session.current_question
    slot = session.plan[index]
    answering_follow_up = session.follow_up_asked

    follow_up = None
    acknowledgement = ""
    # One follow-up per question, so its answer needs no AI call.
    if not answering_follow_up:
        decision = llm.chat_json(
            prompts.turn_messages(session.title, slot, slot["question"], text),
            purpose="turn",
            max_tokens=prompts.TURN_MAX_TOKENS,
            validate=prompts.validate_turn,
        )
        follow_up = decision["follow_up"]
        acknowledgement = decision["acknowledgement"]

    with transaction.atomic():
        # Check again under the lock: another request may have won during the AI call.
        session = InterviewSession.objects.select_for_update().get(pk=session.pk)
        _check_turn(session, turn)
        order = turn
        _add_message(
            session, order, InterviewMessage.CANDIDATE, text,
            question_index=index, is_follow_up=answering_follow_up,
        )
        order += 1

        if follow_up:
            _add_message(
                session, order, InterviewMessage.INTERVIEWER, follow_up,
                question_index=index, is_follow_up=True,
            )
            session.follow_up_asked = True
        else:
            session.current_question = index + 1
            session.follow_up_asked = False
            if session.questions_done:
                _add_message(session, order, InterviewMessage.INTERVIEWER, CLOSING_MESSAGE)
            else:
                next_question = session.plan[session.current_question]["question"]
                if acknowledgement:
                    next_question = f"{acknowledgement} {next_question}"
                _add_message(
                    session, order, InterviewMessage.INTERVIEWER, next_question,
                    question_index=session.current_question,
                )
        session.save(update_fields=["current_question", "follow_up_asked", "updated_at"])
    return session


def _answered_items(session):
    items = {}
    for message in session.messages.all():
        index = message.question_index
        if index is None:
            continue
        slot = session.plan[index]
        item = items.setdefault(index, {
            "index": index,
            "kind": slot["kind"],
            "focus": slot["focus"],
            "question": slot["question"],
            "answer": None,
            "follow_up": None,
            "follow_up_answer": None,
        })
        if message.speaker == InterviewMessage.INTERVIEWER and message.is_follow_up:
            item["follow_up"] = message.text
        elif message.speaker == InterviewMessage.CANDIDATE and message.is_follow_up:
            item["follow_up_answer"] = message.text
        elif message.speaker == InterviewMessage.CANDIDATE:
            item["answer"] = message.text
    return [items[index] for index in sorted(items) if items[index]["answer"] is not None]


def overall_score(scores):
    """0-100 from 1-5 scores. A 1 is "no meaningful answer", so it maps to 0, not 20."""
    mean = sum(scores) / len(scores)
    return round((mean - 1) / 4 * 100)


def finish_interview(session):
    """Grades answered questions only, so ending early works. Raises llm.AIUnavailable."""
    if session.status == InterviewSession.COMPLETED:
        return session

    items = _answered_items(session)
    if not items:
        report = {"summary": "No questions were answered, so there is nothing to grade.", "questions": []}
        score = None
    else:
        graded = llm.chat_json(
            prompts.report_messages(session.title, items),
            purpose="report",
            max_tokens=prompts.REPORT_MAX_TOKENS,
            validate=lambda reply: prompts.validate_report(reply, len(items)),
        )
        questions = []
        for item, grade in zip(items, graded["questions"]):
            questions.append({
                "index": item["index"],
                "kind": item["kind"],
                "focus": item["focus"],
                "question": item["question"],
                **grade,
            })
        report = {"summary": graded["summary"], "questions": questions}
        score = overall_score([question["score"] for question in questions])

    with transaction.atomic():
        session = InterviewSession.objects.select_for_update().get(pk=session.pk)
        if session.status == InterviewSession.COMPLETED:
            return session
        session.report = report
        session.overall_score = score
        session.status = InterviewSession.COMPLETED
        session.save(update_fields=["report", "overall_score", "status", "updated_at"])
    return session
