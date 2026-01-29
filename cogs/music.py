"""
Music Cog - Thiên Lam Tiên Nhạc Công Pháp
Enhanced music system with search selection, queue management, and real-time updates.
"""
import discord
import os
import random
import asyncio
import time
from typing import List
from discord import app_commands, Embed, Color
from discord.ext import commands, tasks
from pytubefix import YouTube, Search
from pytubefix.cli import on_progress
from core.helpers import rainbow_log, txa_embed
from core.format import TXAFormat

DOWNLOADS_DIR = "downloads"
# Optimization for playing local files (no stream options needed)
FFMPEG_OPTIONS = {
    'options': '-vn'
}

if not os.path.exists(DOWNLOADS_DIR):
    os.makedirs(DOWNLOADS_DIR)

class SearchResultView(discord.ui.View):
    def __init__(self, cog, results, user_id):
        super().__init__(timeout=60)
        self.cog = cog
        self.results = results
        self.user_id = user_id
        
        # Create Select Menu
        options = []
        for i, res in enumerate(results[:25]): # Max 25 choices
            options.append(discord.SelectOption(
                label=f"{i+1}. {res['title'][:90]}",
                description=f"Thời lượng: {TXAFormat.time(res['duration']) if res.get('duration') else 'N/A'}",
                value=str(i)
            ))
            
        select = discord.ui.Select(placeholder="📜 Chọn tiên nhạc để khai mở...", options=options)
        select.callback = self.select_callback
        self.add_item(select)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("⚠️ Đạo hữu không phải là người triệu hồi lệnh này!", ephemeral=True)
            return False
        return True

    async def select_callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        select = self.children[0]
        selected_index = int(select.values[0])
        selected_item = self.results[selected_index]
        
        # Construct item for queue
        item = {
            "url": selected_item['url'],
            "title": selected_item['title'],
            "requester": interaction.user.id,
            "channel_id": interaction.channel_id,
            "duration": selected_item['duration']
        }
        
        guild_id = interaction.guild_id
        self.cog.queues.setdefault(guild_id, []).append(item)
        
        # Check if playing
        vc = self.cog.voice_states.get(guild_id)
        if vc and (vc.is_playing() or vc.is_paused()):
            embed = txa_embed(
                "➕ Tàng Kinh Các", 
                f"Đã thêm vào hàng chờ:\n**{selected_item['title']}**", 
                Color.blue()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            embed = txa_embed(
                "⏳ Triệu Hồi Tiên Nhạc", 
                f"Đang chuẩn bị thi triển: **{selected_item['title']}**", 
                Color.gold()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            await self.cog.play_next(guild_id, interaction.channel)

class MusicControlView(discord.ui.View):
    def __init__(self, cog, guild_id):
        super().__init__(timeout=None)
        self.cog = cog
        self.guild_id = guild_id

    @discord.ui.button(emoji="⏯️", style=discord.ButtonStyle.primary)
    async def pause_resume(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = self.cog.voice_states.get(self.guild_id)
        if not vc: return
        
        if vc.is_paused():
            vc.resume()
            await interaction.response.send_message("▶️ Tiếp tục tiên nhạc!", ephemeral=True)
        else:
            vc.pause()
            await interaction.response.send_message("⏸️ Đã ngưng đọng thời gian!", ephemeral=True)
            
    @discord.ui.button(emoji="⏭️", style=discord.ButtonStyle.secondary)
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = self.cog.voice_states.get(self.guild_id)
        if vc:
            vc.stop()
            await interaction.response.send_message("⏭️ Đã bỏ qua chương nhạc này!", ephemeral=True)

    @discord.ui.button(emoji="⏹️", style=discord.ButtonStyle.danger)
    async def stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.cleanup_music(self.guild_id)
        await interaction.response.send_message("⏹️ Đã kết thúc buổi thuyết pháp.", ephemeral=True)

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queues = {}
        self.voice_states = {}
        self.current_meta = {}
        self.now_playing_msgs = {}
        self.loops = {} # guild_id -> bool
        self.transient_msgs = {} # guild_id -> [msg]
        self.cache_manifest = {} # url -> path
        self.progress_updater.start()

    def cog_unload(self):
        self.progress_updater.cancel()

    async def check_access(self, interaction: discord.Interaction):
        return True

    async def reward_music_xp(self, user_id, xp):
        # Placeholder
        pass
        
    async def update_now_playing_display(self, guild_id, create_new=False):
        meta = self.current_meta.get(guild_id)
        if not meta: return

        embed = txa_embed(
            "🎵 Đang Tấu Khúc",
            f"**[{meta['title']}]({meta['url']})**",
            Color.purple()
        )
        if meta.get('thumb'):
            embed.set_thumbnail(url=meta['thumb'])
            
        elapsed = int(time.time() - meta['start_time'] - meta['total_paused_time'])
        total = meta.get('duration') or 0
        progress = (elapsed / total * 100) if total > 0 else 0
        bar = TXAFormat.progress_bar(min(100, progress), 15, "music")
        
        embed.add_field(
            name="⏱️ Tiến Độ",
            value=f"`{bar}`\n`{TXAFormat.time(elapsed)}` / `{TXAFormat.time(total)}`",
            inline=False
        )
        embed.add_field(name="👤 Dẫn Khởi", value=f"<@{meta['requester']}>", inline=True)
        
        view = MusicControlView(self, guild_id)
        
        msg = self.now_playing_msgs.get(guild_id)
        if msg:
            try:
                await msg.edit(embed=embed, view=view)
                return
            except:
                pass # Message might be deleted
        
        if create_new:
            try:
                channel = self.bot.get_channel(meta['channel_id'])
                if channel:
                    msg = await channel.send(embed=embed, view=view)
                    self.now_playing_msgs[guild_id] = msg
            except:
                pass

    def add_transient(self, guild_id, msg):
        if guild_id not in self.transient_msgs:
            self.transient_msgs[guild_id] = []
        self.transient_msgs[guild_id].append(msg)

    async def cleanup_music(self, guild_id):
        if guild_id in self.voice_states:
            vc = self.voice_states[guild_id]
            if vc.is_connected():
                await vc.disconnect()
            del self.voice_states[guild_id]
        self.queues.pop(guild_id, None)
        self.current_meta.pop(guild_id, None)
        self.loops.pop(guild_id, None)
        # Clear now playing msg
        if guild_id in self.now_playing_msgs:
            try: await self.now_playing_msgs[guild_id].delete()
            except: pass
            del self.now_playing_msgs[guild_id]

    def cleanup_cache(self):
        # Implement primitive cleanup: keep last 50 files or clear older than 24h
        pass

    async def search_youtube(self, query: str, max_results: int = 5) -> List[dict]:
        """Tìm kiếm YouTube bằng pytubefix"""
        try:
            loop = asyncio.get_running_loop()
            # Pytube's Search is synchronous
            s = await loop.run_in_executor(None, lambda: Search(query))
            
            results = []
            if s.videos:
                for v in s.videos[:max_results]:
                    results.append({
                        'url': v.watch_url,
                        'title': v.title,
                        'duration': v.length,
                        'thumbnail': v.thumbnail_url,
                        'uploader': v.author
                    })
            return results
        except Exception as e:
            rainbow_log(f"⚠️ Lỗi tìm kiếm: {e}")
            return []

    async def download_media(self, url: str, status_msg: discord.Message = None):
        """Tải nhạc bằng pytubefix"""
        # Kiểm tra Cache
        if url in self.cache_manifest:
            cached_path = self.cache_manifest[url]
            if os.path.exists(cached_path):
                rainbow_log(f"⚡ [Cache Hit] Khai thác linh khí sẵn có cho: {url}")
                # Lấy info nhanh
                try:
                    yt = await asyncio.get_running_loop().run_in_executor(None, lambda: YouTube(url))
                    return cached_path, yt.title, yt.length, yt.thumbnail_url
                except:
                    return cached_path, "Unknown Title", 0, None

        rainbow_log(f"📥 [Pytube] Đang triệu hồi linh khí: {url}")
        
        # Callback wrapper for progress
        progress_data = {'percent': 0}
        
        def progress_func(stream, chunk, bytes_remaining):
            total_size = stream.filesize
            bytes_downloaded = total_size - bytes_remaining
            percent = (bytes_downloaded / total_size) * 100
            progress_data['percent'] = percent

        loop = asyncio.get_running_loop()
        
        # Tách logic tải ra thread riêng để không chặn bot
        def download_logic():
            yt = YouTube(url, on_progress_callback=progress_func)
            stream = yt.streams.get_audio_only()
            # Filename unique
            filename = f"{int(time.time())}.mp3"
            path = stream.download(output_path=DOWNLOADS_DIR, filename=filename)
            return path, yt.title, yt.length, yt.thumbnail_url

        # Background Update Task
        update_task = None
        if status_msg:
            async def update_progress():
                last_update = 0
                while True:
                    await asyncio.sleep(2)
                    p = progress_data['percent']
                    if p >= 100: break
                    
                    if p - last_update >= 15:
                        bar = TXAFormat.progress_bar(p, 15, "music")
                        embed = txa_embed(
                            "📥 Đang Triệu Hồi (Pytube)...",
                            f"`{bar}` **{p:.1f}%**",
                            Color.blue()
                        )
                        try: await status_msg.edit(embed=embed)
                        except: pass
                        last_update = p
            update_task = asyncio.create_task(update_progress())

        try:
            path, title, duration, thumb = await loop.run_in_executor(None, download_logic)
        except Exception as e:
            if update_task: update_task.cancel()
            raise e

        if update_task: update_task.cancel()

        # Update cache
        self.cache_manifest[url] = path
        return path, title, duration, thumb

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
            await self.update_now_playing_display(guild_id, create_new=True)
            
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
