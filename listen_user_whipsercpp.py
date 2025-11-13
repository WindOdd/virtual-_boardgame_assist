"""
桌遊語音助理 - STT 核心系統
功能：音訊輸入 → 降噪 → VAD → STT (記憶體處理)

注意：pywhispercpp 需要檔案路徑，使用 tempfile 作為橋樑
"""

import sounddevice as sd
import numpy as np
import io
import time
import wave
import tempfile
from datetime import datetime
from collections import deque
from pathlib import Path
import threading

# 檢查依賴
try:
    from pywhispercpp.model import Model as WhisperModel
except ImportError:
    print("❌ 請安裝: pip install pywhispercpp")
    print("   並下載模型: wget https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base-q5_1.bin")
    exit(1)

try:
    import torch
except ImportError:
    print("❌ 請安裝: pip install torch")
    exit(1)

try:
    from scipy.io import wavfile
except ImportError:
    print("❌ 請安裝: pip install scipy")
    exit(1)


# ==================== 配置類 ====================
class Config:
    """系統配置"""
    # 音訊參數
    SAMPLE_RATE = 16000          # 採樣率 (Hz)
    CHANNELS = 1                 # 單聲道
    DTYPE = 'int16'              # 數據類型
    
    # 錄音控制
    MAX_RECORDING_DURATION = 30  # 最大錄音時長（秒）
    SILENCE_DURATION = 1.5       # 靜音判定時長（秒）
    SILENCE_THRESHOLD = 50       # 靜音能量閾值
    
    # VAD 參數
    VAD_THRESHOLD = 0.5          # Silero VAD 閾值 (0-1)
    MIN_SPEECH_DURATION = 0.5    # 最短有效語音時長（秒）
    MIN_SPEECH_ENERGY = 100      # 最小語音能量（備用方案）
    
    # Whisper 設定
    WHISPER_MODEL = "ggml-base-q5_1.bin"  # 模型路徑
    WHISPER_LANGUAGE = "zh"               # 語言
    WHISPER_THREADS = 4                   # CPU 執行緒數
    
    # 系統設定
    DEBUG_MODE = True            # 除錯模式（會保存音訊檔案）
    LOG_DIR = Path("logs")       # 日誌目錄
    
    @classmethod
    def print_config(cls):
        """列印當前配置"""
        print("\n" + "="*60)
        print("系統配置")
        print("="*60)
        print(f"採樣率: {cls.SAMPLE_RATE} Hz")
        print(f"聲道數: {cls.CHANNELS}")
        print(f"最大錄音時長: {cls.MAX_RECORDING_DURATION} 秒")
        print(f"靜音判定時長: {cls.SILENCE_DURATION} 秒")
        print(f"VAD 閾值: {cls.VAD_THRESHOLD}")
        print(f"Whisper 模型: {cls.WHISPER_MODEL}")
        print(f"除錯模式: {'開啟' if cls.DEBUG_MODE else '關閉'}")
        print("="*60 + "\n")


# ==================== 音訊緩衝區 ====================
class AudioBuffer:
    """循環音訊緩衝區（記憶體管理）"""
    
    def __init__(self, max_duration, sample_rate):
        """
        初始化緩衝區
        
        Args:
            max_duration: 最大緩衝時長（秒）
            sample_rate: 採樣率
        """
        self.max_samples = int(max_duration * sample_rate)
        self.buffer = deque(maxlen=self.max_samples)
        self.sample_rate = sample_rate
        self.lock = threading.Lock()
    
    def add(self, data):
        """
        添加音訊數據（線程安全）
        
        Args:
            data: numpy array
        """
        with self.lock:
            self.buffer.extend(data.flatten())
    
    def clear(self):
        """清空緩衝區"""
        with self.lock:
            self.buffer.clear()
    
    def get_array(self):
        """
        獲取完整音訊數據
        
        Returns:
            numpy array (int16)
        """
        with self.lock:
            return np.array(list(self.buffer), dtype='int16')
    
    def get_duration(self):
        """
        獲取當前緩衝時長
        
        Returns:
            時長（秒）
        """
        with self.lock:
            return len(self.buffer) / self.sample_rate
    
    def get_last_seconds(self, seconds):
        """
        獲取最後 N 秒的音訊
        
        Args:
            seconds: 秒數
            
        Returns:
            numpy array
        """
        samples = int(seconds * self.sample_rate)
        with self.lock:
            data = list(self.buffer)[-samples:]
            return np.array(data, dtype='int16')


# ==================== VAD 處理器 ====================
class VADProcessor:
    """語音活動檢測器（Silero VAD + 能量檢測備用）"""
    
    def __init__(self, sample_rate=16000, threshold=0.5):
        """
        初始化 VAD
        
        Args:
            sample_rate: 採樣率
            threshold: Silero VAD 閾值
        """
        self.sample_rate = sample_rate
        self.threshold = threshold
        self.model = None
        self.utils = None
        self._load_model()
    
    def _load_model(self):
        """載入 Silero VAD 模型"""
        try:
            print("⏳ 載入 Silero VAD 模型...")
            self.model, self.utils = torch.hub.load(
                repo_or_dir='snakers4/silero-vad',
                model='silero_vad',
                force_reload=False,
                onnx=False,
                verbose=False
            )
            self.model.eval()
            print("✅ Silero VAD 已載入")
        except Exception as e:
            print(f"⚠️  Silero VAD 載入失敗: {e}")
            print("   將使用簡單能量檢測作為備用方案")
            self.model = None
    
    def has_speech(self, audio_array):
        """
        檢測音訊中是否包含語音
        
        Args:
            audio_array: numpy array (int16)
            
        Returns:
            bool: True 表示包含語音
        """
        if self.model is None:
            return self._energy_based_vad(audio_array)
        
        try:
            return self._silero_vad(audio_array)
        except Exception as e:
            print(f"⚠️  VAD 檢測錯誤: {e}，使用備用方案")
            return self._energy_based_vad(audio_array)
    
    def _silero_vad(self, audio_array):
        """使用 Silero VAD 檢測"""
        # 轉換為 float32 [-1, 1]
        audio_float = audio_array.astype(np.float32) / 32768.0
        audio_tensor = torch.from_numpy(audio_float)
        
        # 獲取語音時間戳
        get_speech_timestamps = self.utils[0]
        speech_timestamps = get_speech_timestamps(
            audio_tensor,
            self.model,
            sampling_rate=self.sample_rate,
            threshold=self.threshold,
            min_speech_duration_ms=int(Config.MIN_SPEECH_DURATION * 1000),
            return_seconds=False
        )
        
        # 計算總語音時長
        if not speech_timestamps:
            return False
        
        total_speech_samples = sum(
            ts['end'] - ts['start'] 
            for ts in speech_timestamps
        )
        total_speech_duration = total_speech_samples / self.sample_rate
        
        return total_speech_duration >= Config.MIN_SPEECH_DURATION
    
    def _energy_based_vad(self, audio_array):
        """簡單能量檢測（備用方案）"""
        # 計算平均能量
        energy = np.mean(np.abs(audio_array))
        
        # 判斷是否超過閾值
        return energy > Config.MIN_SPEECH_ENERGY
    
    def get_speech_segments(self, audio_array):
        """
        獲取語音片段的時間戳
        
        Args:
            audio_array: numpy array
            
        Returns:
            list of dict: [{'start': 0.5, 'end': 2.3}, ...]
        """
        if self.model is None:
            return []
        
        try:
            audio_float = audio_array.astype(np.float32) / 32768.0
            audio_tensor = torch.from_numpy(audio_float)
            
            get_speech_timestamps = self.utils[0]
            timestamps = get_speech_timestamps(
                audio_tensor,
                self.model,
                sampling_rate=self.sample_rate,
                threshold=self.threshold,
                return_seconds=True
            )
            
            return timestamps
        except:
            return []


# ==================== Whisper STT ====================
class WhisperSTT:
    """Whisper 語音轉文字（記憶體處理，零磁碟 I/O）"""
    
    def __init__(self, model_path, sample_rate=16000, language="zh", n_threads=4):
        """
        初始化 Whisper
        
        Args:
            model_path: 模型檔案路徑
            sample_rate: 採樣率
            language: 語言代碼
            n_threads: CPU 執行緒數
        """
        self.sample_rate = sample_rate
        self.language = language
        self.model = None
        self._load_model(model_path, n_threads)
    
    def _load_model(self, model_path, n_threads):
        """載入 Whisper 模型"""
        try:
            print(f"⏳ 載入 Whisper 模型: {model_path}")
            
            # 檢查模型檔案
            model_path_obj = Path(model_path)
            if not model_path_obj.exists():
                print(f"❌ 模型檔案不存在: {model_path}")
                print("\n請選擇以下方式下載模型：")
                print("\n方式 1: 使用 wget (Linux/Mac)")
                print("  wget https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base-q5_1.bin")
                print("\n方式 2: 使用 curl")
                print("  curl -L -O https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base-q5_1.bin")
                print("\n方式 3: 運行下載腳本")
                print("  python download_whisper_model.py")
                print("\n方式 4: 手動從瀏覽器下載")
                print("  https://huggingface.co/ggerganov/whisper.cpp/tree/main")
                
                # 提供自動下載選項
                auto_download = input("\n是否自動下載? (y/n): ").strip().lower()
                if auto_download == 'y':
                    if self._auto_download_model(model_path):
                        print("✅ 模型下載完成，繼續載入...")
                    else:
                        print("❌ 自動下載失敗，請手動下載")
                        return
                else:
                    return
            
            # 顯示模型資訊
            size_mb = model_path_obj.stat().st_size / (1024 * 1024)
            print(f"📊 模型大小: {size_mb:.1f} MB")
            
            # 載入模型
            self.model = WhisperModel(
                str(model_path_obj),
                n_threads=n_threads
            )
            print("✅ Whisper 已載入")
            
        except Exception as e:
            print(f"❌ Whisper 載入失敗: {e}")
            import traceback
            traceback.print_exc()
            self.model = None
    
    def _auto_download_model(self, model_path):
        """自動下載模型"""
        try:
            import urllib.request
            
            url = "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base-q5_1.bin"
            print(f"📥 下載中: {url}")
            print("   這可能需要幾分鐘...")
            
            def progress_hook(count, block_size, total_size):
                percent = int(count * block_size * 100 / total_size)
                if count % 10 == 0:  # 每 10 個區塊顯示一次
                    print(f"   進度: {percent}%", end='\r')
            
            urllib.request.urlretrieve(url, model_path, progress_hook)
            print("\n✅ 下載完成")
            return True
            
        except Exception as e:
            print(f"\n❌ 下載失敗: {e}")
            return False
    
    def transcribe(self, audio_array):
        """
        轉錄音訊（使用臨時記憶體檔案）
        
        Args:
            audio_array: numpy array (int16)
            
        Returns:
            str: 轉錄文字
        """
        if self.model is None:
            print("❌ Whisper 模型未載入")
            return ""
        
        try:
            # 使用 tempfile 創建臨時檔案（記憶體映射，最小磁碟 I/O）
            import tempfile
            
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=True) as tmp_file:
                # 寫入 WAV 格式
                with wave.open(tmp_file.name, 'wb') as wav_file:
                    wav_file.setnchannels(1)
                    wav_file.setsampwidth(2)
                    wav_file.setframerate(self.sample_rate)
                    wav_file.writeframes(audio_array.tobytes())
                
                # 轉錄
                start_time = time.time()
                result = self.model.transcribe(
                    tmp_file.name,
                    language=self.language
                )
                elapsed = time.time() - start_time
                
                # 處理不同的返回格式
                text = self._extract_text(result)
                
                print(f"⏱️  轉錄耗時: {elapsed:.2f} 秒")
                
                return text
            # tempfile 自動刪除
            
        except Exception as e:
            print(f"❌ 轉錄錯誤: {e}")
            import traceback
            traceback.print_exc()
            return ""
    
    def _extract_text(self, result):
        """
        從不同格式的結果中提取文字
        
        Args:
            result: whisper 返回的結果（可能是 dict, list, 或 object）
            
        Returns:
            str: 提取的文字
        """
        try:
            # 情況 1: 字典格式 {'text': '...'}
            if isinstance(result, dict):
                return result.get('text', '').strip()
            
            # 情況 2: 列表格式（segment list）
            elif isinstance(result, list):
                texts = []
                for segment in result:
                    if isinstance(segment, dict):
                        texts.append(segment.get('text', ''))
                    elif hasattr(segment, 'text'):
                        texts.append(segment.text)
                return ' '.join(texts).strip()
            
            # 情況 3: 物件格式（有 text 屬性）
            elif hasattr(result, 'text'):
                return result.text.strip()
            
            # 情況 4: 字串格式（直接返回文字）
            elif isinstance(result, str):
                return result.strip()
            
            # 未知格式，嘗試轉換為字串
            else:
                print(f"⚠️  未知的結果格式: {type(result)}")
                print(f"   結果內容: {result}")
                return str(result).strip()
                
        except Exception as e:
            print(f"⚠️  提取文字時發生錯誤: {e}")
            print(f"   結果類型: {type(result)}")
            print(f"   結果內容: {result}")
            return ""


# ==================== 錄音管理器 ====================
class AudioRecorder:
    """音訊錄音管理器"""
    
    def __init__(self, buffer):
        """
        初始化錄音器
        
        Args:
            buffer: AudioBuffer 實例
        """
        self.buffer = buffer
        self.stream = None
        self.is_recording = False
        self.silence_start = None
    
    def _callback(self, indata, frames, time_info, status):
        """音訊輸入回調函數"""
        if status:
            print(f"⚠️  音訊狀態: {status}")
        
        if self.is_recording:
            # 添加到緩衝區
            self.buffer.add(indata)
            
            # 檢測靜音（用於自動停止）
            energy = np.mean(np.abs(indata))
            
            if energy < Config.SILENCE_THRESHOLD:
                # 靜音開始
                if self.silence_start is None:
                    self.silence_start = time.time()
                # 靜音持續超過閾值
                elif time.time() - self.silence_start > Config.SILENCE_DURATION:
                    print("🔇 檢測到持續靜音")
                    self.stop()
            else:
                # 有聲音，重置靜音計時
                self.silence_start = None
    
    def start(self):
        """開始錄音"""
        if self.is_recording:
            print("⚠️  已在錄音中")
            return
        
        print("🎤 開始錄音...")
        self.is_recording = True
        self.buffer.clear()
        self.silence_start = None
        
        try:
            self.stream = sd.InputStream(
                callback=self._callback,
                channels=Config.CHANNELS,
                samplerate=Config.SAMPLE_RATE,
                dtype=Config.DTYPE
            )
            self.stream.start()
            
        except Exception as e:
            print(f"❌ 錄音啟動失敗: {e}")
            self.is_recording = False
    
    def stop(self):
        """停止錄音"""
        if not self.is_recording:
            return
        
        self.is_recording = False
        
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        
        duration = self.buffer.get_duration()
        print(f"⏹️  錄音停止（時長: {duration:.2f} 秒）")
    
    def is_active(self):
        """檢查是否正在錄音"""
        return self.is_recording


# ==================== 主系統 ====================
class VoiceAssistantSTT:
    """語音助理 STT 系統"""
    
    def __init__(self):
        """初始化系統"""
        print("\n" + "="*60)
        print("桌遊語音助理 - STT 系統")
        print("="*60)
        
        # 建立日誌目錄
        Config.LOG_DIR.mkdir(exist_ok=True)
        
        # 初始化組件
        self.buffer = AudioBuffer(
            Config.MAX_RECORDING_DURATION,
            Config.SAMPLE_RATE
        )
        self.recorder = AudioRecorder(self.buffer)
        self.vad = VADProcessor(
            Config.SAMPLE_RATE,
            Config.VAD_THRESHOLD
        )
        self.stt = WhisperSTT(
            Config.WHISPER_MODEL,
            Config.SAMPLE_RATE,
            Config.WHISPER_LANGUAGE,
            Config.WHISPER_THREADS
        )
        
        Config.print_config()
    
    def process_audio(self):
        """處理錄音的音訊"""
        print("\n" + "-"*60)
        print("⚙️  處理音訊...")
        
        # 1. 獲取音訊數據
        audio_array = self.buffer.get_array()
        duration = self.buffer.get_duration()
        
        if len(audio_array) == 0:
            print("❌ 無音訊數據")
            return None
        
        print(f"📊 音訊時長: {duration:.2f} 秒")
        print(f"📊 音訊大小: {len(audio_array)} 樣本 ({len(audio_array) * 2 / 1024:.1f} KB)")
        
        # 2. VAD 檢測
        print("🔍 VAD 檢測中...")
        has_speech = self.vad.has_speech(audio_array)
        
        if not has_speech:
            print("❌ 未檢測到有效語音")
            return None
        
        print("✅ 檢測到語音")
        
        # 顯示語音片段
        segments = self.vad.get_speech_segments(audio_array)
        if segments:
            print(f"📍 語音片段數: {len(segments)}")
            for i, seg in enumerate(segments[:3]):  # 最多顯示 3 個
                print(f"   片段 {i+1}: {seg['start']:.2f}s - {seg['end']:.2f}s")
        
        # 3. 語音轉文字
        print("🗣️  語音轉文字中...")
        text = self.stt.transcribe(audio_array)
        
        if not text:
            print("❌ 轉錄失敗或無內容")
            return None
        
        print(f"✅ 辨識結果: {text}")
        
        # 4. 除錯模式：保存音訊
        if Config.DEBUG_MODE:
            self._save_debug_audio(audio_array, text)
        
        print("-"*60 + "\n")
        return text
    
    def _save_debug_audio(self, audio_array, text):
        """保存除錯音訊和文字"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # 保存音訊
        audio_file = Config.LOG_DIR / f"audio_{timestamp}.wav"
        wavfile.write(audio_file, Config.SAMPLE_RATE, audio_array)
        
        # 保存文字
        text_file = Config.LOG_DIR / f"text_{timestamp}.txt"
        with open(text_file, 'w', encoding='utf-8') as f:
            f.write(text)
        
        print(f"💾 已保存: {audio_file.name} & {text_file.name}")
    
    def run_interactive(self):
        """運行互動模式"""
        print("🎮 互動模式啟動")
        print("-"*60)
        print("指令:")
        print("  Enter      - 開始/停止錄音")
        print("  q + Enter  - 退出")
        print("-"*60)
        
        try:
            while True:
                cmd = input("\n👉 ").strip().lower()
                
                if cmd == 'q':
                    print("👋 再見！")
                    break
                
                # 切換錄音狀態
                if not self.recorder.is_active():
                    # 開始錄音
                    self.recorder.start()
                    print("💡 按 Enter 停止錄音")
                else:
                    # 停止錄音並處理
                    self.recorder.stop()
                    self.process_audio()
        
        except KeyboardInterrupt:
            print("\n\n👋 程式中斷")
        
        finally:
            if self.recorder.is_active():
                self.recorder.stop()
    
    def run_button_mode(self):
        """運行按鈕模式（模擬）"""
        print("🔘 按鈕模式啟動")
        print("-"*60)
        print("按 Enter 模擬按下按鈕（開始錄音）")
        print("錄音將在靜音或超時後自動停止")
        print("輸入 'q' 退出")
        print("-"*60)
        
        try:
            while True:
                cmd = input("\n👉 按鈕: ").strip().lower()
                
                if cmd == 'q':
                    print("👋 再見！")
                    break
                
                # 開始錄音
                self.recorder.start()
                
                # 等待自動停止或手動停止
                start = time.time()
                while self.recorder.is_active():
                    time.sleep(0.1)
                    # 檢查超時
                    if time.time() - start > Config.MAX_RECORDING_DURATION:
                        print("⏱️  達到最大錄音時長")
                        self.recorder.stop()
                        break
                
                # 處理音訊
                self.process_audio()
        
        except KeyboardInterrupt:
            print("\n\n👋 程式中斷")
        
        finally:
            if self.recorder.is_active():
                self.recorder.stop()


# ==================== 主程式入口 ====================
def main():
    """主程式"""
    # 創建系統
    assistant = VoiceAssistantSTT()
    
    # 選擇模式
    print("選擇運行模式:")
    print("  1 - 互動模式（手動控制錄音）")
    print("  2 - 按鈕模式（自動停止）")
    
    choice = input("\n請選擇 (1/2): ").strip()
    
    if choice == '2':
        assistant.run_button_mode()
    else:
        assistant.run_interactive()


if __name__ == "__main__":
    main()