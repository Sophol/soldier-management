from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]

# placeholders from old templates: a key anyone can read in the repository signs valid login tokens
WEAK_SECRET_KEYS = {"", "change-me", "changeme", "secret", "replace-with-random-string", "..."}
MIN_SECRET_KEY_LENGTH = 16


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", extra="ignore")

    DATABASE_URL: str = "mysql+pymysql://root:@localhost:3306/soldier-management?charset=utf8mb4"
    # no default: the API must not start with a key that signs tokens anyone could forge
    SECRET_KEY: str = ""

    @field_validator("SECRET_KEY")
    @classmethod
    def _strong_secret_key(cls, v: str) -> str:
        if v.strip().lower() in WEAK_SECRET_KEYS or len(v.strip()) < MIN_SECRET_KEY_LENGTH:
            raise ValueError(
                f"SECRET_KEY is missing or too weak (placeholder or shorter than {MIN_SECRET_KEY_LENGTH} characters). "
                "Set a long random value in backend/.env (or the environment), e.g. the output of: "
                'python -c "import secrets; print(secrets.token_urlsafe(48))"')
        return v
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    STORAGE_DIR: str = "storage"
    CORS_ORIGINS: str = "http://localhost:5173"
    MAX_UPLOAD_MB: int = 20
    MAX_FAILED_LOGINS: int = 5
    LOCKOUT_MINUTES: int = 15
    # how often approved decisions whose effective date has come are applied to the soldiers (0 = never: tests)
    DECISION_APPLY_MINUTES: int = 30

    @property
    def storage_path(self) -> Path:
        p = Path(self.STORAGE_DIR)
        return p if p.is_absolute() else BASE_DIR / p

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


settings = Settings()
