from pydantic_settings import BaseSettings
from pydantic import Field, AnyHttpUrl
from typing import List


class Settings(BaseSettings):
    port: int = Field(8000, alias="PORT")
    database_url: str = Field(..., alias="DATABASE_URL")
    storage_dir: str = Field("storage/episodes", alias="STORAGE_DIR")
    base_url: AnyHttpUrl = Field("http://localhost:8000", alias="BASE_URL")
    # Directories containing task materials (PDF/JSON/etc.)
    materials_dirs: List[str] = Field(
        [
            "/Users/nenad/Projects/ai-podcast-generator/materials/1",
            "/Users/nenad/Projects/ai-podcast-generator/materials/2",
        ],
        alias="MATERIALS_DIRS",
    )
    openai_api_key: str = Field("", alias="OPENAI_API_KEY")

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
