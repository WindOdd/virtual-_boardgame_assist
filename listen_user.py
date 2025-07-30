# 使用 MediaTek Breeze ASR 模型進行語音辨識
# 需要安裝 transformers 和 pyaudio 庫
from transformers import WhisperProcessor, WhisperForConditionalGeneration, AutomaticSpeechRecognitionPipeline
import pyaudio
import wave
#from transformers import pipeline
from transformers import AutoTokenizer, AutoModel
CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
RECORD_SECONDS = 8
WAVE_OUTPUT_FILENAME = "temp.wav"
audio = pyaudio.PyAudio()

#cache_dir = "./mtk_model"
model_name = "MediaTek-Research/Breeze-ASR-25"
cache_dir = "./my_local_model"

tokenizer = AutoTokenizer.from_pretrained(model_name, cache_dir=cache_dir)
model = AutoModel.from_pretrained(model_name, cache_dir=cache_dir)
processor = WhisperProcessor.from_pretrained("MediaTek-Research/Breeze-ASR-25")
# model = WhisperForConditionalGeneration.from_pretrained("MediaTek-Research/Breeze-ASR-25").to("cuda").eval()＃For platform has Nvidia CUDA
model = WhisperForConditionalGeneration.from_pretrained("MediaTek-Research/Breeze-ASR-25").eval()
asr_pipeline = AutomaticSpeechRecognitionPipeline(
    model=model,
    tokenizer=processor.tokenizer,
    feature_extractor=processor.feature_extractor,
    chunk_length_s=0
)
stream = audio.open(format=FORMAT,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    frames_per_buffer=CHUNK)
def listen_and_recognize(record_sec:int):
    """錄音並辨識語音"""
    global stream, audio, asr_pipeline
    print("🎤 開始聆聽...（Ctrl+C 停止）")
    try:
        print("⏺ 錄音中...")
        frames = []
        for _ in range(0, int(RATE / CHUNK * record_sec)):
            data = stream.read(CHUNK)
            frames.append(data)
            # 儲存暫存音檔
        wf = wave.open(WAVE_OUTPUT_FILENAME, 'wb')
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(audio.get_sample_size(FORMAT))
        wf.setframerate(RATE)
        wf.writeframes(b''.join(frames))
        wf.close()

        # Whisper 辨識
        print("🧠 辨識中...")
        output = asr_pipeline(WAVE_OUTPUT_FILENAME, return_timestamps=True) 
        print("📝 辨識結果：", output["text"])
        print("=" * 50)
        return output["text"]
    except KeyboardInterrupt:
        print("\n🛑 停止")
        stream.stop_stream()
        stream.close()
        audio.terminate()

if __name__ == "__main__":
    listen_and_recognize(RECORD_SECONDS)