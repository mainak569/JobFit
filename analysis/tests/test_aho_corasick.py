import pytest

from analysis.aho_corasick import ROOT, AhoCorasick


def matches(automaton, text):
    return sorted((start, end, automaton.patterns[index]) for start, end, index in automaton.search(text))


def test_classic_example_finds_overlapping_patterns():
    automaton = AhoCorasick(["he", "she", "his", "hers"])
    assert matches(automaton, "ushers") == [(1, 4, "she"), (2, 4, "he"), (2, 6, "hers")]


def test_shared_prefixes_share_nodes():
    automaton = AhoCorasick(["react", "redux", "ruby"])
    # root, r, e, (a, c, t), (d, u, x), (u, b, y)
    assert automaton.node_count == 12


def test_failure_link_jumps_to_the_longest_valid_suffix():
    automaton = AhoCorasick(["abcd", "bce"])
    # After reading "abc", "d" isn't next; the failure link from "abc" goes
    # to "bc", so "e" completes "bce" without re-reading "b" and "c".
    node = ROOT
    for character in "abc":
        node = automaton.children[node][character]
    bc = automaton.children[automaton.children[ROOT]["b"]]["c"]
    assert automaton.fail[node] == bc
    assert matches(automaton, "abce") == [(1, 4, "bce")]


def test_pattern_inside_another_pattern_is_reported_through_failure_links():
    automaton = AhoCorasick(["c++", "+"])
    assert matches(automaton, "c++") == [(0, 3, "c++"), (1, 2, "+"), (2, 3, "+")]


def test_repeated_and_back_to_back_matches():
    automaton = AhoCorasick(["aa"])
    assert matches(automaton, "aaaa") == [(0, 2, "aa"), (1, 3, "aa"), (2, 4, "aa")]


def test_no_matches_and_empty_text():
    automaton = AhoCorasick(["react"])
    assert matches(automaton, "angular and vue") == []
    assert matches(automaton, "") == []


def test_empty_pattern_is_rejected():
    with pytest.raises(ValueError):
        AhoCorasick(["react", ""])
