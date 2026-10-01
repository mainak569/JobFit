"""
Picks what each interview question is about, from the skills the analysis
engine found. No LLM here: the LLM only phrases the questions and grades.

A plan is a list of slots: {"kind", "focus" (a skill or None), "reason"}.
"""

KIND_PROJECT = "project"
KIND_DEPTH = "depth"
KIND_INFERRED = "inferred"
KIND_GAP = "gap"
KIND_CORE = "core"
KIND_BEHAVIORAL = "behavioral"
KIND_GENERAL = "general"

# Also caps AI calls per interview at 8, which keeps it inside the free tiers.
QUESTION_COUNT = 6
MIN_QUESTIONS = 4


def _slot(kind, focus, reason):
    return {"kind": kind, "focus": focus, "reason": reason}


def _times(count):
    return "once" if count == 1 else f"{count} times"


def _by_mentions(counts):
    return sorted(counts, key=lambda name: (-counts[name], name.lower()))


def _finish(slots):
    while len(slots) < MIN_QUESTIONS - 1:
        slots.append(_slot(
            KIND_GENERAL, None,
            "Few specific skills were recognised; ask a solid general question for this role.",
        ))
    slots.append(_slot(
        KIND_BEHAVIORAL, None,
        "Every interview has one behavioural question: ownership, teamwork or handling a setback.",
    ))
    return slots[:QUESTION_COUNT]


def plan_from_match(matched, missing):
    """matched and missing come from the scorer, most mentioned first."""
    named = [skill for skill in matched if not skill.get("inferred_from")]
    inferred = [skill for skill in matched if skill.get("inferred_from")]

    slots = []
    if named:
        top = named[0]
        slots.append(_slot(
            KIND_PROJECT, top["name"],
            f"Warm-up: a project from the resume, ideally one that used {top['name']}, "
            f"which the JD mentions {_times(top['jd_count'])}.",
        ))
    for skill in named[1:3]:
        slots.append(_slot(
            KIND_DEPTH, skill["name"],
            f"The resume names {skill['name']} and the JD mentions it {_times(skill['jd_count'])}; "
            f"check real depth, not just familiarity.",
        ))
    for skill in inferred[:1]:
        slots.append(_slot(
            KIND_INFERRED, skill["name"],
            f"The resume never names {skill['name']} but lists {skill['inferred_from']}, "
            f"which implies it; confirm they actually know {skill['name']}.",
        ))
    gap_count = QUESTION_COUNT - 1 - len(slots)
    for skill in missing[:gap_count]:
        slots.append(_slot(
            KIND_GAP, skill["name"],
            f"The JD mentions {skill['name']} {_times(skill['jd_count'])} and the resume doesn't show it; "
            f"see how they would approach it or what related experience they have.",
        ))
    for skill in named[3:]:
        if len(slots) >= QUESTION_COUNT - 1:
            break
        slots.append(_slot(
            KIND_DEPTH, skill["name"],
            f"The resume names {skill['name']}, which the JD also asks for.",
        ))
    return _finish(slots)


def plan_from_resume(resume_skill_counts):
    names = _by_mentions(resume_skill_counts)
    slots = []
    if names:
        slots.append(_slot(
            KIND_PROJECT, names[0],
            f"Warm-up: a project from the resume, ideally one that used {names[0]}.",
        ))
    for name in names[1:QUESTION_COUNT - 1]:
        slots.append(_slot(
            KIND_DEPTH, name,
            f"The resume mentions {name} {_times(resume_skill_counts[name])}; check real depth.",
        ))
    return _finish(slots)


def plan_from_job(jd_skill_counts):
    names = _by_mentions(jd_skill_counts)
    slots = []
    for name in names[:QUESTION_COUNT - 1]:
        slots.append(_slot(
            KIND_CORE, name,
            f"The job description mentions {name} {_times(jd_skill_counts[name])}.",
        ))
    return _finish(slots)
