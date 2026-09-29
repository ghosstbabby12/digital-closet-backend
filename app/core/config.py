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


settings = Settings()
