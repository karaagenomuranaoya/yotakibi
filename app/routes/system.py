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
    # URLパラメータ: ?admin_key=...
    # これが入ると、時間制限無視 ＆ 連投制限無視（最強）
    input_key = request.args.get('admin_key')
    
    if input_key == env_admin_key:
        session['is_admin'] = True
        # 管理者になったら、デバッグ訪問者フラグは消しておく（混乱防止）
        session.pop('debug_visitor', None)
    
    if session.get('is_admin'):
        return

    # 2. 【追加機能】バックステージパスチェック（関係者通行証モード）
    # URLパラメータ: ?ticket=...
    # これが入ると、時間制限のみ無視 ＆ 連投制限は有効（一般客扱い）
    ticket = request.args.get('ticket')
    if ticket == env_admin_key:
        session['debug_visitor'] = True
    
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