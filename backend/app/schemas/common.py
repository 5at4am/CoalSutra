from fastapi import FastAPI
from pydantic import BaseModel


class Contributor(BaseModel):
    name: str
    role: str


class HealthResponse(BaseModel):
    status: str
    database: str