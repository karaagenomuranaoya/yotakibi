import os
import re
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from functools import wraps

app = Flask(__name__)

# --- 設定周り ---
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-keep-it-secret-yotakibi')

# データベース接続設定の強化
db_uri = os.environ.get('DATABASE_URL')
if db_uri and db_uri.startswith("postgres://"):
    db_uri = db_uri.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_uri or 'sqlite:///yotakibi.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# データベース自動再接続設定
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    "pool_pre_ping": True,
}

db = SQLAlchemy(app)

# --- モデル定義 ---
class Diary(db.Model):
    __tablename__ = 'diaries'
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    aikotoba = db.Column(db.String(20), nullable=False)
    is_public = db.Column(db.Boolean, default=False) 
    created_at = db.Column(db.DateTime, default=datetime.now)

# アプリ起動時にテーブルを作成
with app.app_context():
    db.create_all()

# --- 門番関数（時間のチェック） ---
@app.before_request
def check_opening_hours():
    # ★修正: 審査用に24時間アクセス可能にするため、すぐにリターン（無効化）
    return

    # --- 以下、元のコード（審査後に戻すときは上のreturnを消す） ---
    if request.path.startswith('/static'):
        return

    secret_key = request.args.get('admin_key')
    if secret_key == 'secret_open':
        session['is_admin'] = True
    
    if session.get('is_admin'):
        return

    now = datetime.now()
    hour = now.hour
    
    # 19:00 〜 25:00
    is_open = (hour >= 19) or (hour < 1)
    
    if not is_open:
        if request.endpoint == 'sleeping':
            return
            
        if 0 <= hour < 6:
            reason = 'midnight'
        else:
            reason = 'daytime'
            
        return redirect(url_for('sleeping', reason=reason))


# --- デコレータ: 投稿チェック ---
def fire_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # ★修正: 審査用に誰でも見れるようにする（無効化）
        return f(*args, **kwargs)
        
        # --- 以下、元のコード ---
        # if session.get('is_admin'):
        #     return f(*args, **kwargs)
        
        # if not session.get('has_posted'):
        #     flash('薪を一つ、焚べてからにしませんか。', 'error')
        #     return redirect(url_for('write')) # indexではなくwriteへ
        # return f(*args, **kwargs)
    return decorated_function

# --- ルーティング ---

@app.route('/sleeping')
def sleeping():
    reason = request.args.get('reason', 'daytime')
    return render_template('sleeping.html', reason=reason)

# ★変更: 元のindexをwriteに変更（投稿ページ）
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

        # 3. 合言葉（種火）のバリデーション
        if not re.match(r'^[ぁ-ん]+$', aikotoba):
            flash('種火にはひらがながぴったりです。', 'error')
            return render_template('index.html', kept_content=content)

        if len(aikotoba) > 15:
            flash('種火はもうちょっとだけ静かに（15文字以下）', 'error')
            return render_template('index.html', kept_content=content)
        
        if len(aikotoba) < 3:
            flash('種火がちょっとすぎるのも考えものです（3文字以上）', 'error')
            return render_template('index.html', kept_content=content)

        # 投稿時間の決定
        if session.get('is_admin'):
            post_time = datetime.now().replace(hour=19, minute=15, second=0, microsecond=0)
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
        
        # ★変更: 投稿後はトップページ（一覧）へ戻る
        return redirect(url_for('index'))

    return render_template('index.html')

# ★変更: 元のtimelineをindexに変更（トップページ）
@app.route('/')
@fire_required
def index():
    # ★変更: 全件取得（時間制限なし）
    diaries = Diary.query.order_by(Diary.created_at.desc()).all()
    return render_template('timeline.html', diaries=diaries)

@app.route('/search')
@fire_required
def search():
    query = request.args.get('q')
    if not query:
        # ★変更: 戻り先をindexに
        return redirect(url_for('index'))
    
    results = Diary.query.filter_by(aikotoba=query).order_by(Diary.created_at.desc()).all()
    return render_template('timeline.html', diaries=results, search_query=query)

if __name__ == '__main__':
    app.run(debug=True)