from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
import os


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=os.getenv("ENV_FILE", ".env"), extra="ignore")

    app_name: str = Field(default="skcc_awards")
    app_env: str = Field(default="dev")
    log_level: str = Field(default="INFO")
    database_url: str = Field(default="sqlite+aiosqlite:///./dev.db")
    version: str = Field(default="0.1.0")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
