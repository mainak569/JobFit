from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from analysis import scorer
from analysis.extractor import PDFExtractionError
from analysis.service import create_resume, run_analysis
from analysis.skills import CATEGORY_LABELS
from storage import object_storage

BAR_WIDTH = 24


class Command(BaseCommand):
    help = (
        "Extract a resume PDF, store it, analyse it against a job description "
        "text file, save the result, and print the full analysis."
    )

    def add_arguments(self, parser):
        parser.add_argument("pdf_path", help="Path to the resume PDF")
        parser.add_argument("jd_path", help="Path to a plain-text job description")
        parser.add_argument("--title", default="", help="Job title, e.g. 'Frontend Engineer'")
        parser.add_argument("--company", default="", help="Company name")

    def handle(self, *args, **options):
        pdf_path = Path(options["pdf_path"])
        jd_path = Path(options["jd_path"])

        if not pdf_path.is_file():
            raise CommandError(f"Resume PDF not found: {pdf_path}")
        if not jd_path.is_file():
            raise CommandError(f"Job description file not found: {jd_path}")

        jd_text = jd_path.read_text(encoding="utf-8").strip()
        if not jd_text:
            raise CommandError(f"Job description file is empty: {jd_path}")

        try:
            resume = create_resume(pdf_path.name, pdf_path.read_bytes())
        except PDFExtractionError as exc:
            raise CommandError(str(exc)) from exc

        analysis, result = run_analysis(
            resume,
            jd_text,
            title=options["title"],
            company=options["company"],
        )
        self.print_report(resume, analysis, result, jd_text)

    # ------------------------------------------------------------------ output

    def heading(self, text):
        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING(text))

    def print_report(self, resume, analysis, result, jd_text):
        jd = analysis.job_description

        self.stdout.write(self.style.SUCCESS("=" * 64))
        self.stdout.write(self.style.SUCCESS("  JobFit analysis"))
        self.stdout.write(self.style.SUCCESS("=" * 64))
        self.stdout.write(f"Resume   {resume.filename}  ({len(resume.extracted_text):,} characters extracted)")
        if object_storage.is_configured():
            where = f"bucket {settings.STORAGE_BUCKET}"
        else:
            where = f"local fallback, {settings.MEDIA_ROOT}"
        self.stdout.write(f"Stored   {resume.storage_key}  ({where})")
        self.stdout.write(f"JD       {jd}  ({len(jd_text):,} characters)")

        self.heading(f"Overall score: {analysis.overall_score} / 100")
        self.print_breakdown(result)

        self.heading(f"Matched skills ({len(result.matched_skills)})")
        if result.matched_skills:
            for skill in result.matched_skills:
                self.stdout.write(
                    f"  {self.style.SUCCESS('✓')} {skill['name']:<30} {skill['category']:<10} "
                    f"JD x{skill['jd_count']:<3} resume x{skill['resume_count']}"
                )
        else:
            self.stdout.write("  (none)")

        self.heading(f"Missing skills ({len(result.missing_skills)}, most-mentioned first)")
        if result.missing_skills:
            for skill in result.missing_skills:
                self.stdout.write(
                    f"  {self.style.WARNING('✗')} {skill['name']:<30} {skill['category']:<10} "
                    f"JD x{skill['jd_count']}"
                )
        else:
            self.stdout.write("  (none)")

        self.heading("Coverage by category")
        if result.category_scores:
            for scores in result.category_scores.values():
                filled = round(scores["coverage"] * BAR_WIDTH)
                bar = "█" * filled + "░" * (BAR_WIDTH - filled)
                self.stdout.write(
                    f"  {scores['label']:<16} {bar}  {scores['matched']}/{scores['required']}"
                    f"  {round(scores['coverage'] * 100):>3}%"
                )
        else:
            self.stdout.write("  (the JD names no skills from the taxonomy)")
        uncovered = [label for key, label in CATEGORY_LABELS.items() if key not in result.category_scores]
        if uncovered:
            self.stdout.write(f"  Not asked for by this JD: {', '.join(uncovered)}")

        self.heading("Suggestions")
        for number, suggestion in enumerate(result.suggestions, start=1):
            self.stdout.write(f"  {number}. {suggestion}")

        self.heading("Saved")
        self.stdout.write(f"  Resume          {resume.id}")
        self.stdout.write(f"  JobDescription  {jd.id}")
        self.stdout.write(f"  Analysis        {analysis.id}")

    def print_breakdown(self, result):
        rows = [
            ("skill coverage", result.skill_coverage, scorer.SKILL_COVERAGE_WEIGHT),
            ("cosine similarity", result.similarity_score, scorer.SIMILARITY_WEIGHT),
            ("category balance", result.category_balance, scorer.CATEGORY_BALANCE_WEIGHT),
        ]
        blend_points = 0.0
        for label, value, weight in rows:
            points = value * weight * 100
            blend_points += points
            self.stdout.write(f"  {label:<18} {value:.3f} x {weight:.2f} = {points:5.1f}")
        self.stdout.write(
            f"  {'blend':<18} {'':>12} {blend_points:5.1f}  "
            f"-> rounded, clamped to {scorer.MIN_SCORE}-{scorer.MAX_SCORE} -> {result.overall_score}"
        )
