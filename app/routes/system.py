import os
from datetime import datetime
from flask import Blueprint, request, session, redirect, url_for, render_template

# 'system' という名前のBlueprintを作成
bp = Blueprint('system', __name__)

@bp.before_app_request
def check_opening_hours():
    """
    全リクエストの前に実行される門番機能。
    Blueprint内で before_app_request を使うと、アプリ全体に適用されます。
    """
    # 管理者キーのチェック
    input_key = request.args.get('admin_key')
    env_admin_key = os.environ.get('ADMIN_KEY', 'local_secret_open') 
    
    if input_key == env_admin_key:
        session['is_admin'] = True
    
    if session.get('is_admin'):
        return

    # 静的ファイルはチェックしない
    if request.path.startswith('/static'):
        return

    # ここが変更点: Blueprint化によりエンドポイント名にプレフィックスがつきます
    # 'manual' -> 'main.manual' (次のステップで作ります)
    if request.endpoint == 'main.manual':
        return

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