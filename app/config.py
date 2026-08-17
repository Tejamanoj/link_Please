import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PSEUDOGRAM_API_KEY: str = os.getenv("PSEUDOGRAM_API_KEY", "")
    PSEUDOGRAM_BASE_URL: str = os.getenv("PSEUDOGRAM_BASE_URL", "https://pseudogram-api.onrender.com")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./linkplease.db")
    WEBHOOK_SECRET: str = os.getenv("WEBHOOK_SECRET", "")
    MAX_DM_RETRIES: int = int(os.getenv("MAX_DM_RETRIES", "3"))

    # Supports both WEBHOOK_SIGNATURE_REQUIRED (spec) and VERIFY_WEBHOOK_SIGNATURE (legacy)
    WEBHOOK_SIGNATURE_REQUIRED: bool = os.getenv(
        "WEBHOOK_SIGNATURE_REQUIRED",
        os.getenv("VERIFY_WEBHOOK_SIGNATURE", "true")
    ).lower() in ("true", "1", "yes")

    WORKER_POLL_INTERVAL: float = float(os.getenv("WORKER_POLL_INTERVAL", "0.5"))
    RATE_LIMIT_REQUESTS: int = 10
    RATE_LIMIT_WINDOW_SECONDS: int = 60

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def VERIFY_WEBHOOK_SIGNATURE(self) -> bool:
        """Legacy alias for WEBHOOK_SIGNATURE_REQUIRED."""
        return self.WEBHOOK_SIGNATURE_REQUIRED

    @property
    def hmac_secret(self) -> str:
        """Returns WEBHOOK_SECRET or PSEUDOGRAM_API_KEY as the HMAC signing secret."""
        return self.WEBHOOK_SECRET or self.PSEUDOGRAM_API_KEY

settings = Settings()
