# src/llm/ollama_client.py
import logging
import json
import aiohttp
from typing import Dict, Any
from .base import BaseLLMClient, LLMResponse

logger = logging.getLogger(__name__)

class OllamaClient(BaseLLMClient):
    def __init__(self, config: Dict[str, Any]):
        # 從 system_config.yaml 的 model.local 讀取
        self.model_name = config.get("name")
        if not self.model_name:
            raise ValueError("❌ Local LLM config missing 'name'. Check system_config.yaml")
        # 預設 host，若 config 沒寫則用 localhost
        self.base_url = config.get("host", "http://localhost:11434")
        self.timeout = config.get("timeout", 30)
        
        logger.info(f"🟢 Ollama Client Init: {self.model_name} at {self.base_url}")

    async def generate(self, prompt: str, system_prompt: str = "") -> LLMResponse:
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "stream": False,
            "options": {"temperature": 0.7}
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=self.timeout) as resp:
                    if resp.status != 200:
                        err_text = await resp.text()
                        logger.error(f"Ollama API Error {resp.status}: {err_text}")
                        return LLMResponse(content="系統忙碌中 (Local LLM Error)")
                    
                    data = await resp.json()
                    content = data.get("message", {}).get("content", "")
                    tokens = data.get("eval_count", 0)
                    return LLMResponse(content=content, token_usage=tokens, model_name=self.model_name)
                    
        except Exception as e:
            logger.error(f"Ollama Connection Failed: {e}")
            return LLMResponse(content="系統維護中 (Local Connection Failed)")

    async def generate_json(self, prompt: str, system_prompt: str = "") -> Dict[str, Any]:
        """強制 Ollama 輸出 JSON (用於 Router)"""
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "format": "json",  # Ollama 原生 JSON 模式
            "stream": False,
            "options": {"temperature": 0.1} # Router 需要低溫才準
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=self.timeout) as resp:
                    if resp.status != 200:
                        return {}
                    
                    data = await resp.json()
                    content = data.get("message", {}).get("content", "{}")
                    return json.loads(content)
        except Exception as e:
            logger.error(f"Ollama JSON Error: {e}")
            return {}