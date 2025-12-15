from flask import Blueprint, render_template, request, redirect, url_for, session
from ..models import Diary
from ..utils import fire_required

# 'main' という名前のBlueprintを作成
bp = Blueprint('main', __name__)

@bp.route('/')
@fire_required
def index():
    page = request.args.get('page', 1, type=int)
    per_page = 10 
    
    # クエリビルダーの開始
    query = Diary.query.filter_by(is_hidden=False)

    # 【修正】管理者でない場合のみ、「公開設定」のフィルターをかける
    # つまり、管理者は「非公開（秘密の火）」もタイムラインで見えるようになる
    if not session.get('is_admin'):
        query = query.filter_by(is_timeline_public=True)
    
    # 作成日順に並べて取得
    pagination = query.order_by(Diary.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return render_template('index.html', diaries=pagination.items, pagination=pagination)

@bp.route('/search')
@fire_required
def search():
    query = request.args.get('q')
    if not query:
        return redirect(url_for('main.index'))
    
    # 検索も同様。管理者は hidden 以外なら何でも引っかかるようにしても良いが、
    # 基本的に合言葉検索はピンポイントなのでそのままでもOK。
    # ここでは「管理者なら非公開設定でもヒットする」ようにしておきますか？
    # いや、検索は「種火」を知っている前提なので、現状維持でOKです。
    
    results = Diary.query.filter_by(
        aikotoba=query,
        is_hidden=False
    ).order_by(Diary.created_at.desc()).all()
    
    return render_template('index.html', diaries=results, search_query=query)

# manualルートなどは省略（変更なし）
@bp.route('/manual')
def manual():
    source = request.args.get('source', 'index')
    endpoint_map = {
        'index': 'main.index',
        'write': 'post.write',
    }
    target_endpoint = endpoint_map.get(source, 'main.index')
    return render_template('manual.html', source=target_endpoint)


# rulesルート
@bp.route('/rules')
def rules():
    return render_template('rules.html')