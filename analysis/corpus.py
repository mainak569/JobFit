"""
Corpus statistics for TF-IDF: across all job descriptions JobFit knows, how
many contain each term.

    load()     statistics for scoring (in-memory cache -> database snapshot ->
               rebuild if the snapshot is missing or older than an hour)
    rebuild()  recount every stored job description and save a new snapshot
"""

import logging
from datetime import timedelta

from django.core.cache import cache
from django.utils import timezone

from analysis.demo import seed_job_description_texts
from analysis.models import CorpusSnapshot, JobDescription
from analysis.similarity import CorpusStatistics, tokenize

logger = logging.getLogger(__name__)

CACHE_KEY = "analysis:corpus-statistics"

# WHY two layers and these intervals: counting means tokenising every stored
# job description, which is cheap for hundreds but pointless on every
# request. The snapshot row is shared by all gunicorn workers and survives
# restarts; the in-memory cache saves each worker from reading a large JSON
# column per analysis. The free plan has no scheduled jobs, so "recompute
# periodically" happens on read: a snapshot older than an hour is rebuilt by
# the next request that needs it. New JDs therefore reach IDF within the hour,
# and one extra document moves any weight by roughly 1/N, so that lag doesn't
# matter.
CACHE_SECONDS = 10 * 60
REFRESH_AFTER = timedelta(hours=1)
SNAPSHOT_ID = 1


def build_statistics():
    documents = []
    stored_ids = set()
    for jd_id, raw_text in JobDescription.objects.values_list("id", "raw_text").iterator():
        stored_ids.add(jd_id)
        documents.append(set(tokenize(raw_text)))

    # WHY include the seed files: on a fresh database (local development, or a
    # first deploy before seeding) the corpus would be empty and IDF would
    # carry no information. The four seed job descriptions are always on
    # disk. Any already stored in the database are skipped, so none is
    # counted twice.
    for jd_id, text in seed_job_description_texts():
        if jd_id not in stored_ids:
            documents.append(set(tokenize(text)))

    return CorpusStatistics.from_documents(documents)


def rebuild():
    statistics = build_statistics()
    CorpusSnapshot.objects.update_or_create(
        pk=SNAPSHOT_ID,
        defaults={
            "document_count": statistics.document_count,
            "document_frequencies": statistics.document_frequencies,
        },
    )
    cache.set(CACHE_KEY, statistics, CACHE_SECONDS)
    logger.info(
        "Rebuilt corpus statistics: %d job descriptions, %d distinct terms",
        statistics.document_count,
        len(statistics.document_frequencies),
    )
    return statistics


def load():
    statistics = cache.get(CACHE_KEY)
    if statistics is not None:
        return statistics

    snapshot = CorpusSnapshot.objects.filter(pk=SNAPSHOT_ID).first()
    if snapshot is None or snapshot.updated_at < timezone.now() - REFRESH_AFTER:
        return rebuild()

    statistics = CorpusStatistics(snapshot.document_count, snapshot.document_frequencies)
    cache.set(CACHE_KEY, statistics, CACHE_SECONDS)
    return statistics
