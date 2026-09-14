"""
Word-boundary skill extraction from arbitrary text.

    find_skills("Built a React app with a Go backend")
    -> {"React": 1, "Go": 1}
"""

import re

from analysis.skills import SKILL_TAXONOMY

# WHY: naive substring matching (`alias in text`) is the classic bug here.
# "r" is a substring of "react", "go" of "google", "java" of "javascript",
# "sql" of "postgresql". Every one of those produces a skill the resume doesn't
# have or a gap the JD didn't ask for.
#
# WHY not plain `\b`: `\b` sits between a word char [A-Za-z0-9_] and a non-word
# char. "+", "#" and "." are non-word chars, so `\bc\+\+\b` can never match
# "c++ " (there is no boundary between "+" and " "), and `\bc\b` happily
# matches the "c" in "c++" and "c#". So the boundaries are spelled out as
# lookarounds on the characters that actually make up skill names:
#
#   before: not a letter/digit (so "go" not in "google"),
#           not "." (so "js" not in "node.js"),
#           not "&" (so "d" in "R&D" can't start a match)
#   after:  not a letter/digit (so "r" not in "react", "java" not in "javascript"),
#           not "+" or "#" (so "c" not in "c++" or "c#"),
#           not "&" (so "r" not in "R&D")
#
# "." is allowed AFTER an alias so "I used React." still matches at the end of
# a sentence. "-" and "/" are treated as boundaries so "React-based" and
# "HTML/CSS" match; the cost is "go-to" matching Go.
BOUNDARY_BEFORE = r"(?<![a-z0-9.&])"
BOUNDARY_AFTER = r"(?![a-z0-9+#&])"


def _alias_to_regex(alias):
    escaped = re.escape(alias)
    # WHY: PDF extraction turns layout into whitespace unpredictably, so
    # "rest api" may arrive as "rest  api" or "rest\napi". Any run of
    # whitespace between words counts as the space.
    escaped = escaped.replace(r"\ ", r"\s+")
    # WHY: a hyphenated alias can be split across lines by the PDF
    # ("cloud-\nbased"), so allow optional whitespace after the hyphen.
    escaped = escaped.replace(r"\-", r"-\s*")
    return escaped


def _build_skill_pattern(aliases):
    # WHY: longest alias first. Regex alternation takes the first branch that
    # matches, so "asp.net" must be tried before ".net" and "react native"
    # before "react", otherwise the shorter alias wins and the rest of the
    # phrase is left dangling.
    ordered = sorted(aliases, key=len, reverse=True)
    alternatives = "|".join(_alias_to_regex(alias) for alias in ordered)
    # WHY re.IGNORECASE instead of lowercasing the text first: str.lower() can
    # change a string's length ("İ" becomes two characters), which would shift
    # every highlight offset after it. With the flag, the [a-z0-9] classes in
    # the lookarounds also cover A-Z, and offsets stay true to the original.
    return re.compile(BOUNDARY_BEFORE + "(?:" + alternatives + ")" + BOUNDARY_AFTER, re.IGNORECASE)


# WHY: compiled once at import. There are ~140 skills and every analysis scans
# two documents; recompiling ~280 regexes per request would be wasted work.
SKILL_PATTERNS = []  # list of (canonical name, category, compiled pattern)
SKILL_CATEGORY = {}  # canonical name -> category
for _category, _skills in SKILL_TAXONOMY.items():
    for _name, _aliases in _skills:
        SKILL_PATTERNS.append((_name, _category, _build_skill_pattern(_aliases)))
        SKILL_CATEGORY[_name] = _category


def find_skill_spans(text):
    """
    Return {canonical skill name: [[start, end], ...]} for every skill in text.

    Offsets index into the original text, so the frontend can highlight exactly
    the characters that matched. Each skill's aliases are one alternation, so
    "React (react.js)" gives two spans for React, not three.
    """
    spans = {}
    for name, _category, pattern in SKILL_PATTERNS:
        found = [[match.start(), match.end()] for match in pattern.finditer(text)]
        if found:
            spans[name] = found
    return spans


def find_skills(text):
    """Return {canonical skill name: number of mentions}. Case-insensitive."""
    counts = {}
    for name, skill_spans in find_skill_spans(text).items():
        counts[name] = len(skill_spans)
    return counts


def category_of(skill_name):
    return SKILL_CATEGORY[skill_name]
