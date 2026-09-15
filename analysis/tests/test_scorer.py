from analysis.scorer import (
    MAX_SCORE,
    MAX_SUGGESTIONS,
    MIN_SCORE,
    MIN_SUGGESTIONS,
    analyze_texts,
    clamp_score,
    compute_overall_score,
)


# --- Clamping -----------------------------------------------------------------

def test_score_is_clamped_at_the_bottom():
    assert compute_overall_score(0.0, 0.0, 0.0) == MIN_SCORE == 5


def test_score_is_clamped_at_the_top():
    assert compute_overall_score(1.0, 1.0, 1.0) == MAX_SCORE == 97


def test_clamp_score_bounds():
    assert clamp_score(-20) == 5
    assert clamp_score(4) == 5
    assert clamp_score(5) == 5
    assert clamp_score(50) == 50
    assert clamp_score(97) == 97
    assert clamp_score(98) == 97
    assert clamp_score(150) == 97


def test_weights_blend_before_rounding():
    # 0.45*0.6 + 0.35*0.6 + 0.20*0.6 = 0.6 -> 60. Rounding the blend before
    # multiplying by 100 would give 100 here.
    assert compute_overall_score(0.6, 0.6, 0.6) == 60
    # 0.45*1.0 + 0.35*0.0 + 0.20*0.5 = 0.55 -> 55
    assert compute_overall_score(1.0, 0.0, 0.5) == 55


# --- End to end on text ---------------------------------------------------------

def test_jd_with_no_recognised_skills_scores_floor_and_explains():
    result = analyze_texts("Python developer", "We want a passionate team player.")
    assert result.overall_score == MIN_SCORE
    assert result.matched_skills == []
    assert result.missing_skills == []
    assert "couldn't recognise any technical skills" in result.suggestions[0]
    assert MIN_SUGGESTIONS <= len(result.suggestions) <= MAX_SUGGESTIONS


def test_resume_identical_to_jd_is_capped_below_100():
    text = "React TypeScript Django PostgreSQL Docker AWS"
    assert analyze_texts(text, text).overall_score == MAX_SCORE


def test_missing_skills_are_sorted_most_mentioned_first():
    jd = "Docker, Docker, Docker, Docker. Kubernetes. AWS and AWS."
    result = analyze_texts("Python developer", jd)
    names = [skill["name"] for skill in result.missing_skills]
    assert names == ["Docker", "AWS", "Kubernetes"]
    assert result.missing_skills[0]["jd_count"] == 4
    assert result.suggestions[0] == (
        "The JD mentions Docker 4 times but it doesn't appear in your resume "
        "— consider adding it if you've used it."
    )


def test_matched_missing_and_categories():
    jd = "React and TypeScript on the frontend, Django and PostgreSQL on the backend."
    resume = "Built apps with React, Django and Python."
    result = analyze_texts(resume, jd)

    assert {s["name"] for s in result.matched_skills} == {"React", "Django"}
    assert {s["name"] for s in result.missing_skills} == {"TypeScript", "PostgreSQL"}
    assert result.skill_coverage == 0.5
    # JD categories: languages 0/1, frontend 1/1, backend 1/1, databases 0/1.
    # Mean coverage = (0 + 1 + 1 + 0) / 4.
    assert result.category_balance == 0.5
    assert result.category_scores["languages"]["matched"] == 0
    assert result.category_scores["databases"]["matched"] == 0
    assert result.category_scores["frontend"]["coverage"] == 1.0
    assert MIN_SUGGESTIONS <= len(result.suggestions) <= MAX_SUGGESTIONS


def test_one_match_in_a_category_is_not_full_balance():
    # The JD asks for six concepts; the resume has one. The old "any match
    # covers the category" rule scored this 1.0.
    jd = "AI, microservices, system design, caching, OOP and design patterns."
    result = analyze_texts("Built an AI assistant.", jd)
    assert result.category_scores["concepts"]["required"] == 6
    assert result.category_balance == round(1 / 6, 4)


def test_category_balance_weights_categories_equally():
    # frontend 3/3, databases 0/1: skill coverage is 3/4, balance is (1 + 0) / 2.
    jd = "React, Redux and Tailwind with PostgreSQL."
    result = analyze_texts("React, Redux, Tailwind.", jd)
    assert result.skill_coverage == 0.75
    assert result.category_balance == 0.5


# --- Implied skills ---------------------------------------------------------------

def test_skill_implied_by_the_resume_counts_as_covered_and_is_marked():
    result = analyze_texts("Backend developer. Built REST APIs with Django.", "We need Python and Django.")

    matched = {skill["name"]: skill for skill in result.matched_skills}
    assert result.missing_skills == []
    assert result.skill_coverage == 1.0
    assert matched["Django"]["inferred_from"] is None
    assert matched["Python"]["inferred_from"] == "Django"
    assert matched["Python"]["inference_path"] == ["Django", "Python"]
    # The spans point at the evidence: where "Django" appears.
    resume = "Backend developer. Built REST APIs with Django."
    assert [resume[start:end] for start, end in matched["Python"]["resume_spans"]] == ["Django"]


def test_implication_does_not_run_backwards():
    result = analyze_texts("Five years of JavaScript.", "We need React.")
    assert [skill["name"] for skill in result.missing_skills] == ["React"]
    assert result.matched_skills == []


def test_suggests_naming_an_implied_skill_explicitly():
    result = analyze_texts("Built dashboards in Next.js.", "Frontend role: JavaScript, React and Next.js.")
    assert any('the word "JavaScript" never appears' in s or 'the word "React" never appears' in s for s in result.suggestions)
