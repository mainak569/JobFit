"""
Hand-written TF-IDF vectors and cosine similarity.

    tf(t,d)     = count(t,d) / len(d)
    idf(t)      = log(N / (1 + df(t))) + 1
    tfidf(t,d)  = tf(t,d) * idf(t)
    cosine(a,b) = dot(a,b) / (||a|| * ||b||)

    N      = number of documents in the corpus
    df(t)  = number of corpus documents that contain term t
    len(d) = number of tokens in d

Worked example with a two-document corpus, d1 = "apple banana" and
d2 = "apple cherry", so N = 2:
    idf(apple)  = log(2/3) + 1 = 0.5945    (in both documents)
    idf(banana) = log(2/2) + 1 = 1.0       (in one document)
    d1 = {apple: 0.5 * 0.5945, banana: 0.5 * 1.0} = {apple: 0.2973, banana: 0.5}
    d2 = {apple: 0.2973, cherry: 0.5}
    dot     = 0.2973^2                    = 0.0884
    ||d1||  = sqrt(0.2973^2 + 0.5^2)      = 0.5817   (same for d2)
    cosine  = 0.0884 / (0.5817 * 0.5817)  = 0.2612

Notice that the one word the two documents share gets the *lowest* weight.
That is the bug the next comment is about.
"""

# WHY no scikit-learn / numpy:
#   1. scikit-learn drags in numpy and scipy, a large install that slows every
#      cold build on a free-tier host, all for one function's worth of use.
#      TfidfVectorizer + cosine_similarity is ~50 lines of stdlib Python.
#   2. I need to be able to explain TF-IDF in an interview. Writing it is the
#      only way to be sure I actually understand it rather than the API.
# The trade-off is speed: sklearn uses sparse C matrices. For two documents of
# a few thousand words each, pure Python finishes in milliseconds.
#
# WHY IDF comes from a corpus of job descriptions, not from the two documents
# being compared: the first version computed IDF over just the resume and the
# JD. With N = 2, a term in both documents gets log(2/3) + 1 = 0.59 and a term
# in only one gets 1.0, so the metric down-weighted exactly the vocabulary the
# two documents share, which is what a similarity score is supposed to reward.
# Measured on the demo resume against the seed JDs, raw cosine sat at
# 0.03-0.11 and dragged every overall score down.
#
# IDF is meant to say how informative a word is in general: "python" appears
# in most job posts, so matching it is weak evidence; "aho-corasick" is rare,
# so matching it is strong evidence. That needs many documents, so N and df
# now come from every stored job description (analysis/corpus.py).

import math
import re
from collections import Counter
from dataclasses import dataclass, field

# WHY: a small hand-picked list rather than NLTK's. Stopwords like "the" and
# "and" appear in every document, so they add large shared weights that make
# any two English texts look similar. NLTK would be another dependency for a
# list that fits on one screen.
STOPWORDS = frozenset(
    """
    a about above after again against all also am an and any are as at be because
    been before being below between both but by can could did do does doing down
    during each etc few for from further had has have having he her here hers him
    his how i if in into is it its itself just me more most my no nor not now of
    off on once only or other our ours out over own per same she should so some
    such than that the their theirs them then there these they this those through
    to too under until up us very via was we were what when where which while who
    whom why will with within without would you your yours
    """.split()
)

# WHY: "+", "#" and "." are kept inside tokens so "c++", "c#" and "node.js"
# survive as single terms instead of being shredded into "c" and "js".
TOKEN_SEPARATOR = re.compile(r"[^a-z0-9+#.]+")


def tokenize(text):
    tokens = []
    for raw_token in TOKEN_SEPARATOR.split(text.lower()):
        # Strip sentence punctuation: "react." -> "react", but "node.js" stays.
        token = raw_token.strip(".")
        if not token:
            continue
        if token in STOPWORDS:
            continue
        # WHY: pure numbers ("2025", "94.3") are dates and grades on a resume,
        # not vocabulary shared with a JD.
        if token.replace(".", "").isdigit():
            continue
        tokens.append(token)
    return tokens


def term_frequencies(tokens):
    """tf(t,d) = count(t,d) / len(d)"""
    if not tokens:
        return {}
    counts = Counter(tokens)
    total = len(tokens)
    return {term: count / total for term, count in counts.items()}


@dataclass(frozen=True)
class CorpusStatistics:
    """N and df(t) for a corpus. Immutable: adding a document returns a new object."""

    document_count: int = 0
    document_frequencies: dict = field(default_factory=dict)

    @classmethod
    def from_documents(cls, documents):
        """documents: an iterable of token lists (or sets)."""
        document_frequency = Counter()
        document_count = 0
        for tokens in documents:
            # set(): df counts documents containing the term, not occurrences.
            document_frequency.update(set(tokens))
            document_count += 1
        return cls(document_count, dict(document_frequency))

    def with_document(self, tokens):
        """A copy of these statistics with one more document counted."""
        frequencies = dict(self.document_frequencies)
        for term in set(tokens):
            frequencies[term] = frequencies.get(term, 0) + 1
        return CorpusStatistics(self.document_count + 1, frequencies)

    def contains(self, term):
        return self.document_frequencies.get(term, 0) > 0

    def idf(self, term):
        """idf(t) = log(N / (1 + df(t))) + 1"""
        # WHY the "1 +" and "+ 1": the "1 +" in the denominator is smoothing so
        # df can never divide by zero. The trailing "+ 1" keeps every idf
        # positive: the smallest possible value is log(N / (N + 1)) + 1, which
        # is above 0.3, so a term in every document is weakened, not erased.
        df = self.document_frequencies.get(term, 0)
        return math.log(self.document_count / (1 + df)) + 1


def inverse_document_frequencies(documents):
    """idf for every term in a small corpus given as token lists."""
    corpus = CorpusStatistics.from_documents(documents)
    return {term: corpus.idf(term) for term in corpus.document_frequencies}


def tfidf_vector(tokens, corpus):
    """
    tfidf(t,d) = tf(t,d) * idf(t), for the terms of d that the corpus knows.

    Returns a sparse vector: a {term: weight} dict.
    """
    # WHY dicts rather than fixed-length lists: a dict is a sparse vector.
    # Each document uses a small slice of the vocabulary, and a term absent
    # from a dict is implicitly weight 0, so no vocabulary index is needed.
    #
    # WHY drop terms the corpus has never seen: a word that appears in no job
    # description (a project codename, a university, a person's name) says
    # nothing about fit for a job. Under corpus IDF it would also get the
    # largest possible weight, so keeping it would inflate the resume's vector
    # length and push the cosine down for reasons unrelated to the job.
    tf = term_frequencies(tokens)
    vector = {}
    for term, tf_value in tf.items():
        if corpus.contains(term):
            vector[term] = tf_value * corpus.idf(term)
    return vector


def tfidf_vectors(documents):
    """TF-IDF vectors for documents that are themselves the whole corpus."""
    corpus = CorpusStatistics.from_documents(documents)
    return [tfidf_vector(tokens, corpus) for tokens in documents]


def cosine_similarity(vector_a, vector_b):
    """cosine(a,b) = dot(a,b) / (||a|| * ||b||)"""
    # Only terms present in both vectors contribute to the dot product;
    # every other term is multiplied by an implicit zero.
    dot_product = 0.0
    for term, weight in vector_a.items():
        if term in vector_b:
            dot_product += weight * vector_b[term]

    norm_a = math.sqrt(sum(weight * weight for weight in vector_a.values()))
    norm_b = math.sqrt(sum(weight * weight for weight in vector_b.values()))

    # WHY return 0 instead of raising: an empty document has no direction, so
    # similarity is undefined. Treating it as "no similarity" keeps a blank JD
    # from crashing the scorer; the extractor already rejects empty resumes.
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot_product / (norm_a * norm_b)


def text_similarity(resume_text, jd_text, corpus=None):
    """
    TF-IDF cosine similarity of a resume and a job description, in [0, 1].

    `corpus` must already count this job description (use
    CorpusStatistics.with_document for one that isn't stored yet); otherwise
    its terms are unknown to the corpus and get dropped.
    """
    resume_tokens = tokenize(resume_text)
    jd_tokens = tokenize(jd_text)
    if corpus is None:
        # WHY this default: with no corpus there is no rarity information, so
        # treat the JD as the only document. Every JD term then gets the same
        # IDF, which is a plain term-frequency cosine over the JD's vocabulary.
        # Unlike the old two-document IDF, it doesn't penalise shared words.
        corpus = CorpusStatistics().with_document(jd_tokens)
    return cosine_similarity(tfidf_vector(resume_tokens, corpus), tfidf_vector(jd_tokens, corpus))
