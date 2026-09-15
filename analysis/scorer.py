"""
Turns a resume and a JD into a scored analysis. Pure Python, no Django, so it
can be tested and reasoned about without a database.
"""

from dataclasses import dataclass

from analysis.implications import infer_skills
from analysis.matcher import category_of, find_skill_spans, find_skills
from analysis.similarity import text_similarity
from analysis.skills import CATEGORY_LABELS, SKILL_TAXONOMY

# WHY these weights. They are a judgement call, not a truth:
#   0.45 skill coverage   - the most direct signal of fit. Recruiters and ATS
#                           filters screen on "does the resume name the
#                           required skills", so it gets the largest share.
#   0.35 cosine similarity - catches overlap the taxonomy doesn't know about
#                           (domain words, responsibilities, "scalable",
#                           "event platform"). Less than skills because text
#                           similarity rewards keyword-mirroring as much as
#                           real experience.
#   0.20 category balance - rewards breadth: a full-stack JD matched only on
#                           frontend skills should score lower than one
#                           matched across frontend, backend and databases.
#                           Smallest share because it overlaps with skill
#                           coverage; see _category_balance for the formula.
# They sum to 1.0 so the blend stays in [0, 1]. If I had labelled data (JDs
# with known interview outcomes) these would be fitted, not chosen.
SKILL_COVERAGE_WEIGHT = 0.45
SIMILARITY_WEIGHT = 0.35
CATEGORY_BALANCE_WEIGHT = 0.20

# WHY clamp to 5-97: a 100 claims a perfect fit, which no keyword analysis can
# honestly know, and a 0 almost always means something upstream broke (empty
# extraction, wrong file pasted). Neither is a credible thing to show a user.
MIN_SCORE = 5
MAX_SCORE = 97

MIN_SUGGESTIONS = 3
MAX_SUGGESTIONS = 5
MISSING_SKILLS_TO_SUGGEST = 3
MAX_INFERRED_TO_SUGGEST = 1
LOW_SIMILARITY_THRESHOLD = 0.15
WEAK_CATEGORY_THRESHOLD = 0.5


@dataclass
class AnalysisResult:
    overall_score: int
    similarity_score: float
    skill_coverage: float
    category_balance: float
    matched_skills: list
    missing_skills: list
    category_scores: dict
    suggestions: list


def clamp_score(score):
    if score < MIN_SCORE:
        return MIN_SCORE
    if score > MAX_SCORE:
        return MAX_SCORE
    return score


def compute_overall_score(skill_coverage, cosine_similarity, category_balance):
    blend = (
        SKILL_COVERAGE_WEIGHT * skill_coverage
        + SIMILARITY_WEIGHT * cosine_similarity
        + CATEGORY_BALANCE_WEIGHT * category_balance
    )
    # WHY scale before rounding: the blend is in [0, 1], so rounding it first
    # and then multiplying by 100 (as the spec's formula is literally written)
    # could only ever produce 0 or 100.
    raw_score = round(blend * 100)
    return clamp_score(raw_score)


def _sort_key_most_mentioned_first(skill):
    # WHY the name tie-break: without it, skills mentioned equally often come
    # out in dict order, and the same inputs could list gaps differently
    # between runs of the taxonomy. Stable output is easier to test and trust.
    return (-skill["jd_count"], skill["name"].lower())


def _split_matched_and_missing(jd_skills, resume_spans):
    matched = []
    missing = []
    # Skills the resume never names but must have, e.g. Python behind Django.
    inferred_chains = infer_skills(resume_spans)
    for name, jd_count in jd_skills.items():
        if name in resume_spans:
            matched.append({
                "name": name,
                "category": category_of(name),
                "jd_count": jd_count,
                "resume_count": len(resume_spans[name]),
                # WHY store positions: the UI highlights a skill's occurrences
                # in the resume text. Sending the matcher's own offsets means
                # the highlight can never disagree with the score, which a
                # second matcher reimplemented in JavaScript eventually would.
                "resume_spans": resume_spans[name],
                "inferred_from": None,
                "inference_path": None,
            })
        elif name in inferred_chains:
            # WHY count an inferred skill as covered: reporting Python as
            # "missing" from a Django developer's resume is simply wrong, and
            # it would tell them to add something they already have. The
            # graph's edges are deliberately conservative (see
            # implications.py), and the entry stays marked as inferred so the
            # UI never presents it as if the resume named it.
            chain = inferred_chains[name]
            source = chain[0]
            matched.append({
                "name": name,
                "category": category_of(name),
                "jd_count": jd_count,
                # For an inferred skill, count and spans describe the evidence:
                # where the skill that implies it appears in the resume.
                "resume_count": len(resume_spans[source]),
                "resume_spans": resume_spans[source],
                "inferred_from": source,
                "inference_path": chain,
            })
        else:
            missing.append({
                "name": name,
                "category": category_of(name),
                "jd_count": jd_count,
            })
    # Something the JD names five times matters more than something named once.
    matched.sort(key=_sort_key_most_mentioned_first)
    missing.sort(key=_sort_key_most_mentioned_first)
    return matched, missing


def _build_category_scores(matched, missing):
    """Per-category coverage, only for categories the JD actually asks about."""
    category_scores = {}
    # Iterate the taxonomy so categories always come out in the same order.
    for category in SKILL_TAXONOMY:
        matched_count = sum(1 for skill in matched if skill["category"] == category)
        missing_count = sum(1 for skill in missing if skill["category"] == category)
        required_count = matched_count + missing_count
        if required_count == 0:
            continue
        category_scores[category] = {
            "label": CATEGORY_LABELS[category],
            "matched": matched_count,
            "required": required_count,
            "coverage": round(matched_count / required_count, 4),
        }
    return category_scores


def _category_balance(category_scores):
    """
    Mean of per-category coverage over the categories the JD asks about.

        balance = sum(matched_c / required_c for each JD category c) / number of JD categories
    """
    # WHY the mean of coverages, not "fraction of categories with any match":
    # the first version counted a category as covered if even one of its
    # skills matched. On a real JD that asked for six concepts, a resume
    # matching one of them scored balance 1.0, adding the full 20 points for
    # breadth it didn't have. Averaging the per-category coverage fixes that
    # (1/6 in one category -> 0.167) and moves smoothly as skills are added,
    # instead of jumping from 0 to 1 on the first match.
    #
    # How it still differs from skill coverage: every category counts equally
    # regardless of size. A JD listing eight frontend skills and one database
    # skill gives the database the same weight as all of frontend, so missing
    # a whole area costs more here than in the per-skill fraction. When the JD
    # only asks about one category the two numbers are equal, which is correct:
    # there is no breadth to reward.
    if not category_scores:
        return 0.0
    total_coverage = 0.0
    for scores in category_scores.values():
        total_coverage += scores["matched"] / scores["required"]
    return total_coverage / len(category_scores)


def _missing_skill_suggestion(skill):
    name = skill["name"]
    count = skill["jd_count"]
    if count == 1:
        return (
            f"The JD mentions {name} once and it doesn't appear in your resume "
            f"— add it only if you've genuinely used it."
        )
    return (
        f"The JD mentions {name} {count} times but it doesn't appear in your "
        f"resume — consider adding it if you've used it."
    )


def _weakest_category(category_scores):
    weakest = None
    for category, scores in category_scores.items():
        if scores["coverage"] >= WEAK_CATEGORY_THRESHOLD:
            continue
        if weakest is None or scores["coverage"] < category_scores[weakest]["coverage"]:
            weakest = category
    return weakest


def build_suggestions(matched, missing, category_scores, similarity):
    suggestions = []
    jd_has_skills = bool(matched or missing)

    if not jd_has_skills:
        suggestions.append(
            "We couldn't recognise any technical skills in this job description. "
            "Check that you pasted the full JD, including the requirements section."
        )

    for skill in missing[:MISSING_SKILLS_TO_SUGGEST]:
        suggestions.append(_missing_skill_suggestion(skill))

    weakest = _weakest_category(category_scores)
    if weakest is not None:
        scores = category_scores[weakest]
        suggestions.append(
            f"Your resume covers {scores['matched']} of the {scores['required']} "
            f"{scores['label']} skills this JD asks for — that's the weakest area "
            f"to strengthen."
        )

    inferred = [skill for skill in matched if skill["inferred_from"]]
    for skill in inferred[:MAX_INFERRED_TO_SUGGEST]:
        # WHY suggest naming an inferred skill: the inference is ours. Keyword
        # filters and recruiters skimming for "Python" don't know that Django
        # implies it, so a skill that is only implied can still get a resume
        # screened out.
        suggestions.append(
            f"The JD asks for {skill['name']}. You list {skill['inferred_from']}, so you clearly "
            f"know it, but the word \"{skill['name']}\" never appears. Name it explicitly: "
            f"many screening tools search for the exact word."
        )

    if jd_has_skills and not missing:
        suggestions.append(
            "Every skill we detected in this JD is on your resume, named or implied. "
            "Focus on showing depth: what you built with them and what changed because of it."
        )

    if jd_has_skills and similarity < LOW_SIMILARITY_THRESHOLD:
        suggestions.append(
            "Your resume's wording overlaps very little with the JD. Where you have "
            "the matching experience, describe it in the JD's own terms."
        )

    # WHY fillers: the UI promises 3-5 suggestions. When a resume is a strong
    # match there are few gaps to talk about, so fall back to advice that is
    # always true rather than show a near-empty list.
    fillers = []
    if matched:
        top_matched = ", ".join(skill["name"] for skill in matched[:3])
        fillers.append(
            f"Lead with your strongest overlap with this role ({top_matched}) in "
            f"your summary and first project bullets."
        )
    fillers.append(
        "Quantify outcomes in your bullets (users served, latency reduced, test "
        "coverage) so matched skills read as experience, not a keyword list."
    )
    fillers.append(
        "Tailor your project descriptions to this company's domain so a recruiter "
        "can see the connection without having to infer it."
    )
    for filler in fillers:
        if len(suggestions) >= MIN_SUGGESTIONS:
            break
        suggestions.append(filler)

    return suggestions[:MAX_SUGGESTIONS]


def analyze_texts(resume_text, jd_text, corpus=None):
    """
    Score a resume against a job description.

    `corpus` is the CorpusStatistics used for IDF and must already count this
    job description. Without one, every JD term is weighted equally.
    """
    jd_skills = find_skills(jd_text)
    resume_spans = find_skill_spans(resume_text)
    matched, missing = _split_matched_and_missing(jd_skills, resume_spans)

    # WHY 0.0 when the JD has no recognised skills: coverage is undefined
    # (0 / 0). Scoring it as zero lets the clamp floor the result at 5 and the
    # suggestions explain why, instead of crashing or inventing a number.
    if jd_skills:
        skill_coverage = len(matched) / len(jd_skills)
    else:
        skill_coverage = 0.0

    category_scores = _build_category_scores(matched, missing)
    category_balance = _category_balance(category_scores)

    similarity = text_similarity(resume_text, jd_text, corpus)
    overall_score = compute_overall_score(skill_coverage, similarity, category_balance)
    suggestions = build_suggestions(matched, missing, category_scores, similarity)

    return AnalysisResult(
        overall_score=overall_score,
        similarity_score=round(similarity, 4),
        skill_coverage=round(skill_coverage, 4),
        category_balance=round(category_balance, 4),
        matched_skills=matched,
        missing_skills=missing,
        category_scores=category_scores,
        suggestions=suggestions,
    )
