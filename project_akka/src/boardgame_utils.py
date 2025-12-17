import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Union
import yaml

logger = logging.getLogger(__name__)

class ConfigLoader:
    """通用設定檔讀取器 (支援 YAML/JSON)"""
    def __init__(self, config_path: Union[str, Path]):
        self.config_path = Path(config_path)
        self._data = None

    def load(self, force_reload: bool = False) -> Dict[str, Any]:
        if self._data and not force_reload:
            return self._data

        if not self.config_path.exists():
            logger.error(f"Config not found: {self.config_path}")
            raise FileNotFoundError(f"Config not found: {self.config_path}")
        
        with open(self.config_path, 'r', encoding='utf-8') as f:
            if self.config_path.suffix in ['.yaml', '.yml']:
                self._data = yaml.safe_load(f)
            else:
                self._data = json.load(f)
        return self._data

class PromptManager:
    """
    專門處理 prompts_local.yaml / prompts_cloud.yaml
    不再讀取 txt，而是從 YAML 結構中提取 system_prompt 與 options
    """
    def __init__(self, config_path: Union[str, Path]):
        self.loader = ConfigLoader(config_path)
        self.config = self.loader.load()

    def get_task_config(self, task_name: str) -> Dict[str, Any]:
        """
        取得特定任務的完整設定 (包含 temperature, system_prompt 等)
        例如: task_name='router' -> 回傳 dict
        """
        task_config = self.config.get(task_name)
        if not task_config:
            raise ValueError(f"Task '{task_name}' not found in prompt config.")
        return task_config

    def get_system_prompt(self, task_name: str) -> str:
        """快速取得特定任務的 System Prompt"""
        return self.get_task_config(task_name).get('system_prompt', '')

    def get_options(self, task_name: str) -> Dict[str, Any]:
        """快速取得特定任務的 Model Options (temperature, top_p...)"""
        # 過濾掉 system_prompt，只回傳參數部分給 Ollama/Gemini
        config = self.get_task_config(task_name).copy()
        config.pop('system_prompt', None)
        return config