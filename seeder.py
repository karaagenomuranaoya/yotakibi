import json
import random
from datetime import datetime, timedelta
from app import app, db, Diary # app.py から必要なものを借りる

def seed_data():
    # jsonファイルを読み込む
    try:
        with open('seeds.json', 'r', encoding='utf-8') as f:
            diaries_data = json.load(f)
    except FileNotFoundError:
        print("エラー: seeds.json が見つかりません。")
        return

    print(f"{len(diaries_data)} 件のデータを投入します...")

    with app.app_context():
        count = 0
        for data in diaries_data:
            # 日時の偽装ロジック
            # 1. 過去1日〜7日のどこか
            days_ago = random.randint(1, 7)
            base_date = datetime.now() - timedelta(days=days_ago)

            # 2. 時間を 19:00 〜 25:00 (翌01:00) の間に設定
            # 19時から何分後か？ (6時間 = 360分)
            random_minutes = random.randint(0, 360)
            base_time = base_date.replace(hour=19, minute=0, second=0, microsecond=0)
            fake_created_at = base_time + timedelta(minutes=random_minutes)

            # データベースに追加するための準備
            new_diary = Diary(
                content=data['content'],
                aikotoba=data['aikotoba'],
                is_public=data['is_public'],
                show_aikotoba=data['show_aikotoba'],
                created_at=fake_created_at
            )
            db.session.add(new_diary)
            count += 1
        
        # 最後にまとめて保存
        db.session.commit()
        print(f"完了: {count} 件の種火を灯しました。")

if __name__ == '__main__':
    seed_data()