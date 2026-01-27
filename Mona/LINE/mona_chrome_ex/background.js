// Service Workerを叩き起こし続けるためのアラーム設定
chrome.alarms.create('keepAlive', { periodInMinutes: 1 });

chrome.alarms.onAlarm.addListener(alarm) => {
  if (alarm.name === 'keepAlive') {
    // ログを出すだけでService Workerの寿命がわずかに延びるわ
    console.log('Mona is watching you... (Keep-alive)');
  }
});

// メッセージ受信リスナー
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  // 重要：非同期処理(fetch)を即座に実行する即時関数
  (async () => {
    try {
      const response = await fetch('http://127.0.0.1:5000/moeka', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          message: message.text || "空のメッセージよ",
          timestamp: new Date().toISOString()
        })
      });

      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
      
      const result = await response.json();
      sendResponse({ status: 'success', data: result });
    } catch (error) {
      console.error('Fetch error:', error);
      sendResponse({ status: 'error', message: error.toString() });
    }
  })();

  // ★超重要：これを返さないと、fetchが終わる前にプロセスが殺されるわ！
  return true; 
});
