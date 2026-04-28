"""Loan Buster — App Configuration"""
import json
from typing import Any
from pydantic import field_validator
from pydantic import Json
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.5-flash"
    MAX_FILE_SIZE_MB: int = 15
    ENVIRONMENT: str = "development"
    CORS_ORIGINS: Any = []
    
    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def handle_cors(cls, v: Any):
        # Case 1: already a list (Cloud Run does this sometimes)
        if isinstance(v, list):
            return v

        # Case 2: JSON string
        if isinstance(v, str) and v.startswith("["):
            try:
                return json.loads(v)
            except:
                pass

        # Case 3: comma-separated string
        if isinstance(v, str):
            return [i.strip() for i in v.split(",") if i.strip()]

        return []

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()