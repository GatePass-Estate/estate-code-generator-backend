"""Environment-backed LLM routing (prod → Vertex SA, else → OpenAI key)."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class LlmSettings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    #: ``prod`` uses Gemini Enterprise Agent Platform (ADC); anything else uses OpenAI.
    ENV: str = "local"

    OPENAI_API_KEY: str | None = None
    OPENAI_CHAT_MODEL: str = "gpt-4o-mini"
    OPENAI_BASE_URL: str = "https://api.openai.com"

    GCP_PROJECT_ID: str | None = None
    GCP_VERTEX_LOCATION: str = "global"
    GCP_LLM_CHAT_MODEL: str = "google/gemini-2.5-flash"

    def uses_vertex(self) -> bool:
        return self.ENV.strip().lower() == "prod"


settings = LlmSettings()
