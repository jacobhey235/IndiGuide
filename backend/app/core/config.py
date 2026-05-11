from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    OTM_API_KEY: str
    OTM_BASE_URL: str = "https://api.opentripmap.com/0.1/en/places"

    OSRM_BASE_URL: str = "https://routing.openstreetmap.de/routed-foot"

    # Comma-separated string, e.g. "http://localhost:5173,https://myapp.com"
    CORS_ORIGINS: str = "http://localhost:5173"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",")]

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
