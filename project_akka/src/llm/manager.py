# src/llm/manager.py
from typing import Dict, Any, Optional
import logging
from .local_llm_client import OllamaClient
from .cloud_llm_client import GeminiClient

logger = logging.getLogger(__name__)

class LLMServiceManager:
    def __init__(self, system_config: Dict[str, Any]):
        """
        Args:
            system_config: 來自 system_config.yaml 的完整字典
        """
        self.local_client = None
        self.cloud_client = None
        
        model_cfg = system_config.get("model", {})

        # 1. 初始化 Local (Ollama)
        local_cfg = model_cfg.get("local")
        if local_cfg and local_cfg.get("provider") == "ollama":
            try:
                self.local_client = OllamaClient(local_cfg)
            except Exception as e:
                logger.error(f"Failed to init Local LLM: {e}")

        # 2. 初始化 Cloud (Gemini)
        cloud_cfg = model_cfg.get("cloud")
        if cloud_cfg and cloud_cfg.get("provider") == "google":
            try:
                self.cloud_client = GeminiClient(cloud_cfg)
            except Exception as e:
                logger.warning(f"Cloud LLM disabled (Check API Key): {e}")

    def get_local(self):
        if not self.local_client:
            logger.warning("Local LLM is not available!")
        return self.local_client

    def get_cloud(self):
        if not self.cloud_client:
            logger.warning("Cloud LLM is not available!")
        return self.cloud_client