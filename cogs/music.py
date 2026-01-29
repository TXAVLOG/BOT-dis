"""
Music Cog - Thiên Lam Tiên Nhạc Công Pháp
Enhanced music system with search selection, queue management, and real-time updates.
"""
import discord
import os
import random
import asyncio
import time
from discord import app_commands, Embed, Color
from discord.ext import commands, tasks
from yt_dlp import YoutubeDL
from typing import Optional, List
from core.helpers import rainbow_log, txa_embed, get_rank_info
from core.format import TXAFormat
from core.database import Database

# --- CONFIG ---
DOWNLOADS_DIR = os.path.join(os.getcwd(), "downloads")
os.makedirs(DOWNLOADS_DIR, exist_ok=True)
FFMPEG_OPTIONS = {
    "before_options": "-nostdin",
    "options": "-vn"
}


class SearchResultView(discord.ui.View):
    """View hiển thị kết quả tìm kiếm với các nút chọn và thumbnail"""
    def __init__(self, cog, results: List[dict], user_id: int, timeout=60):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.results = results
        self.user_id = user_id
        
        for i in range(len(results[:5])):
            btn = discord.ui.Button(
                label=f"{i+1}",
                style=discord.ButtonStyle.primary,
                custom_id=f"select_{i}"
            )
            btn.callback = self.get_callback(i)
            self.add_item(btn)
        
        cancel_btn = discord.ui.Button(label="❌ Xong", style=discord.ButtonStyle.secondary, custom_id="cancel")
        cancel_btn.callback = self.cancel_callback
        self.add_item(cancel_btn)
    
    def get_callback(self, index: int):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.user_id:
                return await interaction.response.send_message("Hậu bối không có quyền can thiệp vào tầm đạo của người khác!", ephemeral=True)
            
            selected = self.results[index]
            guild_id = interaction.guild_id
            
            vc = interaction.guild.voice_client
            if not vc:
                return await interaction.response.send_message("⚠️ Hiện tại không có Tiên Âm Điện nào được mở!", ephemeral=True)

            queue = self.cog.queues.get(guild_id, [])
            # Tránh lặp bài trong hàng chờ
            if any(q['url'] == selected['url'] for q in queue):
                return await interaction.response.send_message("⚠️ Tiên nhạc này đã có trong hàng chờ rồi!", ephemeral=True)
            
            # Tránh lặp bài đang phát
            meta = self.cog.current_meta.get(guild_id)
            if meta and meta['url'] == selected['url']:
                return await interaction.response.send_message("⚠️ Tiên nhạc này đang được xướng lên rồi!", ephemeral=True)

            item = {
                "url": selected['url'],
                "title": selected['title'],
                "requester": interaction.user.id,
                "channel_id": interaction.channel_id,
                "thumb": selected['thumbnail']
            }
            
            queue_pos = len(queue)
            self.cog.queues.setdefault(guild_id, []).append(item)
            
            # Cập nhật thông báo trong embed chính
            embeds = interaction.message.embeds.copy()
            if len(embeds) > 0:
                original_desc = embeds[0].description.split("\n")[-1] if "\n" in embeds[0].description else embeds[0].description
                if "tìm thấy" not in original_desc.lower(): 
                     original_desc = f"Tìm thấy {len(self.results)} linh tích tiên nhạc tại hạ giới. Hãy chọn một chương để khởi dẫn:"
                
                embeds[0].description = f"✅ **Đã triệu hồi:** `{TXAFormat.truncate(selected['title'], 40)}`\n📍 Vị trí: **#{queue_pos + 1}**\n\n{original_desc}"
                embeds[0].color = discord.Color.green()
            
            # Xóa embed của bài đã chọn khỏi danh sách hiển thị
            target_prefix = f"{index + 1}. "
            embeds_to_keep = [embeds[0]] # Giữ Main Embed
            for emp in embeds[1:]:
                if emp.title and emp.title.startswith(target_prefix):
                    continue # Bỏ qua embed đã chọn
                embeds_to_keep.append(emp)
            embeds = embeds_to_keep

            # Đổi màu nút đã chọn thành Xanh để đánh dấu
            for child in self.children:
                if isinstance(child, discord.ui.Button) and child.custom_id == f"select_{index}":
                    child.style = discord.ButtonStyle.success
                    child.disabled = True
            
            content = interaction.message.content
            if not vc.is_playing() and not vc.is_paused() and queue_pos == 0:
                asyncio.create_task(self.cog.play_next(guild_id, interaction.channel))
            else:
                content = selected['url']
            
            try:
                # Nếu chỉ còn mỗi Main Embed thì xóa View luôn (đã chọn hết)
                view = self if len(embeds) > 1 else None
                await interaction.response.edit_message(content=content, embeds=embeds, view=view)
                if not view: self.stop()
            except: pass
            
        return callback
    
    async def cancel_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("Hậu bối không có quyền can thiệp!", ephemeral=True)
        try:
            # Xóa luôn bảng kết quả khi bấm Xong
            await interaction.message.delete()
        except: pass
        self.stop()


class MusicControlView(discord.ui.View):
    """View điều khiển nhạc với các nút động và ghi nhớ trạng thái"""
    def __init__(self, cog, guild_id: int):
        super().__init__(timeout=None)
        self.cog = cog
        self.guild_id = guild_id
        
        # Cập nhật icon dựa trên trạng thái thực tế ngay khi khởi tạo
        vc = self.cog.voice_states.get(self.guild_id)
        if vc:
            if vc.is_paused():
                self.pause_play.emoji = "▶️"
            else:
                self.pause_play.emoji = "⏸️"
        
        loop_mode = self.cog.loops.get(self.guild_id, False)
        self.loop.style = discord.ButtonStyle.success if loop_mode else discord.ButtonStyle.secondary

    @discord.ui.button(emoji="⏸️", style=discord.ButtonStyle.primary, custom_id="pause_play")
    async def pause_play(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = self.cog.voice_states.get(self.guild_id)
        if not vc:
            embed = txa_embed("❌ Tiên Nhạc Lỗi", "Chưa có tiên nhạc nào đang vang lên!", Color.red())
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        
        meta = self.cog.current_meta.get(self.guild_id)
        if vc.is_playing():
            vc.pause()
            button.emoji = "▶️"
            if meta: meta['last_pause_time'] = time.time()
        elif vc.is_paused():
            vc.resume()
            button.emoji = "⏸️"
            if meta and meta.get('last_pause_time'):
                pause_duration = time.time() - meta['last_pause_time']
                meta['total_paused_time'] += pause_duration
                meta['last_pause_time'] = None
        
        await interaction.response.edit_message(view=self)
        await self.cog.update_now_playing_display(self.guild_id)

    @discord.ui.button(emoji="⏭️", style=discord.ButtonStyle.secondary, custom_id="skip")
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = self.cog.voice_states.get(self.guild_id)
        if vc:
            await interaction.response.defer()
            vc.stop()
            embed = txa_embed("⏭️ Chuyển Biến Tiên Âm", "Đang chuyển sang chương tiếp theo...", Color.blue())
            msg = await interaction.followup.send(embed=embed)
            self.cog.add_transient(self.guild_id, msg)
        else:
            embed = txa_embed("❌ Tiên Nhạc Lỗi", "Không có bài hát đang phát!", Color.red())
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(emoji="🔀", style=discord.ButtonStyle.secondary, custom_id="shuffle")
    async def shuffle(self, interaction: discord.Interaction, button: discord.ui.Button):
        queue = self.cog.queues.get(self.guild_id, [])
        if len(queue) < 2:
            embed = txa_embed("❌ Thao Tác Thất Bại", "Cần ít nhất 2 bài trong hàng chờ để xáo trộn!", Color.red())
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        
        random.shuffle(queue)
        self.cog.queues[self.guild_id] = queue
        embed = txa_embed("🔀 Tàng Kinh Các", "Đã xáo trộn thứ tự các tiên nhạc trong hàng chờ!", Color.green())
        await interaction.response.send_message(embed=embed, ephemeral=True)
        await self.cog.update_now_playing_display(self.guild_id)

    @discord.ui.button(emoji="🔁", style=discord.ButtonStyle.secondary, custom_id="loop")
    async def loop(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.cog.loops[self.guild_id] = not self.cog.loops.get(self.guild_id, False)
        loop_mode = self.cog.loops[self.guild_id]
        button.style = discord.ButtonStyle.success if loop_mode else discord.ButtonStyle.secondary
        await interaction.response.edit_message(view=self)
        await self.cog.update_now_playing_display(self.guild_id)

    @discord.ui.button(emoji="🛑", style=discord.ButtonStyle.danger, custom_id="stop")
    async def stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild_id = self.guild_id
        await self.cog.cleanup_music(guild_id)
        embed = txa_embed("🛑 Thu Hồi Tiên Nhạc", "Quy nguyên nhập định, Thiên Lam Điện trở lại thanh tịnh.", Color.red())
        await interaction.response.send_message(embed=embed, ephemeral=True)


class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db: Database = bot.db
        self.voice_states: dict[int, discord.VoiceClient] = {}
        self.queues: dict[int, list[dict]] = {}
        self.current_meta: dict[int, dict] = {}
        self.loops: dict[int, bool] = {}
        self.now_playing_msgs: dict[int, discord.Message] = {}
        self.transient_msgs: dict[int, list[discord.Message]] = {}
        self.cache_manifest: dict[str, str] = {} # {url: filepath}
        self.display_locks: dict[int, asyncio.Lock] = {}
        self.progress_updater.start()

    async def update_now_playing_display(self, guild_id: int):
        """Helper để cập nhật hoặc tạo mới tin nhắn Now Playing ngay lập tức"""
        if guild_id not in self.display_locks:
            self.display_locks[guild_id] = asyncio.Lock()
            
        async with self.display_locks[guild_id]:
            meta = self.current_meta.get(guild_id)
            if not meta: return
            
            vc = self.voice_states.get(guild_id)
            if not vc: return
            
            # Tính toán thời gian thực tế (trừ đi thời gian paused)
            now = time.time()
            elapsed = int(now - meta['start_time'] - meta['total_paused_time'])
            if vc.is_paused() and meta.get('last_pause_time'):
                elapsed -= int(now - meta['last_pause_time'])
                
            total = meta.get('duration') or 1
            elapsed = min(total, max(0, elapsed)) # Không vượt quá tổng
            
            progress = (elapsed / total * 100)
            bar = TXAFormat.progress_bar(min(100, progress), 12, "music")
            
            queue_count = len(self.queues.get(guild_id, []))
            is_paused = vc.is_paused()
            
            embed = txa_embed(
                "🎵 Thiên Lam Tiên Nhạc",
                f"**[{meta['title']}]({meta['url']})**",
                Color.orange() if is_paused else Color.purple()
            )
            if meta.get('thumb'): embed.set_thumbnail(url=meta['thumb'])
            
            # Tính toán XP: Bắt đầu từ 20, tăng sau 5s theo cấp số nhân nhẹ
            xp_earned = 0
            if elapsed >= 5:
                # Formula: 20 + (elapsed-5)^1.1 * 0.5
                xp_earned = int(20 + ((elapsed - 5) ** 1.1) * 0.5)
            
            status_icon = "⏸️" if is_paused else "▶️"
            embed.add_field(
                name=f"{status_icon} Linh Lực Quán Chú",
                value=f"`{bar}`\n`{TXAFormat.time(elapsed)}` / `{TXAFormat.time(total)}`",
                inline=False
            )
            embed.add_field(name="👤 Dẫn Khởi", value=f"<@{meta['requester']}>", inline=True)
            embed.add_field(name="📜 Chờ", value=f"`{queue_count}`", inline=True)
            embed.add_field(name="🔁", value="✅" if self.loops.get(guild_id) else "❌", inline=True)
            embed.add_field(name="✨ Tu Vi Tích Lũy", value=f"**+{xp_earned} XP**", inline=True)
            embed.set_footer(text="Thiên Lam Tông - Tiên Âm Công Pháp")
            
            view = MusicControlView(self, guild_id)
            last_msg = self.now_playing_msgs.get(guild_id)
            msg_content = meta['url']
            
            try:
                if last_msg:
                    # Kiểm tra xem tin nhắn có thực sự thuộc guild hiện tại không (tránh edit nhầm)
                    await last_msg.edit(content=msg_content, embed=embed, view=view)
                else:
                    channel = self.bot.get_channel(meta.get('channel_id'))
                    if channel:
                        # Gửi tin nhắn mới và lưu lại
                        new_msg = await channel.send(content=msg_content, embed=embed, view=view)
                        self.now_playing_msgs[guild_id] = new_msg
            except discord.NotFound:
                # Tin nhắn bị xóa, xóa khỏi cache để lần sau gửi mới
                self.now_playing_msgs.pop(guild_id, None)
            except Exception as e:
                rainbow_log(f"⚠️ Lỗi cập nhật display: {e}")
                self.now_playing_msgs.pop(guild_id, None)

    def interaction_check(self, interaction: discord.Interaction):
        if interaction.guild is None:
            return False
        if not self.bot.allowed_channel_ids:
            return True
        if interaction.channel_id not in self.bot.allowed_channel_ids:
            asyncio.create_task(interaction.response.send_message(
                "⛩️ **Cấm Chế:** Tiên nhạc này chỉ có thể vang lên tại địa giới được phép của Thiên Lam Tông!", 
                ephemeral=True
            ))
            return False
        return True

    def cog_unload(self):
        self.progress_updater.cancel()

    def add_transient(self, guild_id: int, msg: discord.Message):
        """Lưu lại tin nhắn để dọn dẹp sau này"""
        if guild_id not in self.transient_msgs:
            self.transient_msgs[guild_id] = []
        self.transient_msgs[guild_id].append(msg)

    async def cleanup_music(self, guild_id: int):
        """Dọn dẹp toàn bộ rác rưởi sau khi dừng nhạc"""
        vc = self.voice_states.get(guild_id)
        if vc:
            try: await vc.disconnect()
            except: pass
            self.voice_states.pop(guild_id, None)
        
        self.queues[guild_id] = []
        self.current_meta.pop(guild_id, None)
        self.loops.pop(guild_id, None)
        
        # Xóa tin nhắn Now Playing
        if guild_id in self.now_playing_msgs:
            try: await self.now_playing_msgs[guild_id].delete()
            except: pass
            self.now_playing_msgs.pop(guild_id, None)
            
        # Xóa các tin nhắn tạm (search, status...)
        msgs = self.transient_msgs.pop(guild_id, [])
        for m in msgs:
            try: await m.delete()
            except: pass
        
        # Cộng XP tích lũy từ bài cuối cùng nếu có
        if guild_id in self.current_meta:
            meta = self.current_meta[guild_id]
            elapsed = int(time.time() - meta['start_time'] - meta['total_paused_time'])
            if elapsed >= 5:
                xp = int(20 + ((elapsed - 5) ** 1.1) * 0.5)
                await self.reward_music_xp(meta['requester'], xp)
        self.current_meta.pop(guild_id, None)

    def cleanup_cache(self):
        """Xóa bớt file trong cache để giải phóng dung lượng"""
        try:
            files = [os.path.join(DOWNLOADS_DIR, f) for f in os.listdir(DOWNLOADS_DIR) if f.endswith('.mp3')]
            # Sắp xếp theo thời gian (cũ nhất trước)
            files.sort(key=os.path.getmtime)
            
            deleted_count = 0
            # Giữ lại 5 file mới nhất, xóa phần còn lại
            if len(files) > 5:
                for f in files[:-5]:
                    try: 
                        os.remove(f)
                        deleted_count += 1
                    except: pass
            
            rainbow_log(f"🧹 Đã dọn dẹp {deleted_count} file nhạc cũ trong cache.")
        except Exception as e:
            rainbow_log(f"⚠️ Lỗi khi dọn dẹp cache: {e}")

    async def reward_music_xp(self, user_id: int, xp: int):
        """Cộng XP cho đạo hữu sau khi nghe nhạc"""
        uid = str(user_id)
        user = await self.db.get_user(uid)
        if user:
            new_exp = user['exp'] + xp
            rainbow_log(f"✨ [Tu Vi] {user['name']} nhận {xp} XP từ việc nghe nhạc.")
            await self.db.update_user(uid, exp=new_exp)
            # Check level up (handled by database or separate logic, let's keep it simple here)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """Dọn dẹp nếu bot bị kick hoặc rời channel"""
        if member.id == self.bot.user.id and before.channel and not after.channel:
            await self.cleanup_music(before.channel.guild.id)

    async def check_access(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id in self.bot.admin_ids:
            return True
        user = await self.db.get_user(str(interaction.user.id))
        if not user:
            embed = txa_embed("⛩️ Thiên Lam Cấm Chế", "Ngươi chưa ghi danh nhập môn! Hãy dùng `/start` để khai mở linh căn.", discord.Color.red())
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return False
        
        # Yêu cầu: Cảnh giới Hóa Thần (Tầng 50+) + Streak 2 ngày
        req_layer = 50  # Hóa Thần
        req_streak = 2
        rank_name, _ = get_rank_info(req_layer)
        
        if user['layer'] < req_layer:
            rainbow_log(f"🚫 [Music] {interaction.user.name} (Tầng {user['layer']}) bị chặn: Chưa đạt {rank_name}")
            embed = txa_embed(
                "🚫 Tu Vi Bất Túc", 
                f"Cần đạt cảnh giới **{rank_name}** (Tầng {req_layer}+) để khai mở tiên nhạc!\n"
                f"Tu vi hiện tại: Tầng **{user['layer']}**", 
                discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return False
        
        if user['daily_streak'] < req_streak:
            rainbow_log(f"🚫 [Music] {interaction.user.name} (Streak {user['daily_streak']}) bị chặn: Chưa đủ đạo tâm")
            embed = txa_embed(
                "🚫 Đạo Tâm Chưa Vững", 
                f"Cần duy trì **điểm danh {req_streak} ngày liên tục** để chứng minh đạo tâm!\n"
                f"Streak hiện tại: **{user['daily_streak']} ngày**", 
                discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return False
        
        rainbow_log(f"✅ [Music] {interaction.user.name} ({rank_name} Tầng {user['layer']}, Streak {user['daily_streak']}) - Được phép")
        return True

    async def search_youtube(self, query: str, max_results: int = 5) -> List[dict]:
        """Tìm kiếm YouTube và trả về danh sách kết quả"""
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": True,
            "default_search": "ytsearch",
            "nocheckcertificate": True,
            "ignoreerrors": False,
            "logtostderr": False,
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Referer": "https://www.youtube.com/",
            },
            "extractor_args": {
                "youtube": {
                    "player_client": ["android", "ios"]
                }
            }
        }
        
        loop = asyncio.get_running_loop()
        with YoutubeDL(ydl_opts) as ydl:
            info = await loop.run_in_executor(None, lambda: ydl.extract_info(f"ytsearch{max_results}:{query}", download=False))
        
        results = []
        for entry in info.get('entries', [])[:max_results]:
            url = entry.get('url') or f"https://www.youtube.com/watch?v={entry.get('id')}"
            results.append({
                'url': url,
                'title': entry.get('title', 'Không rõ tên'),
                'duration': entry.get('duration'),
                'thumbnail': entry.get('thumbnail') or entry.get('thumbnails', [{}])[0].get('url'),
                'uploader': entry.get('uploader', 'Không rõ')
            })
        return results

    async def download_media(self, url: str, status_msg: discord.Message = None):
        """Tải nhạc với cập nhật tiến trình và Caching"""
        # Kiểm tra Cache
        if url in self.cache_manifest:
            cached_path = self.cache_manifest[url]
            if os.path.exists(cached_path):
                rainbow_log(f"⚡ [Cache Hit] Khai thác linh khí sẵn có cho: {url}")
                # Lấy info nhanh để có title/thumb
                ydl_opts = {"quiet": True, "no_warnings": True}
                with YoutubeDL(ydl_opts) as ydl:
                    info = await asyncio.get_running_loop().run_in_executor(None, lambda: ydl.extract_info(url, download=False))
                return cached_path, info.get('title'), info.get('duration'), info.get('thumbnail')

        rainbow_log(f"📥 [Cache Miss] Đang triệu hồi linh khí mới từ hạ giới: {url}")
        progress_data = {'percent': 0, 'speed': None, 'eta': None}
        
        def hook(d):
            if d['status'] == 'downloading':
                total = d.get('total_bytes') or d.get('total_bytes_estimate', 1)
                downloaded = d.get('downloaded_bytes', 0)
                progress_data['percent'] = (downloaded / total) * 100
                progress_data['speed'] = d.get('speed')
                progress_data['eta'] = d.get('eta')

        path = os.path.join(DOWNLOADS_DIR, f"{int(time.time())}.mp3")
        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": path.replace(".mp3", ""),
            "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}],
            "progress_hooks": [hook],
            "quiet": True,
            "nocheckcertificate": True,
            "ignoreerrors": False,
            "logtostderr": False,
            "no_warnings": True,
            "default_search": "auto",
            "source_address": "0.0.0.0",
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Referer": "https://www.youtube.com/",
            },
            "extractor_args": {
                "youtube": {
                    "player_client": ["android", "ios"]
                }
            }
        }
        
        # Background task để cập nhật tiến trình
        update_task = None
        if status_msg:
            async def update_progress():
                last_update = 0
                while True:
                    await asyncio.sleep(2)
                    if progress_data['percent'] >= 100 or progress_data['percent'] - last_update >= 15:
                        bar = TXAFormat.progress_bar(progress_data['percent'], 15, "music")
                        speed_str = TXAFormat.data_speed(progress_data['speed'])
                        eta_str = TXAFormat.remaining_detail(progress_data['eta']) if progress_data['eta'] else "Không xác định"
                        
                        embed = txa_embed(
                            "📥 Đang Triệu Hồi Tiên Nhạc...",
                            f"`{bar}` **{progress_data['percent']:.1f}%**\n\n⚡ Tốc độ: `{speed_str}`\n⏱️ Còn lại: `{eta_str}`",
                            Color.blue()
                        )
                        try:
                            await status_msg.edit(embed=embed)
                        except:
                            pass
                        last_update = progress_data['percent']
                    
                    if progress_data['percent'] >= 100:
                        break
            
            update_task = asyncio.create_task(update_progress())
        
        loop = asyncio.get_running_loop()
        with YoutubeDL(ydl_opts) as ydl:
            info = await loop.run_in_executor(None, lambda: ydl.extract_info(url, download=True))
        
        if update_task:
            update_task.cancel()
        
        # Lưu vào cache
        actual_path = path if os.path.exists(path) else f"{path}.mp3"
        self.cache_manifest[url] = actual_path
        
        return actual_path, info.get('title'), info.get('duration'), info.get('thumbnail')

    async def play_next(self, guild_id: int, channel: discord.TextChannel = None):
        """Phát bài tiếp theo trong hàng chờ"""
        queue = self.queues.get(guild_id, [])
        if not queue:
            # Trước khi hết hàng chờ, cộng XP cho bài vừa kết thúc
            if guild_id in self.current_meta:
                meta = self.current_meta[guild_id]
                elapsed = int(time.time() - meta['start_time'] - meta['total_paused_time'])
                if elapsed >= 5:
                    xp = int(20 + ((elapsed - 5) ** 1.1) * 0.5)
                    await self.reward_music_xp(meta['requester'], xp)
            
            self.current_meta.pop(guild_id, None)
            # Xóa now playing message
            if guild_id in self.now_playing_msgs:
                try:
                    embed = txa_embed("🎵 Tiên Nhạc Kết Thúc", "Hàng chờ đã cạn, hãy thêm bài mới!", Color.orange())
                    await self.now_playing_msgs[guild_id].edit(embed=embed, view=None)
                except:
                    pass
            return

        vc = self.voice_states.get(guild_id)
        if not vc or not vc.is_connected():
            return

        # Cộng XP cho bài vừa kết thúc trước khi chuyển sang bài mới
        if guild_id in self.current_meta:
            meta = self.current_meta[guild_id]
            elapsed = int(time.time() - meta['start_time'] - meta['total_paused_time'])
            if elapsed >= 5:
                xp = int(20 + ((elapsed - 5) ** 1.1) * 0.5)
                await self.reward_music_xp(meta['requester'], xp)

        item = queue.pop(0)
        self.queues[guild_id] = queue
        
        # Gửi tin nhắn đang tải
        target_channel = channel or self.bot.get_channel(item.get('channel_id'))
        status_msg = None
        if target_channel:
            embed = txa_embed("📥 Đang Triệu Hồi Tiên Nhạc...", f"**{item['title']}**", Color.blue())
            try:
                status_msg = await target_channel.send(embed=embed)
                self.add_transient(guild_id, status_msg)
            except:
                pass
        
        try:
            path, title, duration, thumb = await self.download_media(item['url'], status_msg)
            source = discord.FFmpegPCMAudio(path, **FFMPEG_OPTIONS)
            
            def after(error):
                if self.loops.get(guild_id):
                    self.queues[guild_id].insert(0, item)
                asyncio.run_coroutine_threadsafe(self.play_next(guild_id, target_channel), self.bot.loop)
                # KHÔNG xóa file nữa để giữ cache
                # if os.path.exists(path): ...

            vc.play(source, after=after)
            self.current_meta[guild_id] = {
                "title": title or item['title'],
                "url": item['url'],
                "duration": duration,
                "thumb": thumb,
                "start_time": time.time(),
                "last_pause_time": None,
                "total_paused_time": 0,
                "requester": item['requester'],
                "channel_id": item.get('channel_id')
            }
            
            # Xóa tin nhắn tải và dọn dẹp các thông báo tạm (Skip msg, Status msg...)
            # NHƯNG KHÔNG XÓA BẢNG KẾT QUẢ TÌM KIẾM (Search Result View) để user chọn tiếp
            if status_msg:
                try: await status_msg.delete()
                except: pass
            
            if guild_id in self.transient_msgs:
                kept_msgs = []
                for msg in self.transient_msgs[guild_id]:
                    try:
                        # Nếu là status msg hoặc skip msg thì xóa
                        # Check nội dung hoặc embed title để quyết định
                        should_delete = False
                        if msg.id == (status_msg.id if status_msg else 0):
                            should_delete = True
                        elif msg.embeds and "Chuyển Biến Tiên Âm" in str(msg.embeds[0].title):
                            should_delete = True
                        
                        # Nếu không phải bảng tìm kiếm thì xóa
                        is_search_result = False
                        if msg.embeds and "Kết Quả Tầm Đạo" in str(msg.embeds[0].title):
                            is_search_result = True
                        
                        if should_delete:
                            await msg.delete()
                        elif is_search_result:
                            kept_msgs.append(msg)
                        else:
                            # Những msg khác (nếu có) cứ xóa cho sạch
                            await msg.delete()
                    except: pass # Msg đã bị xóa tay hoặc lỗi
                self.transient_msgs[guild_id] = kept_msgs
            
            # Khởi tạo Now Playing Message nếu chưa có
            await self.update_now_playing_display(guild_id)
            
        except Exception as e:
            rainbow_log(f"❌ Lỗi phát nhạc: {e}")
            # Nếu lỗi disk full, thử dọn dẹp cache ngay
            if "No space left" in str(e):
                self.cleanup_cache()
            
            if status_msg:
                try:
                    embed = txa_embed("❌ Lỗi Triệu Hồi", f"Không thể phát bài: **{item['title']}**\n`{str(e)}`", Color.red())
                    await status_msg.edit(embed=embed)
                except:
                    pass
            await self.play_next(guild_id, target_channel)

    @app_commands.command(name="ytplay", description="Tìm kiếm và phát tiên nhạc từ YouTube")
    @app_commands.describe(query="Tên bài hát hoặc URL YouTube")
    async def ytplay(self, interaction: discord.Interaction, query: str):
        if not await self.check_access(interaction):
            return
        
        await interaction.response.defer()
        guild_id = interaction.guild_id
        
        # Kiểm tra voice channel
        vc = interaction.guild.voice_client
        if not vc:
            if not interaction.user.voice:
                embed = txa_embed(
                    "⛩️ Thiên Lam Cấm Chế: Tiên Âm Điện",
                    "Đạo hữu chưa gia nhập **Tiên Âm Điện (Voice Channel)**, làm sao có thể thưởng thức tiên nhạc?",
                    discord.Color.red()
                )
                embed.set_footer(text="Hãy bước vào linh địa âm nhạc trước khi thi triển pháp bảo.")
                return await interaction.followup.send(embed=embed, ephemeral=True)
            vc = await interaction.user.voice.channel.connect()
            self.voice_states[guild_id] = vc
        
        # Nếu là URL, phát trực tiếp
        if query.startswith("http"):
            # Kiểm tra lặp bài trong hàng chờ
            queue = self.queues.get(guild_id, [])
            if any(q['url'] == query for q in queue):
                embed = txa_embed("⚠️ Tàng Kinh Các", "Tiên nhạc này vốn đã nằm trong hàng chờ rồi!", discord.Color.orange())
                return await interaction.followup.send(embed=embed)
                
            # Kiểm tra lặp bài đang phát
            meta = self.current_meta.get(guild_id)
            if meta and meta['url'] == query:
                embed = txa_embed("⚠️ Tàng Kinh Các", "Tiên nhạc này đang được xướng lên rồi!", discord.Color.orange())
                return await interaction.followup.send(embed=embed)

            item = {"url": query, "title": "Tiên Nhạc từ URL", "requester": interaction.user.id, "channel_id": interaction.channel_id}
            if vc.is_playing() or vc.is_paused():
                self.queues.setdefault(guild_id, []).append(item)
                embed = txa_embed(
                    "➕ Tàng Kinh Các", 
                    f"Đã lưu chương nhạc vào hàng chờ:\n**{TXAFormat.truncate(query, 50)}**",
                    discord.Color.blue()
                )
                await interaction.followup.send(embed=embed)
            else:
                self.queues.setdefault(guild_id, []).append(item)
                embed = txa_embed(
                    "⏳ Triệu Hồi Tiên Nhạc",
                    "Đang khởi dẫn chương nhạc từ hạ giới...",
                    discord.Color.gold()
                )
                await interaction.followup.send(embed=embed)
                await self.play_next(guild_id, interaction.channel)
            return
        
        # Tìm kiếm
        results = await self.search_youtube(query)
        if not results:
            embed = txa_embed(
                "❌ Linh Tích Không Tìm Thấy",
                f"Thần thức quét qua hạ giới nhưng không tìm thấy tiên nhạc nào liên quan đến: **{query}**",
                discord.Color.red()
            )
            return await interaction.followup.send(embed=embed)
        
        # Dọn dẹp tuyệt đối các kết quả cũ của guild này trước khi hiện mới
        old_msgs = self.transient_msgs.pop(guild_id, [])
        for old_m in old_msgs:
            try: await old_m.delete()
            except: pass
        
        # Tạo danh sách embeds cho kết quả tìm kiếm
        main_embed = txa_embed(
            "🔍 Kết Quả Tầm Đạo Tiên Nhạc",
            f"Tìm thấy {len(results)} linh tích tiên nhạc tại hạ giới. Hãy chọn một chương để khởi dẫn:",
            Color.blue()
        )
        
        result_embeds = [main_embed]
        for i, r in enumerate(results[:5]):
            duration_str = TXAFormat.time(r['duration']) if r['duration'] else "--:--"
            emb = txa_embed(
                f"{i+1}. {r['title']}", 
                f"⏱️ `{duration_str}` • 👤 `{r['uploader']}`\n🔗 [Xem trên YouTube]({r['url']})", 
                Color.dark_grey()
            )
            if r.get('thumbnail'):
                emb.set_thumbnail(url=r['thumbnail'])
            result_embeds.append(emb)
        
        view = SearchResultView(self, results, interaction.user.id)
        msg = await interaction.followup.send(embeds=result_embeds, view=view)
        self.add_transient(guild_id, msg)
        # Không đợi view.wait() nữa vì view tự xử lý logic callback

    @app_commands.command(name="ytnow", description="Xem thông tin bài đang phát")
    async def ytnow(self, interaction: discord.Interaction):
        guild_id = interaction.guild_id
        meta = self.current_meta.get(guild_id)
        
        if not meta:
            embed = txa_embed("❌ Tiên Nhạc Lỗi", "Chưa có tiên nhạc nào đang vang lên!", Color.red())
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        
        await interaction.response.defer(ephemeral=True)
        
        vc = self.voice_states.get(guild_id)
        is_paused = vc.is_paused() if vc else False
        
        elapsed = int(time.time() - meta['start_time'])
        total = meta.get('duration') or 0
        progress = (elapsed / total * 100) if total > 0 else 0
        bar = TXAFormat.progress_bar(min(100, progress), 15, "music")
        
        queue_count = len(self.queues.get(guild_id, []))
        
        embed = txa_embed(
            "🎵 Thiên Lam Tiên Nhạc",
            f"**[{meta['title']}]({meta['url']})**",
            Color.purple()
        )
        
        if meta.get('thumb'):
            embed.set_thumbnail(url=meta['thumb'])
        
        embed.add_field(
            name="⏱️ Tiến Độ",
            value=f"`{bar}`\n`{TXAFormat.time(elapsed)}` / `{TXAFormat.time(total)}`",
            inline=False
        )
        embed.add_field(name="👤 Dẫn Khởi Bởi", value=f"<@{meta['requester']}>", inline=True)
        embed.add_field(name="📜 Hàng Chờ", value=f"**{queue_count}** bài", inline=True)
        embed.add_field(name="🔁 Chu Kỳ", value="Khai mở" if self.loops.get(guild_id) else "Đóng lại", inline=True)
        embed.add_field(name="⏸️ Trạng Thái", value="Tạm dừng" if is_paused else "Đang phát", inline=True)
        embed.set_footer(text="Thiên Lam Tông - Tiên Âm Công Pháp")
        
        view = MusicControlView(self, guild_id)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    @app_commands.command(name="ytqueue", description="Xem danh sách hàng chờ")
    async def ytqueue(self, interaction: discord.Interaction):
        guild_id = interaction.guild_id
        queue = self.queues.get(guild_id, [])
        
        if not queue:
            embed = txa_embed("📭 Tàng Kinh Các Trống", "Hãy thêm bài mới bằng `/ytplay` để khai mở tiên nhạc!", Color.orange())
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        
        await interaction.response.defer(ephemeral=True)
        
        desc = ""
        total_duration = 0
        for i, item in enumerate(queue[:15]):
            desc += f"**{i+1}.** {TXAFormat.truncate(item['title'], 40)}\n└ 👤 <@{item['requester']}>\n"
            if item.get('duration'):
                total_duration += item['duration']
        
        if len(queue) > 15:
            desc += f"\n*...và {len(queue) - 15} bài khác*"
        
        embed = txa_embed(
            f"📜 Tàng Kinh Các - Hàng Chờ ({len(queue)} bài)",
            desc,
            Color.blue()
        )
        
        if total_duration > 0:
            embed.add_field(name="⏱️ Tổng Thời Lượng (ước tính)", value=TXAFormat.duration_detail(total_duration))
        
        embed.set_footer(text="Dùng /ytplaynow [stt] để phát ngay một bài")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="ytclear", description="Xóa toàn bộ hàng chờ")
    async def ytclear(self, interaction: discord.Interaction):
        guild_id = interaction.guild_id
        queue = self.queues.get(guild_id, [])
        
        if not queue:
            embed = txa_embed("📭 Tàng Kinh Các Trống", "Tàng Kinh Các vốn đã thanh tịnh, không còn tạp âm.", Color.orange())
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        
        count = len(queue)
        self.queues[guild_id] = []
        embed = txa_embed("🧹 Thanh Lọc Tàng Kinh Các", f"Đã giải phóng `{count}` chương tiên nhạc khỏi hàng chờ.", Color.green())
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="ytplaynow", description="Phát ngay một bài trong hàng chờ")
    @app_commands.describe(position="Vị trí bài hát trong hàng chờ (1, 2, 3...)")
    async def ytplaynow(self, interaction: discord.Interaction, position: int):
        guild_id = interaction.guild_id
        queue = self.queues.get(guild_id, [])
        
        if not queue:
            embed = txa_embed("📭 Tàng Kinh Các Trống", "Không có tiên nhạc nào để thi triển!", Color.red())
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        
        if position < 1 or position > len(queue):
            embed = txa_embed("❌ Vị Trí Bất Hợp Lệ", f"Hãy chọn từ 1 đến {len(queue)} trong Tàng Kinh Các.", Color.red())
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        
        # Di chuyển bài được chọn lên đầu
        item = queue.pop(position - 1)
        queue.insert(0, item)
        self.queues[guild_id] = queue
        
        # Dừng bài hiện tại để chuyển sang bài được chọn
        vc = self.voice_states.get(guild_id)
        if vc and (vc.is_playing() or vc.is_paused()):
            vc.stop()
            embed = txa_embed("⚡ Chuyển Biến Tiên Âm", f"Đang khởi dẫn chương nhạc: **{item['title']}**", Color.blue())
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            embed = txa_embed("▶️ Khởi Động Tiên Nhạc", f"Bắt đầu dẫn dắt linh hồn theo: **{item['title']}**", Color.green())
            await interaction.response.send_message(embed=embed, ephemeral=True)
            await self.play_next(guild_id, interaction.channel)

    @ytplaynow.autocomplete("position")
    async def position_autocomplete(self, interaction: discord.Interaction, current: str):
        guild_id = interaction.guild_id
        queue = self.queues.get(guild_id, [])
        
        if not queue:
            return []
        
        choices = []
        for i, item in enumerate(queue[:25]):
            label = f"{i+1}. {TXAFormat.truncate(item['title'], 50)}"
            if current.lower() in label.lower() or current == str(i+1):
                choices.append(app_commands.Choice(name=label, value=i+1))
        
        return choices[:25]

    @app_commands.command(name="ytstop", description="Dừng nhạc và dọn dẹp toàn bộ rác rưởi")
    async def ytstop(self, interaction: discord.Interaction):
        await self.cleanup_music(interaction.guild_id)
        embed = txa_embed("🛑 Thu Hồi Tiên Nhạc", "Đã thu hồi toàn bộ pháp bảo âm nhạc, Thiên Lam Điện trở lại thanh tịnh.", Color.red())
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @tasks.loop(seconds=2)
    async def progress_updater(self):
        """Cập nhật embed now playing theo thời gian thực (Loop mỗi 2 giây)"""
        for guild_id in list(self.current_meta.keys()):
            await self.update_now_playing_display(guild_id)
        
        # Kiểm tra dọn dẹp tin nhắn tàng dư (summoning msgs đã xóa nhưng còn trong danh sách)
        for gid in list(self.transient_msgs.keys()):
            self.transient_msgs[gid] = [m for m in self.transient_msgs[gid] if m.id] # Simple filter

    @progress_updater.before_loop
    async def before_progress_updater(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(Music(bot))
