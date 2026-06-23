"""Pydantic schemas for browser reader, search, and automation."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

class BrowserSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    max_results: int = Field(default=5, ge=1, le=20)


class SearchResultItem(BaseModel):
    title: str
    url: str
    snippet: str = ""


class BrowserSearchResponse(BaseModel):
    status: str  # "ok" | "error"
    results: list[SearchResultItem] = Field(default_factory=list)
    message: str = ""


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

class BrowserReadRequest(BaseModel):
    url: str
    max_chars: int = Field(default=10000, ge=500, le=50000)


class WebLinkItem(BaseModel):
    text: str
    href: str


class BrowserReadResponse(BaseModel):
    status: str  # "ok" | "error"
    title: str = ""
    url: str = ""
    content: str = ""
    links: list[WebLinkItem] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    message: str = ""


# ---------------------------------------------------------------------------
# Summarize
# ---------------------------------------------------------------------------

class BrowserSummarizeRequest(BaseModel):
    url: str
    question: str = Field(default="")
    max_chars: int = Field(default=10000, ge=500, le=50000)


class BrowserSummarizeResponse(BaseModel):
    status: str  # "ok" | "error"
    summary: str = ""
    key_points: list[str] = Field(default_factory=list)
    source_url: str = ""
    message: str = ""


# ---------------------------------------------------------------------------
# Open URL
# ---------------------------------------------------------------------------

class BrowserOpenUrlRequest(BaseModel):
    url: str


class BrowserOpenUrlResponse(BaseModel):
    status: str  # "ok" | "error" | "requires_confirmation"
    message: str
    task_id: UUID | None = None


# ---------------------------------------------------------------------------
# Download candidates & risk classification
# ---------------------------------------------------------------------------

class DownloadCandidateItem(BaseModel):
    text: str
    href: str
    domain: str = ""
    extension: str = ""


class ExtractDownloadCandidatesRequest(BaseModel):
    url: str
    max_chars: int = Field(default=10000, ge=500, le=50000)


class ExtractDownloadCandidatesResponse(BaseModel):
    status: str
    candidates: list[DownloadCandidateItem] = Field(default_factory=list)
    message: str = ""


class ClassifyDownloadRequest(BaseModel):
    candidates: list[DownloadCandidateItem]


class ClassifiedDownloadItem(BaseModel):
    text: str
    href: str
    domain: str
    extension: str
    risk_level: str  # trusted | low | medium | high | blocked | unknown
    reasons: list[str] = Field(default_factory=list)
    suggested_action: str = ""
    requires_confirmation: bool = True


class ClassifyDownloadResponse(BaseModel):
    status: str
    classified: list[ClassifiedDownloadItem] = Field(default_factory=list)
    message: str = ""


# ---------------------------------------------------------------------------
# Browser automation (skeleton)
# ---------------------------------------------------------------------------

class BrowserActionRequest(BaseModel):
    action: str
    target_url: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)


class BrowserActionResponse(BaseModel):
    status: str
    message: str
    action_log_id: UUID | None = None
    task_id: UUID | None = None


# ---------------------------------------------------------------------------
# Trusted download sources
# ---------------------------------------------------------------------------

class TrustedSourceItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    user_id: UUID
    domain: str
    product_key: str | None = None
    trust_level: str
    source_type: str
    note: str | None = None
    created_at: datetime
    updated_at: datetime | None = None


class TrustedSourceListResponse(BaseModel):
    sources: list[TrustedSourceItem]


class TrustedSourceCreateRequest(BaseModel):
    domain: str
    product_key: str | None = None
    trust_level: str = "trusted"
    note: str | None = None


# ---------------------------------------------------------------------------
# Action logs (browser)
# ---------------------------------------------------------------------------

class BrowserActionLogItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    user_id: UUID
    action_type: str
    target_url: str | None = None
    status: str
    message: str | None = None
    error_detail: str | None = None
    payload_json: dict | None = None
    created_at: datetime
    finished_at: datetime | None = None


class BrowserActionLogsResponse(BaseModel):
    logs: list[BrowserActionLogItem]
