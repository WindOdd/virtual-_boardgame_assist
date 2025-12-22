"""
Project Akka - Pipeline Module
Data-Driven Pipeline: FastPath -> Router -> Dispatch

This module handles the main processing pipeline using configuration-based
intent mapping instead of hardcoded Enums.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
import random
import yaml
from boardgame_utils import ConfigLoader, PromptManager
from data_manager import get_data_manager
import os
import asyncio 
import logging
logger = logging.getLogger(__name__)
@dataclass
class RouterResult:
    """Result from the router stage."""
    intent: str  # Raw string intent (no Enum)
    confidence: float = 1.0
    used_fastpath: bool = False


@dataclass
class PipelineResult:
    """Final result from the pipeline."""
    response: str
    intent: Optional[str] = None
    confidence: float = 0.0
    source: str = "unknown"  # "fastpath", "local", "cloud", "content"


class Pipeline:
    """
    Data-driven processing pipeline for user queries.
    
    Flow:
    1. FastPath: Check for pattern matches (greetings, farewells)
    2. Router: Use Local LLM to classify intent (returns raw string)
    3. Dispatch: Check logic_intents first, then content_map
       - Logic intents: RULES -> Cloud LLM, SENSITIVE -> reject, CASUAL_CHAT -> casual chat
       - Content intents: Traverse store_info.yaml path and return response
    """
    
    def __init__(self, config_dir: Optional[Path] = None):
        """
        Initialize the pipeline with configuration files.
        
        Args:
            config_dir: Path to config directory (defaults to Project_Akka/config)
        """
        self.config_dir = config_dir or Path(__file__).parent.parent / "config"
        self.data_manager = get_data_manager()
        #print(self.config_dir)
        # Load configurations
        self._load_configs()
        #self.store_data = ConfigLoader(f"{self.config_dir}/store_info.yaml").load()['responses_pool']
        #self.intent_map = ConfigLoader(f"{self.config_dir}/intent_map.yaml").load()
        #self.local_prompts = PromptManager(f"{self.config_dir}/prompts_local.yaml")
    
    def _load_configs(self) -> None:
        """Load all required YAML configuration files."""
        # Load store_info.yaml
        store_info_path = self.config_dir / "store_info.yaml"
        self.store_info = ConfigLoader(store_info_path).load()
        # Load intent_map.yaml
        intent_map_path = self.config_dir / "intent_map.yaml"
        self.intent_map = ConfigLoader(intent_map_path).load()
        #print(self.intent_map)
        # Load prompts_local.yaml
        prompts_local_path = self.config_dir / "prompts_local.yaml"
        self.prompts_local = PromptManager(prompts_local_path) 
    
    def reload_configs(self) -> None:
        """Hot-reload configuration files."""
        self._load_configs()
    
    async def process(self, user_input: str, llm_service=None) -> PipelineResult:
        """
        Process a user query through the pipeline.
        """
        # 1. Try FastPath (Dynamic check from store_info)
        fastpath_response = self._try_fastpath(user_input)
        if fastpath_response:
            return PipelineResult(
                response=fastpath_response,
                intent="GREETING",  # Or derive from category if needed
                confidence=1.0,
                source="fastpath"
            )
        
        # 2. Route to get intent (requires LLM service)
        if llm_service is None:
            return PipelineResult(
                response="抱歉，系統正在維護中，請稍後再試。",
                source="error"
            )
        
        router_result = await self._route(user_input, llm_service)
        
        # [Stage IV] Safety Filter (Allowlist Check)
        # If intent is SENSITIVE, check if keywords are in the allowlist.
        # If matched, override intent to RULES to prevent false positives.
        if router_result.intent == "SENSITIVE":
            if self._check_allowlist(user_input):
                logger.info(f"Safety Filter: Allowlist hit for '{user_input}'. Overriding SENSITIVE to RULES.")
                router_result.intent = "RULES"
        
        # 3. Dispatch based on intent
        response, source = await self._dispatch(
            router_result.intent, 
            user_input, 
            llm_service
        )
        
        return PipelineResult(
            response=response,
            intent=router_result.intent,
            confidence=router_result.confidence,
            source=source
        )
    
    def _try_fastpath(self, user_input: str) -> Optional[str]:
        """
        Attempt quick pattern matching for common queries.
        Dynamically checks ALL categories in 'common_chat' (e.g., greetings, identity).
        """
        user_input_lower = user_input.strip().lower()
        
        # [FIX] Generalized loop for all chat categories
        common_chat = self.store_info.get("common_chat", {})
        if not isinstance(common_chat, dict):
            return None
            
        for category, data in common_chat.items():
            keywords = data.get("keywords", [])
            responses = data.get("responses", [])
            
            # Check for keyword matches
            for trigger in keywords:
                if trigger.lower() in user_input_lower:
                    if responses:
                        return random.choice(responses)
        
        return None
    
    def _check_allowlist(self, user_input: str) -> bool:
        """
        Check if user input contains any keyword from the allowlist of enabled games.
        """
        try:
            # List all registered games
            games = self.data_manager.list_games()
            for game in games:
                # Allowlist is defined in games_registry.yaml under metadata
                allowlist = game.metadata.get("allowlist_keywords", [])
                for keyword in allowlist:
                    if keyword in user_input:
                        return True
        except Exception as e:
            logger.error(f"Error checking allowlist: {e}")
            
        return False
    
    async def _route(self, user_input: str, llm_service) -> RouterResult:
        """
        Use Local LLM to classify the user's intent.
        """
        router_config = self.prompts_local.get("router", {})
        system_prompt = router_config.get("system_prompt", "")
        
        # Call LLM for intent classification
        try:
            response = await llm_service.generate_json(
                prompt=user_input,
                system_prompt=system_prompt
            )
            intent = response.get("intent", "CASUAL_CHAT")
            confidence = response.get("confidence", 0.8)
            return RouterResult(intent=intent, confidence=confidence)
        except Exception:
            # Fallback to CASUAL_CHAT on error
            return RouterResult(intent="CASUAL_CHAT", confidence=0.5)
    
    async def _dispatch(
        self, 
        intent: str, 
        user_input: str, 
        llm_service
    ) -> tuple[str, str]:
        """
        Dispatch to appropriate handler based on intent.
        Checks logic_intents first, then content_map.
        """
        logic_intents = self.intent_map.get("logic_intents", {})
        content_map = self.intent_map.get("content_map", {})
        
        # --- Check Logic Intents First ---
        if intent in logic_intents:
            logic_config = logic_intents[intent]
            handler = logic_config.get("handler", "")
            
            if handler == "reject":
                return (logic_config.get("response", "抱歉，我無法回答這個問題。"), "reject")
            
            elif handler == "local_llm":
                task_name = logic_config.get("task", "casual_chat")
                task_config = self.prompts_local.get(task_name, {})
                system_prompt = task_config.get("system_prompt", "")
                
                response = await llm_service.generate(
                    prompt=user_input,
                    system_prompt=system_prompt
                )
                return (response.content, "local")
            
            elif handler == "cloud_llm":
                return ("這個規則問題需要連接雲端服務，請稍後再試。", "cloud")
        
        # --- Check Content Map ---
        if intent in content_map:
            content_config = content_map[intent]
            path = content_config.get("path", "")
            fallback = content_config.get("fallback", "抱歉，我找不到這個資訊。")
            template = content_config.get("template")
            
            # Traverse the path in store_info (Root)
            value = self._traverse_path(self.store_info, path)
            
            # If not found, try responses_pool (Backward Compatibility)
            if value is None:
                value = self._traverse_path(self.store_data, path)

            if value is None:
                return (fallback, "content")
            
            # Handle different value types
            if isinstance(value, list):
                return (random.choice(value), "content")
            elif isinstance(value, dict):
                if template:
                    try:
                        response = self._format_template(template, value)
                        return (response, "content")
                    except KeyError:
                        return (fallback, "content")
                else:
                    for v in value.values():
                        if isinstance(v, str):
                            return (v, "content")
                    return (fallback, "content")
            elif isinstance(value, str):
                return (value, "content")
            else:
                return (str(value), "content")
        
        # --- Fallback ---
        return ("抱歉，我不太確定你的問題，可以再說一次嗎？", "fallback")
    
    def _traverse_path(self, data: Dict[str, Any], path: str) -> Any:
        """
        Traverse a dot-separated path in a nested dictionary.
        """
        if not path or not isinstance(data, dict):
            return None
        
        keys = path.split(".")
        current = data
        
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None
        
        return current
    
    def _format_template(self, template: str, data: Dict[str, Any]) -> str:
        """
        Format a template string with nested dictionary values.
        """
        import re
        
        def replace_match(match):
            key_path = match.group(1)
            value = self._traverse_path(data, key_path)
            if value is None:
                value = data.get(key_path, "")
            return str(value) if value is not None else ""
        
        result = re.sub(r'\{([^}]+)\}', replace_match, template)
        return result


# Factory function for convenience
def create_pipeline(config_dir: Optional[Path] = None) -> Pipeline:
    """Create a new Pipeline instance."""
    return Pipeline(config_dir=config_dir)

if __name__ == "__main__":
    try_it=create_pipeline()
    print(asyncio.run(try_it.process("你是誰")))