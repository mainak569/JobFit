from analysis.matcher import find_skill_spans, find_skills
from analysis.skills import SKILL_TAXONOMY


# --- The two cases naive substring matching gets wrong -----------------------

def test_r_does_not_match_inside_react():
    skills = find_skills("Built dashboards in React and React Native.")
    assert "R" not in skills
    assert skills["React"] == 2


def test_standalone_r_still_matches():
    skills = find_skills("Statistical modelling in R, plus some Python.")
    assert skills["R"] == 1
    assert skills["Python"] == 1


def test_go_does_not_match_inside_google():
    skills = find_skills("Worked at Google on Google Cloud; goals were ambitious.")
    assert "Go" not in skills
    assert skills["GCP"] == 1


def test_standalone_go_still_matches():
    skills = find_skills("Backend services written in Go (golang).")
    assert skills["Go"] == 2


# --- Other substring traps ----------------------------------------------------

def test_java_does_not_match_inside_javascript():
    skills = find_skills("Strong JavaScript fundamentals")
    assert "Java" not in skills
    assert skills["JavaScript"] == 1


def test_sql_does_not_match_inside_postgresql():
    skills = find_skills("Experience with PostgreSQL")
    assert "SQL" not in skills
    assert skills["PostgreSQL"] == 1


def test_c_does_not_match_inside_cpp_or_csharp():
    skills = find_skills("C++, C# and .NET")
    assert "C" not in skills
    assert skills["C++"] == 1
    assert skills["C#"] == 1
    assert skills[".NET"] == 1


def test_symbol_skills_match_at_end_of_sentence():
    skills = find_skills("Languages: C, C++.")
    assert skills["C"] == 1
    assert skills["C++"] == 1


def test_r_and_d_is_not_the_r_language():
    assert "R" not in find_skills("Join our R&D team")


# --- General behaviour --------------------------------------------------------

def test_matching_is_case_insensitive():
    assert find_skills("REACT react React")["React"] == 3


def test_multi_word_alias_matches_across_line_break():
    assert find_skills("Design REST\nAPIs for mobile clients")["REST APIs"] == 1


def test_slash_and_hyphen_are_boundaries():
    skills = find_skills("HTML/CSS and React-based UIs")
    assert skills["HTML"] == 1
    assert skills["CSS"] == 1
    assert skills["React"] == 1


def test_english_rest_is_not_rest_apis():
    assert "REST APIs" not in find_skills("You and the rest of the team")


def test_taxonomy_has_at_least_120_unique_skills():
    names = [name for skills in SKILL_TAXONOMY.values() for name, _aliases in skills]
    assert len(names) >= 120
    assert len(names) == len(set(names))
    assert len(SKILL_TAXONOMY) == 6


def test_spans_index_the_original_text_case_preserved():
    text = "Built with REACT, React.js and Go."
    spans = find_skill_spans(text)
    assert [text[start:end] for start, end in spans["React"]] == ["REACT", "React.js"]
    assert [text[start:end] for start, end in spans["Go"]] == ["Go"]


# --- Aho-Corasick matcher: must agree with the regex matcher exactly ------------

import random
from pathlib import Path

import pytest

from analysis.matcher import AHO_CORASICK_MATCHER, REGEX_MATCHER, normalize_for_matching

EDGE_CASE_TEXTS = [
    "Built dashboards in React and React Native.",
    "Statistical modelling in R, plus some Python.",
    "Worked at Google on Google Cloud; goals were ambitious.",
    "Backend services written in Go (golang).",
    "Strong JavaScript fundamentals",
    "Experience with PostgreSQL",
    "C++, C# and .NET",
    "Languages: C, C++.",
    "Join our R&D team",
    "REACT react React",
    "Design REST\nAPIs for mobile clients",
    "HTML/CSS and React-based UIs",
    "You and the rest of the team",
    "Built with REACT, React.js and Go.",
    "cloud-\nbased platform, cloud -based, cloud-  based",
    "ASP.NET and .net core; node.js vs node js",
    "CI/CD, TCP/IP, PL/SQL and SQL Server",
    "Kotlin İstanbul ſql Kubernetes ıos",
    "",
    "   leading and trailing whitespace   ",
]

REAL_DOCUMENTS = sorted(Path("samples").rglob("*.txt"))


@pytest.mark.parametrize("text", EDGE_CASE_TEXTS)
def test_aho_corasick_matches_regex_on_edge_cases(text):
    assert AHO_CORASICK_MATCHER.find_spans(text) == REGEX_MATCHER.find_spans(text)


@pytest.mark.parametrize("path", REAL_DOCUMENTS, ids=lambda path: path.name)
def test_aho_corasick_matches_regex_on_real_documents(path):
    text = path.read_text(encoding="utf-8")
    assert AHO_CORASICK_MATCHER.find_spans(text) == REGEX_MATCHER.find_spans(text)


def test_aho_corasick_matches_regex_on_random_edge_case_texts():
    # WHY random texts: the hand-written cases cover what I thought of. Random
    # mixtures of aliases, fragments, punctuation, whitespace and the four
    # special case-folding letters cover combinations I didn't. The seed is
    # fixed, so a failure is reproducible.
    pieces = [
        "c", "c++", "c#", ".net", "asp.net", "r", "go", "golang", "java", "javascript", "js",
        "node.js", "node", "react", "react native", "redux", "rest api", "rest", "restful",
        "cloud-based", "ci/cd", "tcp/ip", "pl/sql", "sql", "postgresql", "sql server", "google",
        "d", "&", "-", ".", "+", "#", "/", "x", "3", ",", "(", ")",
        " ", "  ", "\n", "\t", "-\n", " ", "İ", "ı", "ſ", "K",
    ]
    generator = random.Random(20260915)
    for _ in range(400):
        tokens = []
        for _ in range(generator.randint(1, 25)):
            token = generator.choice(pieces)
            if generator.random() < 0.3:
                token = token.upper()
            tokens.append(token)
        separator = generator.choice(["", " ", "\n"])
        text = separator.join(tokens)
        assert AHO_CORASICK_MATCHER.find_spans(text) == REGEX_MATCHER.find_spans(text), repr(text)


def test_normalization_keeps_original_positions():
    normalized, positions = normalize_for_matching("Rest  \n API cloud-\n based")
    assert normalized == "rest api cloud-based"
    assert positions[normalized.index("api")] == 8
    assert positions[normalized.index("based")] == 20
