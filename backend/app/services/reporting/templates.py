"""Report templates as structured section lists.

Plain Python dicts on purpose — no templating engine. Each template declares
its section order, per-section drafting instructions, and the entity hints that
help the generator pick relevant facts. The generator turns this into
`content: {"sections": {...}}` on a `Report` row.

Every template leads with an `executive_summary` (the PDF renders it right after
the table of contents) and closes with `sources` (automatic), with the analytical
body in between.
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
                "executive_summary",
                "Executive Summary",
                "Write a 120-150 word executive summary covering the period in "
                "scope, the headline volumes (production, overburden, dispatch), "
                "and the single most material movement or deviation. Cite every "
                "figure.",
            ),
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
                "Compare dated figures period-over-period. For every entity that has "
                "at least two dated values, quantify the movement in absolute terms "
                "and as a percentage, and name the largest single-period move. If the "
                "data does not support a trend, say so explicitly.",
            ),
            _section(
                "observations",
                "Observations",
                "Interpret the figures for management: call out anomalies, outliers, "
                "notable ratios (e.g. production vs overburden), and anything that "
                "warrants attention. Only claims supported by the cited facts.",
            ),
            _section("sources", "Sources", "Aggregate all cited sources below.", automatic=True),
        ],
    },
    "coal_quality_report": {
        "template_type": "coal_quality_report",
        "title": "Coal Quality Report",
        "entity_hints": ["ash_content", "moisture_content", "sulfur_content", "grade", "gcv"],
        "description": "Quality parameters: ash, moisture, sulphur, grade / GCV.",
        "sections": [
            _section(
                "executive_summary",
                "Executive Summary",
                "Write a 120-150 word executive summary of the overall quality picture "
                "and the parameter most out of line with expectations. Cite every figure.",
            ),
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
                "on the cited facts and name the governing parameter for any grade "
                "conclusion.",
            ),
            _section(
                "observations",
                "Observations",
                "Flag parameters that look out of tolerance, seams that stand apart, "
                "and any data gaps (missing values, single observations) the reader "
                "should keep in mind.",
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
                "executive_summary",
                "Executive Summary",
                "Write a 120-150 word executive summary of the reserve estimate: "
                "total, key block/seam splits, and any movement vs earlier figures. "
                "Cite every figure.",
            ),
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
                "Compare reserve figures across the cited dates. Quantify any change in "
                "absolute terms and percentage and name where it moved. If the data "
                "does not support a trend, say so explicitly.",
            ),
            _section(
                "observations",
                "Observations",
                "Interpret the reserve picture: concentration by block, any revisions "
                "over time, and data gaps that affect confidence in the estimate.",
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