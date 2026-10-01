from interviews import planner


def skill(name, jd_count=1, inferred_from=None):
    return {"name": name, "jd_count": jd_count, "inferred_from": inferred_from}


def kinds(plan):
    return [slot["kind"] for slot in plan]


def focuses(plan):
    return [slot["focus"] for slot in plan]


def test_match_plan_covers_project_depth_inferred_gap_and_behavioral():
    matched = [
        skill("React", 4),
        skill("TypeScript", 3),
        skill("Node.js", 2),
        skill("JavaScript", 2, inferred_from="React"),
    ]
    missing = [skill("Docker", 3), skill("AWS", 1)]

    plan = planner.plan_from_match(matched, missing)

    assert kinds(plan) == ["project", "depth", "depth", "inferred", "gap", "behavioral"]
    assert focuses(plan) == ["React", "TypeScript", "Node.js", "JavaScript", "Docker", None]
    assert len(plan) == planner.QUESTION_COUNT


def test_match_plan_with_few_matches_asks_more_about_gaps():
    plan = planner.plan_from_match([skill("Python", 2)], [skill("Docker", 3), skill("AWS", 2), skill("Redis", 1)])

    assert kinds(plan) == ["project", "gap", "gap", "gap", "behavioral"]
    assert focuses(plan)[1:4] == ["Docker", "AWS", "Redis"]


def test_match_plan_reasons_explain_the_choice():
    plan = planner.plan_from_match([skill("React", 2)], [skill("Docker", 1)])

    assert "2 times" in plan[0]["reason"]
    assert "once" in plan[1]["reason"]


def test_nothing_recognised_still_gives_a_usable_interview():
    for plan in (planner.plan_from_match([], []), planner.plan_from_resume({}), planner.plan_from_job({})):
        assert len(plan) == planner.MIN_QUESTIONS
        assert kinds(plan) == ["general", "general", "general", "behavioral"]


def test_resume_plan_questions_most_mentioned_skills():
    plan = planner.plan_from_resume({"Git": 1, "React": 5, "Python": 3, "SQL": 3})

    assert kinds(plan) == ["project", "depth", "depth", "depth", "behavioral"]
    # Most mentioned first; equal counts in name order.
    assert focuses(plan)[:4] == ["React", "Python", "SQL", "Git"]


def test_job_plan_caps_at_question_count():
    counts = {f"Skill{i}": i for i in range(1, 12)}

    plan = planner.plan_from_job(counts)

    assert len(plan) == planner.QUESTION_COUNT
    assert kinds(plan) == ["core"] * 5 + ["behavioral"]
    assert plan[0]["focus"] == "Skill11"


def test_plans_are_deterministic():
    matched = [skill("React", 2), skill("Vue", 2), skill("Angular", 2)]
    assert planner.plan_from_match(matched, []) == planner.plan_from_match(list(matched), [])
