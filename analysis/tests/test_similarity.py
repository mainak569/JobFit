import math

import pytest

from analysis.similarity import (
    cosine_similarity,
    inverse_document_frequencies,
    text_similarity,
    tfidf_vectors,
    tokenize,
)


def test_tfidf_on_two_hand_checkable_documents():
    # d1 = "apple banana", d2 = "apple cherry", N = 2. Worked by hand:
    #   idf(apple)  = log(2 / (1 + 2)) + 1 = log(2/3) + 1   (in both docs)
    #   idf(banana) = log(2 / (1 + 1)) + 1 = 1.0            (in one doc)
    #   tf of every term = 1/2
    documents = [["apple", "banana"], ["apple", "cherry"]]
    idf_shared = math.log(2 / 3) + 1
    assert idf_shared == pytest.approx(0.594535, abs=1e-6)

    idf = inverse_document_frequencies(documents)
    assert idf["apple"] == pytest.approx(idf_shared)
    assert idf["banana"] == pytest.approx(1.0)
    assert idf["cherry"] == pytest.approx(1.0)

    d1, d2 = tfidf_vectors(documents)
    assert d1 == pytest.approx({"apple": 0.5 * idf_shared, "banana": 0.5})
    assert d2 == pytest.approx({"apple": 0.5 * idf_shared, "cherry": 0.5})

    # dot = apple*apple (banana and cherry have no partner)
    # ||d1|| = ||d2|| = sqrt(apple^2 + 0.5^2)
    apple = 0.5 * idf_shared
    expected = (apple * apple) / (apple * apple + 0.25)
    assert expected == pytest.approx(0.2612, abs=1e-4)
    assert cosine_similarity(d1, d2) == pytest.approx(expected)


def test_identical_documents_have_similarity_one():
    assert text_similarity("react python docker", "react python docker") == pytest.approx(1.0)


def test_documents_with_no_shared_terms_have_similarity_zero():
    assert text_similarity("apple banana", "cherry durian") == 0.0


def test_empty_document_has_similarity_zero_instead_of_dividing_by_zero():
    assert text_similarity("", "react python") == 0.0
    assert cosine_similarity({}, {}) == 0.0


def test_tokenize_keeps_symbol_terms_and_drops_stopwords_and_numbers():
    tokens = tokenize("I know C++, C# and Node.js since 2021.")
    assert tokens == ["know", "c++", "c#", "node.js", "since"]
