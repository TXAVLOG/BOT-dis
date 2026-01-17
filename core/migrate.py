import json
import os
from core.database import Database
from core.helpers import rainbow_log

async def migrate_data(db: Database):
    json_path = "tu_tien_v5.json"
    if not os.path.exists(json_path):
        rainbow_log("📂 Không tìm thấy file JSON cũ, bỏ qua migration.")
        return

    rainbow_log("🔄 Phát hiện database cũ, đang tiến hành di cư sang SQLite...")
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        count = 0
        for uid, u in data.items():
            # Basic mapping
            await db.create_user(uid, u.get('name', 'Ẩn danh'))
            await db.update_user(
                uid,
                layer=u.get('layer', 1),
                exp=u.get('exp', 0),
                goal=u.get('goal', 200),
                last_mission_reset=u.get('last_mission_reset', 0),
                missions_completed=u.get('missions_completed', 0),
                last_daily=u.get('last_daily', 0),
                last_daily_date=u.get('last_daily_date', ''),
                daily_streak=u.get('daily_streak', 0),
                missions=u.get('missions', []),
                current_mission=u.get('current_mission')
            )
            count += 1
        
        rainbow_log(f"✅ Di cư thành công {count} đệ tử!")
        # Rename file to avoid double migration
        os.rename(json_path, f"tu_tien_v5.json.bak")
        rainbow_log(f"💾 File cũ đã được lưu thành tu_tien_v5.json.bak")

    except Exception as e:
        rainbow_log(f"❌ Di cư thất bại: {e}")
