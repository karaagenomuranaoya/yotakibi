from flask import Flask
from .config import Config
from .extensions import db, csrf

def create_app():
    # 1. Flaskアプリのインスタンスを作成
    app = Flask(__name__)
    
    # 2. 設定ファイル（config.py）の内容を読み込む
    app.config.from_object(Config)

    # 3. 拡張機能（DBやCSRF）をアプリと紐付ける
    # これにより、extensions.py で作った空の箱に中身が入ります
    db.init_app(app)
    csrf.init_app(app)

    # 4. アプリケーションコンテキスト内での処理
    with app.app_context():
        # モデルをインポートしてSQLAlchemyに認識させる
        from . import models
        
        # テーブルが存在しなければ作成する
        # （これまでは app.py のグローバルスコープでやっていました）
        db.create_all()

        # ※ ここに後ほど「Blueprints（ルート）」の登録処理が入ります
        from .routes import system, main, post

        # Blueprintの登録
        app.register_blueprint(system.bp)
        app.register_blueprint(main.bp)
        app.register_blueprint(post.bp)

    return app