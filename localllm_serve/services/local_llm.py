import sys
import os
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)
import json
import logging
import ollama
from utils.boardgame_utils import ConfigLoader, PromptLoader

logger = logging.getLogger(__name__)

class LocalLLMService:
    def __init__(self, config_path: str = "config/llm_config.json", prompts_dir: str = "prompts"):
        """
        初始化 Local LLM 服務 (Ollama 版本)
        """
        # 1. 載入設定
        self.config_loader = ConfigLoader(config_path)
        self.config = self.config_loader.load()
        self.prompt_loader = PromptLoader(prompts_dir)
        
        # 2. 設定 Ollama Client
        model_cfg = self.config["model_settings"]
        self.model_name = model_cfg.get("model_name", "qwen2.5:3b")
        self.host = model_cfg.get("host", "http://localhost:11434")
        
        try:
            self.client = ollama.Client(host=self.host)
            # 測試連線 (非必要，但建議)
            self.client.list() 
            logger.info(f"Ollama 連線成功 | Host: {self.host} | Model: {self.model_name}")
        except Exception as e:
            logger.error(f"⚠️ 無法連線至 Ollama: {e}")
            raise ConnectionError("Ollama 服務未啟動或連線失敗")

    def _generate(self, system_prompt: str, user_text: str, settings: dict, json_mode: bool = False) -> str:
        """
        呼叫 Ollama API 進行生成
        """
        messages = [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_text},
        ]

        options = {
            'temperature': settings.get('temperature', 0.7),
            'top_p': settings.get('top_p', 0.9),
        }

        try:
            response = self.client.chat(
                model=self.model_name,
                messages=messages,
                options=options,
                format='json' if json_mode else '', # 關鍵：Ollama 原生支援 JSON 模式
            )
            return response['message']['content']
        except Exception as e:
            logger.error(f"Ollama 生成失敗: {e}")
            return ""

    async def classify(self, user_text: str, store_info: dict) -> dict:
        """
        [Router 模式] 判斷用戶意圖
        """
        settings = self.config["router_settings"]
        
        # 準備 Prompt (注入店務資訊)
        store_info_str = json.dumps(store_info, ensure_ascii=False, indent=2)
        try:
            system_prompt = self.prompt_loader.format(
                settings["prompt_file"], 
                STORE_INFO=store_info_str
            )
        except Exception as e:
            logger.error(f"Router Prompt 載入失敗: {e}")
            return {"type": "UNKNOWN"}

        # 呼叫 Ollama (開啟 json_mode)
        raw_response = self._generate(system_prompt, user_text, settings, json_mode=True)
        
        try:
            return json.loads(raw_response)
        except json.JSONDecodeError:
            logger.warning(f"JSON 解析失敗: {raw_response}")
            return {"type": "UNKNOWN"}

    async def respond_joker(self, user_text: str, history: list = None) -> dict:
        """
        [Joker 模式] 閒聊回應
        """
        settings = self.config["joker_settings"]
        
        try:
            system_prompt = self.prompt_loader.format(
                settings["prompt_file"],
                user_text=user_text
            )
        except Exception:
            system_prompt = "你是幽默的店員。"

        # 呼叫 Ollama (一般模式)
        answer = self._generate(system_prompt, user_text, settings, json_mode=False)
        
        return {
            "answer": answer,
            "source": "LOCAL_JOKER"
        }