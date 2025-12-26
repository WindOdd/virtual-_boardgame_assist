# src/llm/gemini_client.py
import logging
import os
import json
import asyncio
from typing import Dict, Any

# Google GenAI SDK
try:
    import google.generativeai as genai
    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False

from .base import BaseLLMClient, LLMResponse

logger = logging.getLogger(__name__)

class GeminiClient(BaseLLMClient):
    def __init__(self, config: Dict[str, Any]):
        if not GOOGLE_AVAILABLE:
            logger.error("❌ google-generativeai package not installed.")
            raise ImportError("Please pip install google-generativeai")

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            logger.warning("⚠️ GEMINI_API_KEY not found in environment variables.")
        
        genai.configure(api_key=api_key)
        self.model_name = config.get("name", "gemini-2.5-flash")
        
        # 初始化模型
        self.model = genai.GenerativeModel(self.model_name)
        logger.info(f"☁️ Gemini Client Init: {self.model_name}")

    async def generate(self, prompt: str, system_prompt: str = "") -> LLMResponse:
        try:
            # Gemini SDK 目前主要為同步或基於 grpc 的 async
            # 這裡使用 asyncio.to_thread 確保不阻塞 Event Loop
            full_prompt = f"System Instruction: {system_prompt}\n\nUser Query: {prompt}"
            
            response = await asyncio.to_thread(
                self.model.generate_content,
                full_prompt
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
            full_prompt = f"System: {system_prompt}\nUser: {prompt}"
            
            # 使用 JSON mode
            response = await asyncio.to_thread(
                self.model.generate_content,
                full_prompt,
                generation_config={"response_mime_type": "application/json"}
            )
            return json.loads(response.text)
        except Exception as e:
            logger.error(f"Gemini JSON Error: {e}")
            return {}