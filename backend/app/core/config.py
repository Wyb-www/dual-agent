"""YAML 配置管理（Pydantic Settings）"""

import os
import re
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel


class LLMConfig(BaseModel):
    provider: str = "deepseek"
    model: str = "deepseek-chat"
    api_base: str = "https://api.deepseek.com/v1"
    api_key: str = ""
    temperature: float = 0.7
    max_tokens: int = 4096


class OllamaConfig(BaseModel):
    api_base: str = "http://localhost:11434"
    model: str = "qwen3:8b"


class AgentConfig(BaseModel):
    max_iterations: int = 5
    success_criteria_default: str = "给出清晰、准确、有帮助的回答"


class ToolsConfig(BaseModel):
    enable_search: bool = False
    enable_wikipedia: bool = True


class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000


class DatabaseConfig(BaseModel):
    path: str = "./data/conversations.db"


class AppConfig(BaseModel):
    name: str = "Multi-Agent Collab"
    version: str = "1.0.0"
    debug: bool = False


class Config(BaseModel):
    app: AppConfig = AppConfig()
    llm: LLMConfig = LLMConfig()
    ollama: OllamaConfig = OllamaConfig()
    agent: AgentConfig = AgentConfig()
    tools: ToolsConfig = ToolsConfig()
    server: ServerConfig = ServerConfig()
    database: DatabaseConfig = DatabaseConfig()


def _resolve_env_vars(value: str) -> str:
    """Replace ${VAR_NAME} with environment variable values."""
    pattern = re.compile(r"\$\{(\w+)\}")
    return pattern.sub(lambda m: os.getenv(m.group(1), ""), value)


def load_config(path: Optional[str] = None) -> Config:
    """Load config from YAML file, resolving environment variables."""
    if path is None:
        path = Path(__file__).parent.parent.parent / "config.yaml"

    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    # Recursively resolve env vars in string values
    def resolve(obj):
        if isinstance(obj, dict):
            return {k: resolve(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [resolve(v) for v in obj]
        elif isinstance(obj, str):
            return _resolve_env_vars(obj)
        return obj

    resolved = resolve(raw)
    return Config(**resolved)


# Singleton
_config: Optional[Config] = None


def get_config() -> Config:
    global _config
    if _config is None:
        _config = load_config()
    return _config
