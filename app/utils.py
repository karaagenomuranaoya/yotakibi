import hashlib
from functools import wraps
from flask import current_app  # 【重要】実行中のアプリを参照するための機能

def get_ip_hash(ip_address):
    """IPアドレスとSaltを組み合わせてハッシュ化する"""
    if not ip_address:
        return None
    
    # app.config['IP_SALT'] の代わりに current_app.config を使う
    salt = current_app.config['IP_SALT']
    
    return hashlib.sha256(f"{ip_address}{salt}".encode('utf-8')).hexdigest()

def fire_required(f):
    """
    デコレータ: 必要な前処理があればここに記述
    現在は単純なパススルーですが、将来的に認証などを挟む場所として維持
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        return f(*args, **kwargs)
    return decorated_function