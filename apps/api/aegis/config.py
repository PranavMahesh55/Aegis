from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="AEGIS_", extra="ignore")

    database_path: Path = Path("var/aegis.db")
    context_database_path: Path = Path("var/aegis-context.db")
    data_mode: str = "seeded"
    prime_blocked: bool = True
    allowed_origin: str = "http://localhost:5173"
    datahub_gms_url: str = Field(
        default="http://localhost:8080", validation_alias="DATAHUB_GMS_URL"
    )
    datahub_gms_token: str = Field(default="", validation_alias="DATAHUB_GMS_TOKEN")
    datahub_graphql_url: str = Field(
        default="http://localhost:8080/api/graphql", validation_alias="DATAHUB_GRAPHQL_URL"
    )
    datahub_frontend_url: str = Field(
        default="http://localhost:9002", validation_alias="DATAHUB_FRONTEND_URL"
    )
    datahub_mcp_url: str = Field(
        default="http://localhost:8082/mcp", validation_alias="DATAHUB_MCP_URL"
    )
    business_mcp_url: str = Field(
        default="http://localhost:8010/mcp", validation_alias="BUSINESS_MCP_URL"
    )
    openai_api_key: str = Field(default="", validation_alias="OPENAI_API_KEY")
    openai_model: str = "gpt-5.6-terra"
    openai_reasoning_effort: str = "low"
    capability_signing_secret: str = "dev-only-change-me"
    datahub_actions_shared_secret: str = "dev-actions-change-me"
    risk_freshness_sla_seconds: int = 900
    run_timeout_seconds: int = 120


@lru_cache
def get_settings() -> Settings:
    return Settings()
