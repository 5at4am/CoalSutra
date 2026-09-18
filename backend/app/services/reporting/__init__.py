"""Report generation & export (one of the three consumer modules)."""

from app.services.reporting.exporter import export_report
from app.services.reporting.generator import (
    generate_report,
    pull_chunks,
    pull_facts,
)
from app.services.reporting.templates import (
    REPORT_TEMPLATES,
    get_template,
    list_templates,
)

__all__ = [
    "REPORT_TEMPLATES",
    "export_report",
    "generate_report",
    "get_template",
    "list_templates",
    "pull_chunks",
    "pull_facts",
]