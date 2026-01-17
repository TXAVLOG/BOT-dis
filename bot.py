import discord
import os
import aiosqlite
from dotenv import load_dotenv

# Load ENV before other imports
load_dotenv()

from discord import app_commands
from discord.ext import commands
from core.database import Database
from core.helpers import rainbow_log, generate_ranks_from_ai, txa_embed
from core.migrate import migrate_data
import random

# --- PHIÊN BẢN MỚI ---
VERSION = "v9.0.0 - Thiên Đạo SQLite"

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
║  ⛩️   THIÊN LAM TÔNG - LUYỆN KHÍ MƯỜI VẠN NĂM (UPGRADED)             ║
║  ⚡  Hệ Thống Đã Được Nâng Cấp Lên SQLite & Cogs                    ║
║  Phiên bản: {VERSION:<49}                                            ║
╚══════════════════════════════════════════════════════════════════════╝
"""

class TXATUTIen(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        # Slash commands only, but we keep a dummy prefix to avoid library errors
        super().__init__(command_prefix="!", intents=intents)
        self.db = Database()
        self.admin_ids = [int(i.strip()) for i in os.getenv("ADMIN_IDS", "").replace(";", ",").split(",") if i.strip()]
        self.admin_role_name = os.getenv("ADMIN_ROLE_NAME", "Tổ Sư Thiên Lam Tông")
        self.allowed_guilds = [discord.Object(id=int(i.strip())) for i in os.getenv("ALLOWED_GUILD_IDS", "").replace(";", ",").split(",") if i.strip()]
        self.allowed_channel_ids = [int(i.strip()) for i in os.getenv("ALLOWED_CHANNEL_IDS", "").replace(";", ",").split(",") if i.strip()]
        self.music_channel_id = self.allowed_channel_ids[0] if self.allowed_channel_ids else None
        self.report_channel_id = 1384167805254897731 # Kênh báo cáo cần tránh

    async def setup_hook(self):
        rainbow_log(ASCII_TXA, is_ascii=True)
        
        # Init DB
        await self.db.initialize()
        # Add aiosqlite reference for cogs
        self.db.aiosqlite = aiosqlite
        
        # Migrate
        await migrate_data(self.db)
        
        # Generate RANKS từ AI (hoặc fallback)
        await generate_ranks_from_ai()
        
        # Load Cogs
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py'):
                try:
                    await self.load_extension(f'cogs.{filename[:-3]}')
                    rainbow_log(f"📦 Đã nạp pháp bảo: {filename}")
                except Exception as e:
                    rainbow_log(f"❌ Lỗi nạp {filename}: {e}")

        # Sync commands - Sync trực tiếp vào Guild để xuất hiện tức thì
        try:
            for guild_obj in self.allowed_guilds:
                # Copy tất cả lệnh từ cogs sang guild
                self.tree.copy_global_to(guild=guild_obj)
                # Sync
                synced = await self.tree.sync(guild=guild_obj)
                
                # Lấy tên Guild để log (Fetch nếu chưa có trong cache)
                try:
                    guild = self.get_guild(guild_obj.id) or await self.fetch_guild(guild_obj.id)
                    guild_name = guild.name
                except:
                    guild_name = "Unknown Guild"
                
                rainbow_log(f"⚡ Đã đồng bộ {len(synced)} pháp lệnh tại: {guild_name} ({guild_obj.id})")
        except Exception as e:
            rainbow_log(f"❌ Sync thất bại: {e}")
            
        # Emoji cache info (Báo cáo cho đạo hữu: File này hiện chưa được sử dụng trong các tính năng hiện tại)
        if os.path.exists("cache/emoji_cache.json"):
             rainbow_log("📜 Phát hiện tàn tích emoji_cache.json (Hiện đang bị phong ấn - không sử dụng)", is_italic=True)

    async def on_ready(self):
        rainbow_log(f"✅ Hộ Pháp {self.user.name} đã sẵn sàng bảo vệ Thiên Lam Tông!")
        
        # --- Tự động gán role Admin (Tổ Sư) ---
        for guild_obj in self.allowed_guilds:
            guild = self.get_guild(guild_obj.id)
            if not guild: continue
            
            # Tìm hoặc tạo role Admin
            role = discord.utils.get(guild.roles, name=self.admin_role_name)
            if not role:
                try:
                    role = await guild.create_role(
                        name=self.admin_role_name,
                        color=discord.Color.from_rgb(255, 215, 0), # Gold
                        hoist=True,
                        mentionable=True,
                        reason="Thiên Lam Tông - Tự động tạo vai trò Tổ Sư tối cao"
                    )
                    rainbow_log(f"✨ Đã kiến tạo pháp vị: {self.admin_role_name} tại {guild.name}")
                except: continue
            
            for admin_id in self.admin_ids:
                member = guild.get_member(admin_id)
                if member and role not in member.roles:
                    try:
                        await member.add_roles(role)
                        rainbow_log(f"👑 Đã sắc phong Tổ Sư: {member.display_name} tại {guild.name}")
                    except: pass

        # Log thông tin kênh được phép
        if self.allowed_channel_ids:
            channels_info = []
            for cid in self.allowed_channel_ids:
                ch = self.get_channel(cid)
                ch_name = ch.name if ch else "Không xác định"
                channels_info.append(f"{ch_name} ({cid})")
            rainbow_log(f"📍 Khu vực hoạt động: {', '.join(channels_info)}")
        else:
            rainbow_log("🌍 Khu vực hoạt động: Toàn vũ trụ (Tất cả các kênh)")

    async def on_message(self, message):
        # Chặn toàn bộ lệnh bắt đầu bằng !
        if message.content.startswith(self.command_prefix) and not message.author.bot:
            try:
                if message.guild and message.channel.permissions_for(message.guild.me).manage_messages:
                    await message.delete()
                
                # Cảnh báo nhẹ nhàng rằng hãy dùng /
                await message.channel.send(f"⛩️ {message.author.mention} **Đạo hữu hãy dùng Slash Commands (gõ /)**. Thiên Lam Tông đã phong ấn các cổ lệnh (`{self.command_prefix}`). Hãy tuân theo Thiên Đạo mới!", delete_after=10)
            except: pass
            return

        # Chỉ xử lý tin nhắn bình thường hoặc DM Rejection
        if message.guild is None and not message.author.bot:
            
            portal_url = "https://discord.com"
            if self.allowed_guilds:
                guild = self.get_guild(self.allowed_guilds[0].id)
                if guild:
                    if self.allowed_channel_ids:
                        portal_url = f"https://discord.com/channels/{guild.id}/{self.allowed_channel_ids[0]}"
                    else:
                        # Tránh kênh report
                        channels = [c for c in guild.text_channels if c.id != self.report_channel_id and c.permissions_for(guild.me).send_messages]
                        if channels:
                            target = random.choice(channels)
                            portal_url = f"https://discord.com/channels/{guild.id}/{target.id}"

            embed = txa_embed(
                "⛩️ Thiên Lam Cấm Chế: Vạn Trượng Kết Giới!", 
                "*Hậu bối to gan! Ngươi dám dùng truyền âm mật pháp để làm phiền quá trình bế quan của Tổ Sư?*\n\n"
                "**Thiên Lam Tông** cấm chế nghiêm ngặt, không tiếp nhận pháp lệnh qua thư riêng (DM).\n\n"
                "> *“Ta chỉ là kẻ tu luyện Luyện Khí kỳ, nhưng quy tắc của Tông môn, không ai được phép phá lệ!”*\n\n"
                "Hãy quay về linh địa chính thức để tiếp tục con đường tu tiên!",
                discord.Color.red()
            )
            embed.set_image(url="https://hoathinh3d.moi/wp-content/uploads/2023/02/luyen-khi-10-van-nam-300x450.jpg")
            embed.set_footer(text="THIÊN LAM TÔNG - MỘT QUYỀN TRẤN ÁP CHƯ THIÊN")
            
            view = discord.ui.View()
            view.add_item(discord.ui.Button(label="Trở về Tông Môn", url=portal_url, emoji="⛩️"))
            try:
                await message.author.send(embed=embed, view=view)
            except: pass

        # Chặn lệnh ở kênh không được phép (nếu có config)
        if self.allowed_channel_ids and message.channel.id not in self.allowed_channel_ids and not message.author.bot:
            if message.content.startswith(self.command_prefix):
                # Check if it's an admin command
                if message.author.id not in self.admin_ids:
                    try:
                        await message.channel.send(f"⚠️ {message.author.mention} Pháp lệnh này không được thi triển tại đây!", delete_after=8)
                    except: pass
                    return
        
        await self.process_commands(message)

    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandNotFound):
            return # Im lặng khi không thấy lệnh
        rainbow_log(f"⚠️ Lỗi pháp thuật: {error}")

    async def on_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CommandSignatureMismatch):
            await interaction.response.send_message("⚠️ Lệnh đã được cập nhật. Vui lòng thử lại sau vài giây hoặc khởi động lại Discord.", ephemeral=True)
            # Thử sync lại guild này
            try:
                await self.tree.sync(guild=interaction.guild)
            except: pass
        else:
            rainbow_log(f"⚠️ Lỗi Slash Command: {error}")

if __name__ == "__main__":
    load_dotenv()
    bot = TXATUTIen()
    bot.run(os.getenv("DISCORD_TOKEN"))
