"""
桌遊語音助理 - 完整 VAD 系統（整合版）

控制方式：
1. Enter 開始錄音
2. Enter 停止錄音 或 40 秒自動停止

處理流程：
- Callback: RNNoise 降噪 → WebRTC VAD → 保存語音段
- 處理: 降噪語音段 → 後置驗證 → Whisper 轉錄
"""

import sounddevice as sd
import numpy as np
import time
import threading
from datetime import datetime
from collections import deque
from pathlib import Path
import gemini_flash_test
import edgTTS
import asyncio
# 檢查依賴
try:
    from faster_whisper import WhisperModel
except ImportError:
    print("❌ 請安裝: pip install faster-whisper")
    exit(1)

try:
    import webrtcvad
except ImportError:
    print("❌ 請安裝: pip install webrtcvad")
    exit(1)

try:
    from scipy.io import wavfile
    from scipy import signal
except ImportError:
    print("❌ 請安裝: pip install scipy")
    exit(1)

# RNNoise（可選）
try:
    from pyrnnoise import RNNoise
    RNNOISE_AVAILABLE = True
except ImportError:
    RNNOISE_AVAILABLE = False
    print("⚠️  RNNoise 未安裝（可選），降噪功能不可用")


# ==================== 配置類 ====================
class Config:
    """系統配置"""
    # 音訊參數
    SAMPLE_RATE = 16000
    CHANNELS = 1
    DTYPE = 'int16'
    FRAME_DURATION_MS = 20
    
    # 錄音控制
    MAX_RECORDING_DURATION = 40  # 最大 40 秒
    
    # 降噪
    ENABLE_RNNOISE = True
    RNNOISE_IN_CALLBACK = True
    
    # VAD
    VAD_STRATEGY = "webrtc_only"
    WEBRTC_AGGRESSIVENESS = 1
    
    # 狀態機
    SPEECH_START_FRAMES = 3
    SPEECH_END_FRAMES = 25
    PRE_SPEECH_FRAMES = 10
    POST_SPEECH_FRAMES = 5
    
    # 後置驗證
    MIN_SPEECH_DURATION = 0.5
    MAX_SPEECH_DURATION = 60
    MIN_ENERGY_THRESHOLD = 50
    
    # Whisper
    WHISPER_MODEL = "small" 
    WHISPER_DEVICE = "cpu"
    WHISPER_COMPUTE_TYPE = "int8"
    WHISPER_LANGUAGE = "zh"
    
    # 系統
    DEBUG_MODE = True
    LOG_DIR = Path("logs")
    
    @classmethod
    def print_config(cls):
        """列印配置"""
        print("\n" + "="*60)
        print("系統配置")
        print("="*60)
        print(f"最大錄音時長: {cls.MAX_RECORDING_DURATION} 秒")
        print(f"RNNoise 降噪: {'開啟（實時）' if cls.ENABLE_RNNOISE and RNNOISE_AVAILABLE else '關閉'}")
        print(f"VAD 策略: WebRTC (激進度={cls.WEBRTC_AGGRESSIVENESS})")
        print(f"Whisper 模型: {cls.WHISPER_MODEL}")
        print(f"除錯模式: {'開啟' if cls.DEBUG_MODE else '關閉'}")
        print("="*60 + "\n")


# ==================== RNNoise 降噪 ====================
class RNNoiseProcessor:
    """RNNoise 降噪處理器"""
    
    def __init__(self, sample_rate=16000):
        self.sample_rate = sample_rate
        self.denoiser = None
        self.available = RNNOISE_AVAILABLE
        
        if not self.available:
            return
        
        try:
            self.denoiser = RNNoise(sample_rate=sample_rate)
            print("✅ RNNoise 已初始化")
        except Exception as e:
            print(f"⚠️  RNNoise 初始化失敗: {e}")
            self.available = False
    
    def process_frame(self, audio_int16):
        """處理音訊幀"""
        if not self.available or self.denoiser is None:
            return audio_int16
        
        try:
            # 重採樣到 48kHz
            audio_48k = self._resample_to_48k(audio_int16)
            
            # 轉 float32
            audio_float = audio_48k.astype(np.float32) / 32768.0
            
            # 降噪
            denoised_float = self.denoiser.denoise_frame(audio_float)
            
            # 轉回 int16
            audio_denoised_48k = (denoised_float * 32768.0).astype(np.int16)
            
            # 重採樣回 16kHz
            audio_denoised_16k = self._resample_to_16k(audio_denoised_48k)
            
            return audio_denoised_16k
            
        except Exception as e:
            return audio_int16
    
    def _resample_to_48k(self, audio_16k):
        """16kHz → 48kHz"""
        num_samples = int(len(audio_16k) * 48000 / 16000)
        return signal.resample(audio_16k, num_samples).astype(np.int16)
    
    def _resample_to_16k(self, audio_48k):
        """48kHz → 16kHz"""
        num_samples = int(len(audio_48k) * 16000 / 48000)
        return signal.resample(audio_48k, num_samples).astype(np.int16)
    
    def reset(self):
        """重置狀態"""
        if self.available and self.denoiser is not None:
            try:
                self.denoiser = RNNoise(sample_rate=self.sample_rate)
            except:
                pass


# ==================== WebRTC VAD ====================
class WebRTCVAD:
    """WebRTC VAD 處理器"""
    
    def __init__(self, sample_rate=16000, aggressiveness=1):
        self.sample_rate = sample_rate
        self.vad = webrtcvad.Vad()
        self.vad.set_mode(aggressiveness)
        print(f"✅ WebRTC VAD 已初始化（激進度: {aggressiveness}）")
    
    def is_speech(self, audio_int16):
        """判斷是否為語音"""
        try:
            frame_length = int(self.sample_rate * Config.FRAME_DURATION_MS / 1000)
            
            if len(audio_int16) != frame_length:
                audio_int16 = self._adjust_frame_size(audio_int16, frame_length)
            
            is_speech = self.vad.is_speech(
                audio_int16.tobytes(),
                sample_rate=self.sample_rate
            )
            
            return is_speech
            
        except Exception as e:
            # 降級到能量檢測
            energy = np.mean(np.abs(audio_int16))
            return energy > Config.MIN_ENERGY_THRESHOLD
    
    def _adjust_frame_size(self, audio, target_length):
        """調整幀大小"""
        if len(audio) < target_length:
            return np.pad(audio, (0, target_length - len(audio)), mode='constant')
        else:
            return audio[:target_length]


# ==================== 音訊緩衝區 ====================
class AudioBuffer:
    """音訊緩衝區"""
    
    def __init__(self):
        self.buffer = []
        self.lock = threading.Lock()
    
    def add(self, data):
        """添加數據"""
        with self.lock:
            self.buffer.append(data)
    
    def get_array(self):
        """獲取完整音訊"""
        with self.lock:
            if not self.buffer:
                return np.array([], dtype='int16')
            return np.concatenate(self.buffer)
    
    def clear(self):
        """清空"""
        with self.lock:
            self.buffer.clear()
    
    def get_duration(self):
        """獲取時長"""
        audio = self.get_array()
        return len(audio) / Config.SAMPLE_RATE


# ==================== 智能錄音器 ====================
class SmartAudioRecorder:
    """智能錄音器（RNNoise + WebRTC VAD + Enter控制 + 超時）"""
    
    def __init__(self):
        """初始化"""
        # 降噪器
        if Config.ENABLE_RNNOISE and Config.RNNOISE_IN_CALLBACK:
            self.denoiser = RNNoiseProcessor(Config.SAMPLE_RATE)
        else:
            self.denoiser = None
        
        # VAD
        self.vad = WebRTCVAD(
            Config.SAMPLE_RATE,
            Config.WEBRTC_AGGRESSIVENESS
        )
        
        # 緩衝區
        self.speech_buffer = AudioBuffer()
        self.pre_buffer = deque(maxlen=Config.PRE_SPEECH_FRAMES)
        
        # 狀態
        self.is_recording = False
        self.is_speaking = False
        self.consecutive_speech = 0
        self.consecutive_silence = 0
        self.stream = None
        self.start_time = None
        
        # ✅ 超時控制
        self.stop_event = threading.Event()
        self.monitor_thread = None
        
        # 統計
        self.total_frames = 0
        self.speech_frames = 0
    
    def _callback(self, indata, frames, time_info, status):
        """音訊回調"""
        if status:
            print(f"⚠️  {status}")
        
        if not self.is_recording:
            return
        
        self.total_frames += 1
        
        # 轉 int16
        audio_frame = indata.flatten().astype('int16')
        
        # 降噪
        if self.denoiser:
            audio_frame = self.denoiser.process_frame(audio_frame)
        
        # VAD 判斷
        is_speech = self.vad.is_speech(audio_frame)
        
        # 狀態機
        self._handle_speech_state(audio_frame, is_speech)
    
    def _handle_speech_state(self, audio_frame, is_speech):
        """狀態機處理"""
        
        if is_speech:
            self.consecutive_speech += 1
            self.consecutive_silence = 0
            self.speech_frames += 1
            
            # 語音開始
            if not self.is_speaking:
                if self.consecutive_speech >= Config.SPEECH_START_FRAMES:
                    self.is_speaking = True
                    print(f"🗣️  語音開始（幀 {self.total_frames}）")
                    
                    # 加入前導緩衝
                    for pre_frame in self.pre_buffer:
                        self.speech_buffer.add(pre_frame)
                    
                    self.pre_buffer.clear()
            
            # 保存語音
            self.speech_buffer.add(audio_frame)
            self.pre_buffer.append(audio_frame)
        
        else:  # 非語音
            self.consecutive_silence += 1
            self.consecutive_speech = 0
            
            # 語音可能結束
            if self.is_speaking:
                # 保存後導
                if self.consecutive_silence <= Config.POST_SPEECH_FRAMES:
                    self.speech_buffer.add(audio_frame)
                
                # 確認結束
                elif self.consecutive_silence >= Config.SPEECH_END_FRAMES:
                    self.is_speaking = False
                    duration = self.speech_buffer.get_duration()
                    print(f"🔇 語音結束（時長: {duration:.2f}s）")
                    
                    # ✅ 語音結束後自動停止
                    self.stop()
            
            else:
                # 維護前導緩衝
                self.pre_buffer.append(audio_frame)
    
    def _monitor_timeout(self):
        """監控超時（獨立線程）"""
        # ✅ 等待停止事件或超時
        timeout_reached = not self.stop_event.wait(
            timeout=Config.MAX_RECORDING_DURATION
        )
        
        if timeout_reached and self.is_recording:
            print(f"\n⏱️  達到 {Config.MAX_RECORDING_DURATION} 秒，自動停止")
            self.stop()
    
    def start(self):
        """開始錄音"""
        if self.is_recording:
            print("⚠️  已在錄音中")
            return
        
        print(f"🎤 開始錄音（最長 {Config.MAX_RECORDING_DURATION} 秒）")
        
        # 重置狀態
        self.is_recording = True
        self.is_speaking = False
        self.consecutive_speech = 0
        self.consecutive_silence = 0
        self.total_frames = 0
        self.speech_frames = 0
        self.start_time = time.time()
        self.stop_event.clear()
        
        # 清空緩衝
        self.speech_buffer.clear()
        self.pre_buffer.clear()
        
        # 重置降噪器
        if self.denoiser:
            self.denoiser.reset()
        
        # 開啟音訊流
        try:
            frame_length = int(Config.SAMPLE_RATE * Config.FRAME_DURATION_MS / 1000)
            
            self.stream = sd.InputStream(
                callback=self._callback,
                channels=Config.CHANNELS,
                samplerate=Config.SAMPLE_RATE,
                dtype=Config.DTYPE,
                blocksize=frame_length
            )
            self.stream.start()
            
            # ✅ 啟動監控線程
            self.monitor_thread = threading.Thread(target=self._monitor_timeout)
            self.monitor_thread.daemon = True
            self.monitor_thread.start()
            
        except Exception as e:
            print(f"❌ 錄音啟動失敗: {e}")
            self.is_recording = False
    
    def stop(self):
        """停止錄音"""
        if not self.is_recording:
            return
        
        self.is_recording = False
        self.stop_event.set()  # ✅ 觸發停止事件
        
        # 停止音訊流
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        
        # 等待監控線程
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=1)
        
        duration = time.time() - self.start_time
        speech_duration = self.speech_buffer.get_duration()
        
        print(f"⏹️  錄音停止")
        print(f"   總時長: {duration:.1f}s")
        print(f"   語音段: {speech_duration:.1f}s")
        if self.total_frames > 0:
            print(f"   語音幀率: {self.speech_frames/self.total_frames*100:.1f}%")
    
    def get_speech(self):
        """獲取語音段"""
        return self.speech_buffer.get_array()
    
    def is_active(self):
        """是否正在錄音"""
        return self.is_recording


# ==================== Whisper STT ====================
class FasterWhisperSTT:
    """faster-whisper 語音轉文字"""
    
    def __init__(self, model_size="base", device="cpu", compute_type="int8", language="zh"):
        self.language = language
        self.model = None
        self._load_model(model_size, device, compute_type)
    
    def _load_model(self, model_size, device, compute_type):
        """載入模型"""
        try:
            print(f"⏳ 載入 Whisper 模型: {model_size}")
            
            self.model = WhisperModel(
                model_size,
                device=device,
                compute_type=compute_type
            )
            
            print("✅ Whisper 已載入")
            
        except Exception as e:
            print(f"❌ Whisper 載入失敗: {e}")
            self.model = None
    
    def transcribe(self, audio_int16):
        """轉錄音訊"""
        if self.model is None:
            return ""
        
        try:
            # 轉 float32
            audio_float32 = audio_int16.astype(np.float32) / 32768.0
            
            # 轉錄
            start_time = time.time()
            segments, info = self.model.transcribe(
                audio_float32,
                language=self.language,
                beam_size=5,
                vad_filter=False,
                without_timestamps=True
            )
            
            text = "".join([segment.text for segment in segments]).strip()
            
            elapsed = time.time() - start_time
            print(f"⏱️  轉錄耗時: {elapsed:.2f} 秒")
            
            return text
            
        except Exception as e:
            print(f"❌ 轉錄錯誤: {e}")
            return ""


# ==================== 主系統 ====================
class VoiceAssistant:
    """語音助理主系統"""
    
    def __init__(self):
        """初始化"""
        print("\n" + "="*60)
        print("桌遊語音助理 - 完整系統")
        print("="*60)
        
        # 建立日誌目錄
        Config.LOG_DIR.mkdir(exist_ok=True)
        
        # 初始化組件
        self.recorder = SmartAudioRecorder()
        self.stt = FasterWhisperSTT(
            Config.WHISPER_MODEL,
            Config.WHISPER_DEVICE,
            Config.WHISPER_COMPUTE_TYPE,
            Config.WHISPER_LANGUAGE
        )
        
        Config.print_config()
    
    def process_speech(self):
        """處理語音"""
        print("\n" + "-"*60)
        print("⚙️  處理語音...")
        
        # 獲取語音段
        audio_int16 = self.recorder.get_speech()
        
        if len(audio_int16) == 0:
            print("❌ 無語音數據")
            return None
        
        duration = len(audio_int16) / Config.SAMPLE_RATE
        print(f"📊 語音時長: {duration:.2f} 秒")
        
        # 後置驗證
        if not self._validate_speech(audio_int16):
            print("❌ 語音驗證失敗")
            return None
        
        # 轉錄
        print("🗣️  語音轉文字中...")
        text = self.stt.transcribe(audio_int16)
        
        if not text:
            print("❌ 轉錄失敗或無內容")
            return None
        
        print(f"✅ 辨識結果: {text}")
        
        # 除錯模式
        if Config.DEBUG_MODE:
            self._save_debug_audio(audio_int16, text)
        
        print("-"*60 + "\n")
        return text
    
    def _validate_speech(self, audio_int16):
        """後置驗證"""
        duration = len(audio_int16) / Config.SAMPLE_RATE
        
        # 時長檢查
        if duration < Config.MIN_SPEECH_DURATION:
            print(f"  ⚠️  語音太短: {duration:.2f}s")
            return False
        
        if duration > Config.MAX_SPEECH_DURATION:
            print(f"  ⚠️  語音太長: {duration:.2f}s")
            return False
        
        # 能量檢查
        energy = np.mean(np.abs(audio_int16))
        if energy < Config.MIN_ENERGY_THRESHOLD:
            print(f"  ⚠️  能量太低: {energy:.1f}")
            return False
        
        print(f"✅ 驗證通過（時長: {duration:.2f}s, 能量: {energy:.1f}）")
        return True
    
    def _save_debug_audio(self, audio_int16, text):
        """保存除錯音訊"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # 保存音訊
        audio_file = Config.LOG_DIR / f"speech_{timestamp}.wav"
        wavfile.write(audio_file, Config.SAMPLE_RATE, audio_int16)
        
        # 保存文字
        text_file = Config.LOG_DIR / f"text_{timestamp}.txt"
        with open(text_file, 'w', encoding='utf-8') as f:
            f.write(f"辨識結果: {text}\n")
            f.write(f"時長: {len(audio_int16)/Config.SAMPLE_RATE:.2f}s\n")
            f.write(f"降噪: {'開啟' if Config.ENABLE_RNNOISE else '關閉'}\n")
            f.write(f"VAD: WebRTC (mode={Config.WEBRTC_AGGRESSIVENESS})\n")
        
        print(f"💾 已保存: {audio_file.name}")
    
    def run(self):
        """運行主循環"""
        print("🎮 系統啟動")
        print("-"*60)
        print("操作說明:")
        print("  1. 按 Enter 開始錄音")
        print("  2. 按 Enter 停止錄音（或等待語音結束/超時）")
        print("  3. 輸入 'q' 退出")
        print("-"*60)
        
        try:
            while True:
                cmd = input("\n👉 ").strip().lower()
                
                if cmd == 'q':
                    print("👋 再見！")
                    break
                
                # 開始錄音
                self.recorder.start()
                
                # ✅ 等待停止（Enter 或自動）
                print("📍 錄音中... 按 Enter 停止")
                input()
                
                # 停止錄音
                self.recorder.stop()
                
                # 處理語音
                userAsk=self.process_speech()
                reply_text=""
                if userAsk:
                    reply_text = gemini_flash_test.try_cloud_LLM(userAsk)
                if reply_text:
                    asyncio.run(edgTTS.play_audio_stream(reply_text))
                    time.sleep(3)
        except KeyboardInterrupt:
            print("\n\n👋 程式中斷")
        
        finally:
            if self.recorder.is_active():
                self.recorder.stop()


# ==================== 主程式 ====================
def main():
    """主程式"""
    assistant = VoiceAssistant()
    assistant.run()


if __name__ == "__main__":
    main()