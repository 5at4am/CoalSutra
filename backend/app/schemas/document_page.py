from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class DocumentPageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    document_id: int
    page_number: int
    text: str
    tables: Optional[list[Any]]