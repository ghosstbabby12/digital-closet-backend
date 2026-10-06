from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    secret_key: str = "dev-secret-change-me"
    access_token_expire_minutes: int = 10080

    database_url: str = "postgresql+psycopg://closet:password@localhost:5432/closet"

    openweather_api_key: str = ""

    ai_provider: str = "rule_based"
    anthropic_api_key: str = ""
    openai_api_key: str = ""

    upload_dir: str = "./uploads"

    # Supabase Storage para las fotos (en la nube). Vacío = disco local.
    supabase_url: str = ""
    supabase_service_key: str = ""
    supabase_bucket: str = "garments"

    @field_validator("database_url")
    @classmethod
    def use_psycopg_driver(cls, value: str) -> str:
        # Los proveedores entregan postgres:// o postgresql://; SQLAlchemy necesita el driver explícito.
        for prefix in ("postgres://", "postgresql://"):
            if value.startswith(prefix):
                return "postgresql+psycopg://" + value[len(prefix):]
        return value


settings = Settings()
