import os
import json
import random
import pytz
import asyncio
from datetime import datetime
from colorama import Fore, Style
from discord import Embed, Color
from dotenv import load_dotenv
from core.format import TXAFormat

load_dotenv()

# --- AI PLATFORM DETECTION ---
# Hỗ trợ: OpenAI, Gemini, cả hai, hoặc không dùng AI (fallback)
_OPENAI_KEY = os.getenv("OPENAI_API_KEY", "").strip()
_GEMINI_KEY = os.getenv("GEMINI_API_KEY", "").strip()

_openai_client = None
_gemini_client = None

if _OPENAI_KEY:
    try:
        from openai import OpenAI
        _openai_client = OpenAI(api_key=_OPENAI_KEY)
    except Exception as _e:
        print(f"[AI] ⚠️ OpenAI init failed: {_e}")

if _GEMINI_KEY:
    try:
        # pyrefly: ignore [missing-import]
        import google.generativeai as genai
        genai.configure(api_key=_GEMINI_KEY)
        _gemini_client = genai.GenerativeModel("gemini-2.0-flash")
    except Exception as _e:
        print(f"[AI] ⚠️ Gemini init failed: {_e}")

_AI_PLATFORM = None
if _openai_client and _gemini_client:
    _AI_PLATFORM = "both"
elif _openai_client:
    _AI_PLATFORM = "openai"
elif _gemini_client:
    _AI_PLATFORM = "gemini"
else:
    _AI_PLATFORM = None

if _AI_PLATFORM:
    print(f"[AI] ✅ Nền tảng AI: {_AI_PLATFORM.upper()}")
else:
    print("[AI] ℹ️ Không có API Key AI — sử dụng cảnh giới mặc định (fallback)")

# --- CONFIG ---
VN_TZ = pytz.timezone('Asia/Ho_Chi_Minh')
ITALIC = "\033[3m"
RESET = Style.RESET_ALL
EMOJI_CACHE_FILE = "cache/emoji_cache.json"

from core.roles_config import DEFAULT_RANKS

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
async def ask_ancestor(system_prompt, user_content, json_mode=False):
    """Hỏi Tổ sư Từ Dương (AI) — hỗ trợ OpenAI, Gemini, hoặc fallback None"""
    if _AI_PLATFORM is None:
        return None

    system_full = f"Bạn là Từ Dương, Tổ sư Thiên Lam Tông. {system_prompt}"

    # --- Thử OpenAI trước nếu có ---
    if _openai_client:
        try:
            args = {
                "model": "gpt-4o",
                "messages": [
                    {"role": "system", "content": system_full},
                    {"role": "user", "content": user_content}
                ],
                "timeout": 15
            }
            if json_mode:
                args["response_format"] = {"type": "json_object"}
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                None, lambda: _openai_client.chat.completions.create(**args)
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            rainbow_log(f"⚠️ OpenAI Error: {e}" + (". Thử Gemini..." if _gemini_client else ""))

    # --- Fallback sang Gemini nếu có ---
    if _gemini_client:
        try:
            prompt = f"{system_full}\n\nNgười dùng: {user_content}"
            if json_mode:
                prompt += "\n\nTRẢ VỀ JSON HỢP LỆ DUY NHẤT, không có markdown hay text thừa."
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                None, lambda: _gemini_client.generate_content(prompt)
            )
            text = response.text.strip()
            # Xóa markdown code block nếu có
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            return text.strip()
        except Exception as e:
            rainbow_log(f"⚠️ Gemini Error: {e}")

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
                # Nếu AI thành công, ta xóa sạch RANKS cũ để dùng hoàn toàn set mới
                RANKS.clear()
                for r in ranks_list:
                    name = r.get('name', 'Vô Danh')
                    color_str = r.get('color', '0x808080')
                    color = int(color_str, 16) if isinstance(color_str, str) else color_str
                    
                    min_layer = r.get('min', 1)
                    # Tìm permissions từ DEFAULT_RANKS gần nhất (không vượt quá min_layer)
                    closest_perms = {}
                    best_match_min = -1
                    for d_name, d_info in DEFAULT_RANKS.items():
                        if d_info['min'] <= min_layer and d_info['min'] > best_match_min:
                            closest_perms = d_info.get('permissions', {})
                            best_match_min = d_info['min']

                    RANKS[name] = {
                        "min": min_layer,
                        "max": r.get('max', 9),
                        "color": color,
                        "emoji": r.get('emoji', '⭐'),
                        "permissions": closest_perms # Kế thừa quyền từ set mặc định
                    }
                
                save_ranks_cache(RANKS)
                rainbow_log(f"✅ [Đạo Pháp] AI đã tạo thành công {len(RANKS)} cảnh giới tu tiên!")
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

def txa_embed(title: str, desc: str, color: Color = Color.from_rgb(47, 49, 54), thumbnail: str = None, image: str = None, footer: str = None):
    """
    Tạo Embed với giao diện Premium (Thiên Lam Tông Style).
    Mặc định sử dụng màu tối sang trọng (Dark Theme friendly).
    """
    # Nếu color là default blue, chuyển sang màu custom sang trọng hơn
    if color == Color.blue():
        color = Color.from_rgb(58, 134, 255) # Bright Blue Premium
        
    embed = Embed(
        title=title, 
        description=desc, 
        color=color,
        timestamp=datetime.now(VN_TZ)
    )
    
    # Premium Footer
    footer_text = footer if footer else "Thiên Lam Tông • Vạn Cổ Trường Tồn"
    embed.set_footer(text=footer_text, icon_url="https://nrotxa.online/uploads/avatar/txa_admintxa_11-22-07%2029-Jan-26.jpg") # Placeholder icon, user can change
    
    if thumbnail:
        embed.set_thumbnail(url=thumbnail)
    
    if image:
        embed.set_image(url=image)
        
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
