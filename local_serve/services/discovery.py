import socket
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
