from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite+aiosqlite:///./splitwise.db"
    SECRET_KEY: str = "your-secret-key-here"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    GOOGLE_CLIENT_ID: str = ""

    class Config:
        env_file = ".env"

    @property
    def async_database_url(self) -> str:
        url = self.DATABASE_URL
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        if "postgresql+asyncpg://" in url:
            from urllib.parse import urlparse, urlencode, parse_qs, urlunparse
            parsed = urlparse(url)
            params = parse_qs(parsed.query)
            params.pop("sslmode", None)
            new_query = urlencode({k: v[0] for k, v in params.items()})
            url = urlunparse(parsed._replace(query=new_query))
        return url


settings = Settings()
