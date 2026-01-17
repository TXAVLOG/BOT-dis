import random
import asyncio
import discord
import time
from core.helpers import ask_ancestor, txa_embed, rainbow_log
from core.game_data import CultivationData

class CombatSystem:
    def __init__(self, bot, player1, player2, p1_data, p2_data):
        self.bot = bot
        self.p1 = player1 # discord.Member
        self.p2 = player2 # discord.Member
        self.p1_data = p1_data # DB Row
        self.p2_data = p2_data # DB Row
        
        # Calculate Stats based on Layer
        self.p1_hp = self.p1_data['layer'] * 100 + 500
        self.p2_hp = self.p2_data['layer'] * 100 + 500
        self.p1_max_hp = self.p1_hp
        self.p2_max_hp = self.p2_hp
        
        self.p1_atk = self.p1_data['layer'] * 10 + 50
        self.p2_atk = self.p2_data['layer'] * 10 + 50
        
        # Apply items/buffs if any (Kiếm rỉ sét...) - Kiểm tra hạn dùng
        now = time.time()
        if any(i['id'] == 'kiem_ri_set' and i.get('expiry', 0) > now for i in self.p1_data['inventory']):
            self.p1_atk *= 2
        if any(i['id'] == 'kiem_ri_set' and i.get('expiry', 0) > now for i in self.p2_data['inventory']):
            self.p2_atk *= 2

        self.turn = 1
        self.history = []
        rainbow_log(f"⚔️ [Combat] Trận đấu khởi tạo: {self.p1.display_name} vs {self.p2.display_name}")
        rainbow_log(f"   - {self.p1.display_name}: HP {self.p1_max_hp}, ATK {self.p1_atk}")
        rainbow_log(f"   - {self.p2.display_name}: HP {self.p2_max_hp}, ATK {self.p2_atk}")

    async def get_ai_description(self, attacker_name, defender_name, damage, is_last=False):
        prompt = (
            f"Miêu tả một hiệp đấu tu tiên giữa {attacker_name} và {defender_name}. "
            f"{attacker_name} tấn công gây {damage} sát thương. "
            f"Phong cách: Hoành tráng, kiếm hiệp, huyền ảo. "
            f"Yêu cầu: Viết 1 câu văn ngắn gọn nhưng khí thế. "
        )
        if is_last:
            prompt += f"Đây là đòn kết liễu khiến {defender_name} gục ngã."
        
        try:
            res = await ask_ancestor("Nhà văn kiếm hiệp ba đời.", prompt)
            if res: return res
        except:
            pass
        
        # Fallback
        return random.choice(CultivationData.COMBAT_NARRATIVES).format(a=attacker_name, b=defender_name)

    def get_status_bar(self, hp, max_hp):
        pct = max(0, hp / max_hp)
        length = 10
        filled = int(length * pct)
        return "❤️" * filled + "🖤" * (length - filled)

    async def start_battle(self, interaction: discord.Interaction):
        embed = txa_embed(
            "⚔️ ĐẤU PHÁP ĐÀI", 
            f"Cuộc so tài giữa **{self.p1.display_name}** và **{self.p2.display_name}** bắt đầu!",
            discord.Color.gold()
        )
        embed.add_field(name=f"🛡️ {self.p1.display_name}", value=f"HP: {self.p1_hp}/{self.p1_max_hp}\n{self.get_status_bar(self.p1_hp, self.p1_max_hp)}", inline=True)
        embed.add_field(name=f"🛡️ {self.p2.display_name}", value=f"HP: {self.p2_hp}/{self.p2_max_hp}\n{self.get_status_bar(self.p2_hp, self.p2_max_hp)}", inline=True)
        
        await interaction.response.send_message(embed=embed)
        msg = await interaction.original_response()

        while self.p1_hp > 0 and self.p2_hp > 0:
            await asyncio.sleep(3) # Wait for dramatic effect
            
            attacker, defender = (self.p1, self.p2) if self.turn % 2 != 0 else (self.p2, self.p1)
            atk_val = self.p1_atk if self.turn % 2 != 0 else self.p2_atk
            
            # Random dmg variance
            dmg = int(atk_val * random.uniform(0.8, 1.2))
            
            if self.turn % 2 != 0:
                self.p2_hp -= dmg
                curr_defender_hp = self.p2_hp
            else:
                self.p1_hp -= dmg
                curr_defender_hp = self.p1_hp
                
            is_last = curr_defender_hp <= 0
            desc = await self.get_ai_description(attacker.display_name, defender.display_name, dmg, is_last)
            
            # Log to console
            rainbow_log(f"[Combat] Hiệp {self.turn}: {attacker.display_name} -> {defender.display_name} ({dmg} dmg). HP còn: {curr_defender_hp}")

            # Update Embed
            embed = txa_embed(
                "⚔️ ĐẤU PHÁP ĐÀI", 
                f"**Hiệp {self.turn}**\n> {desc}",
                discord.Color.red() if is_last else discord.Color.orange()
            )
            
            # P1 Info
            p1_buffs = []
            if any(i['id'] == 'kiem_ri_set' and i.get('expiry', 0) > time.time() for i in self.p1_data['inventory']):
                p1_buffs.append("🗡️ Kiếm Rỉ Sét (ATK x2)")
            
            p1_status = f"HP: {max(0, self.p1_hp)}/{self.p1_max_hp}\n{self.get_status_bar(self.p1_hp, self.p1_max_hp)}"
            if p1_buffs: p1_status += f"\nActive: {', '.join(p1_buffs)}"
            
            # P2 Info
            p2_buffs = []
            if any(i['id'] == 'kiem_ri_set' and i.get('expiry', 0) > time.time() for i in self.p2_data['inventory']):
                p2_buffs.append("🗡️ Kiếm Rỉ Sét (ATK x2)")
            
            p2_status = f"HP: {max(0, self.p2_hp)}/{self.p2_max_hp}\n{self.get_status_bar(self.p2_hp, self.p2_max_hp)}"
            if p2_buffs: p2_status += f"\nActive: {', '.join(p2_buffs)}"

            embed.add_field(name=f"🛡️ {self.p1.display_name}", value=p1_status, inline=True)
            embed.add_field(name=f"🛡️ {self.p2.display_name}", value=p2_status, inline=True)
            
            await msg.edit(embed=embed)
            
            if is_last: break
            self.turn += 1

        winner = self.p1 if self.p1_hp > 0 else self.p2
        loser = self.p2 if self.p1_hp > 0 else self.p1
        
        # Reward: Winner gets Spirit Stones
        stones_win = random.randint(100, 300)
        
        # Check Winner Buffs (x3 Stones)
        winner_data = self.p1_data if winner == self.p1 else self.p2_data
        buffs = winner_data.get('buffs', {})
        is_x3 = buffs.get('stone_x3', 0) > time.time()
        
        if is_x3:
            stones_win *= 3
        
        # Update Database
        await self.bot.db.update_user(str(winner.id), spirit_stones=winner_data['spirit_stones'] + stones_win)
        rainbow_log(f"🏆 [Combat] {winner.display_name} thắng! Nhận {stones_win} 💎. Sau {self.turn} hiệp.")
        
        final_embed = txa_embed(
            "🏆 KẾT QUẢ ĐẤU PHÁP",
            f"**{winner.display_name}** đã giành chiến thắng sau {self.turn} hiệp đấu!\n"
            f"📉 **{loser.display_name}** đã kiệt sức và xin hàng.\n\n"
            f"💰 Phần thưởng: **{stones_win} Linh Thạch**{ ' (🎰 x3)' if is_x3 else ''}",
            discord.Color.gold()
        )
        await msg.reply(embed=final_embed)
