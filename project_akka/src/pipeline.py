"""
Project Akka - Pipeline Module
Orchestrator for Hybrid Routing (Semantic -> LLM)
Refactored for Stateless Architecture (v9.6)
"""

import logging
import asyncio
import random
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

try:
    from .llm import LLMServiceManager
except ImportError:
    from llm.manager import LLMServiceManager

# Project modules
try:
    from .boardgame_utils import ConfigLoader, PromptManager
    from .data_manager import get_data_manager
    from .semantic_router import SemanticRouter
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
        self.system_config = {}
        self.semantic_routes = {}
        
        # 1. Load Configurations
        self._load_configs()
        
        # 2. Initialize Semantic Router
        embedding_config = self.system_config.get("model", {}).get("embedding", {})
        self.semantic_router = SemanticRouter(
            model_config=embedding_config,
            routes_config=self.semantic_routes
        )
        
        # 3. Initialize LLM Manager
        self.llm_manager = LLMServiceManager(self.system_config)
        self.local_llm = self.llm_manager.get_local()
        self.cloud_llm = self.llm_manager.get_cloud()

    def _load_configs(self) -> None:
        """Load all YAML configurations."""
        try:
            self.store_info = ConfigLoader(self.config_dir / "store_info.yaml").load()
            self.intent_map = ConfigLoader(self.config_dir / "intent_map.yaml").load()
            self.local_prompts = PromptManager(self.config_dir / "prompts_local.yaml")
            self.cloud_prompts = PromptManager(self.config_dir / "prompts_cloud.yaml")
            self.system_config = ConfigLoader(self.config_dir / "system_config.yaml").load()
            
            # Optional Configs
            try:
                self.semantic_routes = ConfigLoader(self.config_dir / "semantic_routes.yaml").load()
            except Exception:
                logger.warning("semantic_routes.yaml missing.")
                self.semantic_routes = {}
            
            logger.info("Config loaded.")
        except Exception as e:
            logger.error(f"Config load failed: {e}")
            self.store_info = {}
            self.semantic_routes = {}
            self.intent_map = {}
            self.system_config = {}

    def reload_configs(self) -> None:
        logger.info("Reloading configurations...")
        self._load_configs()
        embedding_config = self.system_config.get("model", {}).get("embedding", {})
        self.semantic_router = SemanticRouter(embedding_config, self.semantic_routes)

    async def process(self, user_input: str, history: List[Dict[str, Any]] = None, llm_service=None) -> PipelineResult:
        """
        Main processing pipeline.
        Args:
            user_input: The current user query.
            history: List of past turns (provided by Client) to extract context.
        """
        user_input = user_input.strip()
        if not user_input:
            return PipelineResult(response="...", source="empty")

        # ============================================================
        # [NEW] Stage 0: Context Extraction (Stateless Logic)
        # ============================================================
        context_str = ""
        if history:
            # 篩選規則：只看 User 的發言，且該發言必須帶有 intent
            recent_user_logs = [
                msg for msg in history 
                if msg.get("role") == "user" and msg.get("intent")
            ]
            
            if recent_user_logs:
                # 取出最後 2 次的意圖軌跡 (例如: RULES -> STORE_PRICING)
                last_intents = [msg["intent"] for msg in recent_user_logs[-2:]]
                context_str = " -> ".join(last_intents)
                logger.info(f"🕵️ Context Extracted from Request: {context_str}")

        # --- Stage 1: Semantic Vector Routing (FastPath) ---
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
        if self.llm_manager is None:
            return PipelineResult(response="系統維護中...", source="error")

        logger.info("🐢 FastPath Miss. Engaging LLM Router...")
    
        # [MODIFY] 將 Context 注入 Prompt
        if context_str:
            final_input = f"[Context: {context_str}] User Input: {user_input}"
        else:
            final_input = user_input

        # 傳送 final_input 給 Router
        router_result = await self._route_with_llm(final_input, self.local_llm)
        # 使用 Logger 而不是 Print，保持 Log 乾淨
        logger.info(f"Router Result: {router_result}") 

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

    async def _route_with_llm(self, final_input: str, llm_service) -> RouterResult:
        """
        Sends the constructed input (with context) to the Local LLM.
        """
        router_config = self.local_prompts.get_task_config("router")
        system_prompt = router_config.get("system_prompt", "")
        
        if not system_prompt:
            logger.warning("Router system prompt is empty!")
            
        if not self.local_llm:
            return RouterResult(intent="UNKNOWN", confidence=0.0, source="error")
            
        try:
            # 直接使用已經組好的 final_input
            response = await self.local_llm.generate_json(final_input, system_prompt)
            intent = response.get("intent", "UNKNOWN")
            confidence = response.get("confidence", 0.0)
            return RouterResult(intent=intent, confidence=confidence, source="llm")
        except Exception as e:
            logger.error(f"Router LLM Error: {e}")
            return RouterResult(intent="UNKNOWN", confidence=0.0, source="fallback")

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

    async def _dispatch(self, intent: str, user_input: str, context: Any = None) -> tuple[str, str]:
        responses_map = self.store_info.get("responses", {})
        
        # 1. Static Responses
        if intent in responses_map:
            candidates = responses_map[intent]
            if candidates: return (random.choice(candidates), "content_static")
        
        # 2. Logic Handlers
        logic_intents = self.intent_map.get("logic_intents", {})
        if intent in logic_intents:
            logic_config = logic_intents[intent]
            handler = logic_config.get("handler", "")
            
            if handler == "local_llm" and self.local_llm:
                # 這裡調用 Persona 進行閒聊
                task = logic_config.get("task", "casual_chat")
                sys_prompt = self.local_prompts.get_task_config("casual_chat").get("system_prompt", "")
                resp = await self.local_llm.generate(user_input, sys_prompt)
                return (resp.content, "local_llm_gen")
            elif handler in ["online_llm", "cloud_llm", "cloud_rag"]:
                if self.cloud_llm:
                    return await self._handle_rules_query(user_input, context)
                else:
                    return ("抱歉，雲端大腦連線有點問題，請稍後再試。", "error")
            elif handler == "reject":
                return (logic_config.get("response", "抱歉"), "reject")

        # 3. Fallback
        fallback = self.store_info.get("responses", {}).get("UNKNOWN_FALLBACK", ["抱歉？"])
        return (random.choice(fallback), "fallback")
    # src/pipeline.py -> class Pipeline

    async def _handle_rules_query(self, user_input: str, context: Dict[str, Any]) -> tuple[str, str]:
        """
        專門處理 RULES 意圖的邏輯函式
        1. 解析 Client 傳來的 Game Name
        2. 透過 DataManager 載入對應規則書
        3. 組合 Prompt 並呼叫 Cloud LLM
        """
        # 1. 取得遊戲名稱 (從 Client 傳來的 context)
        game_ctx = context.get("game_context", {})
        # 優先使用 Client 傳來的 ID，如果沒有則用預設值 (如 'Carcassonne')
        game_id = game_ctx.get("game_name", "Carcassonne")
        
        # 2. 透過 DataManager 取得規則內容 (它會自動查 registry 找路徑)
        # 這裡利用了您現有的 data_manager.py 的功能
        rule_content = self.data_manager.get_rules(game_id)
        
        if not rule_content:
            logger.warning(f"Rulebook not found for game_id: {game_id}")
            # 嘗試用通用規則或回傳錯誤
            rule_content = "（系統提示：目前找不到此遊戲的詳細規則資料，請依據您的通用知識回答，並告知使用者規則書缺失。）"

        # 3. 讀取 System Prompt Template (從 prompts_cloud.yaml)
        # task_name 對應 prompts_cloud.yaml 裡的 key
        task_config = self.cloud_prompts.get_task_config("rules_explainer")
        system_template = task_config.get("system_prompt", "")
        
        # 4. 注入規則 (Prompt Injection)
        # 將 Template 中的 {INJECTED_RAG_CONTENT} 替換成真實規則內容
        final_system_prompt = system_template.replace("{INJECTED_RAG_CONTENT}", rule_content)
        
        # 5. 準備歷史紀錄 (History)
        history = context.get("history", [])
        
        # 6. 呼叫雲端大腦 (Cloud LLM)
        try:
            # 呼叫 src/llm/cloud_llm_client.py
            response = await self.cloud_llm.generate(
                prompt=user_input,
                # 注意：這裡我們把 "System Prompt + 規則書" 當作 system_instruction 傳入
                system_prompt=final_system_prompt
                # History 的處理通常由 LLM Client 內部處理，或是這裡將 history 轉成文字串接在 prompt 前
                # 視您的 CloudLLMClient 實作而定。如果是 Google GenAI SDK，通常需要轉成 message list。
                # 這裡假設 generate 方法能處理基礎文字生成。
            )
            return (response.content, "cloud_gen")
            
        except Exception as e:
            logger.error(f"Cloud Handling Error: {e}")
            return ("抱歉，雲端大腦連線有點問題，請稍後再試。", "error")
def create_pipeline(config_dir: Optional[Path] = None) -> Pipeline:
    return Pipeline(config_dir=config_dir)

if __name__ == "__main__":
    # Test Standalone Pipeline
    import time 
    logging.basicConfig(level=logging.INFO)
    p = create_pipeline()
    print("Pipeline Initialized.")
    print("=============================")
    
    # 測試 1: 一般 FastPath
    print("\n--- Test 1: FastPath (No History) ---")
    print(asyncio.run(p.process("想尿尿")))
    
    # 測試 2: 一般 LLM Router
    print("\n--- Test 2: LLM Router (No History) ---")
    print(asyncio.run(p.process("你好我想知道你們有賣哪些桌遊")))
    
    # 測試 3: Context Aware (模擬 Client 帶入 History)
    print("\n--- Test 3: Context Injection (Simulate Client History) ---")
    # 情境：上一輪問了價格，這一輪只問「那假日呢？」
    mock_history = [
        {"role": "user", "content": "平日多少錢？", "intent": "STORE_PRICING"},
        {"role": "assistant", "content": "平日 60 元..."}
    ]
    # 我們期望這句模糊的「那假日呢」能因為 History 而被識別正確
    print(f"Input: 那假日呢？ (with context: STORE_PRICING)")
    print(asyncio.run(p.process("那假日呢？", history=mock_history)))
    
    print("\n=============================")
    print("Tests Completed.")