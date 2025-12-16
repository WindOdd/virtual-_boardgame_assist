import logging
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
        return "\n".join(lines)

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
