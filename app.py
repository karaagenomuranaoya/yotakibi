import os
import re
import random
import json
import uuid
import hashlib
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from functools import wraps
from flask_wtf import CSRFProtect

app = Flask(__name__)

# --- 設定周り ---
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-keep-it-secret-yotakibi')
# IPハッシュ化用のSalt（本番環境では必ず環境変数で設定すること）
app.config['IP_SALT'] = os.environ.get('IP_SALT', 'dev-salt-change-me')

db_uri = os.environ.get('DATABASE_URL')
if db_uri and db_uri.startswith("postgres://"):
    db_uri = db_uri.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_uri or 'sqlite:///yotakibi.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = { "pool_pre_ping": True }

db = SQLAlchemy(app)
csrf = CSRFProtect(app)

# --- ヘルパー関数 ---
def get_ip_hash(ip_address):
    """IPアドレスとSaltを組み合わせてハッシュ化する"""
    if not ip_address:
        return None
    salt = app.config['IP_SALT']
    return hashlib.sha256(f"{ip_address}{salt}".encode('utf-8')).hexdigest()

# --- モデル定義 ---
class Diary(db.Model):
    __tablename__ = 'diaries'

    # 内部管理用ID
    id = db.Column(db.Integer, primary_key=True)
    # 外部公開用ID（URL等に使用）
    uuid = db.Column(db.String(36), unique=True, default=lambda: str(uuid.uuid4()))

    # コンテンツ
    content = db.Column(db.Text, nullable=False)
    aikotoba = db.Column(db.String(50), nullable=False)

    # --- 公開・利用設定 ---
    # 1. タイムラインに掲載するか
    is_timeline_public = db.Column(db.Boolean, default=False)
    # 2. タイムラインで合言葉を見せるか
    is_aikotoba_public = db.Column(db.Boolean, default=False)
    # 3. SNS等での紹介・引用を許可するか
    allow_sns_share = db.Column(db.Boolean, default=False)
    # 4. SNS等で紹介する際、合言葉を載せていいか
    allow_aikotoba_sns = db.Column(db.Boolean, default=False)

    # --- 管理・モデレーション ---
    # 削除せず「隠す」ためのフラグ（論理削除）
    is_hidden = db.Column(db.Boolean, default=False)
    # 管理者が隠した理由やメモ
    admin_memo = db.Column(db.Text, nullable=True)
    
    # --- セキュリティ・監査ログ ---
    ip_hash = db.Column(db.String(64), nullable=True)
    user_agent = db.Column(db.String(255), nullable=True)

    # メタデータ
    created_at = db.Column(db.DateTime, default=datetime.now, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

with app.app_context():
    db.create_all()

# --- 門番関数 ---
@app.before_request
def check_opening_hours():
    input_key = request.args.get('admin_key')
    env_admin_key = os.environ.get('ADMIN_KEY', 'local_secret_open') 
    
    if input_key == env_admin_key:
        session['is_admin'] = True
    
    if session.get('is_admin'):
        return

    if request.path.startswith('/static'):
        return

    if request.endpoint == 'manual':
        return

    now = datetime.now()
    hour = now.hour
    is_open = (hour >= 19) or (hour < 1)
    
    if not is_open:
        if request.endpoint == 'sleeping':
            return
        if 0 <= hour < 6:
            reason = 'midnight'
        else:
            reason = 'daytime'
        return redirect(url_for('sleeping', reason=reason))

def fire_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        return f(*args, **kwargs)
    return decorated_function

# --- ルーティング ---

@app.route('/sleeping')
def sleeping():
    reason = request.args.get('reason', 'daytime')
    return render_template('sleeping.html', reason=reason)

@app.route('/manual')
def manual():
    source = request.args.get('source', 'index')
    return render_template('manual.html', source=source)

# トップページ（タイムライン）
@app.route('/')
@fire_required
def index():
    page = request.args.get('page', 1, type=int)
    per_page = 10 
    
    # 公開かつ、隠されていない(is_hidden=False)ものを取得
    # ただし管理者は隠されたものも見れるようにする？ -> 今回は「管理画面」を作っていないので、
    # タイムライン上では「公開されているもの」だけを対象にし、
    # 管理操作（消火）は「そこに見えているもの」に対して行う設計にします。
    pagination = Diary.query.filter_by(
        is_timeline_public=True,
        is_hidden=False
    ).order_by(Diary.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return render_template('index.html', diaries=pagination.items, pagination=pagination)

# 書き込みページ
@app.route('/write', methods=['GET', 'POST'])
def write():
    if request.method == 'POST':
        content = request.form.get('content')
        aikotoba = request.form.get('aikotoba')
        
        # フラグ取得（チェックボックス）
        is_timeline_public = True if request.form.get('is_timeline_public') else False
        is_aikotoba_public = True if request.form.get('is_aikotoba_public') else False
        allow_sns_share = True if request.form.get('allow_sns_share') else False
        allow_aikotoba_sns = True if request.form.get('allow_aikotoba_sns') else False

        # --- バックエンド側での整合性チェック ---
        # タイムライン非公開なら、タイムラインでの合言葉公開も強制OFF
        if not is_timeline_public:
            is_aikotoba_public = False
        
        # SNSシェア不可なら、SNS合言葉公開も強制OFF
        if not allow_sns_share:
            allow_aikotoba_sns = False

        # --- バリデーション ---
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

        # --- 日時の決定 ---
        post_time = datetime.now()
        if session.get('is_admin'):
            custom_time_str = request.form.get('custom_time')
            if custom_time_str:
                try:
                    post_time = datetime.strptime(custom_time_str, '%Y-%m-%dT%H:%M')
                except ValueError:
                    post_time = datetime.now()
            else:
                # 管理者用のランダム過去投稿ロジック
                days_ago = random.randint(0, 7)
                base_date = datetime.now() - timedelta(days=days_ago)
                base_time = base_date.replace(hour=19, minute=2, second=0, microsecond=0)
                random_minutes = random.randint(0, 354)
                post_time = base_time + timedelta(minutes=random_minutes)
                if post_time > datetime.now():
                    post_time = post_time - timedelta(days=1)
        else:
            post_time = datetime.now()

        # --- セキュリティ情報 ---
        user_ip = request.remote_addr
        # プロキシ環境下の場合は X-Forwarded-For を考慮
        if request.headers.getlist("X-Forwarded-For"):
            user_ip = request.headers.getlist("X-Forwarded-For")[0]
            
        ip_hash = get_ip_hash(user_ip)
        user_agent = request.headers.get('User-Agent')

        # --- 保存 ---
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
        
        return redirect(url_for('index'))

    return render_template('write.html')

# 消火（論理削除）
@app.route('/extinguish/<int:diary_id>', methods=['POST'])
def extinguish(diary_id):
    if not session.get('is_admin'):
        flash('その操作は許可されていません。', 'error')
        return redirect(url_for('index'))

    diary = Diary.query.get_or_404(diary_id)
    
    # 物理削除ではなく、隠す（論理削除）
    diary.is_hidden = True
    # メモに自動追記（既存のメモがあれば改行して追記）
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
    auto_msg = f"[{timestamp}] 管理操作による消火（非表示）"
    
    if diary.admin_memo:
        diary.admin_memo += f"\n{auto_msg}"
    else:
        diary.admin_memo = auto_msg
        
    db.session.commit()

    flash(f'種火 #{diary.id} をそっと消火（非表示）しました。', 'success')
    return redirect(url_for('index'))

# --- 【追加】管理者用メモ更新ルート ---
@app.route('/memo/<int:diary_id>', methods=['POST'])
def update_memo(diary_id):
    if not session.get('is_admin'):
        flash('その操作は許可されていません。', 'error')
        return redirect(url_for('index'))

    diary = Diary.query.get_or_404(diary_id)
    new_memo = request.form.get('memo')
    
    diary.admin_memo = new_memo
    db.session.commit()
    
    flash(f'種火 #{diary.id} の管理者メモを更新しました。', 'success')
    return redirect(url_for('index'))


@app.route('/search')
@fire_required
def search():
    query = request.args.get('q')
    if not query:
        return redirect(url_for('index'))
    
    # 検索でも論理削除されたものは表示しない
    results = Diary.query.filter_by(
        aikotoba=query,
        is_hidden=False
    ).order_by(Diary.created_at.desc()).all()
    
    return render_template('index.html', diaries=results, search_query=query)


# --- 【データ移行用】 ---
@app.route('/secret_seeding_999')
def secret_seeding():
    try:
        with open('seeds.json', 'r', encoding='utf-8') as f:
            diaries_data = json.load(f)
    except FileNotFoundError:
        return "エラー: seeds.json が見つかりません。"

    count = 0
    for data in diaries_data:
        days_ago = random.randint(1, 7)
        base_date = datetime.now() - timedelta(days=days_ago)
        random_minutes = random.randint(0, 360)
        base_time = base_date.replace(hour=19, minute=0, second=0, microsecond=0)
        fake_created_at = base_time + timedelta(minutes=random_minutes)

        is_timeline = data.get('is_public', False)
        show_aikotoba = data.get('show_aikotoba', False)

        new_diary = Diary(
            content=data['content'],
            aikotoba=data['aikotoba'],
            is_timeline_public=is_timeline,
            is_aikotoba_public=show_aikotoba,
            allow_sns_share=False, 
            allow_aikotoba_sns=False,
            created_at=fake_created_at,
            ip_hash="system_seed"
        )
        db.session.add(new_diary)
        count += 1
    
    db.session.commit()
    return f"完了: {count} 件のデータを新形式で投入しました。"

if __name__ == '__main__':
    app.run(debug=False)