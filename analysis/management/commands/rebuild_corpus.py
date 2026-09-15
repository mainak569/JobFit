from django.core.management.base import BaseCommand

from analysis import corpus


class Command(BaseCommand):
    help = "Recount how many stored job descriptions contain each term (the IDF corpus)."

    def handle(self, *args, **options):
        statistics = corpus.rebuild()
        frequencies = statistics.document_frequencies
        self.stdout.write(
            self.style.SUCCESS(
                f"Corpus: {statistics.document_count} job descriptions, {len(frequencies)} distinct terms."
            )
        )
        most_common = sorted(frequencies.items(), key=lambda item: (-item[1], item[0]))[:10]
        self.stdout.write(
            "Most common terms (weakest evidence): "
            + ", ".join(f"{term} ({count})" for term, count in most_common)
        )
