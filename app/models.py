from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class RenderCacheMode(StrEnum):
    USE = "use"
    FLUSH = "flush"
    DISABLE = "disable"


class CreateSessionRequest(BaseModel):
    title: str | None = None


class AppendOperationRequest(BaseModel):
    code: str = Field(min_length=1)
    render: bool = False
    cache: RenderCacheMode = RenderCacheMode.USE


class RenderRequest(BaseModel):
    cache: RenderCacheMode = RenderCacheMode.USE


class Operation(BaseModel):
    operationId: str
    sectionName: str
    code: str
    createdAt: str


class SectionArtifact(BaseModel):
    operationId: str
    videoUrl: str
    duration: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RenderSummary(BaseModel):
    fullVideoUrl: str
    sections: list[SectionArtifact] = Field(default_factory=list)


class SessionDetail(BaseModel):
    sessionId: str
    title: str | None = None
    operationCount: int
    operations: list[Operation]
    latestRender: RenderSummary | None = None


class SessionSummary(BaseModel):
    sessionId: str
    title: str | None = None
    operationCount: int
    latestRender: RenderSummary | None = None


class AppendOperationResponse(BaseModel):
    sessionId: str
    operation: Operation
    latestRender: RenderSummary | None = None
