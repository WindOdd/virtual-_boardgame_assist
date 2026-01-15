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

    async def process(
        self, 
        user_input: str, 
        history: List[Dict[str, Any]] = None, 
        game_context: Dict[str, Any] = None, # <--- 新增這裡
        llm_service=None
    ) -> PipelineResult:
        """
        Main processing pipeline.
        Args:
            user_input: The current user query.
            history: List of past turns (provided by Client) to extract context.
        """
        user_input = user_input.strip()
        if not user_input:
            return PipelineResult(response="...", source="empty")

        # === DEBUG: Pipeline 入口資料 ===
        logger.info("=" * 50)
        logger.info("🔍 [DEBUG] Pipeline.process() 入口資料:")
        logger.info(f"   user_input: {user_input}")
        logger.info(f"   history: {history}")
        logger.info(f"   game_context: {game_context}")
        logger.info("=" * 50)

        # ============================================================
        # [NEW] Stage 0: Context Extraction (Stateless Logic)
        # ============================================================
        # Extract recent context with queries (INTENT: query format)
        recent_context = self._extract_recent_context(history, window=3, max_length=80)

        # Legacy format for backward compatibility (intent chain)
        context_str = ""
        if history:
            # === DEBUG: 檢查 history 中的意圖標籤 ===
            logger.info("🔍 [DEBUG] Context Extraction - 檢查 history:")
            for i, msg in enumerate(history):
                role = msg.get("role", "?")
                intent = msg.get("intent", "N/A")
                content = msg.get("content", "")[:30]  # 只顯示前 30 字
                logger.info(f"   [{i}] role={role}, intent={intent}, content={content}...")

            # [修正] 篩選規則：從 assistant 的回應提取 intent（因為只有 server 回應才會加上 intent）
            recent_assistant_logs = [
                msg for msg in history
                if msg.get("role") == "assistant" and msg.get("intent")
            ]

            logger.info(f"🔍 [DEBUG] 符合條件的 assistant logs 數量: {len(recent_assistant_logs)}")

            if recent_assistant_logs:
                # 取出最後 2 次的意圖軌跡 (例如: RULES -> STORE_PRICING)
                last_intents = [msg["intent"] for msg in recent_assistant_logs[-2:]]
                context_str = " -> ".join(last_intents)
                logger.info(f"🕵️ Context Extracted (legacy): {context_str}")
            else:
                logger.info("⚠️ [DEBUG] 沒有找到帶 intent 的 assistant log，context_str 為空")

        # Log new format
        if recent_context:
            logger.info("🔍 [DEBUG] Recent Context (new format):")
            for ctx in recent_context:
                logger.info(f"   - {ctx}")

        # [NEW] Get top 3 semantic scores for LLM Router
        top_matches = self.semantic_router.get_top_matches(user_input, top_k=3)
        if top_matches:
            logger.info("🔍 [DEBUG] Top 3 Semantic Scores:")
            for intent, score in top_matches:
                logger.info(f"   - {intent}: {score:.4f}")

        # [NEW] Load STT keywords if game_id is provided
        stt_keywords = []
        if game_context and game_context.get("game_id"):
            game_id = game_context.get("game_id")
            stt_keywords = self._load_stt_keywords(game_id)
            if stt_keywords:
                logger.info(f"🔍 [DEBUG] STT Keywords loaded for {game_id}: {len(stt_keywords)} keywords")

        # --- Stage 1: Semantic Vector Routing (FastPath) ---
        semantic_intent, score = self.semantic_router.route(user_input)
    
        if semantic_intent:
            logger.info(f"⚡ FastPath Hit: {semantic_intent} (Score: {score:.4f})")
            response, source, override_intent = await self._dispatch(semantic_intent, user_input, None)
            final_intent = override_intent if override_intent else semantic_intent
            return PipelineResult(
                response=response,
                intent=final_intent,
                confidence=float(score),
                source=f"fastpath_{source}"
            )

        # --- Stage 2: LLM Intent Routing ---
        if self.llm_manager is None:
            return PipelineResult(response="系統維護中...", source="error")

        logger.info("🐢 FastPath Miss. Engaging LLM Router...")

        # [MODIFY] 將 Context 注入 Prompt
        # Build semantic scores block
        if top_matches:
            scores_lines = "\n".join([f"- {intent}: {score:.2f}" for intent, score in top_matches])
            scores_block = f"[Semantic Scores]\n{scores_lines}\n\n"
        else:
            scores_block = ""

        # Build context string from recent_context (new format)
        if recent_context:
            context_lines = "\n".join([f"- {ctx}" for ctx in recent_context])
            context_block = f"[Recent Context]\n{context_lines}\n\n"
        else:
            context_block = ""

        # Build STT keywords block
        if stt_keywords:
            keywords_str = ", ".join(stt_keywords[:20])  # Limit to first 20 keywords
            keywords_block = f"[Game Keywords]\n{keywords_str}\n\n"
        else:
            keywords_block = ""

        # Legacy context format (for backward compatibility)
        if context_str and not recent_context:
            legacy_context = f"[Context: {context_str}]\n\n"
        else:
            legacy_context = ""

        # Construct final input
        final_input = f"{scores_block}{context_block}{keywords_block}{legacy_context}[User Input] {user_input}"

        # 傳送 final_input 給 Router
        router_result = await self._route_with_llm(final_input, self.local_llm)
        # 使用 Logger 而不是 Print，保持 Log 乾淨
        logger.info(f"Router Result: {router_result}") 

        # --- Stage 3: Safety Filter ---
        if router_result.intent == "SENSITIVE":
            if self._check_allowlist(user_input):
                router_result.intent = "RULES"
        context_pack = {
            "history": history,
            "game_context": game_context
        }
        # === DEBUG: 傳入 Dispatch 的 context_pack ===
        logger.info("🔍 [DEBUG] context_pack 傳入 _dispatch:")
        logger.info(f"   game_context: {context_pack.get('game_context')}")
        logger.info(f"   history items: {len(context_pack.get('history') or [])}")
        # --- Stage 4: Dispatch ---
        response, source, override_intent = await self._dispatch(
            router_result.intent, 
            user_input, 
            context_pack
        )
        
        # 如果有 override_intent（如 ERROR），使用它；否則用原本的 intent
        final_intent = override_intent if override_intent else router_result.intent
        
        return PipelineResult(
            response=response,
            intent=final_intent,
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
            # === DEBUG: Router LLM Prompt ===
            logger.info("=" * 50)
            logger.info("🧠 [DEBUG] Router LLM Prompt:")
            logger.info(f"   [System Prompt] (length: {len(system_prompt)} chars):")
            logger.info(f"   {system_prompt[:500]}..." if len(system_prompt) > 500 else f"   {system_prompt}")
            logger.info(f"   [User Input]: {final_input}")
            logger.info("=" * 50)
            
            # 直接使用已經組好的 final_input
            response = await self.local_llm.generate_json(final_input, system_prompt)
            intent = response.get("intent", "UNKNOWN")
            confidence = response.get("confidence", 0.0)
            return RouterResult(intent=intent, confidence=confidence, source="llm")
        except Exception as e:
            logger.error(f"Router LLM Error: {e}")
            return RouterResult(intent="UNKNOWN", confidence=0.0, source="fallback")

    def _load_stt_keywords(self, game_id: str) -> List[str]:
        """
        Load STT keywords for a specific game.

        Args:
            game_id: Game identifier (e.g., "Carcassonne", "Splendor")

        Returns:
            List of STT keywords for the game
        """
        try:
            # Construct file path
            keywords_file = Path(__file__).parent.parent / "data" / "stt_keywords" / f"{game_id}.txt"

            if not keywords_file.exists():
                logger.warning(f"STT keywords file not found: {keywords_file}")
                return []

            # Read keywords (one per line)
            with open(keywords_file, 'r', encoding='utf-8') as f:
                keywords = [line.strip() for line in f if line.strip()]

            logger.info(f"✅ Loaded {len(keywords)} STT keywords for {game_id}")
            return keywords

        except Exception as e:
            logger.error(f"Failed to load STT keywords for {game_id}: {e}")
            return []

    def _extract_recent_context(
        self,
        history: Optional[List[Dict[str, Any]]],
        window: int = 3,
        max_length: int = 80
    ) -> List[str]:
        """
        Extract recent conversation context in format: "INTENT: user_query"

        Args:
            history: Full conversation history
            window: Number of recent turns to extract (default: 3)
            max_length: Maximum length per query (default: 80 chars)

        Returns:
            List of formatted context strings, e.g.:
            ["STORE_SALES: 你們有賣卡坦島嗎", "RULES: 要怎麼買發展卡"]
        """
        if not history:
            return []

        context = []

        # Iterate through history to find assistant messages with intent
        for i, msg in enumerate(history):
            if msg.get("role") == "assistant" and msg.get("intent"):
                # Find the corresponding user query (previous message)
                if i > 0 and history[i-1].get("role") == "user":
                    user_query = history[i-1].get("content", "").strip()
                    intent = msg.get("intent")

                    # Truncate long queries
                    if len(user_query) > max_length:
                        user_query_short = user_query[:max_length] + "..."
                    else:
                        user_query_short = user_query

                    # Format: "INTENT: query"
                    context.append(f"{intent}: {user_query_short}")

        # Return most recent N entries
        return context[-window:]

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

    async def _dispatch(self, intent: str, user_input: str, context: Any = None) -> tuple[str, str, str]:
        """
        Returns: (response, source, override_intent)
        override_intent: None 表示使用原本的 intent, "ERROR" 表示錯誤
        """
        responses_map = self.store_info.get("responses", {})
        
        # 1. Static Responses
        if intent in responses_map:
            candidates = responses_map[intent]
            if candidates: 
                return (random.choice(candidates), "content_static", None)
        
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
                return (resp.content, "local_llm_gen", None)
            elif handler in ["online_llm", "cloud_llm", "cloud_rag"]:
                if self.cloud_llm:
                    return await self._handle_rules_query(user_input, context)
                else:
                    return ("抱歉，雲端大腦連線有點問題，請稍後再試。", "error", "ERROR")
            elif handler == "reject":
                return (logic_config.get("response", "抱歉"), "reject", None)

        # 3. Fallback
        fallback = self.store_info.get("responses", {}).get("UNKNOWN_FALLBACK", ["抱歉？"])
        return (random.choice(fallback), "fallback", None)
    # src/pipeline.py -> class Pipeline

    # [新增] 整個函式
    async def _handle_rules_query(self, user_input: str, context: Dict[str, Any]) -> tuple[str, str]:
        """
        專門處理 RULES 意圖的邏輯函式
        修正重點：將 history 格式化並注入 System Prompt
        """
        # 1. 取得遊戲名稱 & 歷史紀錄
        ctx = context if isinstance(context, dict) else {}
        game_ctx = ctx.get("game_context", {}) or {}
        game_id = game_ctx.get("game_id", "carcassonne") 
        history = ctx.get("history", []) # 取得歷史紀錄 List
        
        # === DEBUG: _handle_rules_query 入口資料 ===
        logger.info("=" * 50)
        logger.info("🔍 [DEBUG] _handle_rules_query() 資料檢查:")
        logger.info(f"   raw context: {ctx}")
        logger.info(f"   game_ctx: {game_ctx}")
        logger.info(f"   game_id (使用中): {game_id}")
        logger.info(f"   history length: {len(history) if history else 0}")
        logger.info("=" * 50)
        
        # 2. 透過 DataManager 取得規則內容
        rule_content = self.data_manager.get_rules(game_id)
        if not rule_content:
            logger.warning(f"Rulebook not found for game_id: {game_id}")
            rule_content = "（系統提示：目前找不到此遊戲的詳細規則資料，請依據您的通用知識回答。）"
        else:
            logger.info(f"✅ [DEBUG] Rulebook loaded for {game_id}, length: {len(rule_content)} chars")

        # 3. 讀取 System Prompt Template
        # 假設 prompts_cloud.yaml 裡有 {INJECTED_RAG_CONTENT} 和 {history} 兩個佔位符
        task_config = self.cloud_prompts.get_task_config("rules_explainer")
        system_template = task_config.get("system_prompt", "")
        
        # 4. [優化] 格式化 History - 只保留 RULES 相關的對話
        history_str = ""
        if history:
            # 過濾：只保留 intent 為 RULES 或 None 的訊息
            # None 的情況是 user 訊息（沒有 intent），但如果前後有 RULES 則保留
            filtered_history = []
            
            for i, msg in enumerate(history):
                intent = msg.get("intent")
                role = msg.get("role")
                
                # 保留條件：
                # 1. assistant 且 intent 是 RULES
                # 2. user 訊息（需要看下一個 assistant 的 intent 是否為 RULES）
                if role == "assistant" and intent == "RULES":
                    # 把前一則 user 訊息也加入（如果還沒加入）
                    if i > 0 and history[i-1].get("role") == "user":
                        prev_msg = history[i-1]
                        if prev_msg not in filtered_history:
                            filtered_history.append(prev_msg)
                    filtered_history.append(msg)
            
            # 格式化
            if filtered_history:
                history_lines = []
                for msg in filtered_history:
                    role = msg.get("role", "unknown")
                    content = msg.get("content", "")
                    history_lines.append(f"{role}: {content}")
                history_str = "\n".join(history_lines)
                logger.info(f"✅ [DEBUG] History filtered (RULES only): {len(filtered_history)} msgs from {len(history)} total")
            else:
                history_str = "(No RULES-related conversation)"
                logger.info("⚠️ [DEBUG] No RULES history found, using empty context")
        else:
            history_str = "(No previous conversation)"
            logger.info("⚠️ [DEBUG] No history provided")

        # 5. 注入變數 (規則 + 歷史)
        # 注意：這裡使用 replace 簡單替換。建議確認 YAML 裡的佔位符名稱是否一致。
        final_system_prompt = (
            system_template
            .replace("{INJECTED_RAG_CONTENT}", rule_content)
            .replace("{history}", history_str) 
        )
        
        # 6. 呼叫雲端大腦
        try:
            # === DEBUG: Cloud LLM Prompt ===
            logger.info("=" * 50)
            logger.info("☁️ [DEBUG] Cloud LLM Prompt:")
            logger.info(f"   [System Prompt] (length: {len(final_system_prompt)} chars)")
            logger.info(f"   --- System Prompt 前 800 字 ---")
            logger.info(final_system_prompt[:800] if len(final_system_prompt) > 800 else final_system_prompt)
            logger.info(f"   --- System Prompt 後 500 字 ---")
            logger.info(final_system_prompt[-500:] if len(final_system_prompt) > 500 else "(同上)")
            logger.info(f"   [User Input]: {user_input}")
            logger.info("=" * 50)
            
            # 呼叫 Cloud LLM
            # user_input 是當前使用者的問題
            raw_response = await self.cloud_llm.generate(
                user_input,
                system_prompt=final_system_prompt
            )
            
            response_text = raw_response.content if hasattr(raw_response, "content") else str(raw_response)
            return (response_text, "cloud_gen", None)  # None = 使用原本 intent
            
        except Exception as e:
            logger.error(f"Cloud Handling Error: {e}")
            return ("抱歉，雲端大腦連線有點問題，請稍後再試。", "error", "ERROR")  # ERROR intent

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