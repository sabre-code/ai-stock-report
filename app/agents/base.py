"""Abstract base class for all agents."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import AsyncIterator

from app.schemas import ProgressEvent


class BaseAgent(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    async def run(self, *args, **kwargs): ...

    @staticmethod
    def _event(stage: str, message: str, done: bool = False, artifact_url: str | None = None) -> ProgressEvent:
        return ProgressEvent(stage=stage, message=message, done=done, artifact_url=artifact_url)
