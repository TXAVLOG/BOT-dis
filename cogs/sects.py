import discord
import asyncio
import random
from discord import app_commands
from discord.ext import commands
from core.helpers import txa_embed, rainbow_log
from core.database import Database
from core.game_data import CultivationData
import json

class Sects(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db: Database = bot.db
        self.sect_list_msgs = set() # Set of message objects to update

    async def _build_sect_list_embed(self):
        sects = await self.db.get_all_sects()
        if not sects:
            return txa_embed("📜 Danh Sách Tông Môn", "Chưa có tông môn nào được thành lập.", discord.Color.gold())
            
        embed = txa_embed("📜 Danh Sách Tông Môn (SQL Mode)", f"Tổng số: {len(sects)} phái", discord.Color.gold())
        
        async with self.db.aiosqlite.connect(self.db.db_path) as db:
            db.row_factory = self.db.aiosqlite.Row
            for sect in sects:
                # Query members
                async with db.execute("SELECT user_id FROM users WHERE sect_id = ?", (sect['sect_id'],)) as cursor:
                    rows = await cursor.fetchall()
                    member_ids = [r['user_id'] for r in rows]
                
                leader = f"<@{sect['leader_id']}>"
                member_count = len(member_ids)
                member_mentions = ", ".join([f"<@{mid}>" for mid in member_ids[:10]])
                if member_count > 10:
                    member_mentions += f" và {member_count - 10} đệ tử khác..."
                
                content = f"👑 **Tông Chủ:** {leader}\n👥 **Đệ Tử ({member_count}):** {member_mentions if member_ids else 'Chưa có'}"
                embed.add_field(name=f"⛩️ {sect['name']} (Cấp {sect['level']})", value=content, inline=False)
        return embed

    async def update_sect_list_displays(self):
        """Cập nhật tất cả các bảng Admin Sect List đang hiển thị"""
        if not self.sect_list_msgs: return
        
        embed = await self._build_sect_list_embed()
        to_remove = set()
        
        valid_msgs = set()
        for msg in self.sect_list_msgs:
            try:
                await msg.edit(embed=embed)
                valid_msgs.add(msg)
            except discord.NotFound:
                # Message đã bị xóa
                pass
            except Exception:
                pass
        
        self.sect_list_msgs = valid_msgs

    def interaction_check(self, interaction: discord.Interaction):
        if interaction.guild is None: return False
        if not self.bot.allowed_channel_ids: return True
        if interaction.channel_id not in self.bot.allowed_channel_ids:
            asyncio.create_task(interaction.response.send_message(
                "⛩️ **Cấm Chế:** Pháp lệnh khai tông chỉ có thể thi triển tại địa giới được phép của Thiên Lam Tông!", 
                ephemeral=True
            ))
            return False
        return True

    async def sect_name_autocomplete(self, interaction: discord.Interaction, current: str):
        """Autocomplete tìm kiếm Tông Môn"""
        sects = await self.db.get_all_sects()
        # Lọc theo chuỗi hiện tại
        choices = [
            app_commands.Choice(name=s['name'], value=s['name']) 
            for s in sects if current.lower() in s['name'].lower()
        ]
        return choices[:25] # Giới hạn 25 kết quả của Discord

    async def sect_member_autocomplete(self, interaction: discord.Interaction, current: str):
        """Autocomplete tìm kiếm thành viên trong tông môn của mình"""
        uid = str(interaction.user.id)
        sect = await self.check_user_sect(uid)
        if not sect: return []
        
        async with self.db.aiosqlite.connect(self.db.db_path) as db:
            db.row_factory = self.db.aiosqlite.Row
            async with db.execute("SELECT user_id, name FROM users WHERE sect_id = ?", (sect['sect_id'],)) as cursor:
                members = await cursor.fetchall()
        
        choices = []
        for m in members:
            m_name = m['name'] if m['name'] else f"Vô Danh ({m['user_id']})"
            if current.lower() in m_name.lower():
                 choices.append(app_commands.Choice(name=m_name, value=m['user_id']))
        return choices[:25]

    async def check_user_sect(self, user_id: str):
        """Kiểm tra xem user đã tham gia tông môn nào chưa (dựa trên DB)"""
        # Lấy sect_id từ bảng users trước
        user = await self.db.get_user(user_id)
        if user and user.get('sect_id'):
            # Nếu có sect_id, lấy thông tin sect
            async with self.db.aiosqlite.connect(self.db.db_path) as db:
                db.row_factory = self.db.aiosqlite.Row
                async with db.execute("SELECT * FROM sects WHERE sect_id = ?", (user['sect_id'],)) as cursor:
                    row = await cursor.fetchone()
                    if row: return dict(row)
        
        # Fallback: Check leader status (Tông chủ luôn thuộc tông của mình)
        sects = await self.db.get_all_sects()
        for sect in sects:
            if sect['leader_id'] == user_id:
                # Nếu chưa sync sect_id cho leader, sync luôn
                await self.db.update_user(user_id, sect_id=sect['sect_id'])
                return sect
        return None

    @app_commands.command(name="sect_create", description="Sáng lập Tông Môn (Cần Tầng 50+)")
    async def sect_create(self, interaction: discord.Interaction, name: str):
        await interaction.response.defer(ephemeral=True)
        uid = str(interaction.user.id)
        user = await self.db.get_user(uid)
        if not user:
            embed = txa_embed("⛩️ Thiên Lam Cấm Chế", "Ngươi chưa ghi danh! Hãy dùng `/start` để có tư cách sáng lập tông môn.", discord.Color.red())
            return await interaction.followup.send(embed=embed, ephemeral=True)
            
        # Check if user is admin
        is_admin = int(uid) in self.bot.admin_ids
        
        # Check existing membership
        existing_sect = await self.check_user_sect(uid)
        if existing_sect and not is_admin:
            embed = txa_embed(
                "🚫 Nhất Tâm Bất Nhị Dụng", 
                f"Ngươi đang là đệ tử của **{existing_sect['name']}**. Phản bội tông môn là tội chết!", 
                discord.Color.red()
            )
            return await interaction.followup.send(embed=embed, ephemeral=True)

        user = await self.db.get_user(uid)
        
        if not user or user['layer'] < 50:
            embed = txa_embed(
                "⚠️ Cảnh Giới Bất Túc", 
                "Cần đạt tới **Hóa Thần** (Tầng 50+) mới đủ tư cách khai tông lập phái!", 
                discord.Color.red()
            )
            return await interaction.followup.send(embed=embed, ephemeral=True)
        
        try:
            async with self.db.aiosqlite.connect(self.db.db_path) as db:
                cursor = await db.execute("INSERT INTO sects (name, leader_id) VALUES (?, ?)", (name, uid))
                sect_id = cursor.lastrowid
                await db.commit()
            
            # Cập nhật sect_id cho tông chủ và reset nhiệm vụ để nhận công khóa tông môn
            await self.db.update_user(uid, sect_id=sect_id, missions=[])

            embed = txa_embed(
                "🎊 Khai Tông Lập Phái!",
                f"Tông môn **{name}** đã chính thức hiện diện tại Thiên Lam Giới!\n**Tông Chủ:** {interaction.user.mention}",
                discord.Color.gold()
            )
            rainbow_log(f"⛩️ [Sect] {interaction.user.name} đã sáng lập tông môn: {name} (ID: {sect_id})")
            await interaction.followup.send(embed=embed, ephemeral=True)
            asyncio.create_task(self.update_sect_list_displays())
        except Exception as e:
            embed = txa_embed(
                "❌ Thiên Lý Bất Dung",
                f"Tên tông môn đã tồn tại hoặc xảy ra lỗi: {e}",
                discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="sect_info", description="Xem thông tin Tông Môn của bản thân")
    async def sect_info(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        uid = str(interaction.user.id)
        user = await self.db.get_user(uid)
        if not user:
            embed = txa_embed("⛩️ Thiên Lam Cấm Chế", "Ngươi chưa ghi danh! Hãy dùng `/start` để nhập môn.", discord.Color.red())
            return await interaction.followup.send(embed=embed, ephemeral=True)
        
        sect = await self.check_user_sect(uid)
        if not sect: 
            embed = txa_embed("❌ Thần Thức Mờ Mịt", "Ngươi chưa gia nhập tông môn nào cả.", discord.Color.red())
            return await interaction.followup.send(embed=embed)
        
        # Đếm số lượng đệ tử từ bảng users
        async with self.db.aiosqlite.connect(self.db.db_path) as db:
            async with db.execute("SELECT COUNT(*) FROM users WHERE sect_id = ?", (sect['sect_id'],)) as count_cursor:
                count_row = await count_cursor.fetchone()
                member_count = count_row[0] if count_row else 0

        embed = txa_embed(f"⛩️ Tông Môn: {sect['name']}", sect.get('description', "Dấu tích cổ xưa."), discord.Color.gold())
        embed.add_field(name="👑 Tông Chủ", value=f"<@{sect['leader_id']}>", inline=True)
        embed.add_field(name="📈 Quy Mô", value=f"Cấp {sect['level']} • {member_count} đệ tử", inline=True)
        embed.add_field(name="✨ Linh Mạch", value=f"{sect['exp']} EXP", inline=True)
        
        kf_list = sect.get('kung_fu', [])
        kf_text = "\n".join([f"📜 **{CultivationData.KUNG_FU[k]['name']}**" for k in kf_list if k in CultivationData.KUNG_FU]) or "Chưa có"
        embed.add_field(name="📚 Tàng Kinh Các", value=kf_text, inline=False)
        
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="sect_join", description="Bái sư nhập môn")
    @app_commands.autocomplete(name=sect_name_autocomplete)
    async def sect_join(self, interaction: discord.Interaction, name: str):
        await interaction.response.defer(ephemeral=True)
        uid = str(interaction.user.id)
        user = await self.db.get_user(uid)
        if not user:
            embed = txa_embed("⛩️ Thiên Lam Cấm Chế", "Ngươi chưa ghi danh! Hãy dùng `/start` để có tư cách bái sư.", discord.Color.red())
            return await interaction.followup.send(embed=embed, ephemeral=True)
        
        # Check if already in sect
        existing_sect = await self.check_user_sect(uid)
        if existing_sect:
            return await interaction.followup.send(embed=txa_embed("🚫 Nhất Tâm Bất Nhị Dụng", f"Đã là đệ tử của **{existing_sect['name']}**, sao còn đứng núi này trông núi nọ?", discord.Color.red()))

        async with self.db.aiosqlite.connect(self.db.db_path) as db:
            db.row_factory = self.db.aiosqlite.Row
            async with db.execute("SELECT * FROM sects WHERE name = ?", (name,)) as cursor:
                row = await cursor.fetchone()
                if not row: return await interaction.followup.send("❌ Tông môn hư ảo, không tồn tại.")
                sect = dict(row)
            
            # Update user's sect_id and reset missions
            await self.db.update_user(uid, sect_id=sect['sect_id'], missions=[])
            
        await interaction.followup.send(embed=txa_embed("✅ Bái Sư Thành Công", f"Chúc mừng đạo hữu gia nhập **{name}**!\nHãy cống hiến hết mình cho tông môn!", discord.Color.green()))
        rainbow_log(f"🤝 [Sect] {interaction.user.name} gia nhập tông môn: {name}")
        asyncio.create_task(self.update_sect_list_displays())

    @app_commands.command(name="sect_transfer", description="Truyền ngôi Tông Chủ cho đệ tử khác")
    @app_commands.describe(member_id="Chọn đệ tử kế thừa (Dùng autocomplete)")
    @app_commands.autocomplete(member_id=sect_member_autocomplete)
    async def sect_transfer(self, interaction: discord.Interaction, member_id: str):
        await interaction.response.defer(ephemeral=True)
        uid = str(interaction.user.id)
        user = await self.db.get_user(uid)
        if not user:
            embed = txa_embed("⛩️ Thiên Lam Cấm Chế", "Ngươi chưa ghi danh! Làm sao có thể truyền vị?", discord.Color.red())
            return await interaction.followup.send(embed=embed, ephemeral=True)
        
        sect = await self.check_user_sect(uid)
        if not sect:
            return await interaction.followup.send("❌ Ngươi chưa gia nhập tông môn nào.")
            
        if sect['leader_id'] != uid:
            return await interaction.followup.send("🚫 Chỉ Tông Chủ mới có quyền truyền ngôi!")
            
        if member_id == uid:
            return await interaction.followup.send("⚠️ Không thể tự truyền ngôi cho chính mình.")

        # Verify member is in sect
        async with self.db.aiosqlite.connect(self.db.db_path) as db:
            db.row_factory = self.db.aiosqlite.Row
            async with db.execute("SELECT * FROM users WHERE user_id = ? AND sect_id = ?", (member_id, sect['sect_id'])) as cursor:
                target_user = await cursor.fetchone()
                
            if not target_user:
                return await interaction.followup.send(f"❌ Kẻ này (`{member_id}`) không phải đệ tử trong tông.")

            # Transfer
            await db.execute("UPDATE sects SET leader_id = ? WHERE sect_id = ?", (member_id, sect['sect_id']))
            await db.commit()
            
        await interaction.followup.send(embed=txa_embed("👑 Truyền Ngôi", f"Ngai vị Tông Chủ của **{sect['name']}** đã được truyền lại cho <@{member_id}>!", discord.Color.gold()))
        rainbow_log(f"👑 [Sect] {interaction.user.name} truyền ngôi tông chủ {sect['name']} cho {member_id}")
        asyncio.create_task(self.update_sect_list_displays())
        
        # DM Notice
        try:
            target_obj = await self.bot.fetch_user(int(member_id))
            await target_obj.send(embed=txa_embed("👑 Tân Tông Chủ", f"Ngươi đã được truyền ngôi Tông Chủ của **{sect['name']}**!", discord.Color.gold()))
        except: pass

    @app_commands.command(name="sect_leave", description="Phản xuất tông môn")
    async def sect_leave(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        uid = str(interaction.user.id)
        user = await self.db.get_user(uid)
        if not user:
            embed = txa_embed("⛩️ Thiên Lam Cấm Chế", "Ngươi chưa ghi danh! Hãy dùng `/start` để nhập môn.", discord.Color.red())
            return await interaction.followup.send(embed=embed, ephemeral=True)
        
        sect = await self.check_user_sect(uid)
        if not sect:
            return await interaction.followup.send(embed=txa_embed("❌ Vô Môn Vô Phái", "Ngươi vốn là tán tu, có tông môn nào để rời?", discord.Color.red()))
        
        # Nếu là tông chủ
        if sect['leader_id'] == uid:
            async with self.db.aiosqlite.connect(self.db.db_path) as db:
                db.row_factory = self.db.aiosqlite.Row
                # Lấy danh sách thành viên khác (không bao gồm tông chủ)
                async with db.execute("SELECT user_id FROM users WHERE sect_id = ? AND user_id != ?", (sect['sect_id'], uid)) as cursor:
                    rows = await cursor.fetchall()
                    members = [r['user_id'] for r in rows]
            
            if not members:
                 return await interaction.followup.send(embed=txa_embed("🚫 Tông Chủ Đơn Độc", "Tông môn chỉ còn mỗi ngươi. Hãy dùng `/sect_delete` để giải tán (Cần Admin) hoặc tìm người gia nhập để truyền ngôi.", discord.Color.red()))
            
            # Chọn người kế thừa
            new_leader_id = random.choice(members)
            
            # Update DB: Đổi leader và set sect_id của user hiện tại về NULL
            async with self.db.aiosqlite.connect(self.db.db_path) as db:
                await db.execute("UPDATE sects SET leader_id = ? WHERE sect_id = ?", (new_leader_id, sect['sect_id']))
                await db.commit()
            
            await self.db.update_user(uid, sect_id=None)
            
            # Thông báo
            embed = txa_embed(
                "👋 Tông Chủ Quy Ẩn", 
                f"**{interaction.user.name}** đã rời bỏ tông môn.\n👑 Ngai vị Tông Chủ **{sect['name']}** đã tự động chuyển giao cho <@{new_leader_id}>!", 
                discord.Color.orange()
            )
            await interaction.followup.send(embed=embed)
            
            # DM Notice New Leader
            try:
                new_leader_obj = await self.bot.fetch_user(int(new_leader_id))
                dm_embed = txa_embed("👑 Cơ Duyên Bất Ngờ", f"Cựu tông chủ đã rời đi. Ngươi đã được Thiên Đạo chọn làm **Tân Tông Chủ** của **{sect['name']}**!", discord.Color.gold())
                await new_leader_obj.send(embed=dm_embed)
            except: pass
            
        else:
            # Thành viên bình thường
            await self.db.update_user(uid, sect_id=None)
            await interaction.followup.send(embed=txa_embed("👋 Phản Xuất Tông Môn", f"Ngươi đã rời khỏi **{sect['name']}**. Từ nay đường ai nấy đi!", discord.Color.orange()))

        asyncio.create_task(self.update_sect_list_displays())

    @app_commands.command(name="sect_kungfu", description="Tàng Kinh Các - Nghiên cứu công pháp (Chỉ Tông Chủ)")
    async def sect_kungfu(self, interaction: discord.Interaction):
        uid = str(interaction.user.id)
        user = await self.db.get_user(uid)
        if not user:
            embed = txa_embed("⛩️ Thiên Lam Cấm Chế", "Ngươi chưa ghi danh! Hãy dùng `/start` để nhập môn.", discord.Color.red())
            return await interaction.response.send_message(embed=embed, ephemeral=True)
            
        sect = await self.check_user_sect(uid)
        if not sect: return await interaction.response.send_message("❌ Chưa có tông môn!", ephemeral=True)
        if sect['leader_id'] != uid: return await interaction.response.send_message("❌ Chỉ Tông Chủ mới có quyền nghiên cứu!", ephemeral=True)
        
        embed = txa_embed("📚 TÀNG KINH CÁC", "Nghiên cứu công pháp để cường hóa toàn tông môn.", discord.Color.blue())
        for k_id, info in CultivationData.KUNG_FU.items():
            status = "✅ Đã có" if k_id in sect.get('kung_fu', []) else f"💰 {info['price']} EXP"
            embed.add_field(name=f"{info['emoji']} {info['name']} ({status})", value=info['desc'], inline=False)
            
        class KFView(discord.ui.View):
            def __init__(self, db, sect, kf_data):
                super().__init__(timeout=60)
                self.db, self.sect, self.kf_data = db, sect, kf_data
                
            @discord.ui.select(placeholder="Chọn công pháp muốn nghiên cứu...", options=[
                discord.SelectOption(label=v['name'], value=k, emoji=v['emoji']) 
                for k, v in CultivationData.KUNG_FU.items() if k not in sect.get('kung_fu', [])
            ])
            async def select_kf(self, interaction_select, select):
                kid = select.values[0]
                info = CultivationData.KUNG_FU[kid]
                if self.sect['exp'] < info['price']:
                    return await interaction_select.response.send_message("❌ Tông môn không đủ linh mạch (EXP)!", ephemeral=True)
                
                new_kf = self.sect.get('kung_fu', [])
                new_kf.append(kid)
                await self.db.update_sect(self.sect['sect_id'], exp=self.sect['exp'] - info['price'], kung_fu=new_kf)
                rainbow_log(f"📚 [Sect] Tông môn {self.sect['name']} nghiên cứu thành công: {info['name']}")
                await interaction_select.response.send_message(f"✅ Đã nghiên cứu thành công **{info['name']}**!", ephemeral=True)

        await interaction.response.send_message(embed=embed, view=KFView(self.db, sect, CultivationData.KUNG_FU), ephemeral=True)

    @app_commands.command(name="admin_sect_list", description="[Admin] Danh sách toàn bộ Tông Môn và Đệ Tử")
    async def admin_sect_list(self, interaction: discord.Interaction):
        if interaction.user.id not in self.bot.admin_ids:
            return await interaction.response.send_message("🚫 Chỉ có Lão Tổ (Admin) mới có quyền này!", ephemeral=True)
        
        await interaction.response.defer(ephemeral=True)
        embed = await self._build_sect_list_embed()
        msg = await interaction.followup.send(embed=embed, ephemeral=True)
        
        # Lưu lại message để update sau này
        self.sect_list_msgs.add(msg)
        
        # Tự động xóa sau 5 phút (300s)
        async def auto_delete():
            await asyncio.sleep(300)
            try:
                await msg.delete()
            except: pass
            if msg in self.sect_list_msgs:
                self.sect_list_msgs.discard(msg)
        
        asyncio.create_task(auto_delete())

    @app_commands.command(name="sect_delete", description="[ADMIN] Giải tán Tông Môn")
    @app_commands.autocomplete(name=sect_name_autocomplete)
    async def sect_delete(self, interaction: discord.Interaction, name: str):
        if interaction.user.id not in self.bot.admin_ids:
            return await interaction.response.send_message("🚫 Chỉ có Thiên Đạo (Admin) mới có quyền này!", ephemeral=True)
        
        await interaction.response.defer(ephemeral=True)
        async with self.db.aiosqlite.connect(self.db.db_path) as db:
            await db.execute("DELETE FROM sects WHERE name = ?", (name,))
            await db.commit()
        
        await interaction.followup.send(embed=txa_embed("🔥 Diệt Môn", f"Tông môn **{name}** đã bị xóa sổ khỏi thế gian!", discord.Color.dark_red()))
        asyncio.create_task(self.update_sect_list_displays())

async def setup(bot):
    await bot.add_cog(Sects(bot))
