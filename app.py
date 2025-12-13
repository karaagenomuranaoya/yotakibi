import os
import re
import random
import json  # ← これを追加！
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from functools import wraps
from flask_wtf import CSRFProtect

app = Flask(__name__)

# --- 設定周り ---
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-keep-it-secret-yotakibi')

db_uri = os.environ.get('DATABASE_URL')
if db_uri and db_uri.startswith("postgres://"):
    db_uri = db_uri.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_uri or 'sqlite:///yotakibi.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = { "pool_pre_ping": True }

db = SQLAlchemy(app)
csrf = CSRFProtect(app)

# --- モデル定義 ---
class Diary(db.Model):
    __tablename__ = 'diaries'
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    aikotoba = db.Column(db.String(50), nullable=False)
    is_public = db.Column(db.Boolean, default=False) 
    show_aikotoba = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.now)

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
    # URLパラメータ 'source' を取得。なければデフォルトで 'index' (タイムライン)
    source = request.args.get('source', 'index')
    return render_template('manual.html', source=source)

# 【変更】トップページ（タイムライン）
@app.route('/')
@fire_required
def index():
    # URLパラメータからページ番号を取得（デフォルトは1ページ目）
    page = request.args.get('page', 1, type=int)
    
    # 1ページあたりの表示件数（例えば 10件）
    per_page = 10 
    
    # paginate() を使ってデータを取得
    pagination = Diary.query.filter_by(is_public=True).order_by(Diary.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    # 表示用データ（items）とページネーション情報本身（pagination）を渡す
    return render_template('index.html', diaries=pagination.items, pagination=pagination)

# 【変更】書き込みページ（GET:フォーム表示 / POST:保存処理）
@app.route('/write', methods=['GET', 'POST'])
def write():
    # POST（書き込み）処理
    if request.method == 'POST':
        content = request.form.get('content')
        aikotoba = request.form.get('aikotoba')
        is_public = True if request.form.get('is_public') else False
        show_aikotoba = True if request.form.get('show_aikotoba') else False

        if not content or not aikotoba:
            flash('薪と種火が必要です。', 'error')
            return render_template('write.html', kept_content=content) # エラー時は write.html へ
        
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
        else:
            post_time = datetime.now()

        new_diary = Diary(
            content=content, 
            aikotoba=aikotoba, 
            is_public=is_public,
            show_aikotoba=show_aikotoba,
            created_at=post_time 
        )
        
        db.session.add(new_diary)
        db.session.commit()
        
        session['has_posted'] = True
        session['my_aikotoba'] = aikotoba
        
        # 書き込み後はトップ（タイムライン）へ戻る
        return redirect(url_for('index'))

    # GET（フォーム表示）処理
    # ファイル名変更に伴い、テンプレート名を write.html (旧index) に指定
    return render_template('write.html')

@app.route('/extinguish/<int:diary_id>', methods=['POST'])
def extinguish(diary_id):
    if not session.get('is_admin'):
        flash('その操作は許可されていません。', 'error')
        return redirect(url_for('index'))

    diary = Diary.query.get_or_404(diary_id)
    db.session.delete(diary)
    db.session.commit()

    flash(f'種火 #{diary.id} を消火しました。', 'success')
    return redirect(url_for('index'))

@app.route('/search')
@fire_required
def search():
    query = request.args.get('q')
    if not query:
        return redirect(url_for('index'))
    
    results = Diary.query.filter_by(aikotoba=query).order_by(Diary.created_at.desc()).all()
    # 検索結果もタイムライン（index.html）を使って表示
    return render_template('index.html', diaries=results, search_query=query)




# --- 【一時的】データ用のルート ---
@app.route('/secret_seeding_999')
def secret_seeding():
    # 1. JSONファイルを読み込む
    try:
        # app.py と同じ場所にある seeds.json を探す
        with open('seeds.json', 'r', encoding='utf-8') as f:
            diaries_data = json.load(f)
    except FileNotFoundError:
        return "エラー: seeds.json が見つかりません。サーバーにアップロードされていますか？"

    # 2. データを投入
    count = 0
    for data in diaries_data:
        # 日時の偽装ロジック
        days_ago = random.randint(1, 7)
        base_date = datetime.now() - timedelta(days=days_ago)

        random_minutes = random.randint(0, 360) # 19:00〜25:00
        base_time = base_date.replace(hour=19, minute=0, second=0, microsecond=0)
        fake_created_at = base_time + timedelta(minutes=random_minutes)

        new_diary = Diary(
            content=data['content'],
            aikotoba=data['aikotoba'],
            is_public=data['is_public'],
            show_aikotoba=data['show_aikotoba'],
            created_at=fake_created_at
        )
        db.session.add(new_diary)
        count += 1
    
    # 3. 保存
    db.session.commit()
    
    return f"完了: {count} 件の種火をデータベースに灯しました。<br>このルートは後で削除してください。"

# --- ここまで ---


if __name__ == '__main__':
    app.run(debug=False)