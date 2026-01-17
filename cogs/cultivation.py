import discord
import random
import asyncio
import json
import time
from datetime import datetime, timedelta
from discord import app_commands, Color
from discord.ext import commands, tasks
from core.helpers import VN_TZ, ask_ancestor, get_rank_info, txa_embed, number_to_emoji, get_all_rank_names
from core.format import TXAFormat
from core.database import Database

class Cultivation(commands.Cog):
    NARRATIVE_STAGES = [
        (0, "🌀 Bắt đầu vận chuyển linh khí, tâm thần dần nhập định..."),
        (20, "⚡ Linh lực cuộn trào trong kinh mạch, mồ hôi bắt đầu thấm đẫm..."),
        (40, "🔥 Đạo lực bùng phát mãnh liệt, đang cố gắng chế ngự kình lực..."),
        (60, "🌊 Khí hải dâng trào, thiên địa linh khí đang hội tụ về cơ thể..."),
        (80, "💎 Gần như chạm tới ngưỡng cửa viên mãn, đạo tâm kiên định tuyệt đối!"),
        (95, "✨ Linh quang lóe sáng! Bí pháp đã hoàn thành 9 phần, chỉ còn chút hơi sức cuối..."),
    ]

    def __init__(self, bot):
        self.bot = bot
        self.db: Database = bot.db

    async def update_member_visuals(self, member: discord.Member, layer: int):
        """Update nickname and role based on layer - Tận dụng role cũ nếu có"""
        rank_name, rank_info = get_rank_info(layer)
        guild = member.guild
        
        # 1. Tìm hoặc tạo role cho cảnh giới hiện tại
        role = discord.utils.get(guild.roles, name=rank_name)
        if not role:
            try:
                # Tạo role mới nếu chưa tồn tại trong Guild
                role = await guild.create_role(
                    name=rank_name,
                    color=discord.Color(rank_info['color']),
                    reason=f"Thiên Lam Tông - Khai mở cảnh giới {rank_name}"
                )
            except: pass
        
        # 2. Dọn dẹp TẤT CẢ các role cảnh giới cũ (bao gồm cả Default và AI)
        all_ranks = get_all_rank_names()
        roles_to_remove = [r for r in member.roles if r.name in all_ranks and r.id != (role.id if role else 0)]
        
        # 3. Cập nhật role
        if role and role not in member.roles:
            try:
                if roles_to_remove:
                    await member.remove_roles(*roles_to_remove)
                await member.add_roles(role)
            except: pass
        elif not role and roles_to_remove:
            try: await member.remove_roles(*roles_to_remove)
            except: pass
        
        # Nickname
        try:
            new_nick = f"[{rank_name}] {member.name}"[:32]
            if member.nick != new_nick:
                await member.edit(nick=new_nick)
        except: pass

        # --- Gửi DM chúc mừng (Tránh gửi lặp nếu layer mới cập nhật liên tục) ---
        if layer > 1:
            try:
                embed = txa_embed(
                    "🔥 Đột Phá Cảnh Giới!",
                    f"Chúc mừng đạo hữu **{member.display_name}**!\n"
                    f"Ngươi đã thành công đột phá linh mạch, đạt tới: **{rank_name} (Tầng {layer})**.\n\n"
                    f"Pháp vị của ngươi tại Thiên Lam Tông đã được sắc phong: `{rank_name}`.",
                    rank_info['color']
                )
                embed.set_footer(text="Thiên Đạo ghi danh - Tương lai rộng mở!")
                await member.send(embed=embed)
            except: pass

    @tasks.loop(hours=1)
    async def daily_reminder_task(self):
        """Gửi nhắc nhở điểm danh vào 6h sáng (trước reset 1h)"""
        now = datetime.now(VN_TZ)
        if now.hour != 6: return
        
        users = await self.db.get_all_users()
        today_reset = now.replace(hour=7, minute=0, second=0, microsecond=0)
        today_date = (now - timedelta(hours=7)).strftime("%Y-%m-%d")
        
        # Lấy portal link
        portal_url = None
        target_guild = None
        if self.bot.allowed_guilds:
            target_guild = self.bot.get_guild(self.bot.allowed_guilds[0].id)

        if target_guild:
            if self.bot.allowed_channel_ids:
                # Nếu đã set channel thì về đúng kênh đầu tiên (về đúng)
                portal_url = f"https://discord.com/channels/{target_guild.id}/{self.bot.allowed_channel_ids[0]}"
            else:
                # Nếu chưa set thì random kỳ duyên trong server
                # Tránh kênh report
                target_channels = [
                    c for c in target_guild.text_channels 
                    if c.id != self.bot.report_channel_id and c.permissions_for(target_guild.me).send_messages
                ]
                if target_channels:
                    random_channel = random.choice(target_channels)
                    portal_url = f"https://discord.com/channels/{target_guild.id}/{random_channel.id}"

        for u_data in users:
            if u_data['last_daily_date'] != today_date:
                user = self.bot.get_user(int(u_data['user_id']))
                if not user: continue
                
                streak_emoji = number_to_emoji(u_data['daily_streak'])
                timestamp = int(today_reset.timestamp())
                
                embed = txa_embed("⏰ Nhắc Nhở Điểm Danh", "", Color.orange())
                embed.description = (
                    f"🔥 **Chuỗi điểm danh hiện tại:** {streak_emoji} ngày\n"
                    f"⚠️ **Còn 1 giờ nữa là reset!** (<t:{timestamp}:t>)\n\n"
                    f"💡 Hãy dùng `/daily` ngay để giữ chuỗi streak!\n"
                    f"📈 Streak càng cao, phần thưởng càng lớn!"
                )
                embed.add_field(name="🌀 Cổng Dịch Chuyển", value="Nhấn nút bên dưới để trở về Thiên Lam Tông", inline=False)
                # Dùng TXAFormat để chuẩn hóa thời gian
                time_now = TXAFormat.time(now.hour * 3600 + now.minute * 60 + now.second)
                embed.set_footer(text=f"Pháp thời: {time_now} - THIEN-LAM-LIVE-AI BY TXA!")
                
                view = discord.ui.View()
                if portal_url:
                    view.add_item(discord.ui.Button(label="Trở về Tông Môn", url=portal_url, emoji="⛩️"))
                
                try:
                    await user.send(embed=embed, view=view)
                except: pass

    @daily_reminder_task.before_loop
    async def before_daily_reminder(self):
        await self.bot.wait_until_ready()

    async def cog_load(self):
        self.daily_reminder_task.start()

    async def cog_unload(self):
        self.daily_reminder_task.cancel()

    async def cog_check(self, ctx):
        """Prefix commands are disabled, but keeping for safety"""
        return False

    def interaction_check(self, interaction: discord.Interaction):
        """Kiểm tra kênh và chặn DM cho Slash Commands"""
        if interaction.guild is None:
            return False

        # Nếu không giới hạn kênh thì cho qua hết
        if not self.bot.allowed_channel_ids:
            return True

        if interaction.channel_id not in self.bot.allowed_channel_ids:
            # Gửi tin nhắn ẩn (ephemeral) cho người gõ sai kênh
            asyncio.create_task(interaction.response.send_message(
                "⛩️ **Cấm Chế:** Pháp lệnh này chỉ có thể thi triển tại các kênh chuyên biệt của Thiên Lam Tông!", 
                ephemeral=True
            ))
            return False
        return True

    @app_commands.command(name="start", description="Ghi danh vào Thiên Lam Tông")
    async def start(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        uid = str(interaction.user.id)
        user = await self.db.get_user(uid)
        if user:
            return await interaction.followup.send("⛩️ Ngươi đã ghi danh rồi, hãy tập trung tu luyện!", ephemeral=True)
        
        msg = await ask_ancestor(
            "Chào đón đệ tử mới.", 
            f"Đệ tử {interaction.user.display_name} nhập môn. Hãy viết 2 câu chào đón trang trọng, thâm sâu."
        )
        
        await self.db.create_user(uid, interaction.user.display_name)
        await self.update_member_visuals(interaction.user, 1)
        
        embed = txa_embed("⛩️ Thiên Lam Tông - Nhập Môn Ghi Danh", f"**Tổ Sư Từ Dương phán:**\n*\"{msg or 'Đường tu tiên gian nan, đệ tử hãy vững tâm!'}\"*", Color.gold())
        embed.add_field(name="📜 Pháp Lệnh Khai Mở", value="`/nhiem_vu` • `/daily` • `/tu_luyen` • `/info`", inline=False)
        embed.set_footer(text="Pháp môn bí truyền - Chỉ mình ngươi nhìn thấy.")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="info", description="Xem thông tin tu luyện")
    async def info(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        user = await self.db.get_user(str(interaction.user.id))
        if not user: return await interaction.followup.send("⛩️ Ngươi chưa ghi danh! Hãy dùng `/start`.", ephemeral=True)
        
        rank_name, rank_info = get_rank_info(user['layer'])
        progress = (user['exp'] / user['goal']) * 100
        bar = TXAFormat.progress_bar(progress, 15)
        
        embed = txa_embed(f"✨ {rank_name} - Tầng {user['layer']}", f"Thần thức quét qua tu vi của {interaction.user.mention}", rank_info['color'])
        embed.add_field(name="💠 Cảnh Giới", value=f"```ansi\n\u001b[1;36m{rank_name}\u001b[0m\n\u001b[1;34mTầng {user['layer']}\u001b[0m\n```", inline=True)
        embed.add_field(name="🔥 Đạo Tâm", value=f"```ansi\n\u001b[1;33m{user['daily_streak']} ngày\u001b[0m\n```", inline=True)
        embed.add_field(name="✨ Linh Lực Tiến Độ", value=f"{bar} ({TXAFormat.pad2(int(progress))}%)\n**{TXAFormat.number(user['exp'])} / {TXAFormat.number(user['goal'])} EXP**", inline=False)
        
        # Kiểm tra nhiệm vụ đang làm
        if user.get('current_mission'):
            curr = user['current_mission']
            remaining = int(curr['end_time'] - time.time())
            if remaining > 0:
                # Tìm nhiệm vụ tương ứng (ép kiểu ID để tránh lỗi so sánh)
                mission = next((m for m in user['missions'] if int(m['id']) == int(curr['id'])), None)
                mission_name = mission['title'] if mission else "Không rõ"
                
                rem_str = TXAFormat.remaining_detail(remaining)
                embed.add_field(
                    name="⚔️ Công Khóa Hiện Tại",
                    value=f"**{mission_name}**\n⏳ Hoàn thành: <t:{int(curr['end_time'])}:R>\n📊 Còn lại: **{rem_str}**",
                    inline=False
                )
                
                embed.set_thumbnail(url=interaction.user.display_avatar.url)
                embed.set_footer(text="Thần thức riêng tư - Thiên Lam Tông.")
                msg = await interaction.followup.send(embed=embed, ephemeral=True)
                
                # Loop cập nhật real-time (tối đa 5 phút tránh treo)
                loop_end = time.time() + 300
                field_idx = len(embed.fields) - 1
                
                while time.time() < loop_end:
                    now_t = time.time()
                    remaining = int(curr['end_time'] - now_t)
                    if remaining <= 0:
                        # Finalize ngầm và cập nhật UI lần cuối
                        asyncio.create_task(self.finalize_mission(interaction, str(interaction.user.id), user, int(curr['id']), silent=True))
                        embed.set_field_at(field_idx, name="⚔️ Công Khóa Hiện Tại", value="✅ **Đã hoàn tất!** Hãy kiểm tra lại linh trạng.", inline=False)
                        try: await msg.edit(embed=embed)
                        except: pass
                        break
                    
                    rem_str = TXAFormat.remaining_detail(remaining)
                    embed.set_field_at(field_idx, 
                        name="⚔️ Công Khóa Hiện Tại", 
                        value=f"**{mission_name}**\n⏳ Hoàn thành: <t:{int(curr['end_time'])}:R>\n📊 Còn lại: **{rem_str}**",
                        inline=False
                    )
                    
                    try: 
                        await msg.edit(embed=embed)
                    except: 
                        break # User closed ephemeral msg
                    await asyncio.sleep(1)
                return
            else:
                # Nếu đã hết thời gian, tự động finalize ngầm
                asyncio.create_task(self.finalize_mission(interaction, str(interaction.user.id), user, int(curr['id']), silent=True))
        
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.set_footer(text="Thần thức riêng tư - Thiên Lam Tông.")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="daily", description="Nhận quà hàng ngày")
    async def daily(self, interaction: discord.Interaction):
        uid = str(interaction.user.id)
        user = await self.db.get_user(uid)
        if not user:
            embed = txa_embed("⛩️ Thiên Lam Cấm Chế", "Ngươi chưa ghi danh! Hãy dùng `/start` để nhập môn.", discord.Color.red())
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        
        now = datetime.now(VN_TZ)
        reset_hour = 7
        today_reset = now.replace(hour=reset_hour, minute=0, second=0, microsecond=0)
        if now < today_reset: today_reset -= timedelta(days=1)
        
        if user['last_daily'] > today_reset.timestamp():
            await interaction.response.defer(ephemeral=True)
            next_reset = today_reset + timedelta(days=1)
            ts = int(next_reset.timestamp())
            
            # Vòng lặp cập nhật real-time 1s/lần
            # Giới hạn thời gian loop tránh treo tài nguyên (vd: 5 phút)
            loop_end = time.time() + 300 
            
            while time.time() < loop_end:
                now_loop = datetime.now(VN_TZ)
                diff = next_reset - now_loop
                total_seconds = int(diff.total_seconds())
                
                if total_seconds <= 0:
                    break
                
                time_str = TXAFormat.duration_detail(total_seconds)
                
                embed = txa_embed(
                    "⏳ Cấm Chế Thổ Nạp",
                    f"**Đạo hữu hãy tịnh tâm!**\nLinh khí trời đất hiện tại đang khô kiệt, cần thời gian để tái tạo hoàn nguyên.\n\n"
                    f"🌀 **Linh khí hội tụ lại sau:**\n`{time_str}`\n\n"
                    f"⏰ **Thiên thời reset:** <t:{ts}:F> (**<t:{ts}:R>**)",
                    discord.Color.orange()
                )
                embed.set_thumbnail(url="https://hoathinh3d.moi/wp-content/uploads/2023/02/luyen-khi-10-van-nam-300x450.jpg")
                embed.set_footer(text="Thiên Lam Tông - Vạn vật hữu hình, linh khí hữu hạn.")
                
                try:
                    await interaction.edit_original_response(embed=embed)
                except:
                    break # User có thể đã đóng ephemeral message hoặc interaction hết hạn
                
                await asyncio.sleep(1)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        logical_now = now - timedelta(hours=reset_hour)
        today_date = logical_now.strftime("%Y-%m-%d")
        yesterday_date = (logical_now - timedelta(days=1)).strftime("%Y-%m-%d")
        
        streak = user['daily_streak']
        if user['last_daily_date'] == yesterday_date:
            streak += 1
        elif user['last_daily_date'] != today_date:
            streak = 1
            
        reward = 1000 + (streak * 100)
        exp = user['exp'] + reward
        layer = user['layer']
        goal = user['goal']
        
        leveled_up = False
        while exp >= goal:
            exp -= goal
            layer += 1
            goal = layer * 1000
            leveled_up = True
            
        await self.db.update_user(uid, exp=exp, layer=layer, goal=goal, last_daily=now.timestamp(), last_daily_date=today_date, daily_streak=streak)
        if leveled_up: await self.update_member_visuals(interaction.user, layer)
        
        msg = await ask_ancestor("Ban thưởng điểm danh.", f"Đệ tử nhận {reward} EXP ngày {streak}. Viết 1 câu thâm sâu.")
        
        embed = txa_embed("🎁 Thiên Đạo Ban Phước", f"**Tổ Sư Từ Dương phán:**\n*\"{msg or 'Linh khí quán đỉnh, căn cốt tinh anh!'}\"*", Color.blue())
        embed.add_field(name="📈 Linh Lực Tăng Tiến", value=f"**+{reward} EXP**", inline=True)
        embed.add_field(name="🔥 Đạo Tâm Chuỗi", value=f"**{streak} ngày**", inline=True)
        if leveled_up: embed.add_field(name="🔥 ĐỘT PHÁ CẢNH GIỚI", value=f"Chúc mừng đệ tử đã đột phá đạt tới **Tầng {layer}**!", inline=False)
        
        embed.set_footer(text="Cơ duyên trời ban - Thiên Lam Tông.")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="tu_luyen", description="Tọa thiền luyện khí")
    async def tu_luyen(self, interaction: discord.Interaction):
        uid = str(interaction.user.id)
        user = await self.db.get_user(uid)
        if not user:
            embed = txa_embed("⛩️ Thiên Lam Cấm Chế", "Ngươi chưa ghi danh! Hãy dùng `/start` để nhập môn.", discord.Color.red())
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        
        await interaction.response.defer(ephemeral=True)
        
        duration = random.randint(15, 30)
        start_time = time.time()
        end_time = int(start_time + duration)
        
        embed = txa_embed("🧘 Đang Nhập Định Tu Luyện", f"Thanh tẩy thân thể, hội tụ linh khí trời đất mười vạn năm...\n⏳ Ước tính hoàn tất: <t:{end_time}:t> (<t:{end_time}:R>)", Color.blue())
        bar = TXAFormat.progress_bar(0, 15)
        rem_str = TXAFormat.remaining_detail(duration)
        embed.add_field(name="✨ Tiến Độ", value=f"`{bar}` ({TXAFormat.pad2(0)}%) - {rem_str}")
        msg = await interaction.followup.send(embed=embed, ephemeral=True)
        
        # Cập nhật thanh tiến trình mỗi 1 giây (real-time)
        while True:
            now_t = time.time()
            elapsed = now_t - start_time
            remaining = max(0, int(end_time - now_t))
            percent = min(100, int((elapsed / duration) * 100))
            
            if percent >= 100: break
            
            # Chọn narrative text theo %
            stage_msg = self.NARRATIVE_STAGES[0][1]
            for threshold, text in self.NARRATIVE_STAGES:
                if percent >= threshold:
                    stage_msg = text
            
            # Cập nhật mỗi 1 giây
            bar = TXAFormat.progress_bar(percent, 15)
            rem_str = TXAFormat.remaining_detail(remaining)
            
            embed.description = f"{stage_msg}\n⏳ Ước tính hoàn tất: <t:{end_time}:t> (<t:{end_time}:R>)"
            embed.set_field_at(0, name="✨ Tiến Độ", value=f"`{bar}` ({TXAFormat.pad2(percent)}%) - {rem_str}")
            
            try: await msg.edit(embed=embed)
            except: pass
            
            if percent >= 100: break
            await asyncio.sleep(1)
        
        # Re-fetch user to get latest state
        user = await self.db.get_user(uid)
        gain = random.randint(50, 150) + (user['layer'] * 5)
        
        # Bonus Streak (>= 3 ngày)
        bonus_msg = ""
        if user['daily_streak'] >= 3:
            bonus_pct = min(0.5, (user['daily_streak'] // 3) * 0.05)
            bonus_xp = int(gain * bonus_pct)
            gain += bonus_xp
            bonus_msg = f"\n🔥 **Kỳ Duyên Phụ Trợ:** +{bonus_xp} EXP (Streak x{user['daily_streak']})"

        exp = user['exp'] + gain
        layer = user['layer']
        goal = user['goal']
        
        leveled_up = False
        while exp >= goal:
            exp -= goal
            layer += 1
            goal = layer * 1000
            leveled_up = True
            
        await self.db.update_user(uid, exp=exp, layer=layer, goal=goal)
        if leveled_up: await self.update_member_visuals(interaction.user, layer)
        
        res_text = f"Chu thiên tuần hoàn kết thúc, linh khí đã được luyện hóa.\n📈 Nhận được: **{gain} EXP** linh lực.{bonus_msg}"
        res_embed = txa_embed("🧘 Tu Luyện Hoàn Tất", res_text, Color.green())
        if leveled_up: res_embed.add_field(name="🔥 ĐỘT PHÁ CẢNH GIỚI", value=f"Chúc mừng đệ tử đột phá lên **Tầng {layer}**!")
        
        res_embed.set_footer(text="Công khóa hoàn tất. (Nhấn để đóng)")
        try:
            await msg.edit(embed=res_embed)
        except: pass

    async def generate_missions(self, user):
        """Tạo danh sách nhiệm vụ mới via AI hoặc Fallback"""
        uid = str(user['user_id'])
        prompt = (
            "Tạo 5 nhiệm vụ tu tiên ngắn gọn, thâm sâu. "
            "Phân cấp độ khó từ 1 (Dễ nhất) đến 5 (Khó nhất). "
            "Format JSON: [{'id': 1, 'title': '...', 'desc': '...', 'diff': 1-5}]"
        )
        
        rainbow_log(f"🔮 Đang thỉnh thị Tổ Sư Từ Dương tạo công khóa cho {user['name']}...")
        ai_res = await ask_ancestor("Người tạo nhiệm vụ tu tiên.", prompt, json_mode=True)
        
        missions = []
        try:
            raw_missions = json.loads(ai_res)
            if isinstance(raw_missions, dict): 
                raw_missions = raw_missions.get('missions', [])
                
            for i, m in enumerate(raw_missions[:5]):
                diff = m.get('diff', random.randint(1, 5))
                missions.append({
                    "id": i + 1,
                    "title": m.get('title', "Nhiệm vụ vô danh"),
                    "desc": m.get('desc', "Đi tìm cơ duyên..."),
                    "difficulty": diff,
                    "time": diff * random.randint(30, 45), # Giảm thời gian chút cho trải nghiệm tốt
                    "reward": diff * 400 + random.randint(100, 300),
                    "success_rate": 100 - (diff * 12),
                    "done": False
                })
            rainbow_log(f"✅ AI đã ban xuống 5 công khóa mới cho {user['name']}.")
        except Exception as e:
            rainbow_log(f"⚠️ Thỉnh thị AI thất bại: {e}. Sử dụng bí tịch Fallback.")
            # Fallback
            titles = ["Hái linh thảo", "Luyện đan sơ cấp", "Săn thú rừng", "Tẩy tủy kinh nạch", "Trùng kích bình phong"]
            for i, t in enumerate(titles):
                diff = i + 1
                missions.append({
                    "id": i + 1,
                    "title": t,
                    "desc": f"Thực hiện {t} để tích lũy kinh nghiệm.",
                    "difficulty": diff,
                    "time": diff * 40,
                    "reward": diff * 350,
                    "success_rate": 100 - (diff * 12),
                    "done": False
                })
        
        return missions

    async def finalize_mission(self, interaction: discord.Interaction, uid: str, user: dict, mission_id: int, silent: bool = False):
        """Xử lý kết quả nhiệm vụ bị gián đoạn (silent: chỉ cộng điểm không gửi tin nhắn khôi phục)"""
        if not silent:
            await interaction.response.defer(ephemeral=True)
        
        mission = next((m for m in user['missions'] if m['id'] == mission_id), None)
        if not mission:
            await self.db.update_user(uid, current_mission=None)
            return
        
        # Re-fetch user để đảm bảo data mới nhất
        user = await self.db.get_user(uid)
        if not user or not user.get('current_mission'): return

        success = random.randint(1, 100) <= mission['success_rate']
        
        # Xóa current_mission TRƯỚC khi update các cái khác
        await self.db.update_user(uid, current_mission=None)
        
        if success:
            new_missions = user['missions']
            for m in new_missions:
                if m['id'] == mission['id']: m['done'] = True
            
            reward = mission['reward']
            bonus_msg = ""
            if user['daily_streak'] >= 3:
                bonus_pct = min(0.5, (user['daily_streak'] // 3) * 0.05)
                bonus_xp = int(reward * bonus_pct)
                reward += bonus_xp
                bonus_msg = f"\n🔥 **Hào Quang Streak:** +{bonus_xp} EXP"

            exp = user['exp'] + reward
            layer = user['layer']
            goal = user['goal']
            leveled_up = False
            while exp >= goal:
                exp -= goal
                layer += 1
                goal = max(layer * 1000, 200)
                leveled_up = True
            
            await self.db.update_user(uid, missions=new_missions, missions_completed=user['missions_completed'] + 1, exp=exp, layer=layer, goal=goal)
            if leveled_up: await self.update_member_visuals(interaction.user, layer)
            
            if not silent:
                res_embed = txa_embed(
                    "✅ Công Khóa Đã Hoàn Tất", 
                    f"Nhiệm vụ **{mission['title']}** đã hoàn thành viên mãn!\n"
                    f"📈 Nhận được: **{reward} EXP** linh lực.{bonus_msg}", 
                    Color.green()
                )
                if leveled_up: res_embed.add_field(name="🔥 ĐỘT PHÁ CẢNH GIỚI", value=f"Ngươi đã đạt tới **Tầng {layer}**!")
                await interaction.followup.send(embed=res_embed, ephemeral=True)
        else:
            if not silent:
                res_embed = txa_embed(
                    "❌ Tâm Ma Xâm Nhập", 
                    f"Nhiệm vụ **{mission['title']}** đã hoàn tất nhưng do tâm thần bất ổn, ngươi đã thất bại.\n"
                    f"*Hãy tịnh tâm tu luyện và thử lại sau.*", 
                    Color.red()
                )
                await interaction.followup.send(embed=res_embed, ephemeral=True)

    def get_diff_name(self, diff: int):
        """Chuyển độ khó thành danh xưng tu tiên"""
        data = {
            1: "🟢 Thuận Buồm Xuôi Gió",
            2: "🟡 Sóng Yên Biển Lặng",
            3: "🟠 Phong Ba Bão Táp",
            4: "🔴 Kẻ Sống Người Chết",
            5: "💀 Cửu Tử Nhất Sinh"
        }
        return data.get(diff, "❓ Vô Định")

    @app_commands.command(name="nhiem_vu", description="Xem danh sách nhiệm vụ hôm nay")
    async def nhiem_vu(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        uid = str(interaction.user.id)
        user = await self.db.get_user(uid)
        if not user: return await interaction.followup.send("⛩️ Ngươi chưa ghi danh!", ephemeral=True)
        
        now = datetime.now(VN_TZ)
        # Reset lúc 7h sáng
        reset_hour = 7
        today_reset = now.replace(hour=reset_hour, minute=0, second=0, microsecond=0)
        if now < today_reset: today_reset -= timedelta(days=1)
        
        # Kiểm tra reset nhiệm vụ
        should_refresh = False
        if user['last_mission_reset'] < today_reset.timestamp():
            should_refresh = True
        elif all(m['done'] for m in user['missions']) and user['missions_completed'] < 10:
            # Đã xong 5 bài đầu nhưng chưa quá limit 10 bài -> Refresh bài mới
            should_refresh = True
            rainbow_log(f"🔄 {user['name']} đã hoàn tất đợt công khóa, đang làm mới...")

        if should_refresh:
            missions = await self.generate_missions(user)
            await self.db.update_user(uid, missions=missions, last_mission_reset=now.timestamp())
            user['missions'] = missions

        # Kiểm tra nhiệm vụ đang làm (Đồng bộ ID)
        current_mission_id = None
        if user.get('current_mission'):
            curr = user['current_mission']
            remaining = int(curr['end_time'] - time.time())
            if remaining > 0:
                current_mission_id = int(curr['id'])
            else:
                # Tự động finalize nếu đã xong
                asyncio.create_task(self.finalize_mission(interaction, uid, user, int(curr['id']), silent=True))

        async def build_desc(curr_rem=0):
            d = f"📊 **Tiến độ hôm nay:** `{user['missions_completed']}/10` công khóa\n\n"
            for m in user['missions']:
                m_id = int(m['id'])
                if m_id == current_mission_id and curr_rem > 0:
                    status = "⚔️"  # Đang làm
                    time_info = f" • **Còn {TXAFormat.remaining_detail(curr_rem)}**"
                elif m['done']:
                    status = "✅"  # Hoàn thành
                    time_info = ""
                else:
                    status = "⏳"  # Chưa làm
                    time_info = ""
                
                diff_text = self.get_diff_name(m['difficulty'])
                d += f"{status} **[{m['id']}] {m['title']}**{time_info}\n"
                d += f"└ *Độ khó: {diff_text}*\n"
                d += f"└ *Thưởng: {TXAFormat.number(m['reward'])} Linh Lực • TG: {TXAFormat.remaining_detail(m['time'])} • Thành công: {m['success_rate']}%*\n\n"
            return d

        curr_rem = 0
        if current_mission_id:
            curr_rem = int(user['current_mission']['end_time'] - time.time())

        desc = await build_desc(curr_rem)
        embed = txa_embed("📜 Thiên Lam Linh Bảng - Nhiệm Vụ", desc, Color.blue())
        embed.set_footer(text="Sử dụng /lam_nhiem_vu [id] để tiếp nhận cơ duyên.")
        msg = await interaction.followup.send(embed=embed, ephemeral=True)

        if current_mission_id and curr_rem > 0:
            loop_end = time.time() + 300
            while time.time() < loop_end:
                now_t = time.time()
                curr_rem = int(user['current_mission']['end_time'] - now_t)
                
                if curr_rem <= 0:
                    # Cập nhật lần cuối khi xong
                    embed.description = await build_desc(0)
                    try: await msg.edit(embed=embed)
                    except: pass
                    break
                
                embed.description = await build_desc(curr_rem)
                try: await msg.edit(embed=embed)
                except: break
                await asyncio.sleep(1)

    @app_commands.command(name="lam_nhiem_vu", description="Bắt đầu thực hiện nhiệm vụ")
    @app_commands.describe(mission_id="ID của nhiệm vụ trong danh sách của ngươi")
    async def lam_nhiem_vu(self, interaction: discord.Interaction, mission_id: int):
        uid = str(interaction.user.id)
        user = await self.db.get_user(uid)
        if not user:
            embed = txa_embed("⛩️ Thiên Lam Cấm Chế", "Ngươi chưa ghi danh! Hãy dùng `/start`.", discord.Color.red())
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        
        if user['missions_completed'] >= 10:
            embed = txa_embed("⚠️ Kiệt Sức", "Ngươi đã kiệt sức! Hôm nay làm đủ 10 nhiệm vụ rồi, hãy nghỉ ngơi hoặc bế quan dưỡng thần.", discord.Color.orange())
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        if mission_id == -1:
            embed = txa_embed("⛩️ Tổ Sư Nhắc Nhở", "Hãy kiểm tra lại danh sách nhiệm vụ của ngươi!", discord.Color.orange())
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        mission = next((m for m in user['missions'] if m['id'] == mission_id), None)
        if not mission:
            embed = txa_embed("❌ Lỗi Thần Thức", "Không tìm thấy công khóa này trong tàng thư!", discord.Color.red())
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        if mission['done']:
            embed = txa_embed("✅ Công Khóa Hoàn Tất", "Công khóa này ngươi đã hoàn tất viên mãn!", discord.Color.green())
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        if user['current_mission']:
            # Kiểm tra nếu đang trong tiến trình
            curr = user['current_mission']
            remaining = int(curr['end_time'] - time.time())
            if remaining > 0:
                # Lấy tên nhiệm vụ đang làm
                curr_mission = next((m for m in user['missions'] if m['id'] == curr['id']), None)
                curr_name = curr_mission['title'] if curr_mission else "Không rõ"
                
                embed = txa_embed(
                    "⏳ Công Khóa Đang Tiến Hành",
                    f"Ngươi đang dốc sức thực hiện: **{curr_name}**\n\n"
                    f"⏱️ Hoàn thành sau: <t:{int(curr['end_time'])}:R>\n"
                    f"📊 Thời gian còn lại: **{TXAFormat.remaining_detail(remaining)}**",
                    discord.Color.orange()
                )
                embed.set_footer(text="Hãy kiên nhẫn, đạo tâm sẽ dẫn đạo.")
                return await interaction.response.send_message(embed=embed, ephemeral=True)
            else:
                # Nhiệm vụ đã xong nhưng chưa được xử lý (bot restart giữa chừng)
                # Xử lý kết quả ngay
                await self.finalize_mission(interaction, uid, user, curr['id'])
                return

        await interaction.response.defer(ephemeral=True)
        
        # Bắt đầu làm
        start_t = time.time()
        end_time = int(start_t + mission['time'])
        await self.db.update_user(uid, current_mission={"id": mission['id'], "end_time": end_time})
        
        # Để tránh việc hiện "2 phút trước" khi máy chủ lệch giờ, ta dùng text thủ công bên dưới kết hợp timestamp
        embed = txa_embed(f"⚔️ Tiếp Nhận: {mission['title']}", f"{self.NARRATIVE_STAGES[0][1]}\n⏳ Ước tính hoàn tất: <t:{end_time}:t> (<t:{end_time}:R>)", Color.purple())
        bar = TXAFormat.progress_bar(0, 15)
        rem_str = TXAFormat.remaining_detail(mission['time'])
        embed.add_field(name="✨ Tiến Độ", value=f"`{bar}` ({TXAFormat.pad2(0)}%) - {rem_str}")
        msg = await interaction.followup.send(embed=embed, ephemeral=True)
        
        # Cập nhật progress mỗi 1 giây (real-time)
        last_stage_msg = self.NARRATIVE_STAGES[0][1]
        while True:
            now_t = time.time()
            elapsed = now_t - start_t
            remaining = max(0, int(end_time - now_t))
            percent = min(100, int((elapsed / mission['time']) * 100))
            
            if percent >= 100: break
            
            # Chọn narrative text theo %
            stage_msg = self.NARRATIVE_STAGES[0][1]
            for threshold, text in self.NARRATIVE_STAGES:
                if percent >= threshold:
                    stage_msg = text
            
            bar = TXAFormat.progress_bar(percent, 15)
            rem_str = TXAFormat.remaining_detail(remaining)
            
            # Chỉ cập nhật nếu có sự thay đổi đáng kể hoặc tin nhắn mới
            embed.description = f"{stage_msg}\n⏳ Ước tính hoàn tất: <t:{end_time}:t> (<t:{end_time}:R>)"
            embed.set_field_at(0, name="✨ Tiến Độ", value=f"`{bar}` ({TXAFormat.pad2(percent)}%) - {rem_str}")
            
            try: await msg.edit(embed=embed)
            except: pass
            
            if percent >= 100: break
            await asyncio.sleep(1)

        # Xử lý kết quả
        user = await self.db.get_user(uid) # Re-fetch
        success = random.randint(1, 100) <= mission['success_rate']
        
        # Xóa current_mission
        await self.db.update_user(uid, current_mission=None)
        
        if success:
            # Mark done in list
            new_missions = user['missions']
            for m in new_missions:
                if m['id'] == mission['id']: m['done'] = True
            
            reward = mission['reward']
            # Bonus streak
            bonus_msg = ""
            if user['daily_streak'] >= 3:
                bonus_pct = min(0.5, (user['daily_streak'] // 3) * 0.05)
                bonus_xp = int(reward * bonus_pct)
                reward += bonus_xp
                bonus_msg = f"\n🔥 **Hào Quang Streak:** +{bonus_xp} EXP"

            exp = user['exp'] + reward
            layer = user['layer']
            goal = user['goal']
            leveled_up = False
            while exp >= goal:
                exp -= goal
                layer += 1
                goal = max(layer * 1000, 200)
                leveled_up = True
            
            await self.db.update_user(uid, missions=new_missions, missions_completed=user['missions_completed'] + 1, exp=exp, layer=layer, goal=goal)
            if leveled_up: await self.update_member_visuals(interaction.user, layer)
            
            res_embed = txa_embed("✅ Cơ Duyên Viên Mãn", f"Chúc mừng! Ngươi đã hoàn thành **{mission['title']}**.\n📈 Nhận được: **{reward} EXP** linh lực.{bonus_msg}", Color.green())
            if leveled_up: res_embed.add_field(name="🔥 ĐỘT PHÁ CẢNH GIỚI", value=f"Ngươi đã đạt tới **Tầng {layer}**!")
        else:
            res_embed = txa_embed("❌ Tâm Ma Xâm Nhập", f"Đáng tiếc! Do tu vi chưa vững hoặc tâm thần bất ổn, ngươi đã thất bại trong cơ duyên **{mission['title']}**.\n*Hãy tịnh tâm tu luyện và thử lại sau.*", Color.red())

        await msg.edit(embed=res_embed)

    @lam_nhiem_vu.autocomplete("mission_id")
    async def mission_id_autocomplete(self, interaction: discord.Interaction, current: str):
        user = await self.db.get_user(str(interaction.user.id))
        if not user or not user.get('missions'): return []
        
        choices = []
        pending = [m for m in user['missions'] if not m['done']]
        
        if user['missions_completed'] >= 10:
            return [app_commands.Choice(name="💤 Ngươi đã kiệt sức! Hãy nghỉ ngơi đến ngày mai.", value=-1)]
            
        if not pending:
            return [app_commands.Choice(name="✨ Đã xong đợt này! Dùng /nhiem_vu để nhận đợt tiếp theo.", value=-1)]

        for m in pending:
            title = f"{m['id']}. {m['title']} ({self.get_diff_name(m['difficulty'])})"
            if current.lower() in title.lower():
                choices.append(app_commands.Choice(name=title, value=m['id']))
        return choices[:25]

    @app_commands.command(name="bxh", description="Bảng xếp hạng Thiên Lam Tông")
    async def bxh(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        top = await self.db.get_top_users(10)
        
        desc = "```ansi\n"
        desc += "\u001b[1;33m┏━━━━┳━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━┓\u001b[0m\n"
        desc += "\u001b[1;33m┃ HẠNG ┃      ĐẠO HỮU      ┃ CẢNH GIỚI ┃   TU VI   ┃\u001b[0m\n"
        desc += "\u001b[1;33m┣━━━━╋━━━━━━━━━━━━━━━━━━━━━╋━━━━━━━━━━━╋━━━━━━━━━━━┫\u001b[0m\n"
        
        for i, u in enumerate(top, 1):
            rank_name, info = get_rank_info(u['layer'])
            # Cắt ngắn tên nếu quá dài
            name = (u['name'][:15] + '..') if len(u['name']) > 17 else u['name']
            
            # Emojis và màu sắc cho Top 3
            if i == 1: medal, color = "🥇", "\u001b[1;33m" # Gold
            elif i == 2: medal, color = "🥈", "\u001b[1;37m" # Silver
            elif i == 3: medal, color = "🥉", "\u001b[1;31m" # Bronze
            else: medal, color = f"{i:2}", "\u001b[0;37m"
            
            exp_str = f"{u['exp']:,}"
            desc += f"┃ {medal} ┃ {color}{name:<19}\u001b[0m ┃ Tầng {u['layer']:3} ┃ {exp_str:>9} ┃\n"
            
        desc += "\u001b[1;33m┗━━━━┻━━━━━━━━━━━━━━━━━━━━━┻━━━━━━━━━━━┻━━━━━━━━━━━┛\u001b[0m\n"
        desc += "```"
            
        embed = txa_embed("📊 Thiên Lam Tu Vi Bảng", desc or "Chư thiên chưa có ai ghi danh!", Color.gold())
        embed.set_thumbnail(url="https://hoathinh3d.moi/wp-content/uploads/2023/02/luyen-khi-10-van-nam-300x450.jpg")
        embed.add_field(name="✨ Pháp Tắc", value="Đạo hữu có tu vi thâm hậu nhất sẽ đứng đầu thiên bảng.", inline=False)
        embed.set_footer(text="Thần bảng phong vân - Thiên Lam Tông.")
        await interaction.followup.send(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Cultivation(bot))
