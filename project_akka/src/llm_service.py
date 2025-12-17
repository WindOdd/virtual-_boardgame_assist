"""
Project Akka - LLM Service Module
Ollama & Gemini Connectors

This module provides unified interfaces for:
1. Local LLM (Ollama with qwen3:4b-instruct)
2. Cloud LLM (Google Gemini gemini-2.5-flash)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
import json


@dataclass
class LLMResponse:
    """Standardized LLM response."""
    content: str
    model: str
    tokens_used: Optional[int] = None
    latency_ms: Optional[float] = None


class BaseLLMService(ABC):
    """Abstract base class for LLM services."""
    
    @abstractmethod
    async def generate(self, prompt: str, system_prompt: Optional[str] = None) -> LLMResponse:
        """Generate a response from the LLM."""
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the LLM service is available."""
        pass


class OllamaService(BaseLLMService):
    """
    Local LLM service using Ollama.
    
    Used for:
    - Intent routing (fast, low-latency classification)
    - Simple responses that don't need cloud capabilities
    """
    
    def __init__(self, model: str = "qwen3:4b-instruct", base_url: str = "http://:11434"):
        self.model = model
        self.base_url = base_url
    
    async def generate(self, prompt: str, system_prompt: Optional[str] = None) -> LLMResponse:
        """
        Generate response using Ollama.
        
        Args:
            prompt: User prompt
            system_prompt: Optional system prompt for context
            
        Returns:
            LLMResponse with generated content
        """
        # TODO: Implement Ollama API call
        # Use httpx or aiohttp for async HTTP requests
        raise NotImplementedError("Ollama service not yet implemented")
    
    async def generate_json(self, prompt: str, system_prompt: Optional[str] = None) -> dict:
        """
        Generate JSON response, useful for intent routing.
        
        Returns parsed JSON dict.
        """
        response = await self.generate(prompt, system_prompt)
        return json.loads(response.content)
    
    async def health_check(self) -> bool:
        """Check if Ollama is running and model is available."""
        # TODO: Implement health check
        return False


class GeminiService(BaseLLMService):
    """
    Cloud LLM service using Google Gemini.
    
    Used for:
    - Complex reasoning tasks
    - Detailed game rule explanations
    - Natural conversation with personality
    """
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-2.5-flash"):
        self.model = model
        self.api_key = api_key
        # TODO: Initialize google.generativeai client
    
    async def generate(self, prompt: str, system_prompt: Optional[str] = None) -> LLMResponse:
        """
        Generate response using Gemini.
        
        Args:
            prompt: User prompt
            system_prompt: Optional system prompt for persona/context
            
        Returns:
            LLMResponse with generated content
        """
        # TODO: Implement Gemini API call
        raise NotImplementedError("Gemini service not yet implemented")
    
    async def health_check(self) -> bool:
        """Check if Gemini API is accessible."""
        # TODO: Implement health check
        return False


class LLMServiceFactory:
    """Factory for creating LLM service instances."""
    
    @staticmethod
    def create_local(config: dict) -> OllamaService:
        """Create local LLM service from config."""
        return OllamaService(
            model=config.get("name", "qwen3:4b-instruct"),
            base_url=config.get("base_url", "http://localhost:11434")
        )
    
    @staticmethod
    def create_cloud(config: dict, api_key: str) -> GeminiService:
        """Create cloud LLM service from config."""
        return GeminiService(
            api_key=api_key,
            model=config.get("name", "gemini-2.5-flash")
        )
