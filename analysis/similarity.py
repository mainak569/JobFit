"""
Hand-written TF-IDF vectors and cosine similarity.

    tf(t,d)     = count(t,d) / len(d)
    idf(t)      = log(N / (1 + df(t))) + 1
    tfidf(t,d)  = tf(t,d) * idf(t)
    cosine(a,b) = dot(a,b) / (||a|| * ||b||)

    N      = number of documents in the corpus
    df(t)  = number of documents that contain term t
    len(d) = number of tokens in document d

Worked example, d1 = "apple banana", d2 = "apple cherry", so N = 2:
    idf(apple)  = log(2/3) + 1 = 0.5945    (in both documents)
    idf(banana) = log(2/2) + 1 = 1.0       (in one document)
    d1 = {apple: 0.5 * 0.5945, banana: 0.5 * 1.0} = {apple: 0.2973, banana: 0.5}
    d2 = {apple: 0.2973, cherry: 0.5}
    dot     = 0.2973^2                    = 0.0884
    ||d1||  = sqrt(0.2973^2 + 0.5^2)      = 0.5817   (same for d2)
    cosine  = 0.0884 / (0.5817 * 0.5817)  = 0.2612
"""

# WHY no scikit-learn / numpy:
#   1. scikit-learn drags in numpy and scipy, a large install that slows every
#      cold build on a free-tier host, all for one function's worth of use.
#      TfidfVectorizer + cosine_similarity is ~50 lines of stdlib Python.
#   2. I need to be able to explain TF-IDF in an interview. Writing it is the
#      only way to be sure I actually understand it rather than the API.
# The trade-off is speed: sklearn uses sparse C matrices. For two documents of
# a few thousand words each, pure Python finishes in milliseconds, so it
# doesn't matter at this scale.

import math
import re
from collections import Counter

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


def inverse_document_frequencies(documents):
    """idf(t) = log(N / (1 + df(t))) + 1, for every term in any document."""
    n_documents = len(documents)
    document_frequency = Counter()
    for tokens in documents:
        # set(): df counts documents containing the term, not occurrences.
        document_frequency.update(set(tokens))

    # WHY the "1 +" and "+ 1": the "1 +" in the denominator is smoothing so a
    # term's df can never divide by zero. The trailing "+ 1" keeps every idf
    # positive: the smallest possible value is log(N / (N + 1)) + 1, which is
    # still above 0.3. Without it, a term present in every document would get
    # a zero or negative weight and be erased from the comparison entirely.
    #
    # Note that with only two documents (resume and JD), idf has one job: a
    # term in both gets 0.59x the weight of a term in one. That pulls raw
    # cosine down for real pairs (typically 0.1-0.4), which is part of why it
    # is only 35% of the overall score.
    idf = {}
    for term, df in document_frequency.items():
        idf[term] = math.log(n_documents / (1 + df)) + 1
    return idf


def tfidf_vectors(documents):
    """
    tfidf(t,d) = tf(t,d) * idf(t)

    Takes a list of token lists, returns one {term: weight} dict per document.
    """
    # WHY dicts rather than fixed-length lists: a dict is a sparse vector.
    # Each document uses a small slice of the combined vocabulary, and a term
    # absent from a dict is implicitly weight 0, so no vocabulary index needed.
    idf = inverse_document_frequencies(documents)
    vectors = []
    for tokens in documents:
        tf = term_frequencies(tokens)
        vector = {term: tf_value * idf[term] for term, tf_value in tf.items()}
        vectors.append(vector)
    return vectors


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


def text_similarity(text_a, text_b):
    """TF-IDF cosine similarity of two raw texts, in [0, 1]."""
    vector_a, vector_b = tfidf_vectors([tokenize(text_a), tokenize(text_b)])
    return cosine_similarity(vector_a, vector_b)
