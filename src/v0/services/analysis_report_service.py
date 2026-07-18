"""Service for generating HTML reports from AnalysisResult."""

import re
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from src.v0.agents.sql_analyst.models import AnalysisResult

# Project root directory
PROJECT_ROOT = Path(__file__).parent.parent.parent

# Output directory for reports
OUTPUT_DIR = PROJECT_ROOT / "output" / "reports"

# Templates directory
TEMPLATES_DIR = PROJECT_ROOT / "src" / "templates"


class AnalysisReportService:
    """Service for generating standalone HTML reports from AnalysisResult."""

    def __init__(self):
        """Initialize the report service with Jinja2 environment."""
        self.env = Environment(
            loader=FileSystemLoader(TEMPLATES_DIR),
            autoescape=True,
        )
        # Ensure output directory exists
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    def _slugify(self, text: str) -> str:
        """Convert text to a URL-friendly slug."""
        text = text.lower()
        text = re.sub(r"[^\w\s-]", "", text)
        text = re.sub(r"[-\s]+", "_", text)
        return text.strip("_")

    def _generate_filename(self, analysis_result: AnalysisResult) -> str:
        """Generate a filename for the report.

        Format: {profile_id}_{geography_slug}_{timestamp}.html
        """
        geography_slug = self._slugify(analysis_result.target_geography)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{analysis_result.profile_id}_{geography_slug}_{timestamp}.html"

    def _get_score_class(self, score: float) -> str:
        """Get CSS class for score badge."""
        if score >= 70:
            return "score-high"
        elif score >= 50:
            return "score-medium"
        else:
            return "score-low"

    def generate_report(
        self,
        analysis_result: AnalysisResult,
        output_path: Path | None = None,
    ) -> Path:
        """Generate an HTML report from an AnalysisResult.

        Args:
            analysis_result: The analysis result to render
            output_path: Optional custom output path. If None, auto-generates
                filename in output/reports/ directory.

        Returns:
            Path to the generated HTML file
        """
        # Determine output path
        if output_path is None:
            filename = self._generate_filename(analysis_result)
            output_path = OUTPUT_DIR / filename
        else:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

        # Load template
        template = self.env.get_template("analysis_report.html")

        # Render template with context
        html_content = template.render(
            analysis=analysis_result,
            generated_at=datetime.now(),
            get_score_class=self._get_score_class,
        )

        # Write to file
        output_path.write_text(html_content, encoding="utf-8")

        return output_path

    def render_html(self, analysis_result: AnalysisResult) -> str:
        """Render HTML report and return as string.

        Args:
            analysis_result: The analysis result to render

        Returns:
            HTML content as a string
        """
        template = self.env.get_template("analysis_report.html")
        return template.render(
            analysis=analysis_result,
            generated_at=datetime.now(),
            get_score_class=self._get_score_class,
        )
