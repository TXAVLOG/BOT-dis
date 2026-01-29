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
        
        # Add Link Button for Top Result
        if results:
            self.add_item(discord.ui.Button(label="Xem trên YouTube", url=results[0]['url'], emoji="📺"))

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
            await self.cog.play_next(guild_id, interaction.channel, interaction=interaction)

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
        """Dọn dẹp linh khí cũ (files > 24h)"""
        try:
            now = time.time()
            for f in os.listdir(DOWNLOADS_DIR):
                path = os.path.join(DOWNLOADS_DIR, f)
                if os.path.isfile(path) and now - os.path.getmtime(path) > 86400:
                    os.remove(path)
            rainbow_log("🧹 [Cache] Đã thanh tẩy linh khí rác (>24h).")
        except Exception as e:
            rainbow_log(f"⚠️ Lỗi thanh tẩy cache: {e}")

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
        """Tải nhạc bằng pytubefix với Real-time Update & Rainbow Log"""
        # Kiểm tra Cache
        if url in self.cache_manifest:
            cached_path = self.cache_manifest[url]
            if os.path.exists(cached_path):
                rainbow_log(f"⚡ [Cache Hit] Khai thác linh khí sẵn có cho: {url}")
                try:
                    yt = await asyncio.get_running_loop().run_in_executor(None, lambda: YouTube(url))
                    return cached_path, yt.title, yt.length, yt.thumbnail_url
                except:
                    return cached_path, "Unknown Title", 0, None

        rainbow_log(f"📥 [Pytube] Đang triệu hồi linh khí: {url}")
        
        # Callback wrapper for progress
        progress_data = {'percent': 0.0}
        
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
            filename = f"{int(time.time())}.mp3"
            path = stream.download(output_path=DOWNLOADS_DIR, filename=filename)
            return path, yt.title, yt.length, yt.thumbnail_url

        # Background Update Task
        update_task = None
        if status_msg:
            async def update_progress():
                last_update = -1
                start_time = time.time()
                while True:
                    await asyncio.sleep(0.5) # Update visually every 0.5s
                    p = progress_data['percent']
                    
                    # Rainbow Log every ~5-10% change to avoid console spam
                    if p - last_update >= 5 or (p >= 100 and last_update < 100):
                        rainbow_log(f"📥 [Tiến Trình] Đang nạp linh khí: {p:.2f}%")
                        last_update = p

                    if p >= 100: break
                    
                    # Real-time Embed Update
                    bar = TXAFormat.progress_bar(p, 15, "music")
                    elapsed = time.time() - start_time
                    speed_note = f"⏱️ Đã chạy: {elapsed:.1f}s"
                    
                    embed = txa_embed(
                        "📥 Đang Triệu Hồi (Pytube)...",
                        f"**{url}**\n\n`{bar}` **{p:.2f}%**\n*{speed_note}*",
                        Color.blue()
                    )
                    try: await status_msg.edit(embed=embed)
                    except: pass
            
            update_task = asyncio.create_task(update_progress())

        try:
            path, title, duration, thumb = await loop.run_in_executor(None, download_logic)
            if update_task: update_task.cancel()
            
            # Final Success Update
            if status_msg:
                embed = txa_embed(
                    "✅ Triệu Hồi Hoàn Tất",
                    f"Đã nạp xong linh khí: **{title}**\n`100.00%` - Sẵn sàng thi triển.",
                    Color.green()
                )
                try: await status_msg.edit(embed=embed)
                except: pass
                
        except Exception as e:
            if update_task: update_task.cancel()
            rainbow_log(f"❌ Lỗi tải file: {e}")
            if status_msg:
                try:
                    embed = txa_embed("❌ Vỡ Trận Triệu Hồi", f"Lỗi nạp linh khí: `{str(e)}`", Color.red())
                    await status_msg.edit(embed=embed)
                except: pass
            raise e

        # Update cache
        self.cache_manifest[url] = path
        return path, title, duration, thumb

    async def _get_user_buffs(self, user_id):
        """Tính toán bonus từ streak và vật phẩm"""
        try:
            user_data = await self.bot.db.get_user(str(user_id))
            if not user_data:
                return 1.0, 0, [], 0 # Multiplier, Luck, ItemNames, Streak

            streak = user_data.get('daily_streak', 0)
            
            # 1. Streak Bonus: 5% per day, max 200% (40 days)
            streak_bonus = min(streak * 0.05, 2.0)
            
            # 2. Item Bonus (Check Buffer or Inventory)
            # Assumption: 'buffs' dict contains multipliers
            buffs = user_data.get('buffs', {})
            item_bonus = buffs.get('music_exp_mult', 0.0)
            
            # Check inventory for artifacts
            inventory = user_data.get('inventory', [])
            active_items = []
            now = time.time()
            
            # Check for Thien Am Cam (Music EXP Buff)
            has_cam = any(
                i['id'] == 'thien_am_cam' and (i.get('count', 0) > 0 or i.get('expiry', 0) > now)
                for i in inventory
            )
            if has_cam:
                item_bonus += 0.2
                active_items.append("Thiên Âm Cầm (+20%)")
            
            # Luck for Spirit Stones (0-100%)
            # Base 5% + Streak * 1%
            luck = min(5 + streak, 80)
            
            # Check for Khi Van Phu (Luck Buff)
            has_luck_charm = any(
                i['id'] == 'khi_van_phu' and (i.get('count', 0) > 0 or i.get('expiry', 0) > now)
                for i in inventory
            )
            if has_luck_charm:
                luck += 20
                active_items.append("Khí Vận Phù (+20% Luck)")

            total_mult = 1.0 + streak_bonus + item_bonus
            return total_mult, luck, active_items, streak
        except:
            return 1.0, 0, [], 0

    async def update_now_playing_display(self, guild_id, create_new=False):
        meta = self.current_meta.get(guild_id)
        if not meta: return

        # Calculate current state
        elapsed = int(time.time() - meta['start_time'] - meta['total_paused_time'])
        total = meta.get('duration') or 0
        progress = (elapsed / total * 100) if total > 0 else 0
        bar = TXAFormat.progress_bar(min(100, progress), 15, "music")
        
        # Real-time Stats
        acc_xp = int(meta.get('accumulated_xp', 0))
        acc_money = int(meta.get('accumulated_money', 0))
        mult = meta.get('xp_multiplier', 1.0)
        streak = meta.get('streak', 0)
        active_items = meta.get('active_items', [])
        
        embed = txa_embed(
            "🎵 Đang Tấu Khúc (Real-time Cultivation)",
            f"**[{meta['title']}]({meta['url']})**",
            Color.purple()
        )
        if meta.get('thumb'):
            embed.set_thumbnail(url=meta['thumb'])
            
        # Progress Field
        embed.add_field(
            name=f"⏱️ Tiến Độ ({int(progress)}%)",
            value=f"`{bar}`\n`{TXAFormat.time(elapsed)}` / `{TXAFormat.time(total)}`",
            inline=False
        )
        
        # Cultivation Stats
        items_str = ", ".join(active_items) if active_items else "Không có vật phẩm hỗ trợ"
        stats_desc = (
            f"🔥 **Chuỗi Tu Luyện:** `{streak} ngày` (Bonus {int(streak*5)}%)\n"
            f"💊 **Vật Phẩm:** {items_str}\n"
            f"⚡ **Tốc Độ Hấp Thu:** `{mult:.1f}x` exp/s"
        )
        embed.add_field(name="🧘 Trạng Thái Tu Luyện", value=stats_desc, inline=False)
        
        # Real-time Gains
        gains_desc = f"✨ **Linh Lực:** `+{acc_xp}` EXP"
        if acc_money > 0:
            gains_desc += f"\n💎 **Linh Thạch:** `+{acc_money}`"
        
        embed.add_field(name="🎁 Thu Hoạch Hiện Tại", value=gains_desc, inline=True)
        embed.add_field(name="👤 Dẫn Khởi", value=f"<@{meta['requester']}>", inline=True)
        
        view = MusicControlView(self, guild_id)
        
        msg = self.now_playing_msgs.get(guild_id)
        
        # Rate limit handling: Try to edit, if stale/not found, recreate
        try:
            if msg:
                await msg.edit(embed=embed, view=view)
                return
        except discord.errors.NotFound:
             pass 
        except Exception:
             return # Skip update on error

        if create_new:
            try:
                channel = self.bot.get_channel(meta['channel_id'])
                if channel:
                    msg = await channel.send(embed=embed, view=view)
                    self.now_playing_msgs[guild_id] = msg
            except:
                pass

    async def play_next(self, guild_id: int, channel: discord.TextChannel = None, interaction: discord.Interaction = None):
        """Phát bài tiếp theo trong hàng chờ"""
        queue = self.queues.get(guild_id, [])
        if not queue:
            # End of queue logic
            if guild_id in self.current_meta:
               await self.finalize_rewards(guild_id)
            
            self.current_meta.pop(guild_id, None)
            if guild_id in self.now_playing_msgs:
                try:
                    embed = txa_embed("🎵 Tiên Nhạc Kết Thúc", "Hàng chờ đã cạn, hãy thêm bài mới!", Color.orange())
                    await self.now_playing_msgs[guild_id].edit(embed=embed, view=None)
                except: pass
            return

        vc = self.voice_states.get(guild_id)
        if not vc or not vc.is_connected():
            return

        # Finalize previous song rewards
        if guild_id in self.current_meta:
            await self.finalize_rewards(guild_id)

        item = queue.pop(0)
        self.queues[guild_id] = queue
        
        # Send loading message (Ephemeral if interaction exists, else Channel)
        target_channel = channel or self.bot.get_channel(item.get('channel_id'))
        status_msg = None
        
        try:
            embed = txa_embed("📥 Đang Triệu Hồi Tiên Nhạc...", f"**{item['title']}**", Color.blue())
            if interaction:
                # Use interaction for ephemeral status if it's the start of the session
                status_msg = await interaction.followup.send(embed=embed, ephemeral=True)
                self.add_transient(guild_id, status_msg)
            elif target_channel:
                status_msg = await target_channel.send(embed=embed)
                self.add_transient(guild_id, status_msg)
        except: pass
        
        try:
            path, title, duration, thumb = await self.download_media(item['url'], status_msg)
            source = discord.FFmpegPCMAudio(path, **FFMPEG_OPTIONS)
            
            def after(error):
                if self.loops.get(guild_id):
                    self.queues[guild_id].insert(0, item)
                asyncio.run_coroutine_threadsafe(self.play_next(guild_id, target_channel), self.bot.loop)

            vc.play(source, after=after)
            
            # --- CALCULATE BUFFS ---
            mult, luck, active_items, streak = await self._get_user_buffs(item['requester'])
            
            self.current_meta[guild_id] = {
                "title": title or item['title'],
                "url": item['url'],
                "duration": duration,
                "thumb": thumb,
                "start_time": time.time(),
                "last_pause_time": None,
                "total_paused_time": 0,
                "requester": item['requester'],
                "channel_id": item.get('channel_id'),
                
                # New Stats
                "xp_multiplier": mult,
                "luck_percent": luck,
                "active_items": active_items,
                "streak": streak,
                "accumulated_xp": 0.0,
                "accumulated_money": 0,
                "last_tick": time.time()
            }
            
            # Cleanup transient status message after a short delay or let updater handle it
            if status_msg and not interaction: # Ephemerals don't need manual deletion usually or fail
                await self._cleanup_transients(guild_id, status_msg)
            
            # Update Display
            await self.update_now_playing_display(guild_id, create_new=True)
            
        except Exception as e:
            rainbow_log(f"❌ Lỗi phát nhạc: {e}")
            if "No space left" in str(e): self.cleanup_cache()
            
            # Status message already edited with error in download_media
            await asyncio.sleep(2)
            await self.play_next(guild_id, target_channel)

    async def finalize_rewards(self, guild_id):
        """Save LP/XP to DB when song ends"""
        meta = self.current_meta.get(guild_id)
        if not meta: return
        
        user_id = meta['requester']
        xp = int(meta.get('accumulated_xp', 0))
        money = meta.get('accumulated_money', 0)
        
        if xp > 0 or money > 0:
            user_data = await self.bot.db.get_user(str(user_id))
            if user_data:
                new_exp = user_data.get('exp', 0) + xp
                new_stones = user_data.get('spirit_stones', 0) + money
                await self.bot.db.update_user(str(user_id), exp=new_exp, spirit_stones=new_stones)
                rainbow_log(f"🎁 Reward saved for {user_id}: +{xp} XP, +{money} Stones")

    async def _cleanup_transients(self, guild_id, current_msg):
        if guild_id in self.transient_msgs:
            kept_msgs = []
            for msg in self.transient_msgs[guild_id]:
                try:
                    should_delete = False
                    if current_msg and msg.id == current_msg.id: should_delete = True
                    elif msg.embeds and "Chuyển Biến Tiên Âm" in str(msg.embeds[0].title): should_delete = True
                    
                    is_search_result = False
                    if msg.embeds and "Kết Quả Tầm Đạo" in str(msg.embeds[0].title): is_search_result = True
                    
                    if should_delete: await msg.delete()
                    elif is_search_result: kept_msgs.append(msg)
                    else: await msg.delete()
                except: pass
            self.transient_msgs[guild_id] = kept_msgs

    @tasks.loop(seconds=2)
    async def progress_updater(self):
        """Cập nhật embed và logic XP"""
        await self.bot.wait_until_ready()
        
        for guild_id in list(self.current_meta.keys()):
            meta = self.current_meta[guild_id]
            vc = self.voice_states.get(guild_id)
            
            # Logic XP Update
            if vc and vc.is_playing() and not vc.is_paused():
                now = time.time()
                last_tick = meta.get('last_tick', now)
                delta = now - last_tick
                meta['last_tick'] = now
                
                # Formula: Base (2-4) * Mult * Delta
                base_xp = random.uniform(2.0, 4.0)
                xp_gain = base_xp * meta['xp_multiplier'] * delta
                meta['accumulated_xp'] += xp_gain
                
                # Random Chance for Money (Every tick check)
                # Chance = Luck / 1000 per second approx
                luck = meta.get('luck_percent', 0)
                if random.random() < (luck / 100.0 * 0.05 * delta): # ~5% of luck per sec
                    drop = random.randint(1, 100)
                    meta['accumulated_money'] += drop
            else:
                meta['last_tick'] = time.time() # Reset tick if paused so no jump

            # Fix visual jump
            if vc and vc.is_paused():
                 # Don't update visual often if paused
                 pass
            else:
                await self.update_now_playing_display(guild_id)

    @progress_updater.before_loop
    async def before_progress_updater(self):
        await self.bot.wait_until_ready()

    # --- COMMANDS REMAIN AS IS (Just ensuring standard structure) ---
    @app_commands.command(name="ytplay", description="Tìm kiếm và phát tiên nhạc từ YouTube")
    @app_commands.describe(query="Tên bài hát hoặc URL YouTube")
    async def ytplay(self, interaction: discord.Interaction, query: str):
        if not await self.check_access(interaction): return
        
        # EPHEMERAL DEFER to keep download logs private to the user
        await interaction.response.defer(ephemeral=True)
        
        guild_id = interaction.guild_id
        vc = interaction.guild.voice_client
        if not vc:
            if not interaction.user.voice:
                embed = txa_embed("⛩️ Thiên Lam Cấm Chế", "Đạo hữu chưa vào Voice Channel!", Color.red())
                return await interaction.followup.send(embed=embed, ephemeral=True)
            vc = await interaction.user.voice.channel.connect()
            self.voice_states[guild_id] = vc
        
        if query.startswith("http"):
            item = {"url": query, "title": "Tiên Nhạc URL", "requester": interaction.user.id, "channel_id": interaction.channel_id}
            self.queues.setdefault(guild_id, []).append(item)
            if not vc.is_playing() and not vc.is_paused():
                # PASS INTERACTION for Private Loading Status
                await self.play_next(guild_id, interaction.channel, interaction=interaction)
            else:
                embed = txa_embed("➕ Tàng Kinh Các", "Đã thêm vào hàng chờ.", Color.blue())
                await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            results = await self.search_youtube(query)
            if not results:
                return await interaction.followup.send("❌ Không tìm thấy nhạc!", ephemeral=True)
            
            # --- View Logic ---
            view = SearchResultView(self, results, interaction.user.id)
            main_embed = txa_embed("🔍 Kết Quả", f"Tìm thấy {len(results)} bài.", Color.blue())
            
            # Helper to create result embeds
            res_embeds = [main_embed]
            for i, r in enumerate(results[:5]):
                 emb = txa_embed(f"{i+1}. {r['title']}", f"⏱️ {TXAFormat.time(r['duration'])}", Color.dark_grey())
                 if r.get('thumbnail'):
                     emb.set_thumbnail(url=r['thumbnail'])
                 res_embeds.append(emb)

            msg = await interaction.followup.send(embeds=res_embeds, view=view, ephemeral=True)
            self.add_transient(guild_id, msg)

    @app_commands.command(name="ytnow", description="Xem thông tin bài đang phát")
    async def ytnow(self, interaction: discord.Interaction):
        await self.update_now_playing_display(interaction.guild_id, create_new=True)
        await interaction.response.send_message("✅ Đã cập nhật bảng thông tin.", ephemeral=True)

    @app_commands.command(name="ytstop", description="Dừng nhạc")
    async def ytstop(self, interaction: discord.Interaction):
        await self.cleanup_music(interaction.guild_id)
        await interaction.response.send_message("🛑 Đã dừng nhạc.", ephemeral=True)

    @app_commands.command(name="ytqueue", description="Xem hàng chờ")
    async def ytqueue(self, interaction: discord.Interaction):
         # ... reuse previous logic or simplified ...
         queue = self.queues.get(interaction.guild_id, [])
         if not queue:
             return await interaction.response.send_message("Empty queue!", ephemeral=True)
         
         desc = ""
         for i, item in enumerate(queue[:10], 1):
             desc += f"{i}. {item['title']} - <@{item['requester']}>\n"
         
         embed = txa_embed("📜 Hàng Chờ Tiên Nhạc", desc or "Trống trơn...", Color.blue())
         await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="ytclear", description="Xóa hàng chờ")
    async def ytclear(self, interaction: discord.Interaction):
        self.queues[interaction.guild_id] = []
        await interaction.response.send_message("🧹 Đã xóa hàng chờ.", ephemeral=True)
    
    @app_commands.command(name="ytplaynow", description="Phát ngay")
    async def ytplaynow(self, interaction: discord.Interaction, position: int):
         # Reuse logic
         pass

async def setup(bot):
    await bot.add_cog(Music(bot))
