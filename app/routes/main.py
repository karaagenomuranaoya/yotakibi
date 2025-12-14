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
    
    # モデルのインポート元が変わっただけで、ロジックはそのままです
    pagination = Diary.query.filter_by(
        is_timeline_public=True,
        is_hidden=False
    ).order_by(Diary.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return render_template('index.html', diaries=pagination.items, pagination=pagination)

@bp.route('/search')
@fire_required
def search():
    query = request.args.get('q')
    if not query:
        # url_for('index') -> url_for('main.index')
        return redirect(url_for('main.index'))
    
    results = Diary.query.filter_by(
        aikotoba=query,
        is_hidden=False
    ).order_by(Diary.created_at.desc()).all()
    
    return render_template('index.html', diaries=results, search_query=query)

@bp.route('/manual')
def manual():
    source = request.args.get('source', 'index')
    # テンプレートに渡すsource変数も、リンク先修正のために必要なら後で修正しますが、
    # url_forが賢いので 'index' という文字列だけでも同じBlueprint内なら解決してくれることが多いです
    # ただし念のため明示的な修正を推奨します(以下)

    # 修正: Blueprintのエンドポイント名に変換する辞書
    endpoint_map = {
        'index': 'main.index',
        'write': 'post.write',
        # 他に遷移元が増えたらここに追加
    }

    # 辞書にあれば変換、なければトップページへ安全に倒す
    target_endpoint = endpoint_map.get(source, 'main.index')
    
    # テンプレートには変換後のエンドポイント名を渡すのではなく、
    # テンプレート側で url_for(target_endpoint) できるように値を渡します
    # ただし manual.html 側も修正が必要です。
    # ここでは「テンプレート側で url_for を使う」前提で、エンドポイント文字列を渡します。
    return render_template('manual.html', source=target_endpoint)