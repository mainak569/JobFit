"""
Word-boundary skill extraction from arbitrary text.

    find_skills("Built a React app with a Go backend")
    -> {"React": 1, "Go": 1}

Two interchangeable implementations with the same find_spans(text) method:

    RegexSkillMatcher         one compiled regex per skill, so one pass over
                              the text per skill
    AhoCorasickSkillMatcher   every alias of every skill in one automaton,
                              so one pass over the text in total

They must return identical results; the test suite checks that on real
documents and on randomly generated edge cases.
"""

import re
from collections import defaultdict

from analysis.aho_corasick import AhoCorasick
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

# The same rules as character sets, for the Aho-Corasick matcher.
NOT_ALLOWED_BEFORE = frozenset("abcdefghijklmnopqrstuvwxyz0123456789.&")
NOT_ALLOWED_AFTER = frozenset("abcdefghijklmnopqrstuvwxyz0123456789+#&")


def ordered_aliases(aliases):
    # WHY longest alias first: regex alternation takes the first branch that
    # matches, so "asp.net" must be tried before ".net" and "react native"
    # before "react", otherwise the shorter alias wins and the rest of the
    # phrase is left dangling. Both matchers use this order to break ties.
    return sorted(aliases, key=len, reverse=True)


# ---------------------------------------------------------------------------- regex


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


class RegexSkillMatcher:
    """One compiled regex per skill; each find_spans call scans the text once per skill."""

    def __init__(self, taxonomy):
        self.patterns = []  # (canonical name, compiled pattern)
        for skills in taxonomy.values():
            for name, aliases in skills:
                alternatives = "|".join(_alias_to_regex(alias) for alias in ordered_aliases(aliases))
                # WHY re.IGNORECASE instead of lowercasing the text first: str.lower()
                # can change a string's length ("İ" becomes two characters), which would
                # shift every highlight offset after it. With the flag, the [a-z0-9]
                # classes in the lookarounds also cover A-Z, and offsets stay true.
                pattern = re.compile(BOUNDARY_BEFORE + "(?:" + alternatives + ")" + BOUNDARY_AFTER, re.IGNORECASE)
                self.patterns.append((name, pattern))

    def find_spans(self, text):
        spans = {}
        for name, pattern in self.patterns:
            found = [[match.start(), match.end()] for match in pattern.finditer(text)]
            if found:
                spans[name] = found
        return spans


# ---------------------------------------------------------------------------- Aho-Corasick

# WHY these four: with re.IGNORECASE, Python treats "İ" and "ı" as "i", "ſ"
# (long s) as "s", and "K" (Kelvin sign) as "k", but str.lower() doesn't map
# them to those single ASCII letters. Folding them the same way is what keeps
# this matcher's results identical to the regex matcher's.
SPECIAL_CASE_FOLDS = {"İ": "i", "ı": "i", "ſ": "s", "K": "k"}


def _fold(character):
    if character in SPECIAL_CASE_FOLDS:
        return SPECIAL_CASE_FOLDS[character]
    lowered = character.lower()
    # Keep one character per character, so positions still line up.
    return lowered if len(lowered) == 1 else character


def normalize_for_matching(text):
    """
    Return (normalized text, original position of each normalized character).

    The automaton matches exact characters, so the regex's flexible parts are
    applied to the text instead: case is folded, every run of whitespace
    becomes one space (the regex's \\s+), and whitespace straight after a
    hyphen is removed (the regex's -\\s*). The position list maps every match
    back to the original text, so highlights still land on the right words.
    """
    characters = []
    positions = []
    index = 0
    length = len(text)
    while index < length:
        character = text[index]
        if character.isspace():
            run_end = index
            while run_end < length and text[run_end].isspace():
                run_end += 1
            if not (characters and characters[-1] == "-"):
                characters.append(" ")
                positions.append(index)
            index = run_end
            continue
        characters.append(_fold(character))
        positions.append(index)
        index += 1
    return "".join(characters), positions


class AhoCorasickSkillMatcher:
    """Every alias of every skill in one automaton; each find_spans call scans the text once."""

    def __init__(self, taxonomy):
        self.skill_order = []
        patterns = []
        self.pattern_owner = []  # pattern index -> (canonical name, priority within the skill)
        for skills in taxonomy.values():
            for name, aliases in skills:
                self.skill_order.append(name)
                for priority, alias in enumerate(ordered_aliases(aliases)):
                    if alias != alias.strip() or "  " in alias or "- " in alias:
                        raise ValueError(f"Alias {alias!r} has whitespace the normalizer would change")
                    patterns.append(alias)
                    self.pattern_owner.append((name, priority))
        self.automaton = AhoCorasick(patterns)

    def find_spans(self, text):
        normalized, positions = normalize_for_matching(text)

        # 1. One pass: every raw alias hit, kept only if its boundaries are valid.
        hits = defaultdict(list)
        for start, end, index in self.automaton.search(normalized):
            before = normalized[start - 1] if start > 0 else ""
            after = normalized[end] if end < len(normalized) else ""
            if before in NOT_ALLOWED_BEFORE or after in NOT_ALLOWED_AFTER:
                continue
            name, priority = self.pattern_owner[index]
            hits[name].append((start, priority, end))

        # 2. Per skill, choose matches the way the regex does: scanning left to
        #    right, the longest alias at the earliest start wins, and a match
        #    that overlaps the previous one is skipped.
        spans = {}
        for name in self.skill_order:
            if name not in hits:
                continue
            chosen = []
            cursor = 0
            for start, _priority, end in sorted(hits[name]):
                if start < cursor:
                    continue
                chosen.append([positions[start], positions[end - 1] + 1])
                cursor = end
            spans[name] = chosen
        return spans


# ---------------------------------------------------------------------------- public interface

REGEX_MATCHER = RegexSkillMatcher(SKILL_TAXONOMY)
AHO_CORASICK_MATCHER = AhoCorasickSkillMatcher(SKILL_TAXONOMY)
# WHY Aho-Corasick is the active matcher: measured with
# `python manage.py benchmark_matcher`, it was about 7.4x faster on the real
# 146-skill taxonomy (0.96 ms vs 7.05 ms for one 3.8k-character resume), and
# its time stayed flat at ~10 ms as the taxonomy grew to 8,146 skills while
# the regex matcher grew to 4.3 s, because the regex matcher scans the text
# once per skill. The regex matcher stays as the reference implementation:
# the test suite asserts both return identical results, which is what made
# the swap safe.
ACTIVE_MATCHER = AHO_CORASICK_MATCHER

SKILL_CATEGORY = {}  # canonical name -> category
for _category, _skills in SKILL_TAXONOMY.items():
    for _name, _aliases in _skills:
        SKILL_CATEGORY[_name] = _category


def find_skill_spans(text):
    """
    Return {canonical skill name: [[start, end], ...]} for every skill in text.

    Offsets index into the original text, so the frontend can highlight exactly
    the characters that matched. Each skill's aliases are tried longest first,
    so "React (react.js)" gives two spans for React, not three.
    """
    return ACTIVE_MATCHER.find_spans(text)


def find_skills(text):
    """Return {canonical skill name: number of mentions}. Case-insensitive."""
    counts = {}
    for name, skill_spans in find_skill_spans(text).items():
        counts[name] = len(skill_spans)
    return counts


def category_of(skill_name):
    return SKILL_CATEGORY[skill_name]
