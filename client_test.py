import time
import queue
import asyncio
import subprocess
import requests
import numpy as np
import sounddevice as sd
import edge_tts
from scipy import signal
from faster_whisper import WhisperModel

# ================= 配置區域 =================
# 1. 網路設定 (Local Router)
# 請將 IP 改為 Local Router (Jetson) 的 IP
SERVER_URL = "http://100.94.60.23:8000/ask" 
TABLE_ID = "T01"
SESSION_ID = "sess-pi-01"
CURRENT_GAME = "carcassonne"  # 對應 Router 端 YAML 的 id

# 2. 音訊設定 (已驗證的最佳參數)
SAMPLE_RATE = 48000
TARGET_RATE = 16000
CHANNELS = 1
DTYPE = 'float32'
WHISPER_SIZE = "small"

# ================= 核心類別 =================

class AudioHandler:
    """
    [保留] Scipy 重採樣 + SoundDevice (驗證過的高音質方案)
    """
    def __init__(self):
        self.q = queue.Queue()
        self.recording = False
        self.stream = None

    def _callback(self, indata, frames, time, status):
        if status: print(f"⚠️ Audio Status: {status}")
        self.q.put(indata.copy())

    def start(self):
        self.recording = True
        with self.q.mutex: self.q.queue.clear()
        self.stream = sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS, dtype=DTYPE, callback=self._callback)
        self.stream.start()
        print(f"🎙️  [錄音中]...")

    def stop(self):
        self.recording = False
        if self.stream:
            self.stream.stop(); self.stream.close(); self.stream = None
        print("⏹️  錄音結束，處理中...")
        
        data_list = []
        while not self.q.empty(): data_list.append(self.q.get())
        if not data_list: return None
        
        full_audio = np.concatenate(data_list, axis=0)
        
        # 使用 Scipy 進行抗混疊重採樣 (48k -> 16k)
        if SAMPLE_RATE != TARGET_RATE:
            gcd = np.gcd(SAMPLE_RATE, TARGET_RATE)
            return signal.resample_poly(full_audio, int(TARGET_RATE/gcd), int(SAMPLE_RATE/gcd)).flatten()
        return full_audio.flatten()

class NetworkClient:
    """
    [新增] 負責將 STT 文字發送給 Local Router
    """
    def __init__(self, url):
        self.url = url

    def send_query(self, text):
        if not text: return None
        print(f"📤 發送給 Router: {text}")
        
        # 建構符合 v4.0 Spec 的 Payload
        payload = {
            "table_id": TABLE_ID,
            "session_id": SESSION_ID,
            "game_name": CURRENT_GAME,
            "user_text": text,
            "history": [] # Client 暫不維護歷史，交由 Server 或後續實作
        }

        try:
            # 設定 timeout=10s，等待 Jetson 思考
            response = requests.post(self.url, json=payload, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                answer = data.get("answer", "Server 回傳了空的答案")
                source = data.get("source", "UNKNOWN")
                print(f"📥 Router 回覆 ({source}): {answer}")
                return answer
            else:
                err_msg = f"Server Error: {response.status_code}"
                print(f"❌ {err_msg}")
                return "伺服器出錯了，請檢查後端。"
                
        except requests.exceptions.ConnectionError:
            print("❌ 無法連線到 Router (IP 正確嗎？Server 開了嗎？)")
            return "我連不到大腦，請檢查網路。"
        except Exception as e:
            print(f"❌ 發生錯誤: {e}")
            return "發生未知錯誤。"

async def play_tts(text):
    """EdgeTTS -> MPV"""
    if not text: return
    voice = "zh-TW-HsiaoChenNeural"
    communicate = edge_tts.Communicate(text, voice)
    cmd = ["mpv", "--no-cache", "--no-terminal", "--idle=no", "--volume=100", "-"]
    try:
        process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        async for chunk in communicate.stream():
            if chunk["type"] == "audio" and process.stdin:
                process.stdin.write(chunk["data"])
                process.stdin.flush()
        if process.stdin: process.stdin.close()
        process.wait()
    except Exception as e: print(f"TTS Error: {e}")

# ================= 主程式 =================

def main():
    print(f"🚀 載入 Whisper ({WHISPER_SIZE} int8)...")
    whisper = WhisperModel(WHISPER_SIZE, device="cpu", compute_type="int8", cpu_threads=4)
    
    audio = AudioHandler()
    net_client = NetworkClient(SERVER_URL)
    
    print("\n=======================================")
    print(f"📡 Client 連線模式 (Target: {SERVER_URL})")
    print(f"🎮 當前遊戲: {CURRENT_GAME}")
    print("=======================================")
    
    while True:
        try:
            input("\n👉 按下 [Enter] 開始說話...")
            audio.start()
            input("👉 說完請按 [Enter]...")
            audio_data = audio.stop()
            
            if audio_data is None: continue

            # 1. 辨識 (保持高準確度參數)
            print("📝 辨識中...")
            start_t = time.time()
            segments, _ = whisper.transcribe(
                audio_data,
                language="zh",
                beam_size=3,
                best_of=3,
                temperature=0.0,
                condition_on_previous_text=False,
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=300),
                initial_prompt="卡卡頌桌遊規則。詞彙：米寶、農夫、修道院、板塊、城堡、草原、計分、倒下"
            )
            text = " ".join([s.text for s in segments]).strip()
            print(f"📝 聽到了 ({time.time()-start_t:.2f}s): {text}")
            
            # 2. 發送給 Router (取代原本的 RuleBasedBrain)
            reply = net_client.send_query(text)
            
            # 3. 播放回覆
            if reply:
                asyncio.run(play_tts(reply))
                
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"❌ Main Error: {e}")

if __name__ == "__main__":
    main()