import math

import pytest

from analysis.similarity import (
    CorpusStatistics,
    cosine_similarity,
    inverse_document_frequencies,
    text_similarity,
    tfidf_vector,
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


# --- Corpus IDF --------------------------------------------------------------------

def test_two_document_idf_penalises_the_words_both_documents_share():
    # The original bug, kept as a test so the reasoning stays visible:
    # with N = 2 the shared word gets 0.59 and each unshared word 1.0.
    idf = inverse_document_frequencies([["python", "react"], ["python", "django"]])
    assert idf["python"] == pytest.approx(math.log(2 / 3) + 1)
    assert idf["react"] == pytest.approx(1.0)
    assert idf["python"] < idf["react"]


def test_corpus_idf_makes_common_job_words_weak_and_rare_ones_strong():
    job_posts = [["python", "aho-corasick"], ["python", "react"], ["python"], ["python", "django"]]
    corpus = CorpusStatistics.from_documents(job_posts)
    # N = 4. python is in all 4: log(4/5) + 1. aho-corasick is in 1: log(4/2) + 1.
    assert corpus.idf("python") == pytest.approx(math.log(4 / 5) + 1)
    assert corpus.idf("aho-corasick") == pytest.approx(math.log(4 / 2) + 1)
    assert corpus.idf("aho-corasick") > corpus.idf("python") > 0


def test_with_document_returns_new_statistics_without_changing_the_original():
    corpus = CorpusStatistics.from_documents([["python"]])
    bigger = corpus.with_document(["python", "rust", "rust"])
    assert (corpus.document_count, corpus.document_frequencies) == (1, {"python": 1})
    assert (bigger.document_count, bigger.document_frequencies) == (2, {"python": 2, "rust": 1})


def test_terms_no_job_description_uses_are_ignored():
    corpus = CorpusStatistics.from_documents([["react", "typescript"]])
    vector = tfidf_vector(["react", "inngest", "patchgan"], corpus)
    assert set(vector) == {"react"}


def test_shared_vocabulary_scores_higher_with_corpus_idf_than_with_two_document_idf():
    resume = "python django postgresql docker celery"
    jd = "python django postgresql redis kubernetes"
    old_resume_vector, old_jd_vector = tfidf_vectors([tokenize(resume), tokenize(jd)])
    two_document_score = cosine_similarity(old_resume_vector, old_jd_vector)

    other_job_posts = [
        tokenize("python django rest apis"),
        tokenize("react typescript redux"),
        tokenize("java spring kubernetes"),
        tokenize("python flask postgresql"),
    ]
    corpus = CorpusStatistics.from_documents(other_job_posts).with_document(tokenize(jd))
    corpus_score = text_similarity(resume, jd, corpus)

    assert corpus_score > two_document_score
