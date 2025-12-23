"""
Project Akka - Pipeline Module
Orchestrator for Hybrid Routing (Semantic -> LLM)
"""

import logging
import asyncio
import random
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

# Project modules
try:
    from .boardgame_utils import ConfigLoader, PromptManager
    from .data_manager import get_data_manager
    from .semantic_router import SemanticRouter  # [New] Import 獨立模組
except ImportError:
    from boardgame_utils import ConfigLoader, PromptManager
    from data_manager import get_data_manager
    from semantic_router import SemanticRouter

logger = logging.getLogger(__name__)

@dataclass
class RouterResult:
    intent: str
    confidence: float = 0.0
    source: str = "unknown"

@dataclass
class PipelineResult:
    response: str
    intent: Optional[str] = None
    confidence: float = 0.0
    source: str = "unknown"

class Pipeline:
    def __init__(self, config_dir: Optional[Path] = None):
        self.config_dir = config_dir or Path(__file__).parent.parent / "config"
        self.data_manager = get_data_manager()
        
        # 1. Load Configurations
        self._load_configs()
        
        # 2. Initialize Semantic Router (Delegate to new class)
        # 從 system_config 抓 embedding 設定，從 semantic_routes 抓資料
        embedding_config = self.system_config.get("embedding", {})
        print(embedding_config)
        self.semantic_router = SemanticRouter(
            model_config=embedding_config,
            routes_config=self.semantic_routes
        )

    def _load_configs(self) -> None:
        """Load all YAML configurations."""
        try:
            self.store_info = ConfigLoader(self.config_dir / "store_info.yaml").load()
            self.intent_map = ConfigLoader(self.config_dir / "intent_map.yaml").load()
            self.local_prompts = PromptManager(self.config_dir / "prompts_local.yaml")
            
            # Optional Configs
            try:
                self.semantic_routes = ConfigLoader(self.config_dir / "semantic_routes.yaml").load()
            except Exception:
                logger.warning("semantic_routes.yaml missing.")
                self.semantic_routes = {}
            
            try:
                self.system_config = ConfigLoader(self.config_dir / "system_config.yaml").load()
            except Exception:
                logger.error("system_config.yaml missing!")
                self.system_config = {}

            logger.info("Config loaded.")
        except Exception as e:
            logger.error(f"Config load failed: {e}")
            # Init empty defaults
            self.store_info = {}
            self.semantic_routes = {}
            self.intent_map = {}
            self.system_config = {}

    def reload_configs(self) -> None:
        logger.info("Reloading configurations...")
        self._load_configs()
        # Re-init router with new configs
        embedding_config = self.system_config.get("model", {}).get("embedding", {})
        self.semantic_router = SemanticRouter(embedding_config, self.semantic_routes)

    async def process(self, user_input: str, llm_service=None) -> PipelineResult:
        user_input = user_input.strip()
        if not user_input:
            return PipelineResult(response="...", source="empty")

        # --- Stage 1: Semantic Vector Routing (FastPath) ---
        # 呼叫獨立的 router 物件
        semantic_intent, score = self.semantic_router.route(user_input)
        
        if semantic_intent:
            logger.info(f"⚡ FastPath Hit: {semantic_intent} (Score: {score:.4f})")
            response, source = await self._dispatch(semantic_intent, user_input, None)
            return PipelineResult(
                response=response,
                intent=semantic_intent,
                confidence=float(score),
                source=f"fastpath_{source}"
            )

        # --- Stage 2: LLM Intent Routing ---
        if llm_service is None:
            return PipelineResult(response="系統維護中...", source="error")

        logger.info("🐢 FastPath Miss. Engaging LLM Router...")
        router_result = await self._route_with_llm(user_input, llm_service)
        
        # --- Stage 3: Safety Filter ---
        if router_result.intent == "SENSITIVE":
            if self._check_allowlist(user_input):
                router_result.intent = "RULES"

        # --- Stage 4: Dispatch ---
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

    # ... (其餘 _route_with_llm, _check_allowlist, _dispatch 保持不變)
    async def _route_with_llm(self, user_input: str, llm_service) -> RouterResult:
        router_config = self.local_prompts.get("router", {})
        system_prompt = router_config.get("system_prompt", "")
        try:
            response = await llm_service.generate_json(user_input, system_prompt)
            intent = response.get("intent", "CASUAL_CHAT")
            confidence = response.get("confidence", 0.0)
            return RouterResult(intent=intent, confidence=confidence, source="llm")
        except Exception:
            return RouterResult(intent="CASUAL_CHAT", confidence=0.0, source="fallback")

    def _check_allowlist(self, user_input: str) -> bool:
        try:
            games = self.data_manager.list_games()
            for game in games:
                allowlist = game.metadata.get("allowlist_keywords", [])
                for keyword in allowlist:
                    if keyword in user_input: return True
        except Exception:
            pass
        return False

    async def _dispatch(self, intent: str, user_input: str, llm_service) -> tuple[str, str]:
        responses_map = self.store_info.get("responses", {})
        if intent in responses_map:
            candidates = responses_map[intent]
            if candidates: return (random.choice(candidates), "content_static")
        
        logic_intents = self.intent_map.get("logic_intents", {})
        if intent in logic_intents:
            logic_config = logic_intents[intent]
            handler = logic_config.get("handler", "")
            
            if handler == "local_llm" and llm_service:
                task = logic_config.get("task", "casual_chat")
                sys_prompt = self.local_prompts.get(task, {}).get("system_prompt", "")
                resp = await llm_service.generate(user_input, sys_prompt)
                return (resp.content, "local_llm_gen")
            elif handler == "reject":
                return (logic_config.get("response", "抱歉"), "reject")

        fallback = self.store_info.get("responses", {}).get("UNKNOWN_FALLBACK", ["抱歉？"])
        return (random.choice(fallback), "fallback")

def create_pipeline(config_dir: Optional[Path] = None) -> Pipeline:
    return Pipeline(config_dir=config_dir)

if __name__ == "__main__":
    # Test Standalone Pipeline
    import time 
    logging.basicConfig(level=logging.INFO)
    p = create_pipeline()
    print("Pipeline Initialized.")
    print("=============================")
    time.sleep(1)
    print("Use Ask :想尿尿")
    print(asyncio.run(p.process("想尿尿")))
    time.sleep(1)
    print("Use Ask :Wi-Fi")
    print(asyncio.run(p.process("Wi-Fi")))
    time.sleep(1)
    print("Use Ask :你好")
    print(asyncio.run(p.process("你好")))
    time.sleep(1)
    print("Use Ask :你好")
    time.sleep(1)
    print("Use Ask :你好我想知道你們有賣哪些桌遊")
    print(asyncio.run(p.process("你好我想知道你們有賣哪些桌遊")))
    time.sleep(1)
    print("Use Ask :你好我想知道店裡有賣什麼")
    print(asyncio.run(p.process("你好我想知道店裡有賣什麼")))
    time.sleep(1)
    print("Use Ask :有網路嗎")
    print(asyncio.run(p.process("有網路嗎")))