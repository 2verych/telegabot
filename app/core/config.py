from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    db_host: str = Field(default="localhost", alias="DB_HOST")
    db_port: int = Field(default=3306, alias="DB_PORT")
    db_user: str = Field(default="telegabot", alias="DB_USER")
    db_pass: str = Field(default="secret", alias="DB_PASS")
    db_name: str = Field(default="telegabot", alias="DB_NAME")

    api_key: str = Field(default="change-me", alias="API_KEY")
    app_kms_key: str = Field(default="".ljust(32, "0"), alias="APP_KMS_KEY")

    job_exec_timeout_s: int = Field(default=300, alias="JOB_EXEC_TIMEOUT_S")
    account_lock_timeout_s: int = Field(default=30, alias="ACCOUNT_LOCK_TIMEOUT_S")
    heartbeat_interval_s: int = Field(default=15, alias="HEARTBEAT_INTERVAL_S")
    job_stale_timeout_s: int = Field(default=120, alias="JOB_STALE_TIMEOUT_S")

    build_version: Optional[str] = Field(default="dev", alias="BUILD_VERSION")

    @property
    def database_url(self) -> str:
        return (
            f"mysql+pymysql://{self.db_user}:{self.db_pass}" f"@{self.db_host}:{self.db_port}/{self.db_name}?charset=utf8mb4"
        )

    @property
    def kms_key_bytes(self) -> bytes:
        key = self.app_kms_key
        if len(key) == 32:
            return key.encode("utf-8")
        if len(key) == 64:
            try:
                return bytes.fromhex(key)
            except ValueError as exc:  # pragma: no cover - defensive
                raise ValueError("APP_KMS_KEY must be 32-byte hex or utf-8 string") from exc
        raise ValueError("APP_KMS_KEY must be 32 bytes long")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
