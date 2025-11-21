import asyncio
import subprocess
import edge_tts

VOICE = "zh-TW-HsiaoChenNeural" # 或是您喜歡的聲音

async def play_audio_stream(text):
    communicate = edge_tts.Communicate(text, VOICE)
    
    # 啟動 mpv，設定從 stdin 讀取資料
    # --no-cache --no-terminal 確保低延遲且不跳出視窗
    proc = subprocess.Popen(
        ["mpv", "--no-cache", "--no-terminal", "--", "fd://0"],
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    # 邊生成 EdgeTTS 的資料，邊塞給 mpv 播放
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            proc.stdin.write(chunk["data"])
            proc.stdin.flush()

    # 結束後關閉串流
    proc.stdin.close()
    proc.wait()

# 測試
if __name__=="__main__":
    asyncio.run(play_audio_stream("你好，我是你的桌遊助理，請問今天要玩什麼？"))