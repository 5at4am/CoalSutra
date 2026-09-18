from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ReportStatus


class ReportGenerate(BaseModel):
    template_type: str = Field(min_length=1)
    title: Optional[str] = None
    filters: Optional[dict[str, Any]] = None


class ReportCreate(BaseModel):
    title: str
    template_type: str
    content: dict[str, Any]


class ReportRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    template_type: str
    generated_at: datetime
    status: ReportStatus
    content: dict[str, Any]
    export_path: Optional[str]
    review_note: Optional[str] = None