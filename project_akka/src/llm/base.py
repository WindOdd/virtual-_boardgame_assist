# src/llm/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Any, Optional

@dataclass
class LLMResponse:
    content: str
    token_usage: Optional[int] = 0
    model_name: str = "unknown"

class BaseLLMClient(ABC):
    @abstractmethod
    async def generate(self, prompt: str, system_prompt: str = "") -> LLMResponse:
        """生成一般文字回應"""
        pass

    @abstractmethod
    async def generate_json(self, prompt: str, system_prompt: str = "") -> Dict[str, Any]:
        """生成 JSON 格式回應 (強制)"""
        pass