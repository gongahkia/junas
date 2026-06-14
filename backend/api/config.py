import json
from functools import lru_cache
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Junas"
    debug: bool = False
    database_url: str = "postgresql+asyncpg://junas:junas@localhost:5432/junas"
    elasticsearch_url: str = "http://localhost:9200"
    qdrant_url: str = "http://localhost:6333"
    redis_url: str = "redis://localhost:6379/0"
    lecard_data_root: str = "../vendor-data/LeCaRD/data"
    case_biencoder_model_path: str = "models/case-retrieval-biencoder"
    case_cross_encoder_model_path: str = "models/case-retrieval-crossencoder"
    case_retrieval_metrics_path: str = "models/case-retrieval/eval_results.json"
    ledgar_model_path: str = "models/ledgar-classifier/best"
    unfair_tos_model_path: str = "models/unfair-tos-classifier/best"
    ner_model_path: str = "models/ner-german-legal/best"
    ner_multilingual_model_path: str = "models/ner-multilingual-legal/best"
    ner_gazetteer_dir: str = "../vendor-data/Legal-Entity-Recognition/gazetteers"
    llm_provider: str = "ollama"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-20250514"
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    lmstudio_url: str = "http://localhost:1234"
    lmstudio_model: str = "default"
    azure_openai_api_key: str = ""
    azure_openai_endpoint: str = ""
    azure_openai_api_version: str = "2024-08-01-preview"
    azure_openai_deployment: str = ""
    allow_byok: bool = True
    session_storage_path: str = "data/junas_sessions.sqlite3"
    require_auth: bool = False
    api_keys: Annotated[list[str], NoDecode] = Field(default_factory=list)
    rate_limit_enabled: bool = True
    rate_limit_default_per_minute: int = 120
    rate_limit_research_per_minute: int = 10
    rate_limit_search_per_minute: int = 30
    cors_origins: Annotated[list[str], NoDecode] = Field(default_factory=lambda: ["http://localhost:3000"])

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: object) -> list[str] | object:
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return []
            if raw.startswith("["):
                try:
                    loaded = json.loads(raw)
                    if isinstance(loaded, list):
                        return [str(item) for item in loaded if str(item).strip()]
                except json.JSONDecodeError:
                    pass
            return [item.strip() for item in raw.split(",") if item.strip()]
        return value

    @field_validator("api_keys", mode="before")
    @classmethod
    def parse_api_keys(cls, value: object) -> list[str] | object:
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return []
            if raw.startswith("["):
                try:
                    loaded = json.loads(raw)
                    if isinstance(loaded, list):
                        return [str(item).strip() for item in loaded if str(item).strip()]
                except json.JSONDecodeError:
                    pass
            return [item.strip() for item in raw.split(",") if item.strip()]
        return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
