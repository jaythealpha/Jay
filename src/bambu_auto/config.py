from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


ENV_VAR_PATTERN = re.compile(r"\$\{([A-Z_][A-Z0-9_]*)\}")


def _expand_env(value: Any) -> Any:
    if isinstance(value, str):
        def repl(m: re.Match[str]) -> str:
            return os.environ.get(m.group(1), "")
        return ENV_VAR_PATTERN.sub(repl, value)
    if isinstance(value, dict):
        return {k: _expand_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand_env(v) for v in value]
    return value


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open() as f:
        raw = yaml.safe_load(f) or {}
    return _expand_env(raw)


class Secrets(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    meshy_api_key: str = Field(default="", alias="MESHY_API_KEY")
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    data_dir: str = Field(default="./data", alias="BAMBU_AUTO_DATA_DIR")


class MeshyRetry(BaseModel):
    max_attempts: int = 1
    backoff_initial_sec: float = 2.0


class MeshyConfig(BaseModel):
    base_url: str = "https://api.meshy.ai"
    api_version: str = "v2"
    image_ai_model: str = "meshy-6"
    request_timeout_sec: int = 60
    poll_interval_sec: int = 5
    poll_max_minutes: int = 15
    max_concurrent_tasks: int = 2
    retry: MeshyRetry = MeshyRetry()


class StorageConfig(BaseModel):
    data_dir: str = "./data"
    db_path: str = "./data/jobs.db"


class PipelineConfig(BaseModel):
    human_review_gate: bool = True
    auto_repair: bool = True
    default_material: str = "pla"
    default_quality: str = "standard"


class RoutingConfig(BaseModel):
    rules: list[dict[str, Any]] = Field(default_factory=list)


class Settings(BaseModel):
    storage: StorageConfig = StorageConfig()
    meshy: MeshyConfig = MeshyConfig()
    pipeline: PipelineConfig = PipelineConfig()
    routing: RoutingConfig = RoutingConfig()


class BudgetSaving(BaseModel):
    skip_texture_by_default: bool = True
    preview_only_mode: bool = True


class MeshyBudget(BaseModel):
    plan: str = "pro"
    monthly_credit_cap: int = 1000
    daily_credit_cap: int = 50
    reserve_buffer: int = 30
    hard_stop_ratio: float = 0.95
    alert_thresholds: list[float] = Field(default_factory=lambda: [0.7, 0.9])


class Budgets(BaseModel):
    meshy: MeshyBudget = MeshyBudget()
    operation_costs: dict[str, int] = Field(default_factory=dict)
    saving: BudgetSaving = BudgetSaving()


class PrinterDef(BaseModel):
    model: str
    host: str
    serial: str
    access_code: str
    build_volume_mm: list[int]
    has_ams: bool = False
    supported_materials: list[str] = Field(default_factory=list)
    default_profile: str


class Printers(BaseModel):
    printers: dict[str, PrinterDef]


class AppConfig:
    """Loaded config bundle. Use AppConfig.load() once at startup."""

    def __init__(
        self,
        settings: Settings,
        budgets: Budgets,
        printers: Printers,
        secrets: Secrets,
        config_dir: Path,
    ) -> None:
        self.settings = settings
        self.budgets = budgets
        self.printers = printers
        self.secrets = secrets
        self.config_dir = config_dir

    @classmethod
    def load(cls, config_dir: str | Path = "config") -> AppConfig:
        cfg = Path(config_dir)
        secrets = Secrets()
        settings = Settings(**load_yaml(cfg / "settings.yaml"))
        budgets = Budgets(**load_yaml(cfg / "budgets.yaml"))
        printers = Printers(**load_yaml(cfg / "printers.yaml"))
        return cls(settings, budgets, printers, secrets, cfg)
