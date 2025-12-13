import os
import re
import random # ランダム日時用
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from functools import wraps
from flask_wtf import CSRFProtect

app = Flask(__name__)

# --- 設定周り ---
# 本番環境では環境変数 SECRET_KEY を設定してください
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
csrf = CSRFProtect(app)

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
    input_key = request.args.get('admin_key')
    
    # 環境変数がない場合（ローカル）は 'local_secret_open' を正解の鍵にする
    env_admin_key = os.environ.get('ADMIN_KEY', 'local_secret_open') 
    
    if input_key == env_admin_key:
        session['is_admin'] = True
    
    # 管理者は時間制限を無視して通過
    if session.get('is_admin'):
        return

    # 静的ファイルへのアクセスは常に許可
    if request.path.startswith('/static'):
        return

    # 【追加】説明書ページ(manual)へのアクセスも常に許可
    if request.endpoint == 'manual':
        return

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

        # 投稿時間の決定
        post_time = datetime.now() # デフォルト（一般ユーザー用）

        if session.get('is_admin'):
            # 管理者が時間を指定してきたかチェック
            custom_time_str = request.form.get('custom_time')
            
            if custom_time_str:
                # 指定がある場合: 文字列をdatetimeオブジェクトに変換
                try:
                    # input type="datetime-local" は 'YYYY-MM-DDTHH:MM' 形式で送られてくる
                    post_time = datetime.strptime(custom_time_str, '%Y-%m-%dT%H:%M')
                except ValueError:
                    # 万が一形式がおかしい場合は現在時刻にする
                    post_time = datetime.now()
            else:
                # 指定がない場合: 既存の「ランダムな過去の夜」ロジックを使用
                # 1. まず「何日前か」をランダムに決める（0日前〜7日前）
                days_ago = random.randint(0, 7)
                base_date = datetime.now() - timedelta(days=days_ago)

                # 2. その日の「19:02」を基準セットする
                base_time = base_date.replace(hour=19, minute=2, second=0, microsecond=0)

                # 3. 19:02 から 24:56 までの「幅」を分単位で計算 (合計354分)
                random_minutes = random.randint(0, 354)

                # 4. 基準時間にランダムな分数を足す
                post_time = base_time + timedelta(minutes=random_minutes)

                # 【安全装置】未来になってしまったら1日戻す
                if post_time > datetime.now():
                    post_time = post_time - timedelta(days=1)
        else:
            # 一般ユーザーは現在時刻
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

# app.py の write関数の下あたりに追加

@app.route('/extinguish/<int:diary_id>', methods=['POST'])
def extinguish(diary_id):
    # 1. 管理者チェック（必須）
    if not session.get('is_admin'):
        flash('その操作は許可されていません。', 'error')
        return redirect(url_for('index'))

    # 2. 該当の日記を探す
    diary = Diary.query.get_or_404(diary_id)

    # 3. 削除して保存（ここがSQLのDELETEにあたる部分）
    db.session.delete(diary)
    db.session.commit()

    flash(f'種火 #{diary.id} を消火しました。', 'success')
    return redirect(url_for('index'))

@app.route('/')
@fire_required
def index():
    # トップページには「公開(is_public=True)」の火だけを表示
    diaries = Diary.query.filter_by(is_public=True).order_by(Diary.created_at.desc()).all()
    return render_template('timeline.html', diaries=diaries)

@app.route('/search')
@fire_required
def search():
    query = request.args.get('q')
    if not query:
        return redirect(url_for('index'))
    
    # 検索結果には秘密の火も表示（合言葉を知っている人向け）
    results = Diary.query.filter_by(aikotoba=query).order_by(Diary.created_at.desc()).all()
    return render_template('timeline.html', diaries=results, search_query=query)

if __name__ == '__main__':
    app.run(debug=False)