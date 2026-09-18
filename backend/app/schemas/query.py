from pydantic import BaseModel, ConfigDict, Field


class QueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


class Citation(BaseModel):
    document_name: str
    page_number: int
    snippet: str


class QueryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    answer: str
    citations: list[Citation]