import pytest

from analysis.implications import IMPLIES, infer_skills, validate_graph
from analysis.matcher import SKILL_CATEGORY


def test_django_implies_python():
    assert infer_skills({"Django"})["Python"] == ["Django", "Python"]


def test_chains_are_followed_transitively():
    inferred = infer_skills({"Next.js"})
    assert inferred["React"] == ["Next.js", "React"]
    assert inferred["JavaScript"] == ["Next.js", "React", "JavaScript"]


def test_edges_only_go_one_way():
    # React implies JavaScript; JavaScript must not imply React.
    assert "React" not in infer_skills({"JavaScript"})
    assert infer_skills({"JavaScript"}) == {}
    assert "Django" not in infer_skills({"Python"})


def test_named_skills_are_never_reported_as_inferred():
    inferred = infer_skills({"Next.js", "React"})
    assert "React" not in inferred
    assert inferred["JavaScript"] == ["React", "JavaScript"]  # shortest chain wins


def test_cycles_terminate():
    cyclic = {"A": ["B"], "B": ["C"], "C": ["A"]}
    assert infer_skills({"A"}, graph=cyclic) == {"B": ["A", "B"], "C": ["A", "B", "C"]}


def test_github_actions_reaches_git_through_github():
    inferred = infer_skills({"GitHub Actions"})
    assert inferred["GitHub"] == ["GitHub Actions", "GitHub"]
    assert inferred["Git"] == ["GitHub Actions", "GitHub", "Git"]
    assert inferred["CI/CD"] == ["GitHub Actions", "CI/CD"]


def test_every_node_in_the_graph_is_a_real_skill():
    for source, targets in IMPLIES.items():
        assert source in SKILL_CATEGORY
        for target in targets:
            assert target in SKILL_CATEGORY
            assert target != source


def test_validation_rejects_unknown_skills_and_self_edges():
    with pytest.raises(ValueError, match="unknown skill"):
        validate_graph({"Nextjs": ["React"]})
    with pytest.raises(ValueError, match="self-edge"):
        validate_graph({"React": ["React"]})
