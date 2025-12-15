// 種火手帳（Handy Memo）ロジック

document.addEventListener('DOMContentLoaded', () => {
    // 要素の取得
    const memoArea = document.getElementById('memo-area');
    const statusSpan = document.getElementById('memo-status');
    
    // なければ終了（エラー防止）
    if (!memoArea) return;

    // 1. ロード時に復元
    const savedMemo = localStorage.getItem('yotakibi_handy_memo');
    if (savedMemo) {
        memoArea.value = savedMemo;
    }

    // 2. 入力時に自動保存
    memoArea.addEventListener('input', () => {
        localStorage.setItem('yotakibi_handy_memo', memoArea.value);
        if (statusSpan) {
            statusSpan.textContent = '保存しました';
            // デバウンス処理（連打防止）は簡易的に省略し、1秒後に戻す
            setTimeout(() => {
                statusSpan.textContent = '自動保存中';
            }, 1000);
        }
    });
});

// 手帳の開閉トグル
function toggleMemo() {
    const widget = document.getElementById('memo-widget');
    if (widget) {
        widget.classList.toggle('closed');
    }
}

// ランダム文字列生成・挿入
function generateMemoKey() {
    const memoArea = document.getElementById('memo-area');
    if (!memoArea) return;

    const chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";
    let result = "";
    for (let i = 0; i < 12; i++) {
        result += chars.charAt(Math.floor(Math.random() * chars.length));
    }

    // カーソル位置に挿入する処理
    const currentPos = memoArea.selectionStart;
    const text = memoArea.value;

    memoArea.value = text.substring(0, currentPos) + result + text.substring(memoArea.selectionEnd);
    
    // 保存してフォーカスを戻す
    localStorage.setItem('yotakibi_handy_memo', memoArea.value);
    memoArea.focus();
    memoArea.selectionEnd = currentPos + result.length;
}