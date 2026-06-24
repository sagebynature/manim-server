from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class RenderCacheMode(StrEnum):
    USE = "use"
    FLUSH = "flush"
    DISABLE = "disable"


class CreateSessionRequest(BaseModel):
    title: str | None = None
    templateId: str | None = None


class AppendSectionRequest(BaseModel):
    title: str | None = None
    code: str = Field(min_length=1)
    render: bool = False
    cache: RenderCacheMode = RenderCacheMode.USE


class RenderRequest(BaseModel):
    cache: RenderCacheMode = RenderCacheMode.USE


class OkResponse(BaseModel):
    ok: bool


class Section(BaseModel):
    sectionId: str
    title: str | None = None
    code: str
    createdAt: str


class SectionArtifact(BaseModel):
    sectionId: str
    videoUrl: str
    duration: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RenderSummary(BaseModel):
    fullVideoUrl: str
    sections: list[SectionArtifact] = Field(default_factory=list)


class SessionDetail(BaseModel):
    sessionId: str
    title: str | None = None
    templateId: str = "default"
    sectionCount: int
    sections: list[Section]
    latestRender: RenderSummary | None = None


class SessionSummary(BaseModel):
    sessionId: str
    title: str | None = None
    templateId: str = "default"
    sectionCount: int
    latestRender: RenderSummary | None = None


class ListSessionsResponse(BaseModel):
    sessions: list[SessionSummary]


class AppendSectionResponse(BaseModel):
    sessionId: str
    section: Section
    latestRender: RenderSummary | None = None
