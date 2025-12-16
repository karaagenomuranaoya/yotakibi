import os
from datetime import datetime
from flask import Blueprint, request, session, redirect, url_for, render_template

bp = Blueprint('system', __name__)

@bp.before_app_request
def check_opening_hours():
    """
    全リクエストの前に実行される門番機能。
    URLパラメータによる「役（ロール）の切り替え」を最優先で処理します。
    """
    env_admin_key = os.environ.get('ADMIN_KEY', 'local_secret_open') 
    env_ticket_key = os.environ.get('TICKET_KEY', 'local_secret_ticket')

    # --- 1. 役の切り替えスイッチ (Role Switching) ---
    
    input_admin = request.args.get('admin_key')
    input_ticket = request.args.get('ticket')
    input_guest = request.args.get('guest') # 「ただの人」に戻るスイッチ

    # A. 【支配人モード】へ変身
    # URL: /?admin_key=local_secret_open
    if input_admin and input_admin == env_admin_key:
        session['is_admin'] = True
        session.pop('debug_visitor', None) # 他の権限は捨てる
        # パラメータを消して再読み込み（URLを綺麗にする）
        return redirect(request.path)

    # B. 【関係者モード】へ変身（管理者がこれを使うと降格できる）
    # URL: /?ticket=local_secret_ticket
    if input_ticket and input_ticket == env_ticket_key:
        session['debug_visitor'] = True
        session.pop('is_admin', None) # 管理者権限は捨てる
        return redirect(request.path)

    # C. 【一般客モード】へ戻る（全てを忘れる）
    # URL: /?guest=1
    if input_guest:
        session.pop('is_admin', None)
        session.pop('debug_visitor', None)
        return redirect(request.path)


    # --- 2. 既存のセッション維持チェック ---
    # ここより下は「ページ遷移」などの通常のアクセス
    
    if session.get('is_admin'):
        return

    if session.get('debug_visitor'):
        return

    # --- 3. 一般客向けの入場チェック ---

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