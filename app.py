import os
import re
import random # ランダム日時用
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from functools import wraps

app = Flask(__name__)

# --- 設定周り ---
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-keep-it-secret-yotakibi')

# データベース接続設定
db_uri = os.environ.get('DATABASE_URL')
if db_uri and db_uri.startswith("postgres://"):
    db_uri = db_uri.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_uri or 'sqlite:///yotakibi.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    "pool_pre_ping": True,
}

db = SQLAlchemy(app)

# --- モデル定義 ---
class Diary(db.Model):
    __tablename__ = 'diaries'
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    aikotoba = db.Column(db.String(50), nullable=False)
    is_public = db.Column(db.Boolean, default=False) 
    created_at = db.Column(db.DateTime, default=datetime.now)

# アプリ起動時にテーブルを作成
with app.app_context():
    db.create_all()

# --- 門番関数 ---
@app.before_request
def check_opening_hours():
    # ★審査用：24時間オープン（無効化中）
    return

    if request.path.startswith('/static'):
        return

    secret_key = request.args.get('admin_key')
    if secret_key == 'secret_open':
        session['is_admin'] = True
    
    if session.get('is_admin'):
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


# --- デコレータ ---
def fire_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # ★審査用：制限なし（無効化中）
        return f(*args, **kwargs)
        
    return decorated_function

# --- ルーティング ---

@app.route('/sleeping')
def sleeping():
    reason = request.args.get('reason', 'daytime')
    return render_template('sleeping.html', reason=reason)

# ★追加：説明書ページへのルート
@app.route('/manual')
def manual():
    return render_template('manual.html')

@app.route('/write', methods=['GET', 'POST'])
def write():
    if request.method == 'POST':
        content = request.form.get('content')
        aikotoba = request.form.get('aikotoba')
        is_public = True if request.form.get('is_public') else False

        # 1. 必須チェック
        if not content or not aikotoba:
            flash('薪と種火が必要です。', 'error')
            return render_template('index.html', kept_content=content)
        
        # 2. 文字数チェック
        if len(content) > 2000:
            flash('薪が大きすぎて、炉に入りません。（2000文字まで）', 'error')
            return render_template('index.html', kept_content=content)

        if len(content) < 4:
            flash('その薪では、すぐに燃え尽きてしまいます。（5文字以上）', 'error')
            return render_template('index.html', kept_content=content)

        # 3. 種火のバリデーション
        if len(aikotoba) > 30:
            flash('種火が長すぎて、覚えきれません（30文字以下）', 'error')
            return render_template('index.html', kept_content=content)
        
        if len(aikotoba) < 2:
            flash('種火が短すぎると、すぐに消えてしまいます（2文字以上）', 'error')
            return render_template('index.html', kept_content=content)

        # 投稿時間の決定（ランダム日時）
        if session.get('is_admin'):
            random_minutes = random.randint(0, 10000)
            post_time = datetime.now() - timedelta(minutes=random_minutes)
        else:
            post_time = datetime.now()

        # 保存処理
        new_diary = Diary(
            content=content, 
            aikotoba=aikotoba, 
            is_public=is_public,
            created_at=post_time 
        )
        
        db.session.add(new_diary)
        db.session.commit()
        
        session['has_posted'] = True
        session['my_aikotoba'] = aikotoba
        
        return redirect(url_for('index'))

    return render_template('index.html')

@app.route('/')
@fire_required
def index():
    diaries = Diary.query.order_by(Diary.created_at.desc()).all()
    return render_template('timeline.html', diaries=diaries)

@app.route('/search')
@fire_required
def search():
    query = request.args.get('q')
    if not query:
        return redirect(url_for('index'))
    
    results = Diary.query.filter_by(aikotoba=query).order_by(Diary.created_at.desc()).all()
    return render_template('timeline.html', diaries=results, search_query=query)

if __name__ == '__main__':
    app.run(debug=True)