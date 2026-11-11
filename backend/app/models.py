from typing import Any, Literal

from pydantic import BaseModel, Field


OutputMode = Literal["conversational", "dashboard", "report", "presentation", "export", "map"]
RetrievalStrategy = Literal["analytics_api", "direct_sql", "both"]


class MetricRef(BaseModel):
    label: str
    uid: str
    uid_confidence: float = Field(ge=0.0, le=1.0)
    object_type: str = "indicator"


class OrgUnitRef(BaseModel):
    label: str
    uid: str
    level: int = Field(ge=1, default=1)


class EvidenceItem(BaseModel):
    claim: str
    source: Literal["dhis2", "tavily", "llm"]
    source_detail: str
    confidence: float = Field(ge=0.0, le=1.0)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    session_id: str | None = None
    conversation_id: str | None = None
    output_mode: OutputMode | None = None
    allow_web: bool = False
    user_role: Literal["dhis2_user", "external_stakeholder"] = "external_stakeholder"


class GeneratedFile(BaseModel):
    file_id: str
    filename: str
    content_type: str
    row_count: int | None = None


class DataPayload(BaseModel):
    rows: list[list[Any]] = Field(default_factory=list)
    headers: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    sources: list[dict[str, Any]] = Field(default_factory=list)


class ReportPayload(BaseModel):
    html: str = Field(min_length=1)
    title: str = "DHIS2 Analyst Report"
    chart_configs: list[dict[str, Any]] = Field(default_factory=list)
    evidence_items: list[EvidenceItem] = Field(default_factory=list)


class PresentationPayload(BaseModel):
    slides: list[dict[str, Any]]
    title: str = "DHIS2 Analyst Briefing"


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=256)


class Identity(BaseModel):
    user_id: str
    role: Literal["dhis2_user", "external_stakeholder", "admin"] = "external_stakeholder"
    permitted_org_units: list[str] = Field(default_factory=list)
    permitted_indicator_groups: list[str] = Field(default_factory=list)
    # How the caller was authenticated: standalone JWT, a DHIS2 PAT, or a
    # DHIS2 Route carrying the shared key. Only "dhis2_pat" callers have a
    # per-user token to forward to DHIS2.
    auth_source: Literal["standalone", "dhis2_pat", "route"] = "standalone"
