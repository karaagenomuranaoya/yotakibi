import re

"""
NGワードおよび予約語を管理するファイル
方針：立ち上げ期のため、制限は「なりすまし」と「犯罪予告」のみに絞る。
　　　場の空気は管理人の目視（火の番）によって守る。
"""

# ==========================================
# 1. 【絶対禁止】管理者専用パターン（場所不問）
# ==========================================
# 管理人（Falo）へのなりすましは、信頼に関わるため厳禁。
# 大文字小文字問わず禁止。
ADMIN_EXCLUSIVE_PATTERNS = [
    r"falo", 
]

# ==========================================
# 2. 【種火のみ】予約語リスト（文字列）
# ==========================================
# サービス名などを騙るなりすまし防止。
# ※本文（日記）で「夜焚き火楽しかった」と書くのはOK。
RESERVED_AIKOTOBA_WORDS = [
    "夜焚き火", "よたきび", "ヨタキビ", "yotakibi", "Yotakibi", "YOTAKIBI",
    "管理人", "admin", "Admin", "official", "公式", "運営"
]

# ==========================================
# 3. 【全員禁止】共通NGワード（文字列）
# ==========================================
# 法的リスクがあるもの、生命に関わるものだけを最低限設定。
# それ以外の「不快な言葉」や「陰謀論」は、管理人が見つけ次第「消火」する。
GENERAL_NG_WORDS = [
    "殺す", "殺害", "爆破予告", # 明白な犯罪・脅迫
    "死ね", # さすがに直接的すぎる攻撃なので入れておく推奨
]


def check_text_safety(text, check_reserved=False, is_admin=False):
    """
    テキストが安全かどうかを判定する関数
    """
    if not text:
        return True, None
        
    # 1. 共通NGワードチェック
    for word in GENERAL_NG_WORDS:
        if word in text:
            return False, "その言葉は、薪としてくべることはできません。"

    # 2. 管理者権限チェック
    if not is_admin:
        # A. 管理人名（Falo）のなりすましチェック
        for pattern in ADMIN_EXCLUSIVE_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return False, "その言葉（管理人の名前）は使用できません。"

        # B. 予約語（種火）チェック
        if check_reserved:
            for word in RESERVED_AIKOTOBA_WORDS:
                if word in text: 
                    return False, f"「{word}」を含む種火は、管理人が使用するため予約されています。"

    return True, None