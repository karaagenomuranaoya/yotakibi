import random
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
        
        # フラグ取得
        is_timeline_public = True if request.form.get('is_timeline_public') else False
        is_aikotoba_public = True if request.form.get('is_aikotoba_public') else False
        allow_sns_share = True if request.form.get('allow_sns_share') else False
        allow_aikotoba_sns = True if request.form.get('allow_aikotoba_sns') else False

        # 整合性チェック
        if not is_timeline_public:
            is_aikotoba_public = False
        if not allow_sns_share:
            allow_aikotoba_sns = False

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
        post_time = datetime.now()
        if session.get('is_admin'):
            custom_time_str = request.form.get('custom_time')
            if custom_time_str:
                try:
                    post_time = datetime.strptime(custom_time_str, '%Y-%m-%dT%H:%M')
                except ValueError:
                    post_time = datetime.now()
            else:
                days_ago = random.randint(0, 7)
                base_date = datetime.now() - timedelta(days=days_ago)
                base_time = base_date.replace(hour=19, minute=2, second=0, microsecond=0)
                random_minutes = random.randint(0, 354)
                post_time = base_time + timedelta(minutes=random_minutes)
                if post_time > datetime.now():
                    post_time = post_time - timedelta(days=1)

        # セキュリティ情報
        user_ip = request.remote_addr
        if request.headers.getlist("X-Forwarded-For"):
            user_ip = request.headers.getlist("X-Forwarded-For")[0]
            
        ip_hash = get_ip_hash(user_ip)
        user_agent = request.headers.get('User-Agent')

        # 保存
        new_diary = Diary(
            content=content, 
            aikotoba=aikotoba, 
            is_timeline_public=is_timeline_public,
            is_aikotoba_public=is_aikotoba_public,
            allow_sns_share=allow_sns_share,
            allow_aikotoba_sns=allow_aikotoba_sns,
            created_at=post_time,
            ip_hash=ip_hash,
            user_agent=user_agent
        )
        
        db.session.add(new_diary)
        db.session.commit()
        
        session['has_posted'] = True
        session['my_aikotoba'] = aikotoba
        
        # リダイレクト先を修正: 'index' -> 'main.index'
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