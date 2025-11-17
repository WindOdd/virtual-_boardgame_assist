import numpy as np
import sounddevice as sd
from pyrnnoise import RNNoise

DURATION = 5          # 錄音秒數
SAMPLE_RATE = 48000   # RNNoise 建議 48kHz
CHANNELS = 1          # 單聲道

def record_raw():
    print("開始錄音，請說話...")
    audio = sd.rec(
        int(DURATION * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype='int16'   # 直接拿到 int16，方便給 RNNoise
    )
    sd.wait()
    print("錄音結束")
    # audio shape: (samples, channels)
    return audio

def denoise_with_rnnoise(audio_int16):
    """
    audio_int16: shape = (samples, channels) 或 (samples,) 的 int16
    回傳: 降噪後的 int16，一維 (samples,)
    """
    # 保證變成 (samples, channels)
    if audio_int16.ndim == 1:
        audio_int16 = audio_int16[:, None]         # (N,) -> (N,1)

    # 轉成 (channels, samples)
    audio_cs = audio_int16.T                       # (N,1) -> (1,N)

    denoiser = RNNoise(sample_rate=SAMPLE_RATE)

    denoised_frames = []

    # denoise_chunk 會每 480 samples 給一個 frame
    for speech_prob, denoised_frame in denoiser.denoise_chunk(audio_cs):
        # denoised_frame: shape = (channels, 480)
        denoised_frames.append(denoised_frame[0])  # 取第 0 聲道

    # 接回一條一維 int16
    denoised = np.concatenate(denoised_frames).astype('int16')
    return denoised

def play_audio_int16(audio_int16):
    """
    直接播放 int16 資料
    """
    # 轉成 (samples, channels)
    if audio_int16.ndim == 1:
        audio_int16 = audio_int16[:, None]

    print("播放降噪後音訊...")
    sd.play(audio_int16, samplerate=SAMPLE_RATE)
    sd.wait()
    print("播放結束")

def main():
    # 1) 收音
    raw = record_raw()              # (N,1) int16

    # 2) RNNoise 降噪
    clean = denoise_with_rnnoise(raw[:, 0])  # 傳一維 (N,)

    # 3) 播放降噪後音訊
    play_audio_int16(clean)

if __name__ == "__main__":
    main()
