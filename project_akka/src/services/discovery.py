"""
Project Akka - UDP Discovery Service
Allows clients (iPad) to automatically find the Jetson server IP.
Reads configuration from system_config.yaml.

[Fixes applied for Jetson/Docker/Tailscale environment]:
1. Binds to 0.0.0.0 instead of empty string.
2. Sets SO_BROADCAST option explicitly.
"""
import socket
import threading
import json
import logging
import sys
from pathlib import Path
from typing import Optional

# --- Import ConfigLoader ---
# 處理不同執行情境下的 Import 路徑問題
try:
    # 情境 1: 從 src/main.py 啟動 (src 在 Python Path 中)
    from boardgame_utils import ConfigLoader
except ImportError:
    try:
        # 情境 2: 直接執行 src/services/discovery.py (需手動加入 src 到 Path)
        sys.path.append(str(Path(__file__).parent.parent))
        from boardgame_utils import ConfigLoader
    except ImportError:
        # Fallback: 若真的找不到，稍後會用預設值
        ConfigLoader = None

logger = logging.getLogger(__name__)

class DiscoveryService:
    def __init__(self, config_path: Optional[Path] = None):
        # 1. 決定設定檔路徑 (預設為 project_akka/config/system_config.yaml)
        if config_path:
            self.config_path = config_path
        else:
            # __file__ = src/services/discovery.py
            # parent.parent.parent = project_akka 根目錄
            self.config_path = Path(__file__).parent.parent.parent / "config" / "system_config.yaml"

        # 2. 讀取設定 (Load Config)
        self.udp_config = {}
        self.server_config = {}
        
        if ConfigLoader and self.config_path.exists():
            try:
                full_config = ConfigLoader(self.config_path).load()
                self.udp_config = full_config.get("udp_service", {})
                self.server_config = full_config.get("server", {})
                logger.info(f"🔧 Discovery Service config loaded from {self.config_path}")
            except Exception as e:
                logger.error(f"Failed to load system_config.yaml: {e}")
        else:
            logger.warning("ConfigLoader not available or config file missing. Using defaults.")

        # 3. 設定參數 (優先使用設定檔，否則使用預設值)
        # UDP 監聽 Port
        self.port = self.udp_config.get("port", 37020)
        # 通關密語 (Magic String)
        self.magic_string = self.udp_config.get("magic_string", "DISCOVER_AKKA_SERVER")
        # 回傳給 Client 的 API Server Port
        self.api_port = self.server_config.get("port", 8000)

        self.running = False
        self.sock = None

    def start(self):
        """啟動 UDP 監聽執行緒"""
        self.running = True
        # 使用 daemon=True 確保主程式結束時，這個執行緒也會自動結束
        threading.Thread(target=self._listen_loop, daemon=True).start()
        logger.info(f"📡 UDP Discovery Service Started on Port {self.port} (Magic: {self.magic_string})")

    def stop(self):
        """停止服務並關閉 Socket"""
        self.running = False
        if self.sock:
            # 關閉 Socket 以中斷 recvfrom 的阻塞
            try:
                self.sock.close()
            except:
                pass

    def _get_local_ip(self):
        """取得本機在區網中的真實 IP (而非 127.0.0.1)"""
        try:
            # 建立一個測試連線到 Google DNS (不會真的發送數據)
            # 這能讓 OS 告訴我們如果要連外網，會走哪個 IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"

    def _listen_loop(self):
        """持續監聽 UDP 廣播封包"""
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            
            # [Fix 1] 允許 Port 重複使用 (避免重啟時報錯 Address already in use)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            
            # [Fix 2] 明確允許廣播 (Broadcast)
            # 這對某些 Linux 發行版在處理 255.255.255.255 時非常重要
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            
            # [Fix 3] 明確綁定 0.0.0.0
            # 確保監聽所有網卡 (eth0, wlan0, docker0, tailscale0...)
            # 之前綁定 "" 有時在複雜網路環境下會有問題
            self.sock.bind(("0.0.0.0", self.port))
            
            logger.info(f"🎧 Listening for UDP broadcast on 0.0.0.0:{self.port}")
            
            while self.running:
                try:
                    # 接收數據 (Buffer size 1024 bytes)
                    data, addr = self.sock.recvfrom(1024)
                    msg = data.decode().strip()
                    
                    # 驗證 Magic String
                    if self.magic_string in msg:
                        # 回傳 Server 資訊
                        response = {
                            "ip": self._get_local_ip(),
                            "port": self.api_port,
                            "status": "ready"
                        }
                        # 將 JSON 回傳給來源 IP (addr)
                        self.sock.sendto(json.dumps(response).encode(), addr)
                        # [Log] 改為 info 等級以便除錯，確認有收到並回傳
                        logger.info(f"📡 Replying to discovery from {addr} with {response}")
                        
                except OSError:
                    # Socket closed (通常是 stop() 被呼叫)
                    break
                except Exception as e:
                    logger.error(f"UDP Loop Error: {e}")
        except Exception as e:
            logger.error(f"UDP Bind Failed on port {self.port}: {e}")

if __name__ == "__main__":
    # 獨立測試用
    logging.basicConfig(level=logging.INFO)
    service = DiscoveryService()
    service.start()
    
    import time
    try:
        print("Press Ctrl+C to stop...")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        service.stop()
        print("Stopped.")