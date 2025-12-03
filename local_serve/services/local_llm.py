import json
import logging
import ollama
from utils.boardgame_utils import ConfigLoader, PromptLoader

logger = logging.getLogger(__name__)

class LocalLLMService:
    def __init__(self, config_path="config/llm_config.json"):
        self.config = ConfigLoader(config_path).load()
        self.prompt_loader = PromptLoader("prompts")
        
        cfg = self.config["model_settings"]
        self.model_name = cfg.get("model_name", "qwen3:4b-instruct")
        self.client = ollama.Client(host=cfg.get("host", "http://localhost:11434"))
        
        logger.info(f"Local LLM Ready: {self.model_name}")

    async def classify(self, user_text, store_info, game_knowledge):
        settings = self.config["router_settings"]
        store_str = json.dumps(store_info, ensure_ascii=False)
        
        try:
            prompt = self.prompt_loader.format(
                settings["prompt_file"],
                STORE_INFO=store_str,
                GAME_KNOWLEDGE=game_knowledge
            )
            res = self._generate(prompt, user_text, settings, json_mode=True)
            return json.loads(res)
        except Exception as e:
            logger.error(f"Router Error: {e}")
            return {"type": "UNKNOWN"}

    async def respond_joker(self, user_text):
        settings = self.config["joker_settings"]
        prompt = self.prompt_loader.load(settings["prompt_file"])
        res = self._generate(prompt, user_text, settings, json_mode=False)
        return {"answer": res, "source": "LOCAL_JOKER"}

    def _generate(self, system, user, settings, json_mode=False):
        try:
            res = self.client.chat(
                model=self.model_name,
                messages=[{'role': 'system', 'content': system}, {'role': 'user', 'content': user}],
                options={'temperature': settings.get('temperature', 0.1)},
                format='json' if json_mode else ''
            )
            return res['message']['content']
        except Exception as e:
            logger.error(f"Ollama Error: {e}")
            return "{}"
