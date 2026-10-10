from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "EchoShield API"
    environment: str = "development"
    database_url: str
    redis_url: str
    secret_key: str

    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 15
    refresh_token_days: int = 7


@lru_cache
def get_settings() -> Settings:
    return Settings()