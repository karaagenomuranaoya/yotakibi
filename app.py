import os
import re  # ★追加: 正規表現用
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from functools import wraps

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-keep-it-secret-yotakibi')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///yotakibi.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- モデル定義などは変更なし ---
class Diary(db.Model):
    __tablename__ = 'diaries'
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    aikotoba = db.Column(db.String(20), nullable=False)
    is_public = db.Column(db.Boolean, default=False) 
    created_at = db.Column(db.DateTime, default=datetime.now)

with app.app_context():
    db.create_all()

# --- 門番関数（check_opening_hours）などは変更なし ---
@app.before_request
def check_opening_hours():
    if request.path.startswith('/static'):
        return
    secret_key = request.args.get('admin_key')
    if secret_key == 'secret_open':
        session['is_admin'] = True
    if session.get('is_admin'):
        return
    now = datetime.now()
    hour = now.hour
    is_open = (20 <= hour < 24)
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
        if not session.get('has_posted'):
            # ★追加: 優しく諭すメッセージ
            flash('薪を一つ、焚べてからにしませんか。', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# --- ルーティング ---

@app.route('/sleeping')
def sleeping():
    reason = request.args.get('reason', 'daytime')
    return render_template('sleeping.html', reason=reason)

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        content = request.form.get('content')
        aikotoba = request.form.get('aikotoba')
        is_public = True if request.form.get('is_public') else False

        # 1. 必須チェック
        if not content or not aikotoba:
            flash('薪と種火が必要です。', 'error')
            # ★変更: 本文だけは残してあげる
            return render_template('index.html', kept_content=content)
        
        # ★追加: 薪（本文）の長さチェック
        if len(content) > 2000:
            flash('薪が大きすぎて、炉に入りません。（2000文字まで）', 'error')
            return render_template('index.html', kept_content=content)

        if len(content) < 4:
            flash('その薪では、すぐに燃え尽きてしまいます。（5文字以上）', 'error')
            return render_template('index.html', kept_content=content)

        # 2. ひらがなバリデーション
        if not re.match(r'^[ぁ-ん]+$', aikotoba):
            flash('種火にはひらがながぴったりです。', 'error')
            return render_template('index.html', kept_content=content)

        # ★変更 3. 文字数制限 (15文字以内)
        # 粋なエラーメッセージに変更し、本文を保持して戻す
        if len(aikotoba) > 15:
            flash('種火はもうちょっとだけ静かに（15文字以下）', 'error')
            return render_template('index.html', kept_content=content)
        
        if len(aikotoba) < 3:
            flash('種火がちょっとすぎるのも考えものです（3文字以上）', 'error')
            return render_template('index.html', kept_content=content)

        # 保存処理
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
    time_threshold = datetime.now() - timedelta(hours=24)
    diaries = Diary.query.filter(Diary.created_at >= time_threshold)\
                         .order_by(Diary.created_at.desc())\
                         .all()
    return render_template('timeline.html', diaries=diaries)

@app.route('/search')
@fire_required
def search():
    query = request.args.get('q')
    if not query:
        return redirect(url_for('timeline'))
    
    # 検索時もバリデーションはあった方が親切ですが、
    # ここでは「どんな文字列でも探そうとした」という意図を尊重し、エラーにはせずそのまま検索させます
    # (当然、ひらがな以外で検索してもヒットしません)
    results = Diary.query.filter_by(aikotoba=query).order_by(Diary.created_at.desc()).all()
    return render_template('timeline.html', diaries=results, search_query=query)

if __name__ == '__main__':
    app.run(debug=True)