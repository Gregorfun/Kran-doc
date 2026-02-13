"""
Settings Configuration
======================

Zentrale Konfiguration mit Pydantic BaseSettings
Lädt aus .env und config/config.yaml
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    """Zentrale Application Settings"""

    # App
    app_name: str = Field(default="Kran-Doc", description="Application name")
    debug: bool = Field(default=False, description="Debug mode")
    secret_key: Optional[str] = Field(default=None, description="Flask secret key")

    # Paths
    base_dir: Path = Field(default=BASE_DIR, description="Base directory")
    input_dir: Path = Field(default=BASE_DIR / "input", description="Input directory")
    output_dir: Path = Field(default=BASE_DIR / "output", description="Output directory")
    models_dir: Path = Field(default=BASE_DIR / "output" / "models", description="Models directory")
    embeddings_dir: Path = Field(default=BASE_DIR / "output" / "embeddings", description="Embeddings directory")
    logs_dir: Path = Field(default=BASE_DIR / "logs", description="Logs directory")

    # OCR
    tesseract_cmd: Optional[str] = Field(default=None, description="Tesseract command path")
    ocr_enabled: bool = Field(default=True, description="OCR enabled")
    ocr_lang: str = Field(default="deu+eng", description="OCR languages")

    # Redis / Queue
    redis_url: str = Field(default="redis://localhost:6379/0", description="Redis URL for job queue")
    redis_enabled: bool = Field(default=False, description="Redis enabled")

    # Qdrant
    qdrant_url: Optional[str] = Field(default=None, description="Qdrant server URL")
    qdrant_api_key: Optional[str] = Field(default=None, description="Qdrant API key")
    qdrant_collection: str = Field(default="kran_doc", description="Default Qdrant collection")

    # Search
    search_limit: int = Field(default=20, description="Default search result limit")
    semantic_threshold: float = Field(default=0.6, description="Semantic search threshold")

    # Security
    api_key: Optional[str] = Field(default=None, description="API key for protected endpoints")
    pin_code: Optional[str] = Field(default=None, description="PIN code for web access")
    rate_limit_enabled: bool = Field(default=True, description="Enable rate limiting")
    max_upload_size_mb: int = Field(default=50, description="Max upload size in MB")

    # Community
    community_enabled: bool = Field(default=True, description="Community features enabled")

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        env_prefix="KRANDOC_",
        extra="ignore",
    )


_settings_instance: Optional[Settings] = None


def get_settings() -> Settings:
    """Get singleton settings instance"""
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = Settings()

        # Load from config.yaml if exists
        config_path = BASE_DIR / "config" / "config.yaml"
        if config_path.exists():
            try:
                import yaml

                with open(config_path, "r", encoding="utf-8") as f:
                    config_data = yaml.safe_load(f) or {}

                # Override with config.yaml values
                for key, value in config_data.items():
                    if hasattr(_settings_instance, key):
                        setattr(_settings_instance, key, value)
            except Exception as e:
                print(f"Warning: Could not load config.yaml: {e}")

    return _settings_instance


# Global settings instance
settings = get_settings()
