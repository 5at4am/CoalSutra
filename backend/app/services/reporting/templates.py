"""Report templates as structured section lists.

Plain Python dicts on purpose — no templating engine. Each template declares
its section order, per-section drafting instructions, and the entity hints that
help the generator pick relevant facts. The generator turns this into
`content: {"sections": {...}}` on a `Report` row.
"""

from __future__ import annotations

SECTION_KEYS = {"key", "title", "prompt", "automatic"}


def _section(key: str, title: str, prompt: str, automatic: bool = False) -> dict:
    section = {"key": key, "title": title, "prompt": prompt}
    if automatic:
        section["automatic"] = True
    return section


REPORT_TEMPLATES: dict[str, dict] = {
    "production_summary": {
        "template_type": "production_summary",
        "title": "Production Summary",
        "entity_hints": [
            "coal_production",
            "production",
            "ofs",
            "obr",
            "dispatch",
            "ex_face_stock",
        ],
        "description": "Coal production, overburden removal and dispatch figures.",
        "sections": [
            _section(
                "overview",
                "Overview",
                "Summarise the period covered, the operations in scope, and the "
                "headline production numbers. Cite every figure.",
            ),
            _section(
                "key_figures",
                "Key Figures",
                "Present the principal quantities (production, overburden, dispatch) "
                "as short statements, each with a citation.",
            ),
            _section(
                "trends",
                "Trends",
                "Describe month-over-month or period-over-period movement visible in "
                "the cited figures. If the data does not support a trend, say so.",
            ),
            _section(
                "sources",
                "Sources",
                "Aggregate all cited sources below.",
                automatic=True,
            ),
        ],
    },
    "coal_quality_report": {
        "template_type": "coal_quality_report",
        "title": "Coal Quality Report",
        "entity_hints": ["ash_content", "moisture_content", "sulfur_content", "grade", "gcv"],
        "description": "Quality parameters: ash, moisture, sulphur, grade / GCV.",
        "sections": [
            _section(
                "overview",
                "Overview",
                "Summarise the seams/blocks covered and the overall quality picture. "
                "Cite every figure.",
            ),
            _section(
                "key_figures",
                "Key Figures",
                "List the key quality parameters with values and citations.",
            ),
            _section(
                "grade_analysis",
                "Grade Analysis",
                "Interpret how the quality parameters map to coal grades. Base it only "
                "on the cited facts.",
            ),
            _section("sources", "Sources", "Aggregate all cited sources below.", automatic=True),
        ],
    },
    "reserve_estimate": {
        "template_type": "reserve_estimate",
        "title": "Reserve Estimate",
        "entity_hints": [
            "coal_reserve",
            "geological_reserve",
            "mineable_reserve",
            "extractable_reserve",
        ],
        "description": "Coal reserve estimates per block / seam.",
        "sections": [
            _section(
                "overview",
                "Overview",
                "Summarise the reserve estimate: total, per block or seam, and the "
                "reference date. Cite every figure.",
            ),
            _section(
                "reserve_breakdown",
                "Reserve Breakdown",
                "Break the estimate down by block/seam where the cited facts support it.",
            ),
            _section(
                "trends",
                "Trends",
                "Describe changes in reserve estimates across the cited dates, if any.",
            ),
            _section("sources", "Sources", "Aggregate all cited sources below.", automatic=True),
        ],
    },
}


def get_template(template_type: str) -> dict:
    """Return the template dict, raising KeyError for unknown template types."""
    try:
        return REPORT_TEMPLATES[template_type]
    except KeyError:
        raise KeyError(
            f"unknown report template {template_type!r}; "
            f"available: {sorted(REPORT_TEMPLATES)}"
        ) from None


def list_templates() -> list[dict]:
    return [
        {
            "template_type": template["template_type"],
            "title": template["title"],
            "description": template.get("description", ""),
            "sections": [s["key"] for s in template["sections"]],
        }
        for template in REPORT_TEMPLATES.values()
    ]