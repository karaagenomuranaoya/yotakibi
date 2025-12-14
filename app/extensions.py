from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect

# アプリ本体とは紐付けずに、空のインスタンスを作っておきます
db = SQLAlchemy()
csrf = CSRFProtect()