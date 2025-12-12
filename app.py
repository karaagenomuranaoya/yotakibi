import os
import re
import random # ランダム日時用
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from functools import wraps
from flask_wtf import CSRFProtect # 【追加】CSRF対策用

app = Flask(__name__)

# --- 設定周り ---
# 【重要】本番環境では推測不可能なランダムな文字列を環境変数 SECRET_KEY に設定してください
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
csrf = CSRFProtect(app) # 【追加】アプリ全体でCSRF保護を有効化

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
    # 1. 管理者（シークレットモード）判定
    # ハードコードをやめ、環境変数 ADMIN_KEY と一致する場合のみ許可
    input_key = request.args.get('admin_key')
    env_admin_key = os.environ.get('ADMIN_KEY') # 環境変数で設定すること
    
    if env_admin_key and input_key == env_admin_key:
        session['is_admin'] = True
    
    # 管理者は時間制限を無視して通過
    if session.get('is_admin'):
        return

    # 静的ファイルへのアクセスは常に許可
    if request.path.startswith('/static'):
        return

    # 【修正】開発用の強制オープン（return）を削除しました。
    # これにより、以下の時間制限ロジックが正常に機能します。

    # --- 以下、通常営業（夜間のみ）のロジック ---
    now = datetime.now()
    hour = now.hour
    
    # 19:00〜24:59 (深夜1時未満) はオープン
    is_open = (hour >= 19) or (hour < 1)
    
    if not is_open:
        # すでに「おやすみ画面」にいるならリダイレクトしない
        if request.endpoint == 'sleeping':
            return
            
        # 理由判定（深夜か昼間か）
        if 0 <= hour < 6:
            reason = 'midnight'
        else:
            reason = 'daytime'
        return redirect(url_for('sleeping', reason=reason))


# --- デコレータ ---
def fire_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 審査用などの制限無効化ロジックがあればここに書く
        return f(*args, **kwargs)
        
    return decorated_function

# --- ルーティング ---

@app.route('/sleeping')
def sleeping():
    reason = request.args.get('reason', 'daytime')
    return render_template('sleeping.html', reason=reason)

@app.route('/manual')
def manual():
    return render_template('manual.html')

@app.route('/write', methods=['GET', 'POST'])
def write():
    if request.method == 'POST':
        # CSRFチェックはFlask-WTFが自動で行います
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

        # 投稿時間の決定（ランダム日時処理）
        if session.get('is_admin'):
            one_week_minutes = 7 * 24 * 60 
            random_minutes = random.randint(0, one_week_minutes)
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
    # 【修正】トップページには「公開(is_public=True)」の火だけを表示する
    # これにより「秘密の火」がタイムラインに流出する事故を防ぎます
    diaries = Diary.query.filter_by(is_public=True).order_by(Diary.created_at.desc()).all()
    return render_template('timeline.html', diaries=diaries)

@app.route('/search')
@fire_required
def search():
    query = request.args.get('q')
    if not query:
        return redirect(url_for('index'))
    
    # 検索機能は「合言葉を知っている」前提なので、
    # ここでは秘密の火(is_public=False)も含めて検索できるようにしておきます。
    # もし「秘密の火」は検索でも出したくない場合は、ここにも filter_by(is_public=True) を追加してください。
    results = Diary.query.filter_by(aikotoba=query).order_by(Diary.created_at.desc()).all()
    return render_template('timeline.html', diaries=results, search_query=query)

if __name__ == '__main__':
    # 【修正】デバッグモードをFalseに変更（必須）
    app.run(debug=False)