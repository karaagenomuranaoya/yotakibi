import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from functools import wraps

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-keep-it-secret-yotakibi')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///yotakibi.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ---------------------------------------------------------
# データモデル (Diary) - 更新
# ---------------------------------------------------------
class Diary(db.Model):
    __tablename__ = 'diaries'
    
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    aikotoba = db.Column(db.String(20), nullable=False)
    # ★追加: 合言葉を公開するかどうかのフラグ
    is_public = db.Column(db.Boolean, default=False) 
    created_at = db.Column(db.DateTime, default=datetime.now)

with app.app_context():
    db.create_all()

# app.py の該当部分（check_opening_hours）を以下に書き換えてください

# ---------------------------------------------------------
# 時間制限の門番（夜しか開かない ＆ 裏口あり）
# ---------------------------------------------------------
@app.before_request
def check_opening_hours():
    # 1. 静的ファイルは常に許可
    if request.path.startswith('/static'):
        return

    # 2. 管理者（裏口）チェック
    # URLに ?admin_key=... がある、または既に管理者セッションがある場合
    # 本番では環境変数でキーを管理すべきですが、今は簡易的に 'secret_open' とします
    secret_key = request.args.get('admin_key')
    if secret_key == 'secret_open':
        session['is_admin'] = True  # セッションに管理者フラグを立てる
    
    # 管理者なら常に通過許可
    if session.get('is_admin'):
        return

    # 3. 時間チェック
    now = datetime.now()
    hour = now.hour

    # 営業時間: 20時(20) 〜 24時(0)の前まで
    # hourが 20, 21, 22, 23 のいずれかなら営業中
    is_open = (20 <= hour < 24)

    if not is_open:
        # 閉店中だが、sleepingページへのアクセスなら許可
        if request.endpoint == 'sleeping':
            return
        
        # それ以外はsleepingページへ飛ばす
        # その際、時間帯の理由（reason）をURLパラメータで渡す
        if 0 <= hour < 6:
            reason = 'midnight' # 0:00 - 6:00 (寝ろよ)
        else:
            reason = 'daytime'  # 6:00 - 20:00 (まだ早い)
            
        return redirect(url_for('sleeping', reason=reason))

# ---------------------------------------------------------
# アクセス制限デコレータ
# ---------------------------------------------------------
def fire_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('has_posted'):
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# ---------------------------------------------------------
# ルーティング
# ---------------------------------------------------------

# 【閉店画面】
# app.py の sleeping ルート部分

@app.route('/sleeping')
def sleeping():
    reason = request.args.get('reason', 'daytime')
    return render_template('sleeping.html', reason=reason)

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        content = request.form.get('content')
        aikotoba = request.form.get('aikotoba')
        # ★追加: チェックボックスの値を取得
        is_public = True if request.form.get('is_public') else False

        if not content or not aikotoba:
            flash('言葉と合言葉が必要です。', 'error')
            return redirect(url_for('index'))

        new_diary = Diary(content=content, aikotoba=aikotoba, is_public=is_public)
        db.session.add(new_diary)
        db.session.commit()

        session['has_posted'] = True
        session['my_aikotoba'] = aikotoba
        return redirect(url_for('timeline'))

    return render_template('index.html')

@app.route('/timeline')
@fire_required
def timeline():
    diaries = Diary.query.order_by(Diary.created_at.desc()).limit(50).all()
    return render_template('timeline.html', diaries=diaries)

@app.route('/search')
@fire_required
def search():
    query = request.args.get('q')
    if not query:
        return redirect(url_for('timeline'))
    
    results = Diary.query.filter_by(aikotoba=query).order_by(Diary.created_at.desc()).all()
    return render_template('timeline.html', diaries=results, search_query=query)

if __name__ == '__main__':
    app.run(debug=True)