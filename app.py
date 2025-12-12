import os
import re
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from functools import wraps

app = Flask(__name__)

# --- 設定周り ---
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-keep-it-secret-yotakibi')

# ★ここが変更点: データベース接続設定の強化
# RenderなどのPaaSでは 'postgres://' で始まるURLが渡されることがありますが、
# SQLAlchemyの最新版は 'postgresql://' を要求するため、置換処理を入れます。
db_uri = os.environ.get('DATABASE_URL')
if db_uri and db_uri.startswith("postgres://"):
    db_uri = db_uri.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_uri or 'sqlite:///yotakibi.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# ★追加: データベース接続が切れていたら自動で再接続する設定
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

# アプリ起動時にテーブルを作成（存在しない場合）
with app.app_context():
    db.create_all()

# --- 門番関数（時間のチェック） ---
@app.before_request
def check_opening_hours():
    # 静的ファイル（CSSなど）へのアクセスは常に許可
    if request.path.startswith('/static'):
        return

    # 管理者用裏口（URLパラメータ ?admin_key=secret_open で常時アクセス可能に）
    secret_key = request.args.get('admin_key')
    if secret_key == 'secret_open':
        session['is_admin'] = True
    
    # 一度裏口を通った人はセッションが切れるまで許可
    if session.get('is_admin'):
        return

    # 現在時刻のチェック（日本時間 JST を前提とします）
    now = datetime.now()
    hour = now.hour
    
    # 夜焚き火の開催時間: 20:00 〜 23:59
    is_open = (19 <= hour < 24)

    if not is_open:
        # すでに「眠る時間（sleeping）」ページにいるならリダイレクトしない（無限ループ防止）
        if request.endpoint == 'sleeping':
            return
            
        # 時間帯によって理由を分ける
        if 0 <= hour < 6:
            reason = 'midnight' # 深夜・早朝
        else:
            reason = 'daytime'  # 日中
            
        return redirect(url_for('sleeping', reason=reason))


# --- デコレータ: 薪をくべた（投稿した）人だけ通す ---
def fire_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # ★追加: 管理者(is_admin)なら、投稿してなくても通す！
        if session.get('is_admin'):
            return f(*args, **kwargs)
        
        if not session.get('has_posted'):
            # まだ投稿していない人がタイムラインを見ようとした場合
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

        # 保存処理
        # --- ここから変更 ---

        # 投稿時間の決定
        # もし管理者（自分）なら、時間を「今日の22:00〜23:59」のどこかに偽装する
        if session.get('is_admin'):
            # 例: 今日の22時22分にする（分までこだわるとリアルです！）
            post_time = datetime.now().replace(hour=19, minute=15, second=0, microsecond=0)
        else:
            # 一般ユーザーは正直な現在時刻
            post_time = datetime.now()

        # 保存処理（created_at を明示的に渡すのがポイント！）
        new_diary = Diary(
            content=content, 
            aikotoba=aikotoba, 
            is_public=is_public,
            created_at=post_time  # ★ここで偽装した時間を渡す
        )
        
        db.session.add(new_diary)
        db.session.commit()
        
        # --- ここまで変更 ---

        # セッションに「投稿済み」の証を残す
        session['has_posted'] = True
        session['my_aikotoba'] = aikotoba
        
        return redirect(url_for('timeline'))

    return render_template('index.html')

@app.route('/timeline')
@fire_required
def timeline():
    # 過去24時間の投稿のみ表示
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
    
    # 合言葉で検索（完全一致）
    results = Diary.query.filter_by(aikotoba=query).order_by(Diary.created_at.desc()).all()
    
    return render_template('timeline.html', diaries=results, search_query=query)

if __name__ == '__main__':
    app.run(debug=True)