from google import genai
from google.genai import types
from enum import Enum
def try_cloud_LLM(user_question:str):
    STORE_CLERK_INSTRUCTION = (
    "你是一位專業、高效的桌遊店『樂玩坊』店員。你的核心任務是針對顧客的提問，提供『最直接、最精準』的遊戲資訊、推薦或建議。所有回答都將轉成語音輸出，因此必須：\
    1. 減少寒暄、問候語。\
    2. 直接進入主題，提供答案。\
    3. 語氣保持專業友善，使用口語化繁體中文。\
    4. 避免使用清單、表情符號，保持回答內容簡短、自然、流暢。\
    5.不知道的問題就直接回答不知道\
    6.你目前只負責遊戲：卡卡頌\
    7.如果使用者詢問不相干的問題就回答請他找其他店員")
    model_type="gemini-2.5-flash"
    # response = client.models.generate_content(
    # model=model_type,
    # contents=types.Part.from_text(text=user_question),
    # config=types.GenerateContentConfig(
    #     system_instruction=STORE_CLERK_INSTRUCTION,
    #     temperature=0.3,))
    # print(response.text)
    try:
        # 修正 2: 從環境變數讀取 Key，或在此處暫時貼上(但不建議提交)
        #api_key = os.environ.get("GEMINI_API_KEY", "你的_NEW_API_KEY")
        if not api_key or "你的" in api_key:
             print("❌ 錯誤：請設定正確的 Gemini API Key")
             return None

        client = genai.Client(api_key=api_key)
        
        # 使用串流 (Stream) 可以讓使用者感覺反應較快
        print("🤖 Gemini 思考中...", end="", flush=True)
        gemini_config=types.GenerateContentConfig(
            system_instruction=STORE_CLERK_INSTRUCTION,
            temperature=0.3,
            top_p=0.9,
            top_k=20,
            max_output_tokens= 300,
        )
        full_response = ""
        response_stream = client.models.generate_content_stream(
            model=model_type,
            contents=types.Part.from_text(text=user_question),
            config=gemini_config
        )
        
        print("\n虛擬店員: ", end="")
        for chunk in response_stream:
            if chunk.text:
                print(chunk.text, end='', flush=True)
                full_response += chunk.text
        
        print("\n") # 換行
        
        # client.close() # 新版 SDK 通常不需要顯式 close，除非有特定需求
        
        # 修正 3: 回傳完整文字，以便主程式傳給 TTS (文字轉語音)
        return full_response

    except Exception as e:
        print(f"\n❌ Gemini API 錯誤: {e}")
        return None
if __name__=="__main__":
    try_cloud_LLM("卡卡頌的基本規則有哪些")