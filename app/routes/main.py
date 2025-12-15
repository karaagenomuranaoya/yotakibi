from flask import Blueprint, render_template, request, redirect, url_for, session
from sqlalchemy import or_
from ..models import Diary
from ..utils import fire_required

# 'main' という名前のBlueprintを作成
bp = Blueprint('main', __name__)

@bp.route('/')
@fire_required
def index():
    page = request.args.get('page', 1, type=int)
    per_page = 10 
    
    query = Diary.query.filter_by(is_hidden=False)

    if not session.get('is_admin'):
        query = query.filter_by(is_timeline_public=True)
    
    pagination = query.order_by(Diary.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return render_template('index.html', diaries=pagination.items, pagination=pagination)

@bp.route('/search')
@fire_required
def search():
    query_text = request.args.get('q')
    if not query_text:
        return redirect(url_for('main.index'))
    
    # --- 管理者用のスーパー検索ロジック ---
    if session.get('is_admin'):
        query_obj = Diary.query
        
        # 1. 範囲検索 (例: "100-150")
        if '-' in query_text and query_text.replace('-', '').isdigit():
            try:
                start, end = map(int, query_text.split('-'))
                query_obj = query_obj.filter(Diary.id.between(start, end))
            except ValueError:
                query_obj = query_obj.filter(Diary.content.contains(query_text))

        # 2. ID単体検索 (例: "105")
        elif query_text.isdigit():
            d_id = int(query_text)
            query_obj = query_obj.filter(
                or_(
                    Diary.id == d_id,
                    Diary.content.contains(query_text)
                )
            )

        # 3. 本文検索 or 種火検索 (部分一致)
        else:
            # 【修正】種火も部分一致 (contains) に変更
            query_obj = query_obj.filter(
                or_(
                    Diary.content.contains(query_text),
                    Diary.aikotoba.contains(query_text)
                )
            )
            
        results = query_obj.order_by(Diary.created_at.desc()).all()

    # --- 一般ユーザー用の通常検索ロジック ---
    else:
        results = Diary.query.filter_by(
            aikotoba=query_text,
            is_hidden=False
        ).order_by(Diary.created_at.desc()).all()
    
    return render_template('index.html', diaries=results, search_query=query_text)

@bp.route('/manual')
def manual():
    source = request.args.get('source', 'index')
    endpoint_map = {
        'index': 'main.index',
        'write': 'post.write',
    }
    target_endpoint = endpoint_map.get(source, 'main.index')
    return render_template('manual.html', source=target_endpoint)

@bp.route('/rules')
def rules():
    return render_template('rules.html')

#種火消す
@bp.route('/forget_aikotoba')
def forget_aikotoba():
    # セッションから種火情報を削除
    session.pop('my_aikotoba', None)
    # トップページに戻る
    return redirect(url_for('main.index'))