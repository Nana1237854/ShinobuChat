"""BaseJob and JobResult — job contract (Phase 3)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class JobResult:
    status: str = "success"
    summary: str = ""
    data: dict | None = None


class BaseJob:
    name: str = "base_job"
    interval_seconds: int = 60
    enabled: bool = True

    def run_once(self) -> JobResult:
        raise NotImplementedError
