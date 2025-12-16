import logging
from pathlib import Path
from google import genai
from utils.boardgame_utils import ConfigLoader, PromptLoader

logger = logging.getLogger(__name__)

class GeminiRAGService:
    def __init__(self, api_key: str, config_path="config/gemini_config.yaml"):
        self.client = genai.Client(api_key=api_key)
        self.config = ConfigLoader(config_path).load()
        self.prompt_loader = PromptLoader("prompts")
        self.rules_dir = Path("rules")
        logger.info("Gemini RAG Service Ready")

    async def query(self, user_text, rule_filename, game_name, history=[]):
        # 1. 讀取規則
        if rule_filename:
            try:
                with open(self.rules_dir / rule_filename, "r", encoding="utf-8") as f:
                    rule_content = f.read()
            except:
                rule_content = "(找不到規則文件)"
        else:
            rule_content = "(未指定規則，請使用通用知識)"

        # 2. 組合 Prompt
        prompt = self.prompt_loader.format(
            self.config["system_prompt_file"],
            RULES=rule_content,
            HISTORY=str(history),
            USER_QUESTION=user_text
        )

        # 3. 呼叫 API
        try:
            res = await self.client.aio.models.generate_content(
                model=self.config.get("model_name", "gemini-2.5-flash"),
                contents=prompt
            )
            return {"answer": res.text, "source": "CLOUD_GEMINI"}
        except Exception as e:
            logger.error(f"Gemini API Error: {e}")
            return {"answer": "雲端連線失敗", "source": "ERROR"}
