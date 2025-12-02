"""
Gemini RAG 服務 - 遊戲規則查詢
使用新版 Google Gen AI SDK (google-genai)
"""

import os
import json
import logging
from typing import List, Dict, Optional
from pathlib import Path

# 使用新版 Google Gen AI SDK
from google import genai
from google.genai import types

# 使用共用工具庫
from localllm_serve.utils.boardgame_utils import ConfigLoader, PromptLoader, ConfigValidator

logger = logging.getLogger(__name__)


# ==================== Prompt 載入器 ====================

# 已移除，使用共用工具庫的 PromptLoader


# ==================== 規則書載入器 ====================

class RulesLoader:
    """遊戲規則載入器"""
    
    def __init__(self, rules_dir: str = "./rules"):
        """
        初始化
        
        Args:
            rules_dir: 規則文件目錄
        """
        self.rules_dir = Path(rules_dir)
        self.cache = {}
        self.index = None
        
        if not self.rules_dir.exists():
            logger.warning(f"⚠️ 規則目錄不存在: {self.rules_dir}")
            self.rules_dir.mkdir(parents=True, exist_ok=True)
    
    def load_index(self) -> Dict:
        """載入遊戲索引"""
        if self.index:
            return self.index
        
        index_file = self.rules_dir / "_index.json"
        
        if not index_file.exists():
            logger.warning(f"⚠️ 規則索引不存在: {index_file}")
            return {"games": {}}
        
        with open(index_file, 'r', encoding='utf-8') as f:
            self.index = json.load(f)
        
        logger.info(f"📚 載入規則索引: {len(self.index.get('games', {}))} 個遊戲")
        return self.index
    
    def find_game(self, game_name: str) -> Optional[Dict]:
        """
        查找遊戲資訊
        
        Args:
            game_name: 遊戲名稱或別名
            
        Returns:
            遊戲資訊 dict 或 None
        """
        index = self.load_index()
        
        for name, info in index.get('games', {}).items():
            # 精確匹配或別名匹配
            if name == game_name or game_name in info.get('aliases', []):
                return {**info, "canonical_name": name}
        
        return None
    
    def load_rules(self, game_name: str) -> str:
        """
        載入遊戲規則（包含FAQ）
        
        Args:
            game_name: 遊戲名稱
            
        Returns:
            規則內容 (Markdown，包含FAQ)
        """
        # 檢查快取
        if game_name in self.cache:
            logger.debug(f"📦 使用快取規則: {game_name}")
            return self.cache[game_name]
        
        # 查找遊戲
        game_info = self.find_game(game_name)
        if not game_info:
            raise ValueError(f"找不到遊戲: {game_name}")
        
        # 載入規則文件
        rules_file = self.rules_dir / game_info['file']
        
        if not rules_file.exists():
            raise FileNotFoundError(f"規則文件不存在: {rules_file}")
        
        with open(rules_file, 'r', encoding='utf-8') as f:
            rules_content = f.read()
        
        # 快取
        self.cache[game_name] = rules_content
        logger.info(f"📄 載入規則: {game_info['canonical_name']} ({len(rules_content)} 字元)")
        
        return rules_content
    
    def list_games(self) -> List[Dict]:
        """列出所有遊戲"""
        index = self.load_index()
        return [
            {
                "name": name,
                **info
            }
            for name, info in index.get('games', {}).items()
        ]
    
    def reload_all(self):
        """重新載入所有規則"""
        self.cache.clear()
        self.index = None
        logger.info("🔄 已清空規則快取")


# ==================== Prompt 構建器 ====================

class PromptBuilder:
    """Prompt 組裝器"""
    
    def __init__(self, prompt_loader: PromptLoader):
        """
        初始化
        
        Args:
            prompt_loader: 共用工具庫的 PromptLoader 實例
        """
        self.prompt_loader = prompt_loader
    
    def build(
        self,
        game_name: str,
        rules_content: str,
        user_question: str,
        history: Optional[List[Dict]] = None
    ) -> str:
        """
        組裝完整 Prompt
        
        Args:
            game_name: 遊戲名稱
            rules_content: 規則內容（包含FAQ）
            user_question: 用戶問題
            history: 對話歷史 [{"user": "...", "assistant": "..."}, ...]
            
        Returns:
            完整 Prompt
        """
        parts = []
        
        # 1. 系統角色 (從 system_role.txt 載入)
        try:
            system_role = self.prompt_loader.load("system_role", use_cache=True)
            parts.append(system_role)
            parts.append("\n" + "="*80 + "\n")
        except FileNotFoundError:
            logger.warning("⚠️ system_role.txt 不存在,跳過")
        
        # 2. Few-shot 範例 (從 few_shot_examples.txt 載入)
        try:
            examples = self.prompt_loader.load("few_shot_examples", use_cache=True)
            parts.append(examples)
            parts.append("\n" + "="*80 + "\n")
        except FileNotFoundError:
            logger.warning("⚠️ few_shot_examples.txt 不存在,跳過")
        
        # 3. 遊戲資訊與規則
        parts.append(f"## 當前遊戲\n\n你現在要回答的是關於 {game_name} 的問題。\n\n")
        parts.append("="*80 + "\n\n")
        parts.append(f"## 遊戲規則說明書\n\n以下是 {game_name} 的完整規則（包含常見問題FAQ）：\n\n")
        parts.append(rules_content)
        parts.append("\n\n" + "="*80 + "\n\n")
        
        # 4. 對話歷史 (如果有)
        if history and len(history) > 0:
            parts.append("## 對話歷史\n\n以下是最近的對話記錄：\n\n")
            
            for i, turn in enumerate(history[-6:], 1):
                parts.append(f"輪次 {i}\n")
                parts.append(f"玩家: {turn['user']}\n")
                parts.append(f"遊俠: {turn['assistant']}\n\n")
            
            parts.append("="*80 + "\n\n")
        
        # 5. 當前問題
        parts.append(f"## 當前問題\n\n{user_question}\n\n")
        parts.append("---\n\n")
        parts.append("請根據上述規則說明書回答這個問題。如果FAQ中有相關問題，可以參考。記得遵循核心原則和格式要求，特別是字數限制！\n")
        
        return "".join(parts)


# ==================== Gemini RAG 服務 ====================

class GeminiRAGService:
    """Gemini 規則查詢服務"""
    
    def __init__(
        self,
        api_key: str,
        rules_dir: str = "./rules",
        prompts_dir: str = "./prompts",
        config_file: str = "config/gemini_config.yaml"
    ):
        """
        初始化服務
        
        Args:
            api_key: Gemini API Key
            rules_dir: 規則文件目錄
            prompts_dir: Prompt 模板目錄
            config_file: Gemini 配置檔路徑
        """
        # 載入 Gemini 配置（使用共用工具庫）
        self.config_loader = ConfigLoader(config_file)
        config = self.config_loader.load()
        
        # 驗證配置
        ConfigValidator.validate_llm_config(config)
        
        # 使用新版 SDK 創建 Client
        self.client = genai.Client(api_key=api_key)
        
        # 保存配置供後續使用
        self.model_name = config['model_name']
        self.generation_config = config['generation_config']
        
        # 初始化載入器（使用共用工具庫的 PromptLoader）
        self.rules_loader = RulesLoader(rules_dir)
        self.prompt_loader = PromptLoader(prompts_dir)
        self.prompt_builder = PromptBuilder(self.prompt_loader)
        
        logger.info(f"✅ Gemini RAG 服務初始化完成 (新版 SDK)")
        logger.info(f"   - 模型: {self.model_name}")
        logger.info(f"   - Temperature: {self.generation_config['temperature']}")
        logger.info(f"   - 規則目錄: {rules_dir}")
        logger.info(f"   - Prompt 目錄: {prompts_dir}")
        logger.info(f"   - 配置檔: {config_file}")
    
    async def query(
        self,
        game_name: str,
        user_question: str,
        history: Optional[List[Dict]] = None
    ) -> Dict:
        """
        查詢遊戲規則
        
        Args:
            game_name: 遊戲名稱
            user_question: 用戶問題
            history: 對話歷史
            
        Returns:
            {
                "answer": str,
                "confidence": float
            }
        """
        try:
            # 1. 載入規則（包含FAQ）
            rules_content = self.rules_loader.load_rules(game_name)
            
            # 2. 構建 Prompt
            prompt = self.prompt_builder.build(
                game_name=game_name,
                rules_content=rules_content,
                user_question=user_question,
                history=history
            )
            
            logger.info(f"📝 Prompt 長度: {len(prompt)} 字元")
            
            # 3. 調用 Gemini
            response = await self._call_gemini(prompt)
            
            # 4. 解析回應
            answer = response.text.strip()
            
            logger.info(f"✅ Gemini 回應完成")
            
            return {
                "answer": answer,
                "confidence": 0.85
            }
            
        except Exception as e:
            logger.error(f"❌ Gemini 查詢失敗: {e}")
            raise
    
    async def _call_gemini(self, prompt: str):
        """調用 Gemini API"""
        import asyncio
        
        def sync_call():
            return self.model.generate_content(prompt)
        
        response = await asyncio.to_thread(sync_call)
        return response
    
    def reload_config(self):
        """重新載入 Gemini 配置（開發時使用）"""
        config = self.config_loader.reload()
        
        # 驗證配置
        ConfigValidator.validate_llm_config(config)
        
        # 更新配置
        self.model_name = config['model_name']
        self.generation_config = config['generation_config']
        
        logger.info("🔄 Gemini 配置已重新載入")
        logger.info(f"   - Model: {self.model_name}")
        logger.info(f"   - Temperature: {self.generation_config['temperature']}")
    
    def reload_prompts(self):
        """重新載入 Prompt (開發時使用)"""
        self.prompt_loader.reload()  # 使用共用工具庫的 reload 方法
        logger.info("🔄 Prompt 已重新載入")
    
    def reload_rules(self):
        """重新載入規則 (開發時使用)"""
        self.rules_loader.reload_all()
        logger.info("🔄 規則已重新載入")
    
    def list_available_games(self) -> List[Dict]:
        """列出可用遊戲"""
        return self.rules_loader.list_games()


# ==================== 使用範例 ====================

async def example_usage():
    """使用範例"""
    
    # 初始化服務
    api_key = os.getenv("GEMINI_API_KEY", "your-api-key-here")
    rag_service = GeminiRAGService(
        api_key=api_key,
        rules_dir="./rules",
        prompts_dir="./prompts"
    )
    
    # 列出可用遊戲
    games = rag_service.list_available_games()
    print(f"可用遊戲: {[g['name'] for g in games]}")
    
    # 查詢規則
    result = await rag_service.query(
        game_name="阿瓦隆",
        user_question="梅林的能力是什麼?"
    )
    
    print(f"\n回答:\n{result['answer']}")


if __name__ == "__main__":
    import asyncio
    
    logging.basicConfig(level=logging.INFO)
    asyncio.run(example_usage())