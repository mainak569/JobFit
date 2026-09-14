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
