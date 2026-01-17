import discord
import os
import shutil
from datetime import timedelta, datetime
from discord import app_commands
from discord.ext import commands
from core.helpers import rainbow_log, txa_embed

class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db

    async def timed_out_users_autocomplete(self, interaction: discord.Interaction, current: str):
        """Autocomplete tìm những người đang bị timeout"""
        if not interaction.guild: return []
        
        timed_out_members = []
        for m in interaction.guild.members:
            if m.is_timed_out():
                timed_out_members.append(m)
        
        choices = []
        for m in timed_out_members:
            display = f"{m.name} ({m.id})"
            if current.lower() in display.lower():
                choices.append(app_commands.Choice(name=display, value=str(m.id)))
        
        return choices[:25]

    @app_commands.command(name="admin_set_layer", description="[Lão Tổ] Cải Thiên Nghịch Mệnh - Chỉnh sửa cảnh giới đệ tử")
    @app_commands.describe(user="Đệ tử cần chỉ điểm", layer="Cảnh giới mong muốn (Tầng)")
    async def admin_set_layer(self, interaction: discord.Interaction, user: discord.User, layer: int):
        if interaction.user.id not in self.bot.admin_ids:
            return await interaction.response.send_message("🚫 **Phàm nhân to gan!** Ngươi dám trộm sử dụng pháp bảo của Lão Tổ sao?", ephemeral=True)
        
        await interaction.response.defer(ephemeral=True)
        uid = str(user.id)
        current_data = await self.db.get_user(uid)
        
        if not current_data:
            return await interaction.followup.send("⚠️ Kẻ này người trần mắt thịt, chưa từng bước vào con đường tu tiên (Chưa dùng `/start`).")

        # Cập nhật tầng thứ
        await self.db.update_user(uid, layer=layer)
        
        # Thông báo
        embed = txa_embed(
            "⚡ Cải Thiên Nghịch Mệnh ⚡",
            f"Lão Tổ đã thi triển đại thần thông, cưỡng ép nâng cao tu vi của {user.mention} lên **Luyện Khí Tầng {layer}**!\n\n*\"Tiểu tử, cơ duyên đã đến, hãy trân trọng!\"*",
            discord.Color.purple()
        )
        await interaction.followup.send(embed=embed)
        
        # Gửi DM cho user nếu được
        try:
            dm_embed = txa_embed(
                "✨ Cơ Duyên Thiên Định",
                f"Lão Tổ Thiên Lam Tông đã đích thân xuất quan và điều chỉnh tu vi của ngươi thành **Tầng {layer}**.",
                discord.Color.gold()
            )
            await user.send(embed=dm_embed)
        except: pass

    @app_commands.command(name="admin_grant_exp", description="[Lão Tổ] Truyền Công Đại Pháp - Ban phát linh lực")
    @app_commands.describe(user="Đệ tử được truyền công", amount="Lượng linh lực (EXP)")
    async def admin_grant_exp(self, interaction: discord.Interaction, user: discord.User, amount: int):
        if interaction.user.id not in self.bot.admin_ids:
            return await interaction.response.send_message("🚫 **Làm càn!** Linh lực của Lão Tổ há phải thứ ngươi muốn là được?", ephemeral=True)
            
        await interaction.response.defer(ephemeral=True)
        uid = str(user.id)
        current_data = await self.db.get_user(uid)
        
        if not current_data:
            return await interaction.followup.send("⚠️ Kẻ này chưa ghi danh tu luyện.")

        new_exp = current_data['exp'] + amount
        # Check level up simple logic (optional, but keep it raw for admin)
        await self.db.update_user(uid, exp=new_exp)
        
        embed = txa_embed(
            "🌀 Truyền Công Đại Pháp",
            f"Lão Tổ vung tay áo, một luồng linh lực hùng hậu **(+{amount:,} EXP)** đã rót thẳng vào đan điền của {user.mention}!\n\n*\"Hậu bối, hấp thu cho tốt!\"*",
            discord.Color.blue()
        )
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="admin_punish", description="[Lão Tổ] Thiên Phạt - Trừng phạt đệ tử ngỗ nghịch")
    @app_commands.describe(user="Đệ tử bị phạt", reason="Lý do trừng phạt")
    async def admin_punish(self, interaction: discord.Interaction, user: discord.User, reason: str):
        if interaction.user.id not in self.bot.admin_ids:
            return await interaction.response.send_message("🚫 Chỉ có Lão Tổ mới nắm giữ Thiên Phạt Chi Lôi!", ephemeral=True)

        await interaction.response.defer(ephemeral=True)
        uid = str(user.id)
        u_data = await self.db.get_user(uid)
        
        if not u_data:
            return await interaction.followup.send("⚠️ Kẻ này không tồn tại trong danh sách đệ tử.")

        # Trừ 50% EXP và 1 tầng tu vi làm phạt
        new_layer = max(1, u_data['layer'] - 1)
        new_exp = max(0, int(u_data['exp'] * 0.5))
        
        await self.db.update_user(uid, layer=new_layer, exp=new_exp)
        
        embed = txa_embed(
            "⛈️ Thiên Phạt Chi Lôi",
            f"**{user.mention}** đã chọc giận Lão Tổ!\nLý do: *{reason}*\n\n📉 **Hậu quả:**\n- Tu vi rơi xuống: **Tầng {new_layer}**\n- Linh lực tiêu tan: **50%**\n\n*\"Quay đầu là bờ, đừng để ta phải ra tay lần nữa!\"*",
            discord.Color.dark_red()
        )
        await interaction.followup.send(embed=embed)

        await interaction.followup.send(embed=embed)

    @app_commands.command(name="admin_kick", description="[Admin] Trục Xuất Hạ Giới - Kick người ra khỏi server")
    @app_commands.describe(user="Kẻ cần trục xuất", reason="Lý do")
    async def admin_kick(self, interaction: discord.Interaction, user: discord.Member, reason: str = None):
        if interaction.user.id not in self.bot.admin_ids:
            return await interaction.response.send_message("🚫 **Phàm nhân to gan!** Ngươi không có quyền năng này!", ephemeral=True)
        
        await interaction.response.defer(ephemeral=True)
        try:
            await user.kick(reason=reason)
            embed = txa_embed(
                "🦶 Trục Xuất Hạ Giới",
                f"**{user.name}** đã bị trục xuất khỏi Thiên Lam Tông!\nLý do: *{reason or 'Vi phạm thiên quy'}*",
                discord.Color.orange()
            )
            await interaction.followup.send(embed=embed)
        except Exception as e:
            await interaction.followup.send(f"❌ Không thể trục xuất: {e}")

    @app_commands.command(name="admin_ban", description="[Admin] Phong Ấn Vĩnh Viễn - Ban người khỏi server")
    @app_commands.describe(user="Kẻ cần phong ấn", reason="Lý do")
    async def admin_ban(self, interaction: discord.Interaction, user: discord.Member, reason: str = None):
        if interaction.user.id not in self.bot.admin_ids:
            return await interaction.response.send_message("🚫 **Phàm nhân to gan!** Ngươi không có quyền năng này!", ephemeral=True)
            
        await interaction.response.defer(ephemeral=True)
        try:
            await user.ban(reason=reason)
            embed = txa_embed(
                "🚫 Phong Ấn Vĩnh Viễn", 
                f"**{user.name}** đã bị phong ấn vĩnh viễn, không thể bước chân vào Thiên Lam Tông nữa!\nLý do: *{reason or 'Vi phạm thiên quy nghiêm trọng'}*",
                discord.Color.dark_red()
            )
            await interaction.followup.send(embed=embed)
        except Exception as e:
            await interaction.followup.send(f"❌ Không thể phong ấn: {e}")

    @app_commands.command(name="admin_unban", description="[Admin] Giải Khai Phong Ấn - Gỡ ban cho người dùng")
    @app_commands.describe(user_id="ID của kẻ được ân xá")
    async def admin_unban(self, interaction: discord.Interaction, user_id: str):
        if interaction.user.id not in self.bot.admin_ids:
            return await interaction.response.send_message("🚫 **Phàm nhân to gan!** Ngươi không có quyền năng này!", ephemeral=True)
            
        await interaction.response.defer(ephemeral=True)
        try:
            user = await self.bot.fetch_user(int(user_id))
            await interaction.guild.unban(user)
            embed = txa_embed(
                "🔓 Giải Khai Phong Ấn",
                f"Lão Tổ đã ban đại ân xá! **{user.name}** đã được gỡ bỏ phong ấn, có thể quay lại Thiên Lam Tông tu luyện.",
                discord.Color.green()
            )
            await interaction.followup.send(embed=embed)
        except Exception as e:
            await interaction.followup.send(f"❌ Không thể ân xá (Có thể ID sai hoặc chưa bị ban): {e}")

    @app_commands.command(name="admin_ban_list", description="[Admin] Sổ Nam Tào - Xem danh sách bị phong ấn")
    async def admin_ban_list(self, interaction: discord.Interaction):
        if interaction.user.id not in self.bot.admin_ids:
            return await interaction.response.send_message("🚫 Chỉ có Lão Tổ mới được xem Sổ Nam Tào!", ephemeral=True)
            
        await interaction.response.defer(ephemeral=True)
        bans = [entry async for entry in interaction.guild.bans()]
        
        if not bans:
            return await interaction.followup.send(embed=txa_embed("✨ Sổ Nam Tào Trống Rỗng", "Thiên hạ thái bình, không có ai bị phong ấn.", discord.Color.green()))
            
        desc = ""
        for entry in bans[:20]: # Show limit 20
            desc += f"🚫 **{entry.user.name}** (`{entry.user.id}`)\n└ Lý do: *{entry.reason or 'Thiên cơ bất khả lộ'}*\n\n"
            
        if len(bans) > 20:
            desc += f"\n*...và còn {len(bans) - 20} tội đồ khác.*"
            
        embed = txa_embed(f"📜 Sổ Nam Tào ({len(bans)} tội đồ)", desc, discord.Color.dark_red())
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="admin_timeout", description="[Admin] Cấm Ngôn Thuật - Khóa mõm (Timeout)")
    @app_commands.describe(user="Kẻ cần khóa mõm", minutes="Thời gian (phút)", reason="Lý do")
    async def admin_timeout(self, interaction: discord.Interaction, user: discord.Member, minutes: int, reason: str = None):
        if interaction.user.id not in self.bot.admin_ids:
            return await interaction.response.send_message("🚫 Ngươi chưa đủ tu vi để thi triển Cấm Ngôn Thuật!", ephemeral=True)

        await interaction.response.defer(ephemeral=True)
        
        try:
            duration = timedelta(minutes=minutes)
            await user.timeout(duration, reason=reason)
            
            embed = txa_embed(
                "🤐 Cấm Ngôn Thuật",
                f"**{user.mention}** đã bị Lão Tổ phong ấn miệng lưỡi trong **{minutes} phút**!\nLý do: *{reason or 'Nói năng xằng bậy, làm loạn đạo tâm'}*\n\n*\"Im lặng là vàng, hãy sám hối đi!\"*",
                discord.Color.dark_grey()
            )
            await interaction.followup.send(embed=embed)
        except Exception as e:
            await interaction.followup.send(f"❌ Phản phệ! Không thể thi triển cấm ngôn: {e}")
    
    @app_commands.command(name="admin_remove_timeout", description="[Admin] Giải Trừ Cấm Ngôn")
    @app_commands.autocomplete(user_id=timed_out_users_autocomplete)
    async def admin_remove_timeout(self, interaction: discord.Interaction, user_id: str):
        if interaction.user.id not in self.bot.admin_ids:
            return await interaction.response.send_message("🚫 Ngươi không có quyền!", ephemeral=True)
            
        await interaction.response.defer(ephemeral=True)
        try:
            member = interaction.guild.get_member(int(user_id))
            if not member:
                member = await interaction.guild.fetch_member(int(user_id))
            
            if not member:
                 return await interaction.followup.send("❌ Không tìm thấy đệ tử này trong tông môn.")

            if not member.is_timed_out():
                return await interaction.followup.send("⚠️ Kẻ này hiện không bị cấm ngôn.")

            await member.timeout(None) # Remove timeout
            embed = txa_embed(
                "🗣️ Khai Khẩu",
                f"Lão Tổ đã thu hồi Cấm Ngôn Thuật trên người **{member.mention}**. Hãy cẩn trọng lời nói!",
                discord.Color.green()
            )
            await interaction.followup.send(embed=embed)
        except Exception as e:
            await interaction.followup.send(f"❌ Lỗi: {e}")

    @app_commands.command(name="clear_cache", description="Quét sạch linh khí tạp chất trong mọi ngóc ngách")
    async def clear_cache(self, interaction: discord.Interaction):
        """Dọn dẹp linh khí tạp chất (__pycache__, .pyc) - Chỉ dành cho Tổ Sư"""
        if interaction.user.id not in self.bot.admin_ids:
            embed = txa_embed("🚫 Thiên Lam Cấm Chế", "Hậu bối to gan! Ngươi không có quyền hạn thi triển pháp thuật đại tẩy tủy này!", discord.Color.red())
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        
        await interaction.response.defer(ephemeral=True)
        
        count = 0
        cleaned_paths = []
        for root, dirs, files in os.walk("."):
            # Bỏ qua các thư mục không cần thiết
            if ".git" in dirs: dirs.remove(".git")
            if ".agent" in dirs: dirs.remove(".agent")
            
            for d in dirs:
                if d == "__pycache__":
                    full_path = os.path.join(root, d)
                    try:
                        shutil.rmtree(full_path)
                        count += 1
                        cleaned_paths.append(full_path)
                    except: pass
            
            for f in files:
                if f.endswith((".pyc", ".pyo")):
                    full_path = os.path.join(root, f)
                    try:
                        os.remove(full_path)
                        count += 1
                        cleaned_paths.append(full_path)
                    except: pass
        
        res_msg = f"Đã dọn dẹp `{count}` điểm linh khí tạp chất tàn dư.\n" + (", ".join([f"`{p}`" for p in cleaned_paths[:3]]) + ("..." if len(cleaned_paths) > 3 else ""))
        embed = txa_embed("🧹 Đại Tẩy Tủy Hoàn Tất", res_msg, discord.Color.green())
        await interaction.followup.send(embed=embed, ephemeral=True)
        rainbow_log(f"🧹 {interaction.user.name} đã quét sạch cache tại {len(cleaned_paths)} vị trí.")

async def setup(bot):
    await bot.add_cog(Admin(bot))
