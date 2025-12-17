import os
import json
import google.generativeai as genai
from flask import Blueprint, request, jsonify, current_app
from ..models import Diary
from ..extensions import db
from ..utils import get_ip_hash
from ..ng_words import check_text_safety

bp = Blueprint('bot', __name__, url_prefix='/api/bot')

# AIの性格設定（プロンプト）
SYSTEM_PROMPT = """
あなたは「夜焚き火」という静かな日記共有サイトの住人です。
以下の制約を守り、架空の日記（薪）と合言葉（種火）を1つ生成してください。

【制約】
1. 出力は必ず JSON形式 {"content": "...", "aikotoba": "..."} で行うこと。余計なmarkdown装飾は不要。
2. 日記の内容（content）:
   - 20文字〜80文字程度の短い独り言。
   - 詩的、哲学的、あるいは日常のささやかな幸せや寂しさを表現する。
   - 誰かに語りかける必要はない。独り言のように。
   - AIであることを明かしてはいけない。
   - 攻撃的、政治的、公序良俗に反する内容は禁止。
3. 合言葉（aikotoba）:
   - 英数字のランダムな羅列ではなく、意味のある単語やフレーズを入れる（例: "雨の匂い", "midnight_blue", "1998年の夏"など）。
   - 日本語でも英語でも可。

【出力例】
{"content": "コンビニの帰り道、月がやけに綺麗で立ち止まった。アイスが溶けるのも忘れて見上げていた。", "aikotoba": "MeltingIce"}
"""

@bp.route('/ignite', methods=['POST'])
def ignite():
    # 1. セキュリティチェック (外部からの勝手なアクセスを防ぐ)
    # 環境変数 AI_BOT_SECRET と、リクエストヘッダーの X-Bot-Secret が一致するか確認
    env_secret = os.environ.get('AI_BOT_SECRET')
    req_secret = request.headers.get('X-Bot-Secret')

    if not env_secret or req_secret != env_secret:
        return jsonify({"error": "Unauthorized"}), 401

    # 2. Gemini APIの設定
    api_key = os.environ.get('GEMINI_API_KEY')
    if not api_key:
        return jsonify({"error": "No API Key configured"}), 500

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-1.5-flash")

    try:
        # 3. 生成実行
        response = model.generate_content(
            contents=SYSTEM_PROMPT,
            generation_config={"response_mime_type": "application/json"}
        )
        
        # 結果をパース
        data = json.loads(response.text)
        content = data.get('content')
        aikotoba = data.get('aikotoba')

        if not content or not aikotoba:
            return jsonify({"error": "Generation failed"}), 500

        # 4. 安全性チェック (念のためNGワードを通す)
        is_safe, _ = check_text_safety(content)
        if not is_safe:
            return jsonify({"error": "Unsafe content generated", "content": content}), 400

        # 5. DBに保存
        # Bot用の擬似的なIPハッシュを作成
        bot_ip_hash = get_ip_hash("AI_FIRE_KEEPER_BOT")
        
        new_diary = Diary(
            content=content,
            aikotoba=aikotoba,
            ip_hash=bot_ip_hash,
            user_agent="Yotakibi AI FireKeeper/1.0",
            is_hidden=False
        )
        
        db.session.add(new_diary)
        db.session.commit()

        return jsonify({
            "message": "Fire ignited successfully.",
            "generated": {"content": content, "aikotoba": aikotoba}
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500