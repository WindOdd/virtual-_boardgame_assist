import os
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
