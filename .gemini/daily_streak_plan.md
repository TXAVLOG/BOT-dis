# 🔥 Daily Streak System - Implementation Plan

## 📊 Database Schema
```json
{
    "daily_streak": 0,           // Số ngày liên tục
    "last_daily": timestamp,     // Lần điểm danh cuối
    "last_daily_date": "2025-12-26"  // Ngày điểm danh cuối (để check streak)
}
```

## 🎯 Logic Streak

### Khi `/daily`:
1. Lấy `last_daily_date`
2. Tính số ngày chênh lệch với hôm nay
3. **Nếu chênh 1 ngày** → Tăng streak
4. **Nếu chênh > 1 ngày** → Reset streak về 0
5. **Nếu cùng ngày** → Không thay đổi (đã điểm danh rồi)

### Bonus EXP:
```
base_reward = 1000
streak_bonus = streak * 100  // Mỗi ngày streak +100 EXP
total_reward = base_reward + streak_bonus
```

## 🎨 Hiển thị Streak

### Emoji Numbers:
```python
def number_to_emoji(num):
    emoji_map = {
        '0': '0️⃣', '1': '1️⃣', '2': '2️⃣', '3': '3️⃣', '4': '4️⃣',
        '5': '5️⃣', '6': '6️⃣', '7': '7️⃣', '8': '8️⃣', '9': '9️⃣'
    }
    return ''.join(emoji_map[d] for d in str(num))
```

### Ví dụ:
- Streak 0: 0️⃣
- Streak 7: 7️⃣
- Streak 15: 1️⃣5️⃣
- Streak 100: 1️⃣0️⃣0️⃣

## 📩 DM Reminder System

### Background Task:
```python
@tasks.loop(hours=1)
async def check_daily_reminders():
    now = datetime.now(VN_TZ)
    # Chỉ chạy vào 6:00 AM (1 giờ trước reset)
    if now.hour != 6:
        return
    
    db = load_db()
    for user_id, data in db.items():
        # Check nếu chưa điểm danh hôm nay
        last_date = data.get("last_daily_date")
        today = now.strftime("%Y-%m-%d")
        
        if last_date != today:
            # Gửi DM nhắc nhở
            user = await bot.fetch_user(int(user_id))
            await send_daily_reminder(user, data.get("daily_streak", 0))
```

### DM Content:
```
⏰ Nhắc Nhở Điểm Danh

🔥 Chuỗi điểm danh hiện tại: [STREAK_EMOJI]
⚠️ Còn 1 giờ nữa là reset! (7:00 AM)

💡 Hãy dùng /daily ngay để giữ chuỗi streak!
📈 Streak càng cao, phần thưởng càng lớn!

[Button: 🏰 Trở về server / 📍 Đến #channel]
```

## 🎁 Reward Display

### Success Message:
```
🎁 Thiên Đạo Ban Phước

✨ Điểm danh thành công!
📅 Ngày thứ: [STREAK_EMOJI]

💰 Phần thưởng:
  • Cơ bản: 1000 EXP
  • Streak bonus: +[BONUS] EXP
  • Tổng cộng: [TOTAL] EXP

🔥 Chuỗi hiện tại: [STREAK_EMOJI] ngày
⚠️ Đừng quên điểm danh ngày mai để giữ streak!
```

## 📝 Implementation Steps

1. ✅ Thêm `number_to_emoji()` helper
2. ✅ Cập nhật `/daily` với streak logic
3. ✅ Thêm background task cho DM reminder
4. ✅ Tạo `send_daily_reminder()` function
5. ✅ Test streak tăng/giảm
6. ✅ Test DM reminder

## 🚀 Next Steps

- Implement helper functions
- Update `/daily` command
- Add background task
- Test thoroughly
