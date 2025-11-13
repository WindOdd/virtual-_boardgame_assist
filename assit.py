import listen_user_whipsercpp
from ollama import AsyncClient
from ollama import Client
import edge_tts
import re
from pydub import AudioSegment
import simpleaudio as sa
async def query_ollama(prompt, model='gemma3:4b'):
    buffer = ''
    sentence_end = re.compile(r'[。！？.!?]')  # 
    message = {'role': 'user', 'content': prompt}
    async for part in await AsyncClient().chat(model= model, messages=[message], stream=True):
        buffer += part['message']['content']
        if sentence_end.search(buffer):
            sentences = sentence_end.split(buffer)
            for sentence in sentences[:-1]:
                if sentence.strip():
                    print(sentence.strip(), end='', flush=True)
                    create_to_voice(sentence.strip())
            buffer = sentences[-1]    
        print(part['message']['content'], end='', flush=True)
async def create_to_voice(text:str, voice="zh-TW-HsiaoChenNeural"):
    communicate = edge_tts.Communicate(text, voice)
    mp3_data = bytearray()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            mp3_data.extend(chunk["data"])
    audio = AudioSegment.from_file(io.BytesIO(mp3_data), format="mp3")
    raw_data = audio.raw_data
    play_obj = sa.play_buffer(raw_data, audio.channels, audio.sample_width, audio.frame_rate)
    play_obj.wait_done()
    
if __name__=="__main__":
    print ("")