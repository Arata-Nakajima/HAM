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
import pytz
import random
import logging
from gtts import gTTS
from pathlib import Path
from google import genai
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
from playsound import playsound
from datetime import datetime
from zoneinfo import ZoneInfo
from telegram.error import Conflict

chat_history_flag = True

logging.getLogger('telegram').setLevel(logging.CRITICAL)
logging.getLogger('telegram.ext').setLevel(logging.CRITICAL)

def replace_line_in_file(filename, target_string, new_line):
    with open(filename, 'r', encoding='utf-8') as file:
        lines = file.readlines()

    for i, line in enumerate(lines):
        if target_string in line:
            lines[i] = new_line + '\n'  # 必要に応じて改行を追加

    with open(filename, 'w', encoding='utf-8') as file:
        file.writelines(lines)

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

def get_speakers():
    url = "http://localhost:50021/speakers"  # Voicevoxが動いているAPIエンドポイント
    response = requests.get(url)
    if response.status_code == 200:
        speakers = response.json()
        for speaker in speakers:
            name = speaker['name']  # キャラクター名
            style_names = [style['name'] for style in speaker['styles']]  # スタイル名
            style_ids = [style['id'] for style in speaker['styles']]  # スタイルID
            for style_id, style_name in zip(style_ids, style_names):
                print(f"Speaker: {name}, Style: {style_name}, ID: {style_id}")
    else:
        print(f"Error: {response.status_code}")

async def summarize_conversation():
    with open("summarize.txt", "r", encoding="utf-8") as file:
        summarize = file.read()
    with open("chat_history.txt", "r", encoding="utf-8") as file:
        chat_history = file.read()
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents = summarize + chat_history
    )
    print("\n", response.text)
    with open("summary.txt", "w", encoding="utf-8") as f:
        f.write(response.text)

async def read_emotion( input_message ):
    with open("emotion.txt", "r", encoding="utf-8") as file:
        emotion = file.read()
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents = emotion + input_message
    )
    print("\n", response.text)
    #await update.message.reply_text(f"{response.text}")

# メッセージを受け取ったときの処理関数
async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):

    global chat_history_flag

    input_message = update.message.text  # 受け取ったテキスト
    print(f"\n Received message:", input_message)

    await read_emotion( input_message )

    if input_message == "chat history on" :
        chat_history_flag = True
    elif input_message == "chat history off" :
        chat_history_flag = False
    else :
        with open("chat_history.txt", "a", encoding="utf-8") as f:
            f.write("[新の発言]:")
            f.write(input_message)
            f.write("\n")

        with open("master_simple.txt", "r", encoding="utf-8") as file:
            master = file.read()

        with open("chat_history.txt", "r", encoding="utf-8") as file:
            raw_text = file.read()

        if len( raw_text ) > 1200 :
            chat_history = raw_text[-1200:] # 1200 letter FIFO
            with open("chat_history.txt", "w", encoding="utf-8") as file:
                file.write(chat_history)
        else :
            chat_history = raw_text

        await summarize_conversation()
        with open("summary.txt", "r", encoding="utf-8") as file:
            summary = file.read()

        if chat_history_flag :
            #all_prompt = master + chat_history + input_message
            all_prompt = master + summary + input_message 
            #all_prompt = master + summary 
        else :
            all_prompt = master + input_message

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents = all_prompt
        )
        print("\n", response.text)

        with open("chat_history.txt", "a", encoding="utf-8") as f:
            f.write("[萌夏の発言]:")
            f.write(response.text)
            f.write("\n")

        await update.message.reply_text(f"{response.text}")
        speaker = 0 #四国めたん　あまあま
        #speaker = 58 #猫使 ノーマル
        #get_speakers()
        voicevox_synthesize_and_play(response.text, speaker, speedScale = 1.0, pitchScale = 0.0, intonationScale = 1.0)

async def scheduled_task(context: ContextTypes.DEFAULT_TYPE):

    global chat_history_flag
    chat_id = '351535857'

    now = datetime.now(ZoneInfo("Asia/Tokyo"))
    cur_date_and_time = f'- 現在の日付は{now.year}年{now.month}月{now.day}日{now.hour}時{now.minute}分'
    replace_line_in_file('master_simple.txt', '- 現在の日付は', cur_date_and_time)

    if 8 < now.hour or now.hour < 2 :

        with open("master_simple.txt", "r", encoding="utf-8") as file:
            master = file.read()

        with open("small_talk.txt", "r", encoding="utf-8") as file:
            seed_message = file.read()

        with open("chat_history.txt", "r", encoding="utf-8") as file:
            chat_history = file.read()

        if chat_history_flag :
            all_prompt = master + chat_history + seed_message
        else :
            all_prompt = master + seed_message

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents = all_prompt
        )
        print("\n", response.text)
        await context.bot.send_message( chat_id=chat_id, text = response.text )
        speaker = 0 #四国めたん　あまあま
        voicevox_synthesize_and_play(response.text, speaker, speedScale = 1.0, pitchScale = 0.0, intonationScale = 1.0)

async def main():
    app = ApplicationBuilder().token("8373144974:AAE5ZMIPGZ740oqf4lSWm3cQyVKUyGRIXNw").build()

    await app.initialize()
    # メッセージハンドラを登録（テキストメッセージのみ処理）
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), echo))

    #time_target = datetime.time(hour = 23, minute = 4, second = 0, tzinfo=ZoneInfo('Asia/Tokyo'))
    #app.job_queue.run_daily(scheduled_task, time_target)
    app.job_queue.run_repeating(scheduled_task, interval = random.randint( 3600, 7200 ))

    await app.run_polling(drop_pending_updates=True)
    #try :
    #    await app.run_polling(drop_pending_updates=True)
    #    pass
    #except Conflict :
    #    pass

if __name__ == "__main__":
    api_key = os.getenv("GEMINI_API_KEY")
    client = genai.Client(api_key=api_key)

    #with open("master.txt", "r", encoding="utf-8") as file:
    #    master_prompt = file.read()

    asyncio.run(main())