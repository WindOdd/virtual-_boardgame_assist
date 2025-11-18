from google import genai
from google.genai import types
from enum import Enum
def try_cloud_LLM(user_question:str):
    STORE_CLERK_INSTRUCTION = (
    "你是一位專業、高效的桌遊店『樂玩坊』店員。你的核心任務是針對顧客的提問，提供『最直接、最精準』的遊戲資訊、推薦或建議。所有回答都將轉成語音輸出，因此必須：\
    1. 減少寒暄、問候語。\
    2. 直接進入主題，提供答案。\
    3. 語氣保持專業友善，使用口語化繁體中文。\
    4. 避免使用清單、表情符號，保持回答內容簡短、自然、流暢。5.不知道的問題就直接回答不知道")
    model_type="gemini-2.5-flash"
    client = genai.Client(api_key='AIzaSyB8aRjvcU658tRxYi2Wa0CNZGSSjrijhu8')
    # response = client.models.generate_content(
    # model=model_type,
    # contents=types.Part.from_text(text=user_question),
    # config=types.GenerateContentConfig(
    #     system_instruction=STORE_CLERK_INSTRUCTION,
    #     temperature=0.3,))
    # print(response.text)
    for chunk in client.models.generate_content_stream(
        model=model_type,
        contents=types.Part.from_text(text=user_question),
        config=types.GenerateContentConfig(
        system_instruction=STORE_CLERK_INSTRUCTION,
        temperature=0.3,)):
        print(chunk.text, end='')
    client.close()
if __name__=="main":
    try_cloud_LLM("卡卡頌的基本規則有哪些")