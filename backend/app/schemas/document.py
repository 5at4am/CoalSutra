from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import DocumentStatus, SourceType


class DocumentCreate(BaseModel):
    filename: str
    source_type: SourceType
    raw_file_path: str
    status: DocumentStatus = DocumentStatus.pending


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    source_type: SourceType
    upload_date: datetime
    status: DocumentStatus
    raw_file_path: str = Field(examples=["/data/raw/scan_001.pdf"])


class DocumentSummary(DocumentRead):
    fact_count: int = 0