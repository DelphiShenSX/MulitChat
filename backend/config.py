"""配置文件管理"""
import json
import os
from pathlib import Path
from typing import Optional
from models import ModelsConfig, ModelConfig

# 获取项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent


class ConfigManager:
    def __init__(self, config_dir: str = None):
        self.config_dir = Path(config_dir) if config_dir else (BASE_DIR / "data" / "config")
        self.models_file = self.config_dir / "models.json"
        self.settings_file = self.config_dir / "settings.json"
        self._ensure_config_dir()
        self._ensure_config_files()

    def _ensure_config_dir(self):
        self.config_dir.mkdir(parents=True, exist_ok=True)

    def _ensure_config_files(self):
        if not self.models_file.exists():
            default_config = ModelsConfig(models=[], settings={})
            self.save_models_config(default_config)

        if not self.settings_file.exists():
            self.save_settings({})

    def load_models_config(self) -> ModelsConfig:
        try:
            with open(self.models_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return ModelsConfig(**data)
        except Exception as e:
            print(f"Error loading models config: {e}")
            return ModelsConfig(models=[], settings={})

    def save_models_config(self, config: ModelsConfig):
        with open(self.models_file, "w", encoding="utf-8") as f:
            json.dump(config.model_dump(), f, ensure_ascii=False, indent=2, default=str)

    def load_settings(self) -> dict:
        try:
            with open(self.settings_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def save_settings(self, settings: dict):
        with open(self.settings_file, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)

    def get_enabled_models(self) -> list[ModelConfig]:
        config = self.load_models_config()
        return [m for m in config.models if m.enabled]

    def get_model_by_id(self, model_id: str) -> Optional[ModelConfig]:
        config = self.load_models_config()
        for model in config.models:
            if model.id == model_id:
                return model
        return None

    def add_model(self, model: ModelConfig) -> bool:
        config = self.load_models_config()
        for existing in config.models:
            if existing.id == model.id:
                return False
        config.models.append(model)
        self.save_models_config(config)
        return True

    def update_model(self, model: ModelConfig) -> bool:
        config = self.load_models_config()
        for i, existing in enumerate(config.models):
            if existing.id == model.id:
                config.models[i] = model
                self.save_models_config(config)
                return True
        return False

    def delete_model(self, model_id: str) -> bool:
        config = self.load_models_config()
        config.models = [m for m in config.models if m.id != model_id]
        self.save_models_config(config)
        return True

    def export_config(self) -> str:
        config = self.load_models_config()
        return json.dumps(config.model_dump(), ensure_ascii=False, indent=2)

    def import_config(self, json_str: str) -> bool:
        try:
            data = json.loads(json_str)
            config = ModelsConfig(**data)
            self.save_models_config(config)
            return True
        except Exception:
            return False


config_manager = ConfigManager()
