import os

class Config:
    """基本設定クラス"""
    # セキュリティキー（デフォルト値を設定していますが、本番では環境変数を推奨）
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-key-keep-it-secret-yotakibi')
    
    # IPハッシュ化用のSalt
    IP_SALT = os.environ.get('IP_SALT', 'dev-salt-change-me')

    # データベース設定
    # Heroku等のPostgreSQL対応: postgres:// を postgresql:// に置換する処理
    _db_uri = os.environ.get('DATABASE_URL')
    if _db_uri and _db_uri.startswith("postgres://"):
        _db_uri = _db_uri.replace("postgres://", "postgresql://", 1)
    
    SQLALCHEMY_DATABASE_URI = _db_uri or 'sqlite:///yotakibi.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # DB接続切れ防止の設定
    SQLALCHEMY_ENGINE_OPTIONS = { "pool_pre_ping": True }

    # 管理者キー（環境変数から取得）
    ADMIN_KEY = os.environ.get('ADMIN_KEY', 'local_secret_open')