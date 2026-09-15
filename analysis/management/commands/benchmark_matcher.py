"""
Time the regex matcher against the Aho-Corasick matcher.

    python manage.py benchmark_matcher

Two experiments:
  1. Text length: the real 146-skill taxonomy on the demo resume repeated.
  2. Pattern count: the real taxonomy plus synthetic skills, on a fixed text.

Before timing anything, both matchers are checked to return identical results.
"""

import random
import string
import time
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from analysis.matcher import AhoCorasickSkillMatcher, RegexSkillMatcher
from analysis.skills import SKILL_TAXONOMY


def best_time_ms(function, text, repeat):
    """Fastest of `repeat` runs, in milliseconds. The minimum is the least noisy estimate."""
    best = float("inf")
    for _ in range(repeat):
        start = time.perf_counter()
        function(text)
        best = min(best, time.perf_counter() - start)
    return best * 1000


def synthetic_taxonomy(skill_count, seed=7):
    """The real taxonomy plus `skill_count` made-up skills with 1-3 aliases each."""
    generator = random.Random(seed)
    skills = []
    for number in range(skill_count):
        aliases = set()
        for _ in range(generator.randint(1, 3)):
            length = generator.randint(5, 12)
            aliases.add("".join(generator.choice(string.ascii_lowercase) for _ in range(length)))
        skills.append((f"Synthetic {number}", sorted(aliases)))
    taxonomy = dict(SKILL_TAXONOMY)
    taxonomy["synthetic"] = skills
    return taxonomy


class Command(BaseCommand):
    help = "Benchmark the regex skill matcher against the Aho-Corasick skill matcher."

    def add_arguments(self, parser):
        parser.add_argument("--repeat", type=int, default=15, help="Runs per measurement (the fastest is reported)")

    def handle(self, *args, **options):
        repeat = options["repeat"]
        resume_path = Path(settings.BASE_DIR) / "samples" / "seed" / "demo_resume.txt"
        if not resume_path.is_file():
            raise CommandError(f"Missing {resume_path}")
        resume = resume_path.read_text(encoding="utf-8")

        self.stdout.write(self.style.MIGRATE_HEADING("1. Text length (real taxonomy)"))
        regex = RegexSkillMatcher(SKILL_TAXONOMY)
        aho = AhoCorasickSkillMatcher(SKILL_TAXONOMY)
        pattern_count = len(aho.automaton.patterns)
        self.stdout.write(
            f"   {len(regex.patterns)} skills, {pattern_count} aliases, "
            f"{aho.automaton.node_count} trie nodes"
        )
        self.stdout.write(f"   {'text':<28} {'regex ms':>9} {'aho ms':>9} {'aho vs regex':>13}")
        for copies in (1, 10, 50):
            text = "\n".join([resume] * copies)
            if regex.find_spans(text) != aho.find_spans(text):
                raise CommandError(f"Matchers disagree on the resume x{copies}")
            regex_ms = best_time_ms(regex.find_spans, text, repeat)
            aho_ms = best_time_ms(aho.find_spans, text, repeat)
            label = f"resume x{copies} ({len(text):,} chars)"
            self.stdout.write(f"   {label:<28} {regex_ms:>9.2f} {aho_ms:>9.2f} {regex_ms / aho_ms:>12.2f}x")

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("2. Pattern count (demo resume x10)"))
        text = "\n".join([resume] * 10)
        self.stdout.write(f"   {'skills':>7} {'aliases':>8} {'regex ms':>9} {'aho ms':>9} {'aho vs regex':>13} {'build ms':>9}")
        for extra in (0, 500, 2000, 8000):
            taxonomy = synthetic_taxonomy(extra)
            regex = RegexSkillMatcher(taxonomy)
            start = time.perf_counter()
            aho = AhoCorasickSkillMatcher(taxonomy)
            build_ms = (time.perf_counter() - start) * 1000
            if regex.find_spans(text) != aho.find_spans(text):
                raise CommandError(f"Matchers disagree with {extra} synthetic skills")
            regex_ms = best_time_ms(regex.find_spans, text, max(3, repeat // 3))
            aho_ms = best_time_ms(aho.find_spans, text, max(3, repeat // 3))
            self.stdout.write(
                f"   {len(regex.patterns):>7} {len(aho.automaton.patterns):>8} {regex_ms:>9.2f} "
                f"{aho_ms:>9.2f} {regex_ms / aho_ms:>12.2f}x {build_ms:>9.1f}"
            )

        self.stdout.write("")
        self.stdout.write("   \"aho vs regex\" above 1.00x means Aho-Corasick is faster.")
