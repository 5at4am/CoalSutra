from typing import Optional

from pydantic import BaseModel


class MetricsSummaryRead(BaseModel):
    documents_total: int
    documents_processed: int
    open_conflicts: int
    flagged_documents_pct: float
    avg_query_ms: Optional[float] = None
    queries_served: int