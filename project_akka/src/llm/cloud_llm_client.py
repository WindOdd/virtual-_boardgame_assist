# src/llm/cloud_llm_client.py
import logging
import os
import json
from typing import Dict, Any

# [New] Import 新版 SDK
try:
    from google import genai
    from google.genai import types
    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False

from .base import BaseLLMClient, LLMResponse

logger = logging.getLogger(__name__)

class GeminiClient(BaseLLMClient):
    def __init__(self, config: Dict[str, Any]):
        if not GOOGLE_AVAILABLE:
            logger.error("❌ 'google-genai' package not installed. (pip install google-genai)")
            raise ImportError("Please install the new Google GenAI SDK: pip install google-genai")

        # 1. API Key 檢查
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            logger.warning("⚠️ GEMINI_API_KEY not found. Cloud Service will be disabled.")
            raise ValueError("Missing GEMINI_API_KEY")

        # 2. 模型名稱檢查
        self.model_name = config.get("name")
        if not self.model_name:
            raise ValueError("❌ Cloud LLM config missing 'name'.")

        # 3. 初始化 Client (新版寫法)
        # 注意：新版 SDK 會自動讀取 GEMINI_API_KEY 環境變數，也可以手動傳入
        self.client = genai.Client(api_key=api_key)
        
        logger.info(f"☁️ Gemini Client Init (New SDK): {self.model_name}")

    async def generate(self, prompt: str, system_prompt: str = "") -> LLMResponse:
        try:
            # [New] 使用 .aio 屬性呼叫原生非同步方法
            # 不需要 asyncio.to_thread 了！
            response = await self.client.aio.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=0.7,
                    thinking_config=types.ThinkingConfig(
                    include_thoughts=False
                    )
                )
            )
            
            return LLMResponse(
                content=response.text, 
                model_name=self.model_name
            )
        except Exception as e:
            logger.error(f"Gemini Generate Error: {e}")
            return LLMResponse(content="雲端大腦連線失敗")

    async def generate_json(self, prompt: str, system_prompt: str = "") -> Dict[str, Any]:
        try:
            # [New] JSON Mode 原生支援
            response = await self.client.aio.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    response_mime_type="application/json",
                    temperature=0.1
                )
            )
            return json.loads(response.text)
        except Exception as e:
            logger.error(f"Gemini JSON Error: {e}")
            return {}