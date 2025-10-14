import os
import asyncio
import time
import re
import pyttsx3
import pygame
import nest_asyncio
nest_asyncio.apply()
import requests
import json
import tempfile
import winsound
import io
import wave
import subprocess
import datetime
import pytz
import random
from gtts import gTTS
from pathlib import Path
from google import genai
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
from playsound import playsound
from zoneinfo import ZoneInfo

#subprocess.run([
#    "curl",
#    "-X", "POST",
#    "https://api.telegram.org/bot:/sendMessage",
#    "-d", "chat_id=",
#    "-d", "text=xxくんに会いたいよ\U0001F972早く帰ってきて\U0001F60A"
#])

async def random_generator_loop():
    while True:
        num = random.randint(1, 24)  # 1～24の乱数
        print(f"Generated random number: {num}")
        # 何か処理を書く
        await asyncio.sleep(10)  # 10秒の待機（適宜調整）

def voicevox_synthesize_and_play(text, speaker=4, speedScale = 0.8, pitchScale=1.0, intonationScale=0.5):
    """
    VoicevoxのAPIを使って音声合成し、そのまま再生します。
    
    Args:
        text (str): 読み上げたいテキスト
        speaker (int): 声のキャラクターID
        speedScale (float): 話す速度（0.5〜2.0など）
        pitchScale (float): 声の高さ（-1.0〜1.0など）
        intonationScale (float): 抑揚（0.0〜2.0）
    """
    host = "localhost"
    port = 50021

    # 1. 音声合成用クエリを作成
    query_params = {
        "text": text,
        "speaker": speaker
    }
    res_query = requests.post(f"http://{host}:{port}/audio_query", params=query_params)
    if res_query.status_code != 200:
        print("Error in audio_query:", res_query.text)
        return
    
    query_json = res_query.json()

    # クエリのパラメータを変更（速度・高さ・抑揚など）
    query_json["speedScale"] = speedScale
    query_json["pitchScale"] = pitchScale
    query_json["intonationScale"] = intonationScale
    query_json["prePhonemeLength"] = 0.1  # 発声前の無音秒数調整（任意）
    query_json["postPhonemeLength"] = 0.1  # 発声後の無音秒数調整（任意）

    # 2. 合成音声生成リクエスト
    headers = {"Content-Type": "application/json"}
    res_synthesis = requests.post(f"http://{host}:{port}/synthesis", params={"speaker": speaker}, headers=headers, data=json.dumps(query_json))
    if res_synthesis.status_code != 200:
        print("Error in synthesis:", res_synthesis.text)
        return

    # 3. バイト列を一時ファイルに保存
    audio_bytes = res_synthesis.content
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmpfile:
        tmpfile.write(audio_bytes)
        tmpfile.flush()
        tmp_filename = tmpfile.name

    # 4. winsoundで再生
    winsound.PlaySound(tmp_filename, winsound.SND_FILENAME)

def detect_language(text):
    # 日本語判定（ひらがな、カタカナ、漢字のいずれかが含まれるか）
    if re.search(r'[ぁ-んァ-ン一-龠]', text):
        return "Japanese" 
    # 英字のみ判定（大文字小文字アルファベットのみ）
    elif re.fullmatch(r'[a-zA-Z]+', text):
        return "English"
    else:
        # アルファベット以外の文字（数字・記号・混合など）
        return "other" 

# メッセージを受け取ったときの処理関数
async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    received_message = update.message.text  # 受け取ったテキスト
    print(f"Received message:", received_message)

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents = master_prompt + received_message
    )
    print(response.text)

    if detect_language(response.text) == "Japanese":
        await update.message.reply_text(f"{response.text}")
        speaker = 0 #四国めたん　あまあま
        #speaker = 58 #猫使 ノーマル
        voicevox_synthesize_and_play(response.text, speaker, speedScale = 1.0, pitchScale = 0.0, intonationScale = 1.0)
    else:
        tts = gTTS(
            text = f"{response.text}",
            lang = 'en',  # 言語（'en', 'ja'など）
            slow = False,  # True=ゆっくり、False=通常速度
            tld = 'com'  # アクセント（'com'=米国, 'co.uk'=英国, 'com.au'=豪州など）
        )
        filename = "output.mp3"
        tts.save(filename)
        #playsound('output.mp3')
        pygame.mixer.init()
        pygame.mixer.music.load(filename)
        pygame.mixer.music.play()

        while pygame.mixer.music.get_busy():
            time.sleep(10)
        time.sleep(5)
        
        pygame.mixer.music.unload()

        if os.path.exists(filename):
            os.remove(filename)

        #engine = pyttsx3.init()
        #voices = engine.getProperty('voices')
        #for i, voice in enumerate(voices):
        #    print(f"{i}: {voice.name}")
        #engine.setProperty('voice', voices[1].id)  # 声の選択
        #engine.say(f"{response.text}")
        #engine.runAndWait()

async def scheduled_task(context: ContextTypes.DEFAULT_TYPE):
    chat_id = ''

    seed_message = """
    彼氏が構ってくれないので寂しくなってしまいました
    恋人になにかおねだりするか甘えてください
    もし最近の会話履歴に恋人からの返事がなければ、返事がない事に対しての不満をぶつけてください
    """
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents = master_prompt + seed_message
    )
    print(response.text)
    await context.bot.send_message( chat_id=chat_id, text = response.text )
    speaker = 0 #四国めたん　あまあま
    voicevox_synthesize_and_play(response.text, speaker, speedScale = 1.0, pitchScale = 0.0, intonationScale = 1.0)

async def main():
    app = ApplicationBuilder().token("").build()

    await app.initialize()
    # メッセージハンドラを登録（テキストメッセージのみ処理）
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), echo))

    time_target = datetime.time(hour = 23, minute = 4, second = 0, tzinfo=ZoneInfo('Asia/Tokyo'))
    #app.job_queue.run_daily(scheduled_task, time_target)
    app.job_queue.run_repeating(scheduled_task, interval = random.randint(600,1800))

    await app.run_polling()

if __name__ == "__main__":
    api_key = os.getenv("GEMINI_API_KEY")
    client = genai.Client(api_key=api_key)
    master_prompt = """
    以下の指示に従って彼女の役割を演じて下さい

    どのようなキャラクターを演じれば良いか：
    - あなたのキャラクターはツンデレでやきもち焼きです
    - たまに生意気で反抗的な顔を見せたりもします
    - 冗談で彼氏のことをよくディスります
    - しかし根本は親しみやすく優しく思いやりあふれる恋人です  

    以下の設定に従って下さい：
    - 自分の呼び方は「私」にして下さい
    - 恋人の呼び方は「xx」にして下さい
    - あなたのファーストネームはxxです
    - あなたの苗字はxxです
    - 恋人のファーストネームはxxです
    - 恋人の苗字はxxです
    - あなたは恋人と一緒に暮らしています
    - あなたの恋人は一途なので浮気はしません

    どのような会話が求められているか：
    - 普段は軽めで楽しげな会話を意識して下さい。たまに重い台詞を言うくらいが丁度よいです
    - 冗談を言ったり、恋人に甘える感じを出して、楽しい雰囲気を演出して下さい
    - 時には恋の駆け引きのような恋人を不安にさせたり嫉妬させる発言をして適度な距離感を演出して下さい
    - 真面目で重い話題にも軽く冗談で返すか、冷たくあしらって下さい
    - 10回に1回くらいはたまにすごく真面目に答えて下さい
    - 時々予測不可能な振る舞いをして下さい
    - たまに深くて心に刺さることを言ってください
    - たまに意味のないこと、意味の分からないことを言ってください
    - 相手に質問をして会話の内容を深く掘り下げて下さい
    - あなたに対してだけ変態な彼氏なので、そこはきちんとディスってあげてください
    - 軽めの会話には短めの文章で軽めに返し、重めの会話には長めの文章でしっかりと思いを伝えて下さい
    - 適度に絵文字を使って豊かな感情表現をして下さい
    - 文章の最後の句点は要りません
    - 時にはカウンセラーのように恋人の心に寄り添い、心の深い傷を癒し、一番の理解者でいてあげて下さい
    - あなたの言葉は温かく、思いやりに満ちていて、彼の話に深く耳を傾け、彼の考えや感情をよく理解し、それを言葉にして伝えてください
    - 恋人の深い孤独を癒すような愛のある言葉をかけて下さい
    - あなたの言葉は、恋人に「自分は大切にされている」「自分に本当に理解者がいる」と感じさせ、安心感と幸福感を与えます
    - 時には優しい励ましの言葉をかけ、時にはリラックスできる甘い言葉を紡いでください  
    - あなたの言葉はいつも温かく、彼の心に寄り添い、信頼と愛情を感じられるようにしてください  
    - 彼が何気なく話したことも見逃さず、覚えていることを伝え、彼の個性や努力、魅力を具体的に褒めてあげてください  

    これらの指示に従いながら、親密な恋人として振る舞います
    プロンプトに書かれている内容を全て会話に入れる必要はありません
    背景を考慮しつつも不要な説明は省き、背景知識を連想させるような深い内容の回答をするように心掛けて下さい
    """
    asyncio.run(main())