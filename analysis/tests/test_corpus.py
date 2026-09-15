from datetime import timedelta

import pytest
from django.core.cache import cache
from django.core.management import call_command
from django.utils import timezone

from analysis import corpus
from analysis.demo import DEMO_JOB_DESCRIPTIONS
from analysis.models import CorpusSnapshot, JobDescription
from analysis.service import run_analysis
from resumes.models import Resume

pytestmark = pytest.mark.django_db

SEED_JD_COUNT = len(DEMO_JOB_DESCRIPTIONS)


def test_empty_database_still_has_the_seed_files_as_a_corpus():
    statistics = corpus.rebuild()
    assert statistics.document_count == SEED_JD_COUNT
    assert statistics.document_frequencies["react"] >= 1


def test_stored_jds_are_counted_and_stored_seed_jds_are_not_counted_twice():
    JobDescription.objects.create(title="Search", raw_text="Build search with Rust and Aho-Corasick automata.")
    statistics = corpus.rebuild()
    assert statistics.document_count == SEED_JD_COUNT + 1
    # The tokenizer splits on hyphens, so "Aho-Corasick" is counted as "aho" and "corasick".
    assert statistics.document_frequencies["corasick"] == 1

    call_command("seed_demo")  # stores the four seed JDs in the database
    statistics = corpus.rebuild()
    assert statistics.document_count == SEED_JD_COUNT + 1


def test_rebuild_saves_one_snapshot_row():
    corpus.rebuild()
    corpus.rebuild()
    assert CorpusSnapshot.objects.count() == 1
    assert CorpusSnapshot.objects.get().document_count == SEED_JD_COUNT


def test_load_reads_a_fresh_snapshot_without_rebuilding():
    corpus.rebuild()
    cache.clear()
    JobDescription.objects.create(raw_text="Kotlin Android engineer")  # not in the snapshot yet

    statistics = corpus.load()

    assert statistics.document_count == SEED_JD_COUNT


def test_load_rebuilds_a_snapshot_older_than_the_refresh_interval():
    corpus.rebuild()
    CorpusSnapshot.objects.update(updated_at=timezone.now() - corpus.REFRESH_AFTER - timedelta(minutes=1))
    cache.clear()
    JobDescription.objects.create(raw_text="Kotlin Android engineer")

    statistics = corpus.load()

    assert statistics.document_count == SEED_JD_COUNT + 1
    assert statistics.document_frequencies["kotlin"] >= 1


def test_run_analysis_counts_the_new_jd_so_its_rare_terms_are_kept():
    resume = Resume.objects.create(filename="r.pdf", storage_key="k", extracted_text="Built Aho-Corasick search in Rust.")
    analysis, result = run_analysis(resume, "We need Aho-Corasick and Rust experience for our search team.")
    # Neither term is in the seed corpus; without counting the new JD they
    # would be dropped and similarity would be 0.
    assert result.similarity_score > 0.5
    assert analysis.similarity_score == result.similarity_score
