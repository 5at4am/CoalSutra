"""Lint every draft report: flag figures that are not backed by facts or cited."""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import Base, SessionLocal, engine  # noqa: E402
from app.models import Report  # noqa: E402
from app.services.reporting.lint import lint_sections  # noqa: E402

Base.metadata.create_all(engine)
session = SessionLocal()

reports = session.query(Report).order_by(Report.id.asc()).all()
if not reports:
    print("No reports to lint.")
    sys.exit(0)

failed = False
for report in reports:
    content = report.content or {}
    result = lint_sections(
        content.get("sections") or {},
        content.get("facts") or [],
    )
    summary = result["summary"]
    print(
        f"report {report.id:<4} [{report.template_type}] status={report.status.value:<9} "
        f"figures={summary['figures_checked']:<4} ok={result['ok']}"
        f"  (errors={summary['errors']}, warnings={summary['warnings']}, "
        f"infos={summary['infos']})"
    )
    if not result["ok"]:
        failed = True
    for issue in result["issues"]:
        if issue["severity"] in ("error", "warning"):
            print(
                f"    [{issue['severity']}] {issue['section']}: "
                f"{issue['number']} — {issue['reason']}"
            )

print()
if failed:
    print("LINT FAILED: some reports contain unverifiable figures.")
    sys.exit(1)
print("LINT OK: every figure is backed by a fact.")