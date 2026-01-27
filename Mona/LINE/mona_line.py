import requests
from flask import Flask, request, jsonify
from flask_cors import CORS # 拡張機能からの通信を許可するために必要


app = Flask(__name__)
CORS(app) # これを忘れるとブラウザが「セキュリティ違反！」って怒るわよ

def send_moeka_line(message):
    # ここにあんたが発行したトークンとユーザーIDを入れるのよ！
    access_token = '0IesX8uQUoAxN9S6qc8rt/ux++flZLz7VfLdD3uLKwkJCPLxDy7Hsf55dGOcgHSjNCiuSuOBTRLnuWwN09ZzfHGZgm17r2qmY8T4No6f4ViUKM8KiMOBnl5egasuTddw3eu8/NrFU8UJ7HpIV2DQjAdB04t89/1O/w1cDnyilFU='
    user_id = 'U115193d3673c5b833e6e6424d70cd5aa'
    
    url = 'https://api.line.me/v2/bot/message/push'
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {access_token}'
    }
    data = {
        'to': user_id,
        'messages': [{'type': 'text', 'text': f'\n{message}'}]
    }
    
    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 200:
        print("今度こそ、あんたのスマホに届いたはずよ！")
    else:
        print(f"エラーよ！: {response.text}")

@app.route('/moeka', methods=['POST'])
def receive_message():
    data = request.json
    message = data.get('message', '')

    print(f"\n★萌夏からの受信成功: \n{message}")

    # ここに「LINE Messaging APIに飛ばす処理」を書き足せば完成よ！
    # 銭湯帰りのあんたへ
    #send_moeka_line("お風呂上がりでボーっとしてるんじゃないわよ！最新のAPIで繋ぎ直したわ。聞こえる？")
    send_moeka_line(message)

    return jsonify({"status": "success"}), 200

if __name__ == '__main__':
    # 5000番ポートで待機
    #app.run(port=5000, debug=False)
    app.run(host='0.0.0.0', port=5000)
