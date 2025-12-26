#!/usr/bin/env python3
import discord
from discord import app_commands, Embed, Color
from discord.ext import commands, tasks
from openai import OpenAI
import os, json, random, asyncio, pytz, sys, aiohttp
from datetime import datetime, timedelta
from dotenv import load_dotenv
from colorama import init, Fore, Style

# --- KHỞI TẠO ---
init(autoreset=True)
load_dotenv()
ITALIC = "\033[3m"
RESET = Style.RESET_ALL

# --- PHIÊN BẢN ---
VERSION = "v7.5.0 - Thời Không Luân Chuyển"

# --- NGHỆ THUẬT CHỮ ASCII ---
ASCII_TXA = rf"""
╔══════════════════════════════════════════════════════════════════════╗
║                                                                      ║
║  ████████╗██╗  ██╗ █████╗     ██████╗ ██████╗  ██████╗               ║
║  ╚══██╔══╝╚██╗██╔╝██╔══██╗    ██╔══██╗██╔══██╗██╔═══██╗              ║
║     ██║    ╚███╔╝ ███████║    ██████╔╝██████╔╝██║   ██║              ║
║     ██║    ██╔██╗ ██╔══██║    ██╔═══╝ ██╔══██╗██║   ██║              ║
║     ██║   ██╔╝ ██╗██║  ██║    ██║     ██║  ██║╚██████╔╝              ║
║     ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝    ╚═╝     ╚═╝  ╚═╝ ╚═════╝               ║
║                                                                      ║
║══════════════════════════════════════════════════════════════════════║
║                                                                      ║
║  ⛩️   THIÊN LAM TÔNG - LUYỆN KHÍ MƯỜI VẠN NĂM                        ║
║  🌟  Live Updates System - Hệ Thống Cập Nhật Thời Gian Thực          ║
║                                                                      ║
║══════════════════════════════════════════════════════════════════════║
║                                                                      ║
║  🛠️   Phiên bản:  {VERSION:<49}                                      ║
║  📜  Tác giả:     TXA                                                ║
║  ⚡  Trạng thái:   Đang Khởi Động Pháp Trận...                      ║
║                                                                      ║
╚══════════════════════════════════════════════════════════════════════╝
"""

def rainbow_log(msg, is_ascii=False, is_italic=False):
    colors = [Fore.RED, Fore.YELLOW, Fore.GREEN, Fore.CYAN, Fore.BLUE, Fore.MAGENTA]
    style = ITALIC if is_italic else ""
    if is_ascii:
        lines = msg.splitlines()
        for i, line in enumerate(lines):
            print(colors[i % len(colors)] + line)
    else:
        now = datetime.now(pytz.timezone('Asia/Ho_Chi_Minh')).strftime("%H:%M:%S")
        colored = "".join(colors[i % len(colors)] + c for i, c in enumerate(f"[{now}] {msg}"))
        print(f"{style}{colored}{RESET}")

# --- KIỂM TRA LINH LỰC ---
REQUIRED = ["DISCORD_TOKEN", "OPENAI_API_KEY", "ALLOWED_GUILD_IDS", "ADMIN_IDS"]
if any(not os.getenv(v) for v in REQUIRED):
    rainbow_log("❌ THIẾU CẤU HÌNH TRONG .ENV!", is_italic=True)
    sys.exit(1)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
VN_TZ = pytz.timezone('Asia/Ho_Chi_Minh')
BOT_NAME = "THIEN-LAM-LIVE-AI"

def get_env_ids(key):
    val = os.getenv(key, "")
    return [int(i.strip()) for i in val.split(",") if i.strip().isdigit()]

ALLOWED_GUILDS = get_env_ids("ALLOWED_GUILD_IDS")
ADMIN_IDS = get_env_ids("ADMIN_IDS")
ALLOWED_CHANNEL_IDS = get_env_ids("ALLOWED_CHANNEL_IDS")  # Kênh hướng dẫn & DM redirect

# --- HỆ THỐNG CẢNH GIỚI TU LUYỆN ---
RANKS = {
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

# --- DATABASE ---
def load_db():
    try:
        with open("tu_tien_v5.json", "r", encoding="utf-8") as f: return json.load(f)
    except: return {}

def save_db(data):
    with open("tu_tien_v5.json", "w", encoding="utf-8") as f: json.dump(data, f, indent=4, ensure_ascii=False)

# --- EMOJI CACHE SYSTEM ---
EMOJI_CACHE_FILE = "cache/emoji_cache.json"

def load_emoji_cache():
    try:
        os.makedirs("cache", exist_ok=True)
        with open(EMOJI_CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_emoji_cache(cache):
    os.makedirs("cache", exist_ok=True)
    with open(EMOJI_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=4, ensure_ascii=False)

async def get_cached_emoji(key, prompt):
    """Lấy emoji từ cache hoặc tạo mới bằng AI"""
    cache = load_emoji_cache()
    if key in cache:
        return cache[key]
    
    # Tạo emoji mới bằng AI
    ai_prompt = f"{prompt}. Trả về JSON: {{\"emoji\": \"single emoji character\"}}"
    res = await ask_ancestor("Chọn 1 emoji phù hợp.", ai_prompt, json_mode=True)
    try:
        emoji = json.loads(res).get("emoji", "⭐")
    except:
        emoji = "⭐"
    
    cache[key] = emoji
    save_emoji_cache(cache)
    return emoji

# --- AI HELPER FUNCTIONS ---
async def ask_ancestor(system_prompt, user_content, json_mode=False):
    """Hỏi Tổ sư Từ Dương (AI)"""
    try:
        args = {
            "model": "gpt-4o",
            "messages": [
                {"role": "system", "content": f"Bạn là Từ Dương, Tổ sư Thiên Lam Tông. {system_prompt}"},
                {"role": "user", "content": user_content}
            ]
        }
        if json_mode:
            args["response_format"] = {"type": "json_object"}
        
        response = client.chat.completions.create(**args)
        return response.choices[0].message.content.strip()
    except Exception as e:
        rainbow_log(f"⚠️ Thiên Đạo chấn động (AI Error): {e}")
        return None

async def generate_daily_missions(layer):
    """Tạo 5 nhiệm vụ hàng ngày bằng AI"""
    prompt = f"""Hãy tạo 5 nhiệm vụ tu tiên hàng ngày cho đệ tử tầng {layer} của Thiên Lam Tông.
    
Tham khảo phong cách từ truyện "Luyện Khí Mười Vạn Năm" (https://hoathinh3d.gg/luyen-khi-muoi-van-nam):
- Nhiệm vụ phải có phong cách tu tiên cổ điển
- Tên địa danh: Huyền Thiên Lâm, Vạn Yêu Sơn, Kiếm Các, Đan Phòng...
- Hoạt động: Hái linh dược, tọa thiền luyện khí, diệt yêu thú, luyện đan, tham ngộ kiếm đạo...
- Phù hợp với cảnh giới tu luyện

Trả về JSON chứa danh sách 'missions' gồm: 'id' (1-5), 'title', 'desc', 'difficulty' (E, D, C, B, A, S), 'exp_reward' (50-500), 'time_required' (seconds, 5-20)."""
    
    res = await ask_ancestor("Bạn là Thiên Đạo của Thiên Lam Tông, tạo sứ mệnh theo phong cách tu tiên cổ điển. Trả về JSON format.", prompt, json_mode=True)
    try:
        return json.loads(res).get("missions", [])
    except:
        # Fallback missions phong cách Luyện Khí Mười Vạn Năm
        fallback_missions = [
            {"id": 1, "title": "Hái Linh Dược", "desc": "Thu thập 10 cây Linh Chi trong Huyền Thiên Lâm", "difficulty": "E", "exp_reward": 80, "time_required": 6},
            {"id": 2, "title": "Tọa Thiền Luyện Khí", "desc": "Tĩnh tâm vận chuyển linh khí 100 chu thiên", "difficulty": "D", "exp_reward": 150, "time_required": 8},
            {"id": 3, "title": "Diệt Yêu Thú", "desc": "Tiêu diệt 5 con Huyền Minh Hổ ở Vạn Yêu Sơn", "difficulty": "C", "exp_reward": 250, "time_required": 12},
            {"id": 4, "title": "Luyện Đan Dược", "desc": "Luyện chế 3 viên Trúc Cơ Đan cho tông môn", "difficulty": "B", "exp_reward": 350, "time_required": 15},
            {"id": 5, "title": "Tham Ngộ Kiếm Đạo", "desc": "Lĩnh ngộ Thiên Lam Kiếm Pháp tại Kiếm Các", "difficulty": "A", "exp_reward": 500, "time_required": 20}
        ]
        # Shuffle nội dung nhưng gán lại ID từ 1-5
        shuffled = random.sample(fallback_missions, 5)
        for i, mission in enumerate(shuffled, 1):
            mission["id"] = i
        return shuffled

async def calculate_divine_limit(u):
    """AI tính toán mốc EXP thăng cấp dựa trên tầng và lịch sử nhiệm vụ"""
    layer = u['layer']
    if layer == 1: return 100
    missions_done = u.get("missions_completed", 0)
    prompt = (f"Đệ tử {u['name']} tầng {layer}, đã hoàn thành {missions_done} nhiệm vụ. "
              f"Hãy tính mốc linh lực cần nén ép để đạt tầng tiếp theo. "
              f"Trả về JSON: {{\"goal\": int}}.")
    res = await ask_ancestor("Bạn là Thiên Đạo tính giới hạn tu vi.", prompt, json_mode=True)
    try:
        return json.loads(res).get("goal", layer * 300)
    except:
        return layer * 300

# --- BOT CLASS ---
class ThienLamSect(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=discord.Intents.all())

    async def setup_hook(self):
        rainbow_log(ASCII_TXA, is_ascii=True)
        
        for g_id in ALLOWED_GUILDS:
            try:
                g_obj = discord.Object(id=g_id)
                # Xóa lệnh cũ trong guild
                self.tree.clear_commands(guild=g_obj)
                # Copy global commands vào guild
                self.tree.copy_global_to(guild=g_obj)
                # Sync
                await self.tree.sync(guild=g_obj)
                rainbow_log(f"⚡ Đã đồng bộ pháp trận tại: {g_id} (Instant Update)", is_italic=True)
            except Exception as e:
                rainbow_log(f"❌ Lỗi đồng bộ: {e}")
    
    async def on_ready(self):
        """Tự động sync roles cho tất cả users khi bot ready"""
        rainbow_log(f"✅ Bot đã sẵn sàng! Đăng nhập: {self.user.name}", is_italic=True)
        
        # Đọc database
        db = load_db()
        if not db:
            rainbow_log("📂 Database trống, bỏ qua sync roles", is_italic=True)
            return
        
        # Tạo tất cả roles cảnh giới trước
        rainbow_log("🎭 Đang tạo/kiểm tra roles cảnh giới...", is_italic=True)
        for guild in self.guilds:
            if guild.id not in ALLOWED_GUILDS:
                continue
            
            bot_member = guild.get_member(self.user.id)
            if not bot_member or not bot_member.guild_permissions.manage_roles:
                rainbow_log(f"❌ Bot thiếu quyền Manage Roles trong {guild.name}")
                continue
            
            created_count = 0
            for rank_name, rank_info in RANKS.items():
                role = discord.utils.get(guild.roles, name=rank_name)
                if not role:
                    # Tạo role mới
                    try:
                        # Xác định permissions dựa trên min layer
                        min_layer = rank_info['min']
                        permissions = discord.Permissions()
                        permissions.update(
                            view_channel=True,
                            send_messages=True,
                            read_message_history=True,
                            use_application_commands=True
                        )
                        
                        if min_layer >= 10:
                            permissions.update(embed_links=True, attach_files=True, add_reactions=True)
                        if min_layer >= 30:
                            permissions.update(use_external_emojis=True, use_external_stickers=True, create_public_threads=True)
                        if min_layer >= 50:
                            permissions.update(create_private_threads=True, send_messages_in_threads=True, manage_threads=True)
                        if min_layer >= 100:
                            permissions.update(change_nickname=True)
                        
                        role = await guild.create_role(
                            name=rank_name,
                            color=discord.Color(rank_info['color']),
                            permissions=permissions,
                            hoist=True,
                            mentionable=True,
                            reason=f"Tự động tạo role cảnh giới {rank_name}"
                        )
                        
                        # Di chuyển role xuống dưới bot role
                        try:
                            await role.edit(position=max(1, bot_member.top_role.position - 1))
                        except:
                            pass
                        
                        created_count += 1
                        rainbow_log(f"  ✅ Tạo role: {rank_name} (Layer {min_layer}+)", is_italic=True)
                    except Exception as e:
                        rainbow_log(f"  ❌ Lỗi tạo role {rank_name}: {e}")
                else:
                    rainbow_log(f"  ✓ Role đã tồn tại: {rank_name}", is_italic=True)
            
            if created_count > 0:
                rainbow_log(f"🎭 Đã tạo {created_count} roles mới trong {guild.name}!", is_italic=True)
        
        # Sync roles cho users
        rainbow_log(f"🔄 Bắt đầu sync roles cho {len(db)} đệ tử...", is_italic=True)
        synced_count = 0
        
        for guild in self.guilds:
            if guild.id not in ALLOWED_GUILDS:
                continue
                
            for user_id, user_data in db.items():
                try:
                    member = guild.get_member(int(user_id))
                    if not member:
                        continue
                    
                    # Admin luôn có role cao nhất (Thánh Nhân)
                    if int(user_id) in ADMIN_IDS:
                        await update_member_rank(member, 100000)  # Thánh Nhân
                        rainbow_log(f"👑 Admin {member.name} được gán role Thánh Nhân", is_italic=True)
                    else:
                        layer = user_data.get("layer", 1)
                        await update_member_rank(member, layer)
                    
                    synced_count += 1
                    
                except Exception as e:
                    rainbow_log(f"❌ Lỗi sync role cho {user_id}: {e}")
        
        rainbow_log(f"✅ Đã sync roles cho {synced_count} đệ tử!", is_italic=True)
        
        # Start background task cho daily reminders
        if not self.check_daily_reminders.is_running():
            self.check_daily_reminders.start()
            rainbow_log("📩 Đã khởi động daily reminder system!", is_italic=True)
    
    async def on_message(self, message):
        """Xử lý tin nhắn DM và log"""
        # Bỏ qua tin nhắn từ bot
        if message.author.bot:
            return
        
        # Chỉ xử lý DM (không phải tin nhắn trong server)
        if message.guild is None:
            # Log console
            rainbow_log(f"📩 DM từ {message.author.name} ({message.author.id}): {message.content}", is_italic=True)
            
            # Tạo embed cảnh báo
            embed = Embed(
                title="⛔ Kênh DM Không Được Cấp Phép",
                description=(
                    "⚠️ **CẢNH BÁO:** Tin nhắn riêng không được pháp trận ghi nhận!\n\n"
                    "📜 Vui lòng trở về linh địa chính thức để thi triển pháp lệnh.\n"
                    "⚡ Dùng các slash command như `/start`, `/info`, `/tu_luyen`.\n"
                    "💾 Mọi hành động sẽ được lưu trữ khi thực hiện tại server."
                ),
                color=Color.red()
            )
            
            # Tạo view với buttons
            view = discord.ui.View(timeout=None)
            
            if not ALLOWED_CHANNEL_IDS:
                # Không có channel ID -> redirect về server
                for guild in self.guilds:
                    if guild.id in ALLOWED_GUILDS:
                        button = discord.ui.Button(
                            label=f"🏰 Trở về {guild.name}",
                            style=discord.ButtonStyle.link,
                            url=f"https://discord.com/channels/{guild.id}"
                        )
                        view.add_item(button)
                        break
            elif len(ALLOWED_CHANNEL_IDS) == 1:
                # 1 channel ID -> redirect về channel đó
                channel_id = ALLOWED_CHANNEL_IDS[0]
                channel = self.get_channel(channel_id)
                if channel:
                    button = discord.ui.Button(
                        label=f"📍 Đến #{channel.name}",
                        style=discord.ButtonStyle.link,
                        url=f"https://discord.com/channels/{channel.guild.id}/{channel_id}"
                    )
                    view.add_item(button)
            else:
                # Nhiều channel IDs -> hiển thị tất cả
                for channel_id in ALLOWED_CHANNEL_IDS[:5]:  # Giới hạn 5 buttons
                    channel = self.get_channel(channel_id)
                    if channel:
                        button = discord.ui.Button(
                            label=f"📍 #{channel.name}",
                            style=discord.ButtonStyle.link,
                            url=f"https://discord.com/channels/{channel.guild.id}/{channel_id}"
                        )
                        view.add_item(button)
            
            embed.add_field(
                name="🌀 Cổng Dịch Chuyển",
                value="Nhấn nút bên dưới để trở về Thiên Lam Tông",
                inline=False
            )
            embed.add_field(
                name="💡 Cần Trợ Giúp?",
                value="Hãy ping Tổ Sư tại kênh hướng dẫn.",
                inline=False
            )
            
            now = datetime.now(VN_TZ).strftime("%H:%M:%S %d/%m/%y")
            embed.set_footer(text=f"Time: {now} - {BOT_NAME} BY TXA!")
            
            try:
                await message.author.send(embed=embed, view=view)
            except discord.Forbidden:
                rainbow_log(f"❌ Không thể gửi DM cho {message.author.name}")
    
    @tasks.loop(hours=1)
    async def check_daily_reminders(self):
        """Gửi DM nhắc nhở điểm danh vào 6:00 AM (1 giờ trước reset)"""
        now = datetime.now(VN_TZ)
        
        # Chỉ chạy vào 6:00 AM
        if now.hour != 6:
            return
        
        rainbow_log("📩 Kiểm tra daily reminders...", is_italic=True)
        db = load_db()
        today = now.strftime("%Y-%m-%d")
        sent_count = 0
        
        for user_id, user_data in db.items():
            try:
                # Check nếu chưa điểm danh hôm nay
                last_daily_date = user_data.get("last_daily_date", "")
                
                if last_daily_date != today:
                    # User chưa điểm danh hôm nay
                    user = await self.fetch_user(int(user_id))
                    streak = user_data.get("daily_streak", 0)
                    
                    # Tạo embed nhắc nhở
                    streak_emoji = number_to_emoji(streak)
                    
                    embed = Embed(
                        title="⏰ Nhắc Nhở Điểm Danh",
                        description=(
                            f"🔥 **Chuỗi điểm danh hiện tại:** {streak_emoji} ngày\n"
                            f"⚠️ **Còn 1 giờ nữa là reset!** (7:00 AM)\n\n"
                            f"💡 Hãy dùng `/daily` ngay để giữ chuỗi streak!\n"
                            f"📈 Streak càng cao, phần thưởng càng lớn!"
                        ),
                        color=Color.orange()
                    )
                    
                    # Tạo view với buttons redirect
                    view = discord.ui.View(timeout=None)
                    
                    if not ALLOWED_CHANNEL_IDS:
                        # Redirect về server
                        for guild in self.guilds:
                            if guild.id in ALLOWED_GUILDS:
                                button = discord.ui.Button(
                                    label=f"🏰 Trở về {guild.name}",
                                    style=discord.ButtonStyle.link,
                                    url=f"https://discord.com/channels/{guild.id}"
                                )
                                view.add_item(button)
                                break
                    elif len(ALLOWED_CHANNEL_IDS) == 1:
                        # Redirect về 1 channel
                        channel_id = ALLOWED_CHANNEL_IDS[0]
                        channel = self.get_channel(channel_id)
                        if channel:
                            button = discord.ui.Button(
                                label=f"📍 Đến #{channel.name}",
                                style=discord.ButtonStyle.link,
                                url=f"https://discord.com/channels/{channel.guild.id}/{channel_id}"
                            )
                            view.add_item(button)
                    else:
                        # Nhiều channels
                        for channel_id in ALLOWED_CHANNEL_IDS[:5]:
                            channel = self.get_channel(channel_id)
                            if channel:
                                button = discord.ui.Button(
                                    label=f"📍 #{channel.name}",
                                    style=discord.ButtonStyle.link,
                                    url=f"https://discord.com/channels/{channel.guild.id}/{channel_id}"
                                )
                                view.add_item(button)
                    
                    embed.add_field(
                        name="🌀 Cổng Dịch Chuyển",
                        value="Nhấn nút bên dưới để trở về Thiên Lam Tông",
                        inline=False
                    )
                    
                    now_str = now.strftime("%H:%M:%S %d/%m/%y")
                    embed.set_footer(text=f"Time: {now_str} - {BOT_NAME} BY TXA!")
                    
                    try:
                        await user.send(embed=embed, view=view)
                        sent_count += 1
                        rainbow_log(f"  ✅ Gửi reminder cho {user.name}", is_italic=True)
                    except discord.Forbidden:
                        rainbow_log(f"  ❌ Không thể DM {user.name}")
                    except Exception as e:
                        rainbow_log(f"  ❌ Lỗi gửi reminder cho {user_id}: {e}")
            
            except Exception as e:
                rainbow_log(f"❌ Lỗi xử lý reminder cho {user_id}: {e}")
        
        if sent_count > 0:
            rainbow_log(f"📩 Đã gửi {sent_count} daily reminders!", is_italic=True)
    
    @check_daily_reminders.before_loop
    async def before_check_daily_reminders(self):
        """Đợi bot ready trước khi start task"""
        await self.wait_until_ready()



bot = ThienLamSect()

def txa_embed(title, desc, color=Color.random()):
    embed = Embed(title=title, description=desc, color=color)
    now = datetime.now(VN_TZ).strftime("%H:%M:%S %d/%m/%y")
    embed.set_footer(text=f"Pháp giới: {now} - ©️{BOT_NAME} BY TXA!")
    return embed

def get_progress_bar(percent, length=10):
    filled = int(length * percent / 100)
    return "🟩" * filled + "⬜" * (length - filled)

def number_to_emoji(num):
    """Chuyển số thành emoji số"""
    emoji_map = {
        '0': '0️⃣', '1': '1️⃣', '2': '2️⃣', '3': '3️⃣', '4': '4️⃣',
        '5': '5️⃣', '6': '6️⃣', '7': '7️⃣', '8': '8️⃣', '9': '9️⃣'
    }
    return ''.join(emoji_map[d] for d in str(num))

async def check_access(interaction: discord.Interaction):
    db = load_db()
    if str(interaction.user.id) not in db:
        await interaction.response.send_message("⛩️ Ngươi chưa ghi danh nhập môn! Hãy dùng `/start` để bắt đầu.", ephemeral=True)
        return False
    return True

async def update_member_rank(member: discord.Member, layer: int):
    """Cập nhật nickname và Discord role dựa trên cảnh giới tu luyện"""
    try:
        # Lấy thông tin cảnh giới
        rank_name, rank_info = get_rank_info(layer)
        guild = member.guild
        
        # Kiểm tra bot permissions
        bot_member = guild.get_member(bot.user.id)
        if not bot_member.guild_permissions.manage_roles:
            rainbow_log(f"❌ Bot thiếu quyền Manage Roles trong server {guild.name}")
            return
        
        if not bot_member.guild_permissions.manage_nicknames:
            rainbow_log(f"⚠️ Bot thiếu quyền Manage Nicknames trong server {guild.name}")
        
        # Tìm hoặc tạo role cho cảnh giới này
        role = discord.utils.get(guild.roles, name=rank_name)
        
        if not role:
            # Xác định permissions dựa trên cảnh giới
            permissions = discord.Permissions()
            
            # Quyền cơ bản cho tất cả
            permissions.update(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                use_application_commands=True
            )
            
            # Thêm quyền dựa trên layer
            if layer >= 10:  # Luyện Khí trở lên
                permissions.update(
                    embed_links=True,
                    attach_files=True,
                    add_reactions=True
                )
            
            if layer >= 30:  # Kim Đan trở lên
                permissions.update(
                    use_external_emojis=True,
                    use_external_stickers=True,
                    create_public_threads=True
                )
            
            if layer >= 50:  # Hóa Thần trở lên
                permissions.update(
                    create_private_threads=True,
                    send_messages_in_threads=True,
                    manage_threads=True
                )
            
            if layer >= 100:  # Đại Thừa trở lên
                permissions.update(
                    mention_everyone=False,
                    manage_messages=False,
                    change_nickname=True
                )
            
            if layer >= 200:  # Chân Tiên trở lên
                permissions.update(
                    manage_nicknames=False,
                    kick_members=False,
                    ban_members=False
                )
            
            # Tạo role mới với màu và permissions
            # Đặt position thấp hơn bot role
            role = await guild.create_role(
                name=rank_name,
                color=discord.Color(rank_info['color']),
                permissions=permissions,
                hoist=True,
                mentionable=True,
                reason=f"Tự động tạo role cho cảnh giới {rank_name}"
            )
            
            # Di chuyển role xuống dưới bot role
            bot_top_role = bot_member.top_role
            try:
                await role.edit(position=max(1, bot_top_role.position - 1))
            except discord.Forbidden:
                rainbow_log(f"⚠️ Không thể di chuyển role {rank_name}, giữ position mặc định")
            
            rainbow_log(f"🎭 Đã tạo role mới: {rank_name} (Layer {layer}+)", is_italic=True)
        
        # Kiểm tra hierarchy trước khi gán role
        if role.position >= bot_member.top_role.position:
            rainbow_log(f"❌ Role {rank_name} cao hơn bot role, không thể gán!")
            return
        
        # Xóa tất cả roles cảnh giới cũ của user
        old_rank_roles = [r for r in member.roles if r.name in RANKS.keys()]
        if old_rank_roles:
            await member.remove_roles(*old_rank_roles, reason="Cập nhật cảnh giới mới")
        
        # Gán role mới
        await member.add_roles(role, reason=f"Đạt cảnh giới {rank_name} - Tầng {layer}")
        
        # Cập nhật nickname
        try:
            new_nick = f"[{rank_name}] {member.name}"
            await member.edit(nick=new_nick[:32])  # Discord giới hạn 32 ký tự
        except discord.Forbidden:
            rainbow_log(f"⚠️ Không thể đổi nickname cho {member.name}")
        
        rainbow_log(f"🎭 {member.name} được gán role: {rank_name}", is_italic=True)
    except discord.Forbidden as e:
        rainbow_log(f"❌ Lỗi quyền khi cập nhật role: {e}")
    except Exception as e:
        rainbow_log(f"❌ Lỗi cập nhật role: {e}")

def get_rank_info(layer: int):
    """Lấy thông tin cảnh giới dựa trên tầng"""
    for rank_name, info in sorted(RANKS.items(), key=lambda x: x[1]['min'], reverse=True):
        if layer >= info['min']:
            return rank_name, info
    return "Phàm Nhân", RANKS["Phàm Nhân"]

# --- COMMANDS ---

@bot.tree.command(name="daily", description="Nhận quà 7h sáng (Real-time countdown)")
async def daily(interaction: discord.Interaction):
    if not await check_access(interaction): return
    db = load_db(); uid = str(interaction.user.id)
    now = datetime.now(VN_TZ)
    reset = now.replace(hour=7, minute=0, second=0, microsecond=0)
    if now < reset: reset -= timedelta(days=1)
    
    if db[uid].get("last_daily", 0) > reset.timestamp():
        next_7am = reset + timedelta(days=1)
        # Sử dụng defer trước khi tính toán để tránh hết hạn interaction
        await interaction.response.defer(ephemeral=True)
        
        # Hiển thị countdown real-time
        msg = None
        for i in range(900):  # 15 phút countdown
            rem = next_7am - datetime.now(VN_TZ)
            if rem.total_seconds() <= 0: 
                await interaction.followup.send(
                    embed=txa_embed("✅ Đã Đến Giờ!", "Ngươi có thể nhận quà rồi! Hãy dùng `/daily` lại.", Color.green()),
                    ephemeral=True
                )
                break
            
            # Tính toán thời gian còn lại
            total_seconds = int(rem.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60
            
            embed = txa_embed("⏳ Chờ Đợi", f"Ngươi đã nhận quà hôm nay rồi.\n\n⏰ Quà tiếp theo sau:\n**{hours:02d}h {minutes:02d}m {seconds:02d}s**", Color.red())
            
            if i == 0:
                msg = await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                try:
                    await msg.edit(embed=embed)
                except: break # Phòng trường hợp user đóng message
            
            await asyncio.sleep(1)
        return

    await interaction.response.defer()
    
    # Tính streak
    today = now.strftime("%Y-%m-%d")
    last_daily_date = db[uid].get("last_daily_date", "")
    current_streak = db[uid].get("daily_streak", 0)
    
    if last_daily_date:
        try:
            yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")
            if last_daily_date == yesterday:
                current_streak += 1
            elif last_daily_date != today:
                current_streak = 1
        except:
            current_streak = 1
    else:
        current_streak = 1
    
    # Tính phần thưởng
    base_reward = 1000
    streak_bonus = current_streak * 100
    total_reward = base_reward + streak_bonus
    
    # AI tạo câu chuyện (Xử lý lỗi quota)
    story = "Thiên Đạo cảm ứng, ban xuống linh khí dồi dào thấm nhuần kinh mạch."
    try:
        prompt = f"Đệ tử {db[uid]['name']} điểm danh ngày thứ {current_streak} liên tục, nhận {total_reward} linh lực. Viết 1 câu chuyện ngắn thâm sâu. JSON: {{\"story\": \"string\"}}"
        res_raw = await ask_ancestor("Thiên Đạo ban phước.", prompt, json_mode=True)
        res = json.loads(res_raw)
        story = res.get("story", story)
    except Exception as e:
        rainbow_log(f"⚠️ Dùng fallback story do lỗi AI: {e}")

    # Cập nhật database
    db[uid]["exp"] += total_reward
    db[uid]["last_daily"] = now.timestamp()
    db[uid]["last_daily_date"] = today
    db[uid]["daily_streak"] = current_streak
    
    # Kiểm tra đột phá
    leveled_up = False
    while db[uid]["exp"] >= db[uid].get("goal", 100):
        db[uid]["exp"] -= db[uid].get("goal", 100)
        db[uid]["layer"] += 1
        db[uid]["goal"] = await calculate_divine_limit(db[uid])
        leveled_up = True
    
    save_db(db)
    
    streak_emoji = number_to_emoji(current_streak)
    embed = txa_embed("🎁 Thiên Đạo Ban Phước", f"**Tổ sư phán:** \"{story}\"", Color.blue())
    
    reward_text = f"💰 **Phần thưởng:**\n"
    reward_text += f"  • Cơ bản: `{base_reward} EXP`\n"
    if streak_bonus > 0:
        reward_text += f"  • Streak bonus: `+{streak_bonus} EXP`\n"
    reward_text += f"  • **Tổng cộng: `{total_reward} EXP`**"
    embed.add_field(name="📈 Linh Lực Nhận Được", value=reward_text, inline=False)
    
    streak_text = f"🔥 **Chuỗi hiện tại:** {streak_emoji} ngày\n"
    streak_text += f"⚠️ Đừng quên điểm danh ngày mai để giữ streak!"
    embed.add_field(name="📅 Điểm Danh Liên Tục", value=streak_text, inline=False)
    
    if leveled_up:
        embed.add_field(name="🔥 ĐỘT PHÁ CẢNH GIỚI!", value=f"Chúc mừng đệ tử đạt tới **Tầng {db[uid]['layer']}**!", inline=False)
        embed.color = Color.gold()
        await update_member_rank(interaction.user, db[uid]["layer"])
        
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="phat_truat", description="Phế tu vi đệ tử (Chỉ dành cho Tổ Sư)")
@app_commands.describe(user="Đệ tử cần phế tu vi", ly_do="Lý do hình phạt")
async def phat_truat(interaction: discord.Interaction, user: discord.Member, ly_do: str):
    if interaction.user.id not in ADMIN_IDS: 
        return await interaction.response.send_message("❌ Ngươi không có quyền hạn của Tổ Sư! Cút!", ephemeral=True)
    
    db = load_db(); uid = str(user.id)
    if uid in db:
        old_layer = db[uid]["layer"]
        db[uid]["layer"] = 1
        db[uid]["exp"] = 0
        db[uid]["goal"] = 100
        save_db(db)
        await update_member_rank(user, 1)
        
        rainbow_log(f"⚡ TỔ SƯ {interaction.user.name} PHẾ TU VI {user.name} TẠI {interaction.guild.name}. Tầng cũ: {old_layer}. LÝ DO: {ly_do}", is_italic=True)
        
        embed = txa_embed("⚡ Hình Phạt Thiên Đạo", f"Phế bỏ tu vi của {user.mention} về lại Tầng 1.\n\n📜 **Lý do:** {ly_do}", Color.red())
        embed.set_author(name=f"Tổ Sư {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)
        await interaction.response.send_message(embed=embed)
    else:
        await interaction.response.send_message("⛩️ Đệ tử này chưa có trong danh sách thu nhận!", ephemeral=True)

@bot.tree.command(name="info", description="Xem thông tin tu luyện hiện tại")
async def info(interaction: discord.Interaction):
    await interaction.response.defer()
    if not await check_access(interaction): return
    db = load_db(); uid = str(interaction.user.id)
    user = db[uid]

    
    # Lấy thông tin cảnh giới
    rank_name, rank_info = get_rank_info(user['layer'])
    
    # Tính progress
    progress_percent = (user['exp'] / user.get('goal', 100)) * 100
    progress_bar = get_progress_bar(progress_percent, 15)
    
    # Lấy emoji từ cache hoặc tạo mới
    rank_emoji = await get_cached_emoji(f"rank_{rank_name}", f"Emoji đại diện cho cảnh giới tu tiên '{rank_name}'")
    
    # AI tạo mô tả cảnh giới
    ai_prompt = f"Đệ tử {user['name']} đang ở cảnh giới {rank_name}, tầng {user['layer']}. Hãy viết 1-2 câu mô tả ngắn gọn, huyền bí về trạng thái tu vi hiện tại của họ (phong cách tiên hiệp). JSON: {{\"description\": \"string\"}}"
    res_raw = await ask_ancestor("Mô tả cảnh giới tu luyện.", ai_prompt, json_mode=True)
    try:
        description = json.loads(res_raw).get("description", f"Tu vi đang ở cảnh giới {rank_name}.")
    except:
        description = f"Linh khí vận chuyển, đang ở cảnh giới {rank_name}."
    
    # Tạo embed cải tiến
    embed = Embed(title=f"{rank_emoji} {rank_name} - Tầng {user['layer']}", description=f"*{description}*", color=rank_info['color'])
    
    # Thông tin cơ bản
    embed.add_field(name="👤 Đạo Hiệu", value=f"```{user['name']}```", inline=True)
    embed.add_field(name="💠 Cảnh Giới", value=f"```{rank_name}```", inline=True)
    embed.add_field(name="🔼 Tu Vi", value=f"```Tầng {user['layer']}```", inline=True)
    
    # Progress bar
    embed.add_field(
        name="✨ Tu Vi Tiến Độ",
        value=f"{progress_bar}\n**{user['exp']}** / **{user.get('goal', 100)}** ({int(progress_percent)}%)",
        inline=False
    )
    
    # Thống kê chi tiết
    missions_today = len([m for m in user.get('missions', []) if m.get('done')])
    total_missions_today = len(user.get('missions', []))
    
    stats = f"🎯 Nhiệm vụ hôm nay: **{missions_today}/{total_missions_today}**\n"
    stats += f"📈 Tổng nhiệm vụ hoàn thành: **{user.get('missions_completed', 0)}**\n"
    
    # Tính daily streak (số ngày liên tục nhận quà)
    last_daily = user.get('last_daily', 0)
    if last_daily > 0:
        days_since = (datetime.now(VN_TZ).timestamp() - last_daily) / 86400
        if days_since < 2:  # Trong vòng 2 ngày
            stats += f"🔥 Streak: **{int(user.get('daily_streak', 1))} ngày**"
    
    embed.add_field(name="📊 Thống Kê", value=stats, inline=False)
    
    # Cảnh giới tiếp theo
    next_rank = None
    for r_name, r_info in sorted(RANKS.items(), key=lambda x: x[1]['min']):
        if r_info['min'] > user['layer']:
            next_rank = r_name
            break
    
    if next_rank:
        embed.add_field(name="🎯 Mục Tiêu Tiếp Theo", value=f"**{next_rank}** (Tầng {RANKS[next_rank]['min']})", inline=False)
    
    now = datetime.now(VN_TZ).strftime("%H:%M:%S %d/%m/%y")
    embed.set_footer(text=f"Pháp giới: {now} - ©️{BOT_NAME} BY TXA!")
    embed.set_thumbnail(url=interaction.user.display_avatar.url)
    
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="bxh", description="Xem bảng xếp hạng Thiên Lam Tông")
async def bxh(interaction: discord.Interaction):
    await interaction.response.defer()
    db = load_db()
    
    if not db:
        return await interaction.followup.send(embed=txa_embed("📊 Bảng Xếp Hạng", "Chưa có đệ tử nào ghi danh!", Color.red()))
    
    # Sắp xếp theo tầng
    sorted_users = sorted(db.items(), key=lambda x: (x[1].get('layer', 0), x[1].get('exp', 0)), reverse=True)
    
    # Lấy top 10
    top_10 = sorted_users[:10]
    
    # Tạo description
    desc = ""
    for idx, (uid, user_data) in enumerate(top_10, 1):
        rank_name, rank_info = get_rank_info(user_data['layer'])
        medal = "🥇" if idx == 1 else "🥈" if idx == 2 else "🥉" if idx == 3 else f"**{idx}.**"
        desc += f"{medal} **{user_data['name']}**\n"
        desc += f"└ {rank_info['emoji']} {rank_name} - Tầng {user_data['layer']} ({user_data['exp']}/{user_data.get('goal', 100)} EXP)\n\n"
    
    # Thống kê tổng quan
    total_disciples = len(db)
    avg_layer = sum(u.get('layer', 1) for u in db.values()) / total_disciples if total_disciples > 0 else 0
    highest_layer = max((u.get('layer', 1) for u in db.values()), default=1)
    
    embed = Embed(title="📊 Bảng Xếp Hạng Thiên Lam Tông", description=desc, color=Color.gold())
    embed.add_field(name="👥 Tổng Đệ Tử", value=f"**{total_disciples}**", inline=True)
    embed.add_field(name="📈 Tầng TB", value=f"**{avg_layer:.1f}**", inline=True)
    embed.add_field(name="🏆 Cao Nhất", value=f"**Tầng {highest_layer}**", inline=True)
    
    now = datetime.now(VN_TZ).strftime("%H:%M:%S %d/%m/%y")
    embed.set_footer(text=f"Pháp giới: {now} - ©️{BOT_NAME} BY TXA!")
    
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="start", description="Ghi danh vào Thiên Lam Tông")
async def start(interaction: discord.Interaction):
    await interaction.response.defer()
    db = load_db(); uid = str(interaction.user.id)
    if uid in db: return await interaction.followup.send("Ngươi đã ghi danh rồi!", ephemeral=True)
    
    # AI tạo lời chào đón
    msg = await ask_ancestor(
        "Bạn là Tổ Sư Từ Dương của Thiên Lam Tông, chào đón đệ tử mới theo phong cách tu tiên cổ điển.", 
        f"Đệ tử {interaction.user.display_name} nhập môn Thiên Lam Tông. Hãy viết 2-3 câu chào đón trang trọng, khuyến khích họ tu luyện."
    )
    
    # Tạo database
    db[uid] = {
        "name": interaction.user.display_name, 
        "layer": 1, 
        "exp": 0, 
        "goal": 100, 
        "last_mission_reset": 0, 
        "missions": [], 
        "missions_completed": 0, 
        "last_daily": 0, 
        "current_mission": None,
        "daily_streak": 0
    }
    save_db(db)
    
    # Tạo embed đẹp
    embed = Embed(
        title="⛩️ Thiên Lam Tông - Nhập Môn Pháp Lệnh",
        description=f"**Tổ Sư Từ Dương phán:**\n*\"{msg or 'Chào mừng ngươi gia nhập Thiên Lam Tông!'}\"*",
        color=Color.gold()
    )
    
    embed.add_field(
        name="🌟 Thông Tin Đệ Tử",
        value=f"👤 **Đạo Hiệu:** {interaction.user.display_name}\n💠 **Cảnh Giới:** Phàm Nhân\n🔼 **Tu Vi:** Tầng 1",
        inline=False
    )
    
    embed.add_field(
        name="📜 Hướng Dẫn Tu Luyện",
        value=(
            "🎯 `/nhiem_vu` - Nhận sứ mệnh hàng ngày\n"
            "⚔️ `/lam_nhiem_vu` - Thực hiện nhiệm vụ\n"
            "🧘 `/tu_luyen` - Tọa thiền luyện khí\n"
            "🎁 `/daily` - Nhận quà mỗi ngày (7h sáng)\n"
            "📊 `/info` - Xem thông tin tu vi\n"
            "🏆 `/bxh` - Bảng xếp hạng tông môn"
        ),
        inline=False
    )
    
    embed.add_field(
        name="💡 Lời Khuyên",
        value="*Hãy bắt đầu bằng `/nhiem_vu` để nhận nhiệm vụ hàng ngày và `/daily` để nhận quà từ Thiên Đạo!*",
        inline=False
    )
    
    embed.set_thumbnail(url=interaction.user.display_avatar.url)
    embed.set_footer(text=f"Chúc mừng {interaction.user.display_name} gia nhập Thiên Lam Tông! - ©️{BOT_NAME}")
    
    # Gán role Phàm Nhân cho user mới
    await update_member_rank(interaction.user, 1)
    
    rainbow_log(f"⛩️ {interaction.user.display_name} nhập môn Thiên Lam Tông", is_italic=True)
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="nhiem_vu", description="Xem sứ mệnh hàng ngày (Cập nhật tự động)")
async def nhiem_vu(interaction: discord.Interaction):
    # Gọi defer ngay lập tức
    await interaction.response.defer(ephemeral=True)
    
    db = load_db(); uid = str(interaction.user.id); u = db.get(uid)
    if not u: return await interaction.followup.send("Hãy `/start` trước!", ephemeral=True)
    
    # Không có nhiệm vụ đang làm, hoặc có thì cũng hiển thị danh sách với status động
    now_ts = datetime.now(VN_TZ).timestamp()
    today_7am = datetime.now(VN_TZ).replace(hour=7, minute=0, second=0, microsecond=0)
    if datetime.now(VN_TZ) < today_7am: today_7am -= timedelta(days=1)
    
    if u.get("last_mission_reset", 0) < today_7am.timestamp():
        u["missions"] = await generate_daily_missions(u['layer'])
        u["last_mission_reset"] = now_ts
        save_db(db)



    reset_time = today_7am + timedelta(days=1)

    # Kiểm tra xem đã hoàn thành hết nhiệm vụ chưa
    all_done = all(m.get("done", False) for m in u["missions"]) if u["missions"] else False
    
    if all_done:
        # Hiển thị thông báo đặc biệt khi hoàn thành hết (với countdown real-time)
        for i in range(900):  # 15 phút countdown
            rem = reset_time - datetime.now(VN_TZ)
            total_seconds = int(rem.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60
            
            desc = f"🎉 **Chúc mừng! Ngươi đã hoàn thành tất cả nhiệm vụ hôm nay!**\n\n"
            desc += f"✨ Tổng số nhiệm vụ: **{len(u['missions'])}**\n"
            desc += f"📈 Tổng EXP nhận được: **{sum(m.get('exp_reward', 0) for m in u['missions'])}**\n\n"
            desc += f"⏰ Nhiệm vụ mới sẽ được nhận vào: **{hours:02d}h {minutes:02d}m {seconds:02d}s**\n\n"
            desc += f"💡 *Hãy dùng `/tu_luyen` hoặc `/daily` để tiếp tục tu luyện!*"
            
            embed = txa_embed("🏆 Hoàn Thành Xuất Sắc!", desc, Color.gold())
            
            if i == 0:
                msg = await interaction.followup.send(embed=embed)
            else:
                await msg.edit(embed=embed)
            
            await asyncio.sleep(1)
        return

    # Hiển thị danh sách nhiệm vụ với countdown real-time
    for i in range(900):  # 15 phút
        rem = reset_time - datetime.now(VN_TZ)
        total_seconds = int(rem.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        
        desc = f"✨ **Thiên Đạo sẽ đổi sứ mệnh trong:** **{hours:02d}h {minutes:02d}m {seconds:02d}s**\n\n"
        
        # Kiểm tra current_mission để hiển thị status động
        current = u.get("current_mission")
        current_id = current.get("id") if current else None
        
        # Nếu có current_mission, tính thời gian còn lại
        if current:
            start_time = current.get("start_time", datetime.now(VN_TZ).timestamp())
            total_time = current.get("time_required", 10)
            elapsed = datetime.now(VN_TZ).timestamp() - start_time
            remaining = max(0, total_time - int(elapsed))
        
        for m in u["missions"]:
            # Xác định status
            if m.get("done"):
                status = "✅ Đã hoàn thành"
            elif current_id == m["id"]:
                # Nhiệm vụ đang làm
                if remaining <= 0:
                    status = "✅ Đã hoàn thành (Chờ xác nhận)"
                else:
                    percent = min(100, (elapsed / total_time) * 100)
                    status = f"🔄 Đang làm ({int(percent)}% - {remaining}s)"
            else:
                status = "⏳ Đang chờ"
            
            desc += f"📜 **[{m['id']}] {m['title']}** ({m['difficulty']})\n└ *{m['desc']}*\n└ Thưởng: `{m['exp_reward']} EXP` | `{m.get('time_required', 10)}s` | {status}\n\n"
        
        embed = txa_embed("📋 Cửu Thiên Sứ Mệnh", desc, Color.blue())
        
        if i == 0:
            msg = await interaction.followup.send(embed=embed)
        else:
            await msg.edit(embed=embed)
        
        await asyncio.sleep(1)

# Autocomplete cho lam_nhiem_vu
async def mission_autocomplete(interaction: discord.Interaction, current: str):
    db = load_db()
    uid = str(interaction.user.id)
    
    if uid not in db or not db[uid].get("missions"):
        return []
    
    missions = db[uid]["missions"]
    return [
        app_commands.Choice(name=f"[{m['id']}] {m['title']} ({m['difficulty']}) - {m['exp_reward']} EXP", value=m['id'])
        for m in missions if not m.get("done") and (current.lower() in m['title'].lower() or current == "")
    ][:25]  # Discord giới hạn 25 choices

@bot.tree.command(name="lam_nhiem_vu", description="Thực hiện sứ mệnh với tiến độ thực tế")
@app_commands.autocomplete(mission_id=mission_autocomplete)
async def lam_nhiem_vu(interaction: discord.Interaction, mission_id: int):
    # Gọi defer ngay lập tức
    await interaction.response.defer()
    
    db = load_db(); uid = str(interaction.user.id); u = db.get(uid)
    if not u: return await interaction.followup.send("Hãy `/start` trước!", ephemeral=True)
    
    # Kiểm tra xem đang làm nhiệm vụ khác không
    if u.get("current_mission"):
        return await interaction.followup.send("⚔️ Ngươi đang thực hiện nhiệm vụ khác! Hãy dùng `/nhiem_vu` để xem tiến độ.", ephemeral=True)
    
    # Kiểm tra xem user đã nhận nhiệm vụ chưa
    if not u.get("missions"):
        return await interaction.followup.send("⛩️ Ngươi chưa nhận nhiệm vụ! Hãy dùng `/nhiem_vu` để nhận nhiệm vụ hàng ngày.", ephemeral=True)

    m = next((item for item in u["missions"] if item["id"] == mission_id), None)
    if not m: return await interaction.followup.send("Sứ mệnh không tồn tại!", ephemeral=True)
    if m.get("done"): return await interaction.followup.send("Sứ mệnh này đã hoàn thành!", ephemeral=True)


    total_time = m.get("time_required", 10)
    
    # Lưu trạng thái đang làm nhiệm vụ
    u["current_mission"] = {
        "id": m["id"],
        "title": m["title"],
        "time_required": total_time,
        "start_time": datetime.now(VN_TZ).timestamp()
    }
    save_db(db)
    
    rainbow_log(f"🎯 {u['name']} bắt đầu nhiệm vụ: {m['title']} (Tầng {u['layer']})", is_italic=True)
    
    for i in range(total_time + 1):
        percent = (i / total_time) * 100
        bar = get_progress_bar(percent)
        embed = txa_embed("⚔️ Đang Thực Hiện Sứ Mệnh", f"Đệ tử đang nỗ lực: **{m['title']}**\n\n{bar} **{int(percent)}%**\n⏳ Còn lại: `{total_time - i}s`", Color.orange())
        if i == 0:
            msg = await interaction.followup.send(embed=embed)
        else:
            await msg.edit(embed=embed)
        if i < total_time: await asyncio.sleep(1)

    # Tính tỷ lệ thành công dựa trên độ khó
    difficulty_rates = {"E": 95, "D": 85, "C": 75, "B": 65, "A": 50, "S": 35}
    success_rate = difficulty_rates.get(m.get("difficulty", "E"), 80)
    is_success = random.randint(1, 100) <= success_rate
    
    if is_success:
        # THÀNH CÔNG
        prompt = f"Đệ tử {u['name']} hoàn thành thành công '{m['title']}'. Viết 1 câu phán bảo thâm sâu về thành công này. JSON: {{\"story\": \"str\"}}"
        res_raw = await ask_ancestor("Phán quyết sứ mệnh thành công.", prompt, json_mode=True)
        try: res = json.loads(res_raw)
        except: res = {"story": "Ngươi đã hoàn thành sứ mệnh một cách xuất sắc."}

        m["done"] = True
        u["exp"] += m["exp_reward"]
        u["missions_completed"] = u.get("missions_completed", 0) + 1
        
        leveled_up = False
        while u["exp"] >= u.get("goal", 100):
            u["exp"] -= u.get("goal", 100)
            u["layer"] += 1
            u["goal"] = await calculate_divine_limit(u)
            leveled_up = True
        
        # Clear current_mission
        u["current_mission"] = None
        save_db(db)
        
        rainbow_log(f"✅ {u['name']} hoàn thành nhiệm vụ: {m['title']} (+{m['exp_reward']} EXP)", is_italic=True)
        
        final_embed = txa_embed("✅ Sứ Mệnh Hoàn Tất", f"\"{res['story']}\"\n\n📈 Nhận: **{m['exp_reward']} Linh lực**.", Color.green())
        if leveled_up:
            final_embed.add_field(name="🔥 ĐỘT PHÁ!", value=f"Đạt tới **Tầng {u['layer']}**!", inline=False)
            final_embed.color = Color.gold()
            await update_member_rank(interaction.user, u['layer'])
            rainbow_log(f"🔥 {u['name']} ĐỘT PHÁ lên Tầng {u['layer']}!", is_italic=True)
    else:
        # THẤT BẠI
        prompt = f"Đệ tử {u['name']} thất bại trong '{m['title']}'. Viết 1 câu phán bảo về thất bại này (không quá nghiêm khắc). JSON: {{\"story\": \"str\"}}"
        res_raw = await ask_ancestor("Phán quyết sứ mệnh thất bại.", prompt, json_mode=True)
        try: res = json.loads(res_raw)
        except: res = {"story": "Ngươi chưa đủ tu vi để hoàn thành sứ mệnh này."}
        
        # Không đánh dấu done, user có thể thử lại
        # Clear current_mission
        u["current_mission"] = None
        save_db(db)
        
        rainbow_log(f"❌ {u['name']} thất bại nhiệm vụ: {m['title']}", is_italic=True)
        
        final_embed = txa_embed("❌ Sứ Mệnh Thất Bại", f"\"{res['story']}\"\n\n💔 Không nhận được phần thưởng. Hãy thử lại sau!", Color.red())
        final_embed.add_field(name="🔄 Thử Lại", value="Ngươi có thể thử lại nhiệm vụ này!", inline=False)
        
        # Gửi message mới thay vì edit
        await interaction.followup.send(embed=final_embed)
        return
    
    # Chỉ edit khi thành công
    await msg.edit(embed=final_embed)

@bot.tree.command(name="tu_luyen", description="Tọa thiền với thanh tiến độ thời gian thực")
async def tu_luyen(interaction: discord.Interaction):
    # Gọi defer ngay lập tức
    await interaction.response.defer()
    
    db = load_db(); uid = str(interaction.user.id); u = db.get(uid)
    if not u: return await interaction.followup.send("Hãy `/start` trước!", ephemeral=True)

    duration = random.randint(4, 15)  # Random 4-15 giây
    rainbow_log(f"🧘 {u['name']} bắt đầu tu luyện ({duration}s)", is_italic=True)
    for i in range(duration + 1):
        percent = (i / duration) * 100
        bar = get_progress_bar(percent)
        embed = txa_embed("🧘 Đang Nhập Định", f"Linh khí hội tụ...\n{bar} **{int(percent)}%**", Color.blue())
        if i == 0: msg = await interaction.followup.send(embed=embed)
        else: await msg.edit(embed=embed)
        if i < duration: await asyncio.sleep(1)

    prompt = f"Đệ tử {u['name']} tầng {u['layer']} tu luyện. Cho EXP 20-80. JSON: {{\"exp\": int, \"story\": \"string\"}}"
    res_raw = await ask_ancestor("Phán bảo tu luyện. JSON.", prompt, json_mode=True)
    try: 
        res = json.loads(res_raw)
    except: 
        # Fallback với random reward
        exp_gain = random.randint(30, 100)
        stories = [
            "Linh khí hội tụ, kinh mạch thông suốt.",
            "Ngươi lĩnh ngộ được chút đạo lý tu tiên.",
            "Tu vi tăng tiến, tâm cảnh minh tĩnh.",
            "Thiên địa linh khí thấm nhuần đan điền."
        ]
        res = {"exp": exp_gain, "story": random.choice(stories)}

    u["exp"] += res['exp']
    leveled_up = False
    while u["exp"] >= u.get("goal", 100):
        u["exp"] -= u.get("goal", 100)
        u["layer"] += 1
        u["goal"] = await calculate_divine_limit(u)
        leveled_up = True
    
    save_db(db)
    rainbow_log(f"✅ {u['name']} tu luyện xong (+{res['exp']} EXP)", is_italic=True)
    
    embed_res = txa_embed("🧘 Kết Quả Tu Hành", f"**Tổ sư phán:** \"{res['story']}\"\n📈 Nhận: **{res['exp']} Linh lực**.", Color.gold() if leveled_up else Color.green())
    if leveled_up: 
        embed_res.add_field(name="🔥 ĐỘT PHÁ!", value=f"Tầng {u['layer']}!")
        await update_member_rank(interaction.user, u['layer'])
        rainbow_log(f"🔥 {u['name']} ĐỘT PHÁ lên Tầng {u['layer']}!", is_italic=True)
    await msg.edit(embed=embed_res)

@bot.command(name="sync", description="Đồng bộ lệnh ngay lập tức (Admin only)")
async def sync(ctx):
    if ctx.author.id not in ADMIN_IDS: return
    msg = await ctx.send("⏳ Đang điều chỉnh quy tắc Thiên Đạo...")
    
    if ctx.guild:
        bot.tree.copy_global_to(guild=ctx.guild)
        await bot.tree.sync(guild=ctx.guild)
        await msg.edit(content="✅ Đã đồng bộ pháp thuật cho giới diện này (Server-only)!")
    else:
        await bot.tree.sync()
        await msg.edit(content="✅ Đã đồng bộ pháp thuật toàn cõi (Global)!")

if __name__ == "__main__":
    try:
        rainbow_log(f"⚔️ Đang khởi động pháp trận {BOT_NAME}...")
        bot.run(os.getenv("DISCORD_TOKEN"))
    except Exception as e:
        rainbow_log(f"❌ PHÁP TRẬN SỤP ĐỔ: {e}")