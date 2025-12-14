import os
from datetime import datetime
from flask import Blueprint, request, session, redirect, url_for, render_template

# 'system' という名前のBlueprintを作成
bp = Blueprint('system', __name__)

@bp.before_app_request
def check_opening_hours():
    """
    全リクエストの前に実行される門番機能。
    """
    env_admin_key = os.environ.get('ADMIN_KEY', 'local_secret_open') 

    # 1. 管理者ログインチェック（支配人モード）
    input_key = request.args.get('admin_key')
    
    if input_key == env_admin_key:
        session['is_admin'] = True
        session.pop('debug_visitor', None) # デバッグ訪問者フラグは消す
        # 【重要】キーがURLに残らないように、クエリパラメータを消したURLへ即リダイレクト
        return redirect(request.path)
    
    # 既に管理者セッションを持っていれば通す
    if session.get('is_admin'):
        return

    # 2. バックステージパスチェック（関係者通行証モード）
    ticket = request.args.get('ticket')
    if ticket == env_admin_key: # チケットキーも同じ環境変数を使っていますが、必要なら分けてください
        session['debug_visitor'] = True
        # こちらも証拠隠滅リダイレクト
        return redirect(request.path)
    
    # パスを持っている一般客なら通す
    if session.get('debug_visitor'):
        return

    # --- 以下、通常の一般客向けチェック ---

    # 静的ファイルはチェックしない
    if request.path.startswith('/static'):
        return

    # マニュアルはいつでも見れる
    if request.endpoint == 'main.manual':
        return

    # 営業時間チェック
    now = datetime.now()
    hour = now.hour
    is_open = (hour >= 19) or (hour < 1)
    
    if not is_open:
        # 'sleeping' -> 'system.sleeping'
        if request.endpoint == 'system.sleeping':
            return
        
        if 0 <= hour < 6:
            reason = 'midnight'
        else:
            reason = 'daytime'
        
        # url_for も 'system.sleeping' を指定する必要があります
        return redirect(url_for('system.sleeping', reason=reason))

@bp.route('/sleeping')
def sleeping():
    reason = request.args.get('reason', 'daytime')
    return render_template('sleeping.html', reason=reason)