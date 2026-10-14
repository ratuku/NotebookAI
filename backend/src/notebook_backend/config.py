from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = (
        "postgresql+psycopg://notebook:local_notebook_password@localhost:5433/notebook"
    )
    cors_origins: list[str] = ["http://localhost:3000"]
    max_upload_bytes: int = 10 * 1024 * 1024


settings = Settings()
