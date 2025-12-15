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
    # 【変更】キーをそれぞれ個別に取得する
    env_admin_key = os.environ.get('ADMIN_KEY', 'local_secret_open') 
    env_ticket_key = os.environ.get('TICKET_KEY', 'local_secret_ticket') # デフォルト値も変えておく

    # 1. 管理者ログインチェック（支配人モード）
    input_key = request.args.get('admin_key')
    
    # input_key が存在し、かつ正しい ADMIN_KEY と一致する場合
    if input_key and input_key == env_admin_key:
        session['is_admin'] = True
        session.pop('debug_visitor', None) 
        return redirect(request.path)
    
    if session.get('is_admin'):
        return

    # 2. バックステージパスチェック（関係者通行証モード）
    ticket = request.args.get('ticket')
    
    # ticket が存在し、かつ正しい TICKET_KEY と一致する場合
    if ticket and ticket == env_ticket_key:
        session['debug_visitor'] = True
        return redirect(request.path)
    
    if session.get('debug_visitor'):
        return

    # --- 以下、通常の一般客向けチェック ---

    # 静的ファイルはチェックしない
    if request.path.startswith('/static'):
        return

    # マニュアルとルールはいつでも見れる
    if request.endpoint in ['main.manual', 'main.rules']:
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
        
        return redirect(url_for('system.sleeping', reason=reason))

@bp.route('/sleeping')
def sleeping():
    reason = request.args.get('reason', 'daytime')
    return render_template('sleeping.html', reason=reason)