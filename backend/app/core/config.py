from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", extra="ignore")

    DATABASE_URL: str = "mysql+pymysql://root:@localhost:3306/soldier-management?charset=utf8mb4"
    SECRET_KEY: str = "change-me"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    STORAGE_DIR: str = "storage"
    CORS_ORIGINS: str = "http://localhost:5173"
    MAX_UPLOAD_MB: int = 20
    MAX_FAILED_LOGINS: int = 5
    LOCKOUT_MINUTES: int = 15

    @property
    def storage_path(self) -> Path:
        p = Path(self.STORAGE_DIR)
        return p if p.is_absolute() else BASE_DIR / p

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


settings = Settings()
