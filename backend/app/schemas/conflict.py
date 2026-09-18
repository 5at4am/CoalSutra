from pydantic import BaseModel, ConfigDict

from app.models.enums import ConflictStatus


class ConflictFlagCreate(BaseModel):
    fact_a_id: int
    fact_b_id: int
    reason: str
    status: ConflictStatus = ConflictStatus.open


class ConflictFlagResolve(BaseModel):
    status: ConflictStatus
    resolved_by: str


class ConflictFlagRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    fact_a_id: int
    fact_b_id: int
    reason: str
    status: ConflictStatus
    resolved_by: str | None
    resolution: str | None = None