from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "AgroStake Core API"
    API_V1_PREFIX: str = "/api/v1"
    DATABASE_URL: str
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 14
    IOT_INGEST_API_KEY: str

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
