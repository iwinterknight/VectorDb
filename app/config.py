from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    app_name: str = "VectorDB"
    embedding_dim: int = 384
    cohere_api_key: str | None = "pa6sRhnVAedMVClPAwoCvC1MjHKEwjtcGSTjWRMd"

settings = Settings()
