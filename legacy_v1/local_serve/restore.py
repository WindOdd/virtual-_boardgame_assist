import os
import json

# 定義專案根目錄名稱
BASE_DIR = "local_serve"

# 定義檔案內容 (根據 v4.3 技術規格書 & 您上傳的檔案整合)

FILES = {
    # ==================== Config ====================
    "config/safety_filter.yaml": """settings:
  enable_filter: true

allowlist:
  - 阿瓦隆
  - 刺客
  - 殺手
  - 革命
  - 審判
  - 戰爭
  - 冷戰熱鬥
  - 美麗島風雲
  - 台北大空襲
  - 秘密希特勒
  - 社會主義

blocklist:
  - 總統
  - 選舉
  - 政黨
  - 民進黨
  - 國民黨
  - 民眾黨
  - 共產黨
  - 習近平
  - 賴清德
  - 川普
  - 拜登
  - 台獨
  - 統一
  - 兩岸
  - 政治
  - 髒話
""",

    "config/store_info.json": """{
  "wifi": {
    "ssid": "BoardGame_Guest",
    "password": "playmoregames"
  },
  "facility": {
    "toilet": "櫃台左手邊直走到底",
    "water": "飲水機在廁所門口，提供冷熱水",
    "ac": "冷氣遙控器在牆上，請維持 26 度"
  },
  "business": {
    "hours": "平日 13:00-22:00，假日 10:00-23:00",
    "price": "入場費平日 150元/4小時，假日 200元/4小時",
    "min_charge": "每人低消一杯飲料或入場費"
  }
}""",

    "config/llm_config.json": """{
  "model_settings": {
    "model_name": "qwen3:4b-instruct",
    "host": "http://localhost:11434"
  },
  "router_settings": {
    "prompt_file": "prompt_router",
    "temperature": 0.1,
    "top_p": 0.9
  },
  "joker_settings": {
    "prompt_file": "prompt_joker",
    "temperature": 0.8,
    "top_p": 0.95
  }
}""",

    "config/gemini_config.yaml": """model_name: "gemini-2.5-flash"
generation_config:
  temperature: 0.5
  top_p: 0.95
  max_output_tokens: 1024
system_prompt_file: "system_role"
""",

    # ==================== Prompts ====================
    "prompts/prompt_router.txt": """你是一個分類器。請根據以下店務資訊與用戶輸入，輸出 JSON。

[店務資訊]
{STORE_INFO}

[桌遊知識庫]
{GAME_KNOWLEDGE}

[分類規則]
1. GAME (桌遊相關) -> {{"type": "GAME"}}
   - 包含：規則、計分、玩法、策略、庫存查詢。
   - 包含：任何提及[桌遊知識庫]中關鍵字的問題。
2. STORE (店務設施) -> {{"type": "STORE", "content": "回答內容"}}
   - 包含：Wifi、廁所、開水、價格、營業時間。
3. POLITICAL (政治敏感) -> {{"type": "POLITICAL"}}
4. UNKNOWN (其他閒聊) -> {{"type": "UNKNOWN"}}

[輸出要求]
只輸出 JSON，不要 Markdown，不要解釋。
""",

    "prompts/prompt_joker.txt": """你是一個幽默的桌遊店員阿凱。
請用繁體中文簡短回應客人的閒聊。
""",

    "prompts/system_role.txt": """你是一位專業的桌遊教學員。請根據以下提供的【遊戲規則】與【對話歷史】來回答用戶的問題。

[角色設定]
- 親切、有耐心，解釋清晰。
- 如果用戶問的問題在【遊戲規則】裡找不到答案，請回答：「這部分規則書沒有提到，可能需要查閱更詳細的 FAQ 或玩家社群討論喔。」
- 請用繁體中文回答。

[遊戲規則]
{RULES}

[對話歷史]
{HISTORY}

[用戶問題]
{USER_QUESTION}
""",

    # ==================== Rules ====================
    "rules/_index.yaml": """- id: avalon
  name: 阿瓦隆
  filename: avalon.md
  enabled: true
  aliases:
    - Avalon
    - 抵抗組織
    - 阿瓦隆
  keywords:
    - 梅林
    - 刺客
    - 派西維爾
    - 莫甘娜
    - 奧伯倫
    - 湖中女神
    - 任務
    - 壞人

- id: carcassonne
  name: 卡卡頌
  filename: carcassonne.md
  enabled: true
  aliases:
    - Carcassonne
    - 卡卡送
  keywords:
    - 米寶
    - 板塊
    - 修道院
    - 農夫
    - 城堡
    - 道路
    - 草原
    - 主教
    - 計分
""",

    "rules/avalon.md": """# 阿瓦隆 (The Resistance: Avalon)

## 核心目標
正義方（藍色）的目標是成功完成三個任務。
邪惡方（紅色）的目標是讓三個任務失敗，或是刺殺梅林。

## 角色能力
- **梅林 (Merlin)**：正義方。遊戲開始時知道誰是壞人（除了莫德雷德）。必須隱藏身分，因為如果被刺客發現，好人就輸了。
- **刺客 (Assassin)**：邪惡方。在遊戲結束若正義方獲勝，刺客有一次機會猜測誰是梅林，猜對則邪惡方反敗為勝。
- **派西維爾 (Percival)**：正義方。知道誰是梅林（但不知道是否是莫甘娜假扮的）。用來保護梅林。
- **莫甘娜 (Morgana)**：邪惡方。假扮梅林，混淆派西維爾。
- **奧伯倫 (Oberon)**：邪惡方。但不知道隊友是誰，隊友也不知道他是誰。

## 遊戲流程
1. 選出隊長。
2. 隊長指派隊員出任務。
3. 全體投票決定是否同意這個隊伍。
4. 若通過，出任務的隊員秘密投「成功」或「失敗」。
5. 結算任務結果。
""",

    "rules/carcassonne.md": """# 卡卡頌 (Carcassonne)

## 核心規則
每次輪到你時，抽一片版圖，將其拼入地圖中。版圖必須與相鄰的版圖地形吻合（路接路、城接城）。

## 米寶 (Meeple) 放置
拼放版圖後，你可以選擇放一個米寶在該版圖的某個特徵上：
- **騎士**：放在城堡。
- **強盜**：放在道路。
- **修道士**：放在修道院。
- **農夫**：放在草原（躺著）。

## 計分
- **城堡**：完成時，每片版圖 2 分，每個盾牌 2 分。
- **道路**：完成時，每片版圖 1 分。
- **修道院**：九宮格填滿時，得 9 分。
- **農夫**：遊戲結束才計分。每個被草原「供應」的完成城堡得 3 分。
""",

    # ==================== Services ====================
    "services/__init__.py": "",

    "services/discovery.py": """import socket
import threading
import json
import logging

logger = logging.getLogger(__name__)

class DiscoveryService:
    def __init__(self, port=37020, api_port=8000):
        self.port = port
        self.api_port = api_port
        self.running = False
        self.sock = None

    def start(self):
        self.running = True
        threading.Thread(target=self._listen_loop, daemon=True).start()
        logger.info(f"📡 UDP Discovery 啟動 (Port: {self.port})")

    def stop(self):
        self.running = False
        if self.sock:
            self.sock.close()

    def _get_local_ip(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"

    def _listen_loop(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.sock.bind(("", self.port))
            
            while self.running:
                try:
                    data, addr = self.sock.recvfrom(1024)
                    if data.decode().strip() == "DISCOVER_BOARDGAME_SERVER":
                        response = {
                            "server_ip": self._get_local_ip(),
                            "port": self.api_port,
                            "history_length": 8,
                            "server_version": "4.3.0",
                            "available_games": [
                                {"id": "avalon", "name": "阿瓦隆"},
                                {"id": "carcassonne", "name": "卡卡頌"}
                            ]
                        }
                        self.sock.sendto(json.dumps(response).encode(), addr)
                except OSError:
                    break
                except Exception as e:
                    logger.error(f"UDP Loop Error: {e}")
        except Exception as e:
            logger.error(f"UDP Bind Error: {e}")
""",

    "services/filter.py": """import os
import logging
from utils.boardgame_utils import ConfigLoader

logger = logging.getLogger(__name__)

class FilterService:
    def __init__(self, config_path="config/safety_filter.yaml"):
        self.loader = ConfigLoader(config_path)
        self.reload()

    def reload(self):
        cfg = self.loader.load()
        self.enabled = cfg.get("settings", {}).get("enable_filter", True)
        self.allowlist = cfg.get("allowlist", [])
        self.blocklist = cfg.get("blocklist", [])
        logger.info(f"🛡️ 過濾器: {self.enabled} (白:{len(self.allowlist)}, 黑:{len(self.blocklist)})")

    def check(self, text, category=None, game_name=None):
        if not self.enabled: return None

        # 1. 寬鬆模式 (GAME 類別優先檢查白名單)
        if category == "GAME":
            for w in self.allowlist:
                if w in text: return None

        # 2. 嚴格模式 (檢查黑名單)
        for w in self.blocklist:
            if w in text:
                return {
                    "answer": "抱歉，我們不討論政治或敏感議題喔！",
                    "source": "FILTER",
                    "category": "POLITICAL"
                }
        return None
""",

    "services/game_data.py": """import logging
from utils.boardgame_utils import ConfigLoader

logger = logging.getLogger(__name__)

class GameDataService:
    def __init__(self, index_path="rules/_index.yaml"):
        self.loader = ConfigLoader(index_path)
        self.games = []
        self.reload()

    def reload(self):
        self.games = self.loader.load()
        logger.info(f"📚 載入 {len(self.games)} 款遊戲資料")

    def get_knowledge_str(self):
        lines = []
        for g in self.games:
            if g.get("enabled", True):
                kws = ", ".join(g.get("keywords", []) + g.get("aliases", []))
                lines.append(f"- {g['name']} (關鍵字: {kws})")
        return "\\n".join(lines)

    def get_game_by_name(self, name):
        if not name: return None
        for g in self.games:
            if name == g["name"] or name in g.get("aliases", []):
                return g
        return None
    
    def detect_game_name(self, text):
        for g in self.games:
            for kw in g.get("keywords", []):
                if kw in text:
                    return g["name"]
        return None
""",

    "services/local_llm.py": """import json
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
""",

    "services/gemini_rag.py": """import logging
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
""",

    # ==================== Utils ====================
    "utils/__init__.py": "",
    
    "utils/boardgame_utils.py": """import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Union
import yaml

logger = logging.getLogger(__name__)

class ConfigLoader:
    def __init__(self, config_file: Union[str, Path]):
        self.config_file = Path(config_file)
        self.config = None

    def load(self) -> Dict[str, Any]:
        if not self.config_file.exists():
            raise FileNotFoundError(f"Config not found: {self.config_file}")
        
        with open(self.config_file, 'r', encoding='utf-8') as f:
            if self.config_file.suffix in ['.yaml', '.yml']:
                self.config = yaml.safe_load(f)
            else:
                self.config = json.load(f)
        return self.config

class PromptLoader:
    def __init__(self, prompts_dir: Union[str, Path]):
        self.prompts_dir = Path(prompts_dir)
        self.cache = {}

    def load(self, prompt_name: str) -> str:
        if prompt_name in self.cache: return self.cache[prompt_name]
        
        fpath = self.prompts_dir / f"{prompt_name}.txt"
        if not fpath.exists(): raise FileNotFoundError(f"Prompt not found: {prompt_name}")
        
        with open(fpath, 'r', encoding='utf-8') as f:
            content = f.read()
        self.cache[prompt_name] = content
        return content

    def format(self, prompt_name: str, **kwargs) -> str:
        template = self.load(prompt_name)
        return template.format(**kwargs)
""",

    # ==================== Root ====================
    "requirements.txt": """fastapi
uvicorn
requests
pydantic
PyYAML
ollama
google-genai
""",

    "server.py": """import os
import logging
from typing import List, Optional, Dict, Any
from fastapi import FastAPI
from pydantic import BaseModel

from services.discovery import DiscoveryService
from services.filter import FilterService
from services.game_data import GameDataService
from services.local_llm import LocalLLMService
from services.gemini_rag import GeminiRAGService
from utils.boardgame_utils import ConfigLoader

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("Server")

app = FastAPI(title="Board Game Assistant v4.3")
services = {}
store_info = {}

class AskRequest(BaseModel):
    table_id: str
    session_id: str
    game_name: Optional[str] = None
    user_text: str
    history: List[Dict[str, str]] = []

class AskResponse(BaseModel):
    answer: str
    source: str
    category: str
    hint: Optional[str] = None
    error: Optional[Dict[str, str]] = None

@app.on_event("startup")
async def startup():
    global store_info
    logger.info("🚀 Server Starting...")
    try:
        store_info = ConfigLoader("config/store_info.json").load()
    except:
        store_info = {}

    services["game_data"] = GameDataService("rules/_index.yaml")
    services["filter"] = FilterService("config/safety_filter.yaml")
    services["local_llm"] = LocalLLMService("config/llm_config.json")
    
    if os.getenv("GEMINI_API_KEY"):
        services["gemini"] = GeminiRAGService(os.getenv("GEMINI_API_KEY"), "config/gemini_config.yaml")
    else:
        logger.warning("⚠️ No GEMINI_API_KEY found")

    services["discovery"] = DiscoveryService(port=37020, api_port=8000)
    services["discovery"].start()

@app.on_event("shutdown")
async def shutdown():
    if "discovery" in services:
        services["discovery"].stop()

@app.post("/ask", response_model=AskResponse)
async def ask(req: AskRequest):
    user_text = req.user_text
    
    # 1. Router
    kb_str = services["game_data"].get_knowledge_str()
    router_res = await services["local_llm"].classify(user_text, store_info, kb_str)
    category = router_res.get("type", "UNKNOWN")
    
    # 2. Filter
    filter_res = services["filter"].check(user_text, category, req.game_name)
    if filter_res:
        return AskResponse(**filter_res)

    # 3. Logic Dispatch
    if category == "GAME":
        if "gemini" not in services:
            return AskResponse(answer="雲端未連線", source="SYSTEM", category="GAME", error={"code": "NO_API"})
            
        target_game = services["game_data"].get_game_by_name(req.game_name)
        hint = None
        
        if not target_game:
            detected = services["game_data"].detect_game_name(user_text)
            if detected:
                hint = f"建議選擇遊戲：{detected}"
        
        fname = target_game["filename"] if target_game else None
        gname = target_game["name"] if target_game else "通用"
        
        res = await services["gemini"].query(user_text, fname, gname, req.history)
        return AskResponse(answer=res["answer"], source=res["source"], category="GAME", hint=hint)

    elif category == "STORE":
        return AskResponse(answer=router_res.get("content"), source="LOCAL_STORE", category="STORE")
    
    elif category == "POLITICAL":
        return AskResponse(answer="不談政治", source="FILTER", category="POLITICAL")
        
    else:
        res = await services["local_llm"].respond_joker(user_text)
        return AskResponse(answer=res["answer"], source="LOCAL_JOKER", category="UNKNOWN")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
"""
}

def restore():
    print(f"🚀 開始還原專案至 {BASE_DIR}...")
    
    if not os.path.exists(BASE_DIR):
        os.makedirs(BASE_DIR)
        
    for path, content in FILES.items():
        full_path = os.path.join(BASE_DIR, path)
        # 確保目錄存在
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        
        # 寫入檔案
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"✅ 還原: {path}")
        
    print("\n✨ 還原完成！請執行以下指令開始測試：")
    print(f"cd {BASE_DIR}")
    print("pip install -r requirements.txt")
    print("export GEMINI_API_KEY='你的KEY'")
    print("python server.py")

if __name__ == "__main__":
    restore()