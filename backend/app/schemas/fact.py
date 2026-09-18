from datetime import date
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ExtractedFactCreate(BaseModel):
    document_id: int
    entity: str
    value: str
    unit: Optional[str] = None
    date_reference: Optional[date] = None
    page_number: Optional[int] = None
    raw_snippet: str
    confidence: float = Field(ge=0.0, le=1.0)


class ExtractedFactRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    document_id: int
    entity: str
    value: str
    unit: Optional[str]
    date_reference: Optional[date]
    page_number: Optional[int]
    raw_snippet: str
    confidence: float