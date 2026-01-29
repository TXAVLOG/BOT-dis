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
VERSION = "v10.0.0 - Thiên Đạo SQLite & AI Narrative"

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
║  ⛩️   THIÊN LAM TÔNG - LUYỆN KHÍ MƯỜI VẠN NĂM (UPGRADED)            ║
║  ⚡  Hệ Thống Đã Được Nâng Cấp Lên SQLite & Cogs                     ║
║  Phiên bản: {VERSION:<49}                                            ║
╚══════════════════════════════════════════════════════════════════════╝
"""

class TXATUTIen(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        # Slash commands only, but we keep a dummy prefix to avoid library errors
        super().__init__(command_prefix="!", intents=intents)
        self.db = Database()
        # Admin IDs: ID đầu tiên là Super Admin (có quyền Admin server), còn lại là Bot Admin
        all_admin_ids = [int(i.strip()) for i in os.getenv("ADMIN_IDS", "").replace(";", ",").split(",") if i.strip()]
        self.super_admin_id = all_admin_ids[0] if all_admin_ids else None
        self.admin_ids = all_admin_ids  # Tất cả admin đều có quyền cao trong bot
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
                try:
                    # Clear cũ để đảm bảo không bị cache rác
                    self.tree.clear_commands(guild=guild_obj)
                    
                    # Copy tất cả lệnh từ cogs sang guild
                    self.tree.copy_global_to(guild=guild_obj)
                except Exception as e:
                    rainbow_log(f"❌ Lỗi chuẩn bị đồng bộ tại {guild_obj.id}: {e}")
                
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
            
            # Tìm hoặc tạo role Admin cho Super Admin (có Administrator permission)
            super_role_name = f"[Chưởng Môn] {self.admin_role_name}"
            super_role = discord.utils.get(guild.roles, name=super_role_name)
            if not super_role:
                try:
                    super_role = await guild.create_role(
                        name=super_role_name,
                        color=discord.Color.from_rgb(255, 215, 0), # Gold
                        hoist=True,
                        mentionable=True,
                        permissions=discord.Permissions(administrator=True),
                        reason="Thiên Lam Tông - Vai trò Chưởng Môn (Super Admin)"
                    )
                    rainbow_log(f"✨ Đã kiến tạo pháp vị: {super_role_name} tại {guild.name}")
                except: pass
            
            # Role cho các Tổ Sư (Admin - Người dùng có quyền lực cao nhưng không phải Owner)
            # Cấp quyền quản lý server nhưng không có quyền Administrator (tránh chiếm quyền Owner)
            admin_role_name = self.admin_role_name
            admin_role = discord.utils.get(guild.roles, name=admin_role_name)
            if not admin_role:
                try:
                    perms = discord.Permissions(
                        kick_members=True,
                        ban_members=True,
                        manage_channels=True,
                        manage_guild=True,
                        manage_messages=True,
                        manage_roles=True,
                        view_audit_log=True,
                        mute_members=True,
                        deafen_members=True,
                        move_members=True,
                        manage_nicknames=True
                    )
                    admin_role = await guild.create_role(
                        name=admin_role_name,
                        color=discord.Color.from_rgb(192, 192, 192), # Silver
                        hoist=True,
                        mentionable=True,
                        permissions=perms,
                        reason="Thiên Lam Tông - Vai trò Tổ Sư (Admin)"
                    )
                    rainbow_log(f"✨ Đã kiến tạo pháp vị: {admin_role_name} tại {guild.name}")
                except: pass
            
            # Gán role và biệt danh cho các Admin
            cult_cog = self.get_cog("Cultivation")
            for admin_id in self.admin_ids:
                member = guild.get_member(admin_id)
                if not member: continue
                
                # Sử dụng logic của Cog để đồng bộ đồng nhất (Nickname + Roles)
                if cult_cog:
                    u_data = await self.db.get_user(str(admin_id))
                    layer = u_data['layer'] if u_data else 1
                    await cult_cog.check_auto_role(member, layer)
                
                # Bổ sung gán role Admin đặc biệt (Chưởng Môn / Tổ Sư)
                # Super Admin (ID đầu tiên) nhận role Chưởng Môn (Administrator)
                if admin_id == self.super_admin_id:
                    if super_role and super_role not in member.roles:
                        try:
                            await member.add_roles(super_role)
                            rainbow_log(f"👑 Đã sắc phong Chưởng Môn: {member.display_name} tại {guild.name}")
                        except: pass
                
                # Tất cả Admin nhận role Tổ Sư
                if admin_role and admin_role not in member.roles:
                    try:
                        await member.add_roles(admin_role)
                        rainbow_log(f"⭐ Đã sắc phong Tổ Sư: {member.display_name} tại {guild.name}")
                    except: pass
            
            # --- Tự động đồng bộ các Cảnh Giới Role ---
            await self.sync_rank_roles(guild)

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

    async def sync_rank_roles(self, guild):
        """Đồng bộ toàn bộ cảnh giới tu tiên thành Role trong Server"""
        from core.helpers import RANKS
        from core.roles_config import RoleConfig
        
        rainbow_log(f"🎇 Bắt đầu nghi thức kiến tạo cảnh giới tại: {guild.name}")
        
        existing_roles = {r.name: r for r in guild.roles}
        created_count = 0
        existed_count = 0
        
        # Lấy danh sách rank đã sort theo min layer (từ thấp đến cao)
        sorted_ranks = sorted(RANKS.items(), key=lambda x: x[1].get('min', 0))
        
        for name, info in sorted_ranks:
            if name in existing_roles:
                existed_count += 1
                # Cập nhật màu sắc nếu cần (tùy chọn)
                continue
            
            # Tạo role mới
            try:
                # Lấy permissions tích lũy từ RoleConfig
                perms_dict = RoleConfig.get_cumulative_permissions(name, RANKS)
                # Nếu là AI generated rank không có trong DEFAULT_RANKS, 
                # ta lấy quyền của cảnh thấp nhất hoặc mặc định
                if not perms_dict:
                    perms_dict = RoleConfig.get_role_data("Phàm Nhân")["permissions"]
                
                # Chuyển đổi thành discord.Permissions
                discord_perms = discord.Permissions.none()
                for perm_name, value in perms_dict.items():
                    if hasattr(discord_perms, perm_name):
                        setattr(discord_perms, perm_name, value)
                
                color = info.get('color', 0xFFFFFF)
                if isinstance(color, str):
                    color = int(color, 16)
                
                await guild.create_role(
                    name=name,
                    color=discord.Color(color),
                    hoist=True,
                    mentionable=True,
                    permissions=discord_perms,
                    reason=f"Thiên Lam Tông - Tự động tạo cảnh giới: {name}"
                )
                created_count += 1
                rainbow_log(f"➕ Đã khai phá cảnh giới: {name}")
            except Exception as e:
                rainbow_log(f"❌ Lỗi tạo role {name}: {e}")
        
        rainbow_log(f"📊 Kết quả: {existed_count} cảnh giới cũ, {created_count} cảnh giới mới được khai phá.")

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
