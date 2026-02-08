"""Application configuration management."""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Application
    app_name: str = "OnCall Assistant Agent"
    debug: bool = False
    
    # Database
    database_url: str = "mysql+aiomysql://oncall:oncall123@localhost:3306/oncall"
    
    # JWT
    jwt_secret_key: str = "your-secret-key-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_hours: int = 24
    
    # LLM Configuration
    llm_provider: str = "openai"  # openai or dashscope
    openai_api_key: str = ""
    openai_model: str = "gpt-4"
    openai_base_url: str = "https://api.openai.com/v1"
    
    # Dashscope (Aliyun Tongyi)
    dashscope_api_key: str = ""
    dashscope_model: str = "qwen-turbo"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
