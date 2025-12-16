import json
import logging
import ollama
import asyncio  # <--- 1. 引入 asyncio
from utils.boardgame_utils import ConfigLoader, PromptLoader

logger = logging.getLogger(__name__)

class LocalLLMService:
    def __init__(self, config_path="config/llm_config.json"):
        self.config = ConfigLoader(config_path).load()
        self.prompt_loader = PromptLoader("prompts")
        
        cfg = self.config["model_settings"]
        self.model_name = cfg.get("model_name", "qwen3:4b-instruct")
        self.client = ollama.Client(host=cfg.get("host", "http://localhost:11434"))
        
        # 2. 建立一把鎖，保護 Ollama 不被同時呼叫
        self.lock = asyncio.Lock()
        
        logger.info(f"Local LLM Ready: {self.model_name}")

    async def classify(self, user_text, store_info, game_knowledge):
        settings = self.config["router_settings"]
        store_str = json.dumps(store_info, ensure_ascii=False)
        
        prompt = self.prompt_loader.format(
            settings["prompt_file"],
            STORE_INFO=store_str,
            GAME_KNOWLEDGE=game_knowledge
        )
        
        # 3. 使用 async with self.lock 進行排隊
        async with self.lock:
            res = await self._generate_async(prompt, user_text, settings, json_mode=True)
            
        try:
            return json.loads(res)
        except:
            return {"type": "UNKNOWN"}

    async def respond_joker(self, user_text):
        settings = self.config["joker_settings"]
        prompt = self.prompt_loader.load(settings["prompt_file"])
        
        # 3. 使用 async with self.lock 進行排隊
        async with self.lock:
            res = await self._generate_async(prompt, user_text, settings, json_mode=False)
            
        return {"answer": res, "source": "LOCAL_JOKER"}

    # 4. 改寫為非同步呼叫 (使用 run_in_executor)
    # 因為 ollama.Client 是同步的，直接呼叫會卡住整個 Event Loop
    async def _generate_async(self, system, user, settings, json_mode=False):
        loop = asyncio.get_running_loop()
        
        def sync_call():
            try:
                # 這裡是原本的同步呼叫邏輯
                response = self.client.chat(
                    model=self.model_name,
                    messages=[{'role': 'system', 'content': system}, {'role': 'user', 'content': user}],
                    options={'temperature': settings.get('temperature', 0.1)},
                    format='json' if json_mode else ''
                )
                return response['message']['content']
            except Exception as e:
                logger.error(f"Ollama Error: {e}")
                return "{}"

        # 讓同步程式碼在 ThreadPool 中執行，避免卡住主執行緒
        return await loop.run_in_executor(None, sync_call)