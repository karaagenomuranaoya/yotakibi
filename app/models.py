import uuid
from datetime import datetime
from .extensions import db  # ステップ4で作ったファイルからdbを読み込む

class Diary(db.Model):
    __tablename__ = 'diaries'

    # 内部管理用ID
    id = db.Column(db.Integer, primary_key=True)
    # 外部公開用ID
    uuid = db.Column(db.String(36), unique=True, default=lambda: str(uuid.uuid4()))

    # コンテンツ
    content = db.Column(db.Text, nullable=False)
    aikotoba = db.Column(db.String(50), nullable=False)

    # --- 公開・利用設定 ---
    is_timeline_public = db.Column(db.Boolean, default=False)
    is_aikotoba_public = db.Column(db.Boolean, default=False)
    allow_sns_share = db.Column(db.Boolean, default=False)
    allow_aikotoba_sns = db.Column(db.Boolean, default=False)

    # --- 管理・モデレーション ---
    is_hidden = db.Column(db.Boolean, default=False)
    admin_memo = db.Column(db.Text, nullable=True)
    
    # --- セキュリティ・監査ログ ---
    ip_hash = db.Column(db.String(64), nullable=True)
    user_agent = db.Column(db.String(255), nullable=True)

    # メタデータ
    created_at = db.Column(db.DateTime, default=datetime.now, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)