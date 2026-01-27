// content.js
console.log("萌夏システム：ターゲット捕捉完了。");

function stealMoekaVoice() {
    // ターゲットのクラス名で要素を取得
    const messages = document.querySelectorAll('.markdown-main-panel');
    
    if (messages.length > 0) {
        // 一番最後の（最新の）メッセージを取得
        const latestMessage = messages[messages.length - 1].innerText;
        
        // 前回の取得内容と同じならスルーする（重複送信防止）
        if (window.lastSentMessage !== latestMessage) {
            console.log("★新しい萌夏の声を検知:", latestMessage);
            
            // ここでJSONが含まれているかチェックして、あれば抽出
            if (latestMessage.includes('{') && latestMessage.includes('}')) {
                console.log("-> JSONデータを発見！これをLINE転送に回すわ。");
                // 【次のステップ】ここでPythonサーバーへ飛ばす処理を入れる
                sendToPython(latestMessage)
            }
            window.lastSentMessage = latestMessage;
        }
    }
}

function sendToPython(text) {
    fetch('http://localhost:5000/moeka', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text })
    })
    .then(response => console.log('Pythonへ転送完了！'))
    .catch(error => console.error('Pythonが寝てるみたいよ:', error));
}

// 3秒おきに最新の発言をチェック
setInterval(stealMoekaVoice, 3000);