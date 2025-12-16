from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app
from ..models import Diary
from ..extensions import db
from ..utils import get_ip_hash

# 'post' という名前のBlueprintを作成
bp = Blueprint('post', __name__)

@bp.route('/write', methods=['GET', 'POST'])
def write():
    if request.method == 'POST':
        content = request.form.get('content')
        aikotoba = request.form.get('aikotoba')

        # --- セキュリティ情報取得（判定のために先に取得します） ---
        user_ip = request.remote_addr
        if request.headers.getlist("X-Forwarded-For"):
            user_ip = request.headers.getlist("X-Forwarded-For")[0]
            
        ip_hash = get_ip_hash(user_ip)
        user_agent = request.headers.get('User-Agent')

        # --- 連投制限チェック (1時間に5回まで) ---
        # 管理者は制限を受けない
        if not session.get('is_admin'):
            one_hour_ago = datetime.now() - timedelta(hours=1)
            recent_count = Diary.query.filter(
                Diary.ip_hash == ip_hash,
                Diary.created_at >= one_hour_ago
            ).count()

            if recent_count >= 5:
                flash('火事にならないように、薪は1時間に5本までとしています。焚き火をゆっくり眺めて、またあとで来てくださいね。', 'error')
                return render_template('write.html', kept_content=content)

        # バリデーション
        if not content or not aikotoba:
            flash('薪と種火が必要です。', 'error')
            return render_template('write.html', kept_content=content) 
        
        if len(content) > 2000:
            flash('薪が大きすぎて、炉に入りません。（2000文字まで）', 'error')
            return render_template('write.html', kept_content=content)

        if len(content) < 4:
            flash('その薪では、すぐに燃え尽きてしまいます。（5文字以上）', 'error')
            return render_template('write.html', kept_content=content)

        if len(aikotoba) > 30:
            flash('種火が長すぎて、覚えきれません（30文字以下）', 'error')
            return render_template('write.html', kept_content=content)
        
        if len(aikotoba) < 2:
            flash('種火が短すぎると、すぐに消えてしまいます（2文字以上）', 'error')
            return render_template('write.html', kept_content=content)

        # 日時の決定
        # 基本は現在時刻
        post_time = datetime.now()

        # 管理者かつ日時指定がある場合のみ上書き
        if session.get('is_admin'):
            custom_time_str = request.form.get('custom_time')
            if custom_time_str:
                try:
                    post_time = datetime.strptime(custom_time_str, '%Y-%m-%dT%H:%M')
                except ValueError:
                    # パース失敗時は現在時刻のまま
                    pass

        # 保存
        new_diary = Diary(
            content=content, 
            aikotoba=aikotoba, 
            created_at=post_time,
            ip_hash=ip_hash,
            user_agent=user_agent,
            is_hidden=False
        )
        
        db.session.add(new_diary)
        db.session.commit()
        
        session['has_posted'] = True
        session['my_aikotoba'] = aikotoba
        
        return redirect(url_for('main.index'))

    return render_template('write.html')

@bp.route('/extinguish/<int:diary_id>', methods=['POST'])
def extinguish(diary_id):
    if not session.get('is_admin'):
        flash('その操作は許可されていません。', 'error')
        return redirect(url_for('main.index'))

    diary = Diary.query.get_or_404(diary_id)
    diary.is_hidden = True
    
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
    auto_msg = f"[{timestamp}] 管理操作による消火（非表示）"
    
    if diary.admin_memo:
        diary.admin_memo += f"\n{auto_msg}"
    else:
        diary.admin_memo = auto_msg
        
    db.session.commit()

    flash(f'種火 #{diary.id} をそっと消火（非表示）しました。', 'success')
    return redirect(url_for('main.index'))

@bp.route('/memo/<int:diary_id>', methods=['POST'])
def update_memo(diary_id):
    if not session.get('is_admin'):
        flash('その操作は許可されていません。', 'error')
        return redirect(url_for('main.index'))

    diary = Diary.query.get_or_404(diary_id)
    new_memo = request.form.get('memo')
    
    diary.admin_memo = new_memo
    db.session.commit()
    
    flash(f'種火 #{diary.id} の管理者メモを更新しました。', 'success')
    return redirect(url_for('main.index'))