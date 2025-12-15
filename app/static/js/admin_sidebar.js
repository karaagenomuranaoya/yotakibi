// 管理者サイドバー用スクリプト

document.addEventListener('DOMContentLoaded', () => {
    // 起動時に描画
    renderPins();
    updateButtons();

    // 動的にボタンのイベントをキャッチ（イベント委譲）
    document.body.addEventListener('click', (e) => {
        if (e.target.classList.contains('pin-toggle-trigger')) {
            handlePinClick(e.target);
        }
    });
});

// サイドバー開閉
function toggleSidebar() {
    const sidebar = document.getElementById('pin-sidebar');
    if(sidebar) sidebar.classList.toggle('active');
}

// クリック時のデータ処理
function handlePinClick(btn) {
    const data = btn.dataset;
    const flags = {
        is_timeline_public: data.tl === 'True',
        is_aikotoba_public: data.tlKey === 'True',
        allow_sns_share: data.sns === 'True',
        allow_aikotoba_sns: data.snsKey === 'True'
    };
    
    togglePin(data.id, data.content, data.aikotoba, flags);
}

// 保存・削除ロジック
function togglePin(id, content, aikotoba, flags) {
    let pins = JSON.parse(localStorage.getItem('yotakibi_pins') || '[]');
    id = String(id);
    
    const existingIndex = pins.findIndex(p => String(p.id) === id);

    if (existingIndex >= 0) {
        pins.splice(existingIndex, 1); // 削除
    } else {
        // 新規追加
        pins.push({ 
            id, 
            content, 
            aikotoba, 
            flags, 
            added_at: new Date().toISOString() 
        });
        const sidebar = document.getElementById('pin-sidebar');
        if(sidebar) sidebar.classList.add('active'); // 自動で開く
    }

    localStorage.setItem('yotakibi_pins', JSON.stringify(pins));
    renderPins();
    updateButtons();
}

// 描画ロジック
function renderPins() {
    const listEl = document.getElementById('pin-list');
    if (!listEl) return;

    const pins = JSON.parse(localStorage.getItem('yotakibi_pins') || '[]');
    listEl.innerHTML = '';

    if (pins.length === 0) {
        listEl.innerHTML = '<div class="pin-empty-msg">クリップボードは空です</div>';
        return;
    }

    // 設定divから検索用URLを取得
    const configEl = document.getElementById('admin-js-config');
    const searchBaseUrl = configEl ? configEl.dataset.searchUrl : '/search?q=';

    pins.forEach(pin => {
        const div = document.createElement('div');
        div.className = 'pin-card';
        
        const f = pin.flags || {};
        const badge = (label, isOn) => `
            <div class="pin-badge ${isOn ? 'active' : 'inactive'}">
                <span>${label}</span> <span>${isOn ? 'ON' : 'OFF'}</span>
            </div>`;

        // URL生成
        const idSearchUrl = `${searchBaseUrl}%23${pin.id}`;
        const keySearchUrl = `${searchBaseUrl}${encodeURIComponent(pin.aikotoba)}`;

        div.innerHTML = `
            <div class="pin-row-header">
                <a href="${idSearchUrl}" class="pin-id-link">#${pin.id} の詳細へ</a>
                <a href="${keySearchUrl}" class="pin-aikotoba-btn" title="この種火で検索">🔥 ${pin.aikotoba}</a>
            </div>
            <div class="pin-badges-grid">
                ${badge('TL公開', f.is_timeline_public)}
                ${badge('TL種火', f.is_aikotoba_public)}
                ${badge('SNS共有', f.allow_sns_share)}
                ${badge('SNS種火', f.allow_aikotoba_sns)}
            </div>
            <textarea rows="4" readonly onclick="this.select()">${pin.content}</textarea>
            <div class="pin-actions">
                <button class="pin-btn-action" onclick="copyPinText(this)">Copy</button>
                <button class="pin-btn-action pin-btn-delete" onclick="removePin('${pin.id}')">削除</button>
            </div>
        `;
        listEl.appendChild(div);
    });
}

// ボタンの状態更新（タイムライン側）
function updateButtons() {
    const pins = JSON.parse(localStorage.getItem('yotakibi_pins') || '[]');
    const pinnedIds = pins.map(p => String(p.id));

    document.querySelectorAll('.pin-toggle-trigger').forEach(btn => {
        const id = btn.dataset.id;
        if (pinnedIds.includes(id)) {
            btn.classList.add('pinned');
            btn.textContent = '✅ kept';
        } else {
            btn.classList.remove('pinned');
            btn.textContent = '📌 keep';
        }
    });
}

// ユーティリティ
function removePin(id) {
    togglePin(id); 
}

function clearPins() {
    if (confirm('クリップボードを全て空にしますか？')) {
        localStorage.removeItem('yotakibi_pins');
        renderPins();
        updateButtons();
    }
}

function copyPinText(btn) {
    const textarea = btn.parentElement.previousElementSibling;
    textarea.select();
    document.execCommand('copy');
    const original = btn.textContent;
    btn.textContent = 'Copied!';
    setTimeout(() => btn.textContent = original, 1000);
}