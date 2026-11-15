"""Load explicit deployment settings without connecting to external services."""

import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Settings(BaseModel):
    """Required locations are supplied by the deployment, never the browser."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    files_root: Path
    files_backend: Literal["local", "pvc"] = "pvc"
    temporal_address: str = Field(min_length=1)
    temporal_namespace: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{0,62}$")
    task_queue: str = Field(pattern=r"^[a-z0-9][a-z0-9.-]{0,127}$")

    @field_validator("files_root")
    @classmethod
    def absolute_directory(cls, value: Path) -> Path:
        if not value.is_absolute() or not value.is_dir():
            raise ValueError("files_root must be an existing absolute directory")
        return value

    @classmethod
    def from_environment(cls) -> "Settings":
        """Reject missing settings without printing environment values or secrets."""
        values = {
            field: os.environ[f"M1_{field.upper()}"]
            for field in cls.model_fields
            if f"M1_{field.upper()}" in os.environ
        }
        return cls.model_validate(values)
