"""
桌遊語音助理 - STT 核心系統 (faster-whisper 版本)
功能：音訊輸入 → VAD → STT (完全記憶體處理)

優勢：
- 更快的轉錄速度（2-3倍）
- 無 Windows 檔案鎖定問題
- 直接處理 numpy array
- 標準化的返回格式
"""

import sounddevice as sd
import numpy as np
import time
from datetime import datetime
from collections import deque
from pathlib import Path
import threading

# 檢查依賴
try:
    from faster_whisper import WhisperModel
except ImportError:
    print("❌ 請安裝: pip install faster-whisper")
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
    WHISPER_MODEL = "base"       # 模型大小: tiny, base, small, medium, large
    WHISPER_DEVICE = "cpu"       # 設備: cpu, cuda
    WHISPER_COMPUTE_TYPE = "int8" # 計算類型: int8, float16, float32
    WHISPER_LANGUAGE = "zh"      # 語言
    
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
        print(f"Whisper 模型: {cls.WHISPER_MODEL}")
        print(f"計算類型: {cls.WHISPER_COMPUTE_TYPE}")
        print(f"設備: {cls.WHISPER_DEVICE}")
        print(f"語言: {cls.WHISPER_LANGUAGE}")
        print(f"除錯模式: {'開啟' if cls.DEBUG_MODE else '關閉'}")
        print("="*60 + "\n")


# ==================== 音訊緩衝區 ====================
class AudioBuffer:
    """循環音訊緩衝區（記憶體管理）"""
    
    def __init__(self, max_duration, sample_rate):
        self.max_samples = int(max_duration * sample_rate)
        self.buffer = deque(maxlen=self.max_samples)
        self.sample_rate = sample_rate
        self.lock = threading.Lock()
    
    def add(self, data):
        """添加音訊數據（線程安全）"""
        with self.lock:
            self.buffer.extend(data.flatten())
    
    def clear(self):
        """清空緩衝區"""
        with self.lock:
            self.buffer.clear()
    
    def get_array(self):
        """獲取完整音訊數據（float32 格式）"""
        with self.lock:
            # faster-whisper 需要 float32 [-1, 1]
            audio_int16 = np.array(list(self.buffer), dtype='int16')
            audio_float32 = audio_int16.astype(np.float32) / 32768.0
            return audio_float32
    
    def get_duration(self):
        """獲取當前緩衝時長"""
        with self.lock:
            return len(self.buffer) / self.sample_rate


# ==================== VAD 處理器 ====================
class VADProcessor:
    """語音活動檢測器"""
    
    def __init__(self, sample_rate=16000, threshold=0.5):
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
    
    def has_speech(self, audio_float32):
        """
        檢測音訊中是否包含語音
        
        Args:
            audio_float32: numpy array (float32, [-1, 1])
        """
        if self.model is None:
            return self._energy_based_vad(audio_float32)
        
        try:
            return self._silero_vad(audio_float32)
        except Exception as e:
            print(f"⚠️  VAD 檢測錯誤: {e}，使用備用方案")
            return self._energy_based_vad(audio_float32)
    
    def _silero_vad(self, audio_float32):
        """使用 Silero VAD 檢測"""
        audio_tensor = torch.from_numpy(audio_float32)
        
        get_speech_timestamps = self.utils[0]
        speech_timestamps = get_speech_timestamps(
            audio_tensor,
            self.model,
            sampling_rate=self.sample_rate,
            threshold=self.threshold,
            min_speech_duration_ms=int(Config.MIN_SPEECH_DURATION * 1000),
            return_seconds=False
        )
        
        if not speech_timestamps:
            return False
        
        total_speech_samples = sum(
            ts['end'] - ts['start'] 
            for ts in speech_timestamps
        )
        total_speech_duration = total_speech_samples / self.sample_rate
        
        return total_speech_duration >= Config.MIN_SPEECH_DURATION
    
    def _energy_based_vad(self, audio_float32):
        """簡單能量檢測（備用方案）"""
        energy = np.mean(np.abs(audio_float32))
        # float32 的能量閾值需要調整
        return energy > (Config.MIN_SPEECH_ENERGY / 32768.0)


# ==================== faster-whisper STT ====================
class FasterWhisperSTT:
    """faster-whisper 語音轉文字（完全記憶體處理）"""
    
    def __init__(self, model_size="base", device="cpu", compute_type="int8", language="zh"):
        """
        初始化 faster-whisper
        
        Args:
            model_size: 模型大小 (tiny, base, small, medium, large)
            device: 運行設備 (cpu, cuda)
            compute_type: 計算類型 (int8, float16, float32)
            language: 語言代碼
        """
        self.language = language
        self.model = None
        self._load_model(model_size, device, compute_type)
    
    def _load_model(self, model_size, device, compute_type):
        """載入 faster-whisper 模型"""
        try:
            print(f"⏳ 載入 faster-whisper 模型: {model_size}")
            print(f"   設備: {device}, 計算類型: {compute_type}")
            
            self.model = WhisperModel(
                model_size,
                device=device,
                compute_type=compute_type
            )
            
            print("✅ faster-whisper 已載入")
            
        except Exception as e:
            print(f"❌ faster-whisper 載入失敗: {e}")
            import traceback
            traceback.print_exc()
            self.model = None
    
    def transcribe(self, audio_float32):
        """
        轉錄音訊（完全記憶體處理）
        
        Args:
            audio_float32: numpy array (float32, [-1, 1])
            
        Returns:
            str: 轉錄文字
        """
        if self.model is None:
            print("❌ faster-whisper 模型未載入")
            return ""
        
        try:
            start_time = time.time()
            
            # faster-whisper 可以直接接受 numpy array！
            segments, info = self.model.transcribe(
                audio_float32,
                language=self.language,
                beam_size=5,
                vad_filter=False,  # 我們已經用 Silero VAD 了
                without_timestamps=True  # 不需要時間戳，更快
            )
            
            # 組合所有 segment 的文字
            text = "".join([segment.text for segment in segments]).strip()
            
            elapsed = time.time() - start_time
            
            # 顯示辨識資訊
            print(f"⏱️  轉錄耗時: {elapsed:.2f} 秒")
            print(f"📊 檢測語言: {info.language} (置信度: {info.language_probability:.2%})")
            
            return text
            
        except Exception as e:
            print(f"❌ 轉錄錯誤: {e}")
            import traceback
            traceback.print_exc()
            return ""


# ==================== 錄音管理器 ====================
class AudioRecorder:
    """音訊錄音管理器"""
    
    def __init__(self, buffer):
        self.buffer = buffer
        self.stream = None
        self.is_recording = False
        self.silence_start = None
    
    def _callback(self, indata, frames, time_info, status):
        """音訊輸入回調函數"""
        if status:
            print(f"⚠️  音訊狀態: {status}")
        
        if self.is_recording:
            self.buffer.add(indata)
            
            # 檢測靜音
            energy = np.mean(np.abs(indata))
            
            if energy < Config.SILENCE_THRESHOLD:
                if self.silence_start is None:
                    self.silence_start = time.time()
                elif time.time() - self.silence_start > Config.SILENCE_DURATION:
                    print("🔇 檢測到持續靜音")
                    self.stop()
            else:
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
        print("桌遊語音助理 - STT 系統 (faster-whisper)")
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
        self.stt = FasterWhisperSTT(
            Config.WHISPER_MODEL,
            Config.WHISPER_DEVICE,
            Config.WHISPER_COMPUTE_TYPE,
            Config.WHISPER_LANGUAGE
        )
        
        Config.print_config()
    
    def process_audio(self):
        """處理錄音的音訊"""
        print("\n" + "-"*60)
        print("⚙️  處理音訊...")
        
        # 1. 獲取音訊數據（float32 格式）
        audio_float32 = self.buffer.get_array()
        duration = self.buffer.get_duration()
        
        if len(audio_float32) == 0:
            print("❌ 無音訊數據")
            return None
        
        print(f"📊 音訊時長: {duration:.2f} 秒")
        print(f"📊 樣本數量: {len(audio_float32)}")
        
        # 2. VAD 檢測
        print("🔍 VAD 檢測中...")
        has_speech = self.vad.has_speech(audio_float32)
        
        if not has_speech:
            print("❌ 未檢測到有效語音")
            return None
        
        print("✅ 檢測到語音")
        
        # 3. 語音轉文字
        print("🗣️  語音轉文字中...")
        text = self.stt.transcribe(audio_float32)
        
        if not text:
            print("❌ 轉錄失敗或無內容")
            return None
        
        print(f"✅ 辨識結果: {text}")
        
        # 4. 除錯模式：保存音訊
        if Config.DEBUG_MODE:
            self._save_debug_audio(audio_float32, text)
        
        print("-"*60 + "\n")
        return text
    
    def _save_debug_audio(self, audio_float32, text):
        """保存除錯音訊和文字"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # 轉回 int16 保存
        audio_int16 = (audio_float32 * 32768.0).astype(np.int16)
        
        # 保存音訊
        audio_file = Config.LOG_DIR / f"audio_{timestamp}.wav"
        wavfile.write(audio_file, Config.SAMPLE_RATE, audio_int16)
        
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
                
                if not self.recorder.is_active():
                    self.recorder.start()
                    print("💡 按 Enter 停止錄音")
                else:
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
                
                self.recorder.start()
                
                start = time.time()
                while self.recorder.is_active():
                    time.sleep(0.1)
                    if time.time() - start > Config.MAX_RECORDING_DURATION:
                        print("⏱️  達到最大錄音時長")
                        self.recorder.stop()
                        break
                
                self.process_audio()
        
        except KeyboardInterrupt:
            print("\n\n👋 程式中斷")
        
        finally:
            if self.recorder.is_active():
                self.recorder.stop()


# ==================== 主程式入口 ====================
def main():
    """主程式"""
    assistant = VoiceAssistantSTT()
    
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