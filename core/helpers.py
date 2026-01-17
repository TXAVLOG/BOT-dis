import os
import json
import random
import pytz
import asyncio
from datetime import datetime
from colorama import Fore, Style
from openai import OpenAI
from discord import Embed, Color
from dotenv import load_dotenv
from core.format import TXAFormat

load_dotenv()

# --- CONFIG ---
VN_TZ = pytz.timezone('Asia/Ho_Chi_Minh')
ITALIC = "\033[3m"
RESET = Style.RESET_ALL
EMOJI_CACHE_FILE = "cache/emoji_cache.json"

# --- RANKS (Fallback / Default) ---
DEFAULT_RANKS = {
    "Phàm Nhân": {"min": 1, "max": 9, "color": 0x808080, "emoji": "🌱"},
    "Luyện Khí": {"min": 10, "max": 19, "color": 0x00FF00, "emoji": "💨"},
    "Trúc Cơ": {"min": 20, "max": 29, "color": 0x00FFFF, "emoji": "🔷"},
    "Kim Đan": {"min": 30, "max": 39, "color": 0xFFD700, "emoji": "💊"},
    "Nguyên Anh": {"min": 40, "max": 49, "color": 0xFF00FF, "emoji": "👶"},
    "Hóa Thần": {"min": 50, "max": 69, "color": 0xFF0000, "emoji": "🔥"},
    "Luyện Hư": {"min": 70, "max": 89, "color": 0x9400D3, "emoji": "🌌"},
    "Hợp Thể": {"min": 90, "max": 109, "color": 0xFF1493, "emoji": "⚡"},
    "Đại Thừa": {"min": 110, "max": 149, "color": 0xFFFFFF, "emoji": "✨"},
    "Độ Kiếp": {"min": 150, "max": 199, "color": 0x8B0000, "emoji": "⚔️"},
    "Chân Tiên": {"min": 200, "max": 299, "color": 0x00CED1, "emoji": "🌟"},
    "Huyền Tiên": {"min": 300, "max": 499, "color": 0x4169E1, "emoji": "💫"},
    "Kim Tiên": {"min": 500, "max": 999, "color": 0xFFD700, "emoji": "👑"},
    "Đại La Kim Tiên": {"min": 1000, "max": 9999, "color": 0xFF4500, "emoji": "🔱"},
    "Chuẩn Thánh": {"min": 10000, "max": 99999, "color": 0xF0E68C, "emoji": "🌞"},
    "Thánh Nhân": {"min": 100000, "max": 999999, "color": 0xFFFFFF, "emoji": "☀️"},
}

# Active RANKS (sẽ được AI generate hoặc fallback)
RANKS = DEFAULT_RANKS.copy()
RANKS_CACHE_FILE = "cache/ranks_cache.json"

def get_all_rank_names():
    """Lấy tất cả tên rank khả dĩ (Active + Default) để dọn dẹp role"""
    names = set(DEFAULT_RANKS.keys())
    names.update(RANKS.keys())
    return list(names)

# --- LOGGING ---
def rainbow_log(msg, is_ascii=False, is_italic=False):
    colors = [Fore.RED, Fore.YELLOW, Fore.GREEN, Fore.CYAN, Fore.BLUE, Fore.MAGENTA]
    style = ITALIC if is_italic else ""
    if is_ascii:
        lines = msg.splitlines()
        for i, line in enumerate(lines):
            print(colors[i % len(colors)] + line)
    else:
        # Lấy giờ phút giây hiện tại
        now_dt = datetime.now(VN_TZ)
        now_str = TXAFormat.time(now_dt.hour * 3600 + now_dt.minute * 60 + now_dt.second)
        colored = "".join(colors[i % len(colors)] + c for i, c in enumerate(f"[{now_str}] {msg}"))
        print(f"{style}{colored}{RESET}")

# --- AI HELPERS ---
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

async def ask_ancestor(system_prompt, user_content, json_mode=False):
    """Hỏi Tổ sư Từ Dương (AI)"""
    try:
        args = {
            "model": "gpt-4o",
            "messages": [
                {"role": "system", "content": f"Bạn là Từ Dương, Tổ sư Thiên Lam Tông. {system_prompt}"},
                {"role": "user", "content": user_content}
            ],
            "timeout": 15
        }
        if json_mode:
            args["response_format"] = {"type": "json_object"}
        
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(None, lambda: openai_client.chat.completions.create(**args))
        return response.choices[0].message.content.strip()
    except Exception as e:
        rainbow_log(f"⚠️ Thiên Đạo chấn động (AI Error): {e}")
        return None

# --- EMOJI CACHE ---
def load_emoji_cache():
    try:
        os.makedirs("cache", exist_ok=True)
        if os.path.exists(EMOJI_CACHE_FILE):
            with open(EMOJI_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except:
        pass
    return {}

def save_emoji_cache(cache):
    os.makedirs("cache", exist_ok=True)
    with open(EMOJI_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=4, ensure_ascii=False)

# --- RANKS CACHE (AI-Generated) ---
def load_ranks_cache():
    """Tải RANKS đã được AI tạo từ cache"""
    global RANKS
    try:
        os.makedirs("cache", exist_ok=True)
        if os.path.exists(RANKS_CACHE_FILE):
            with open(RANKS_CACHE_FILE, "r", encoding="utf-8") as f:
                cached = json.load(f)
                if cached:
                    RANKS.update(cached)
                    rainbow_log(f"✨ [Đạo Pháp] Đã khôi phục {len(cached)} cảnh giới từ thiên thư cũ.")
                    return True
    except Exception as e:
        rainbow_log(f"⚠️ Lỗi tải RANKS cache: {e}")
    return False

def save_ranks_cache(ranks_data: dict):
    """Lưu RANKS vào cache"""
    os.makedirs("cache", exist_ok=True)
    with open(RANKS_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(ranks_data, f, indent=4, ensure_ascii=False)
    rainbow_log(f"💾 [Đạo Pháp] Đã lưu {len(ranks_data)} cảnh giới vào thiên thư.")

async def generate_ranks_from_ai():
    """
    Gọi AI để tạo danh sách RANKS theo phong cách Luyện Khí 10 Vạn Năm.
    Sử dụng fallback nếu AI không khả dụng.
    """
    global RANKS
    
    # Kiểm tra cache trước
    if load_ranks_cache():
        return RANKS
    
    rainbow_log("🔮 [Đạo Pháp] Đang thỉnh thị Tổ Sư Từ Dương tạo các cảnh giới tu tiên...")
    
    prompt = (
        "Tạo danh sách 16 cảnh giới tu tiên theo phong cách 'Luyện Khí Mười Vạn Năm'. "
        "Mỗi cảnh giới cần có: tên (tiếng Việt), min layer, max layer, mã màu hex, và 1 emoji phù hợp. "
        "Bắt đầu từ cảnh giới thấp nhất (Phàm Nhân, min=1) đến càng cao (Thánh Nhân, min=100000). "
        "Mỗi cảnh giới cao hơn có min layer lớn hơn cảnh trước. "
        "Format JSON: {\"ranks\": [{\"name\": \"...\", \"min\": 1, \"max\": 9, \"color\": \"0xFFFFFF\", \"emoji\": \"...\"}]}"
    )
    
    try:
        ai_res = await ask_ancestor("Nhà tạo cảnh giới tu tiên.", prompt, json_mode=True)
        if ai_res:
            data = json.loads(ai_res)
            ranks_list = data.get('ranks', [])
            
            if ranks_list and len(ranks_list) >= 10:
                new_ranks = {}
                for r in ranks_list:
                    name = r.get('name', 'Vô Danh')
                    color_str = r.get('color', '0x808080')
                    color = int(color_str, 16) if isinstance(color_str, str) else color_str
                    new_ranks[name] = {
                        "min": r.get('min', 1),
                        "max": r.get('max', 9),
                        "color": color,
                        "emoji": r.get('emoji', '⭐')
                    }
                
                RANKS.update(new_ranks)
                save_ranks_cache(new_ranks)
                rainbow_log(f"✅ [Đạo Pháp] AI đã tạo thành công {len(new_ranks)} cảnh giới tu tiên!")
                return RANKS
                
    except Exception as e:
        rainbow_log(f"⚠️ [Đạo Pháp] AI thất bại: {e}. Sử dụng cảnh giới mặc định.")
    
    # Fallback
    rainbow_log("📜 [Đạo Pháp] Sử dụng cảnh giới thượng cổ (Fallback).")
    RANKS = DEFAULT_RANKS.copy()
    return RANKS

async def get_cached_emoji(key, prompt):
    cache = load_emoji_cache()
    if key in cache:
        return cache[key]
    
    ai_prompt = f"{prompt}. Trả về JSON: {{\"emoji\": \"single emoji character\"}}"
    res = await ask_ancestor("Chọn 1 emoji phù hợp.", ai_prompt, json_mode=True)
    try:
        emoji = json.loads(res).get("emoji", "⭐")
    except:
        emoji = "⭐"
    
    cache[key] = emoji
    save_emoji_cache(cache)
    return emoji

# --- UTILS ---
def get_rank_info(layer: int):
    for rank_name, info in sorted(RANKS.items(), key=lambda x: x[1]['min'], reverse=True):
        if layer >= info['min']:
            return rank_name, info
    return "Phàm Nhân", RANKS["Phàm Nhân"]

def txa_embed(title: str, desc: str, color: Color = Color.blue()):
    embed = Embed(
        title=title, 
        description=desc, 
        color=color,
        timestamp=datetime.now(VN_TZ)
    )
    return embed

def get_progress_bar(percent, length=12):
    percent = max(0, min(100, percent))
    filled = int(length * percent / 100)
    
    # Màu sắc thay đổi theo tiến độ (Xanh -> Vàng -> Cam -> Đỏ)
    if percent < 25: emoji = "🟩"
    elif percent < 50: emoji = "🟨"
    elif percent < 75: emoji = "🟧"
    else: emoji = "🟥"
    
    return emoji * filled + "⬜" * (length - filled)

def number_to_emoji(num: int):
    """Converts a number to regional indicator emojis (blue boxes)"""
    emoji_map = {
        '0': '0️⃣', '1': '1️⃣', '2': '2️⃣', '3': '3️⃣', '4': '4️⃣', 
        '5': '5️⃣', '6': '6️⃣', '7': '7️⃣', '8': '8️⃣', '9': '9️⃣'
    }
    return "".join(emoji_map[d] for d in str(num))
