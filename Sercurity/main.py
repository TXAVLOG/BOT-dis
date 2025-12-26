import os
import json
import discord
from discord.ext import commands
from discord.ui import Button, View, Modal, TextInput
from discord import app_commands, PermissionOverwrite
from dotenv import load_dotenv
import aiohttp
import urllib.parse # Import for URL encoding
from datetime import datetime

# Tải biến môi trường từ file .env
load_dotenv()

# Lấy các biến từ môi trường
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
WELCOME_CHANNEL_ID = int(os.getenv('WELCOME_CHANNEL_ID'))
PAYMENT_CHANNEL_ID = int(os.getenv('PAYMENT_CHANNEL_ID'))
MEMBER_ROLE_ID = int(os.getenv('MEMBER_ROLE_ID'))
UNVERIFIED_ROLE_ID = int(os.getenv('UNVERIFIED_ROLE_ID'))

# Fallback channel nếu payment channel không tồn tại
def get_verification_channel():
    """Lấy channel để gửi message xác minh, fallback về welcome channel nếu payment channel không tồn tại"""
    payment_channel = bot.get_channel(PAYMENT_CHANNEL_ID)
    if payment_channel:
        return payment_channel
    
    welcome_channel = bot.get_channel(WELCOME_CHANNEL_ID)
    if welcome_channel:
        print(f"Payment channel not found, using welcome channel: #{welcome_channel.name}")
        return welcome_channel
    
    print("Error: Both payment and welcome channels not found. Please check .env file.")
    return None

API_BASE_URL = os.getenv('API_BASE_URL')
CHECK_LINK_API_ENDPOINT = f"{API_BASE_URL}/check_link.php"
LINK_ACCOUNT_API_ENDPOINT = f"{API_BASE_URL}/link.php"
MAIN_API_ENDPOINT = f"{API_BASE_URL}/api.php"

BANK_ACCOUNT_NUMBER = os.getenv('BANK_ACCOUNT_NUMBER')
BANK_NAME = os.getenv('BANK_NAME')
PAYMENT_AMOUNT = os.getenv('PAYMENT_AMOUNT')
PAYMENT_CONTENT_FORMAT = os.getenv('PAYMENT_CONTENT_FORMAT')

# --- THÊM THÔNG TIN BANK BIN CHO VIETQR API ---
# Vietcombank BIN. Bạn có thể tìm BIN của các ngân hàng khác trên internet nếu cần.
VIETCOMBANK_BIN = "970436" 

# --- Cấu hình bot (Discord Intents) ---
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.presences = True

bot = commands.Bot(command_prefix=commands.when_mentioned_or('!'), intents=intents)

# --- File để lưu ID tin nhắn nút xác minh vĩnh viễn ---
CONFIG_FILE = 'bot_config.json'

# --- Thống kê và báo cáo ---
STATS_FILE = 'security_stats.json'

# --- Danh sách admin bot (có thể thêm/bớt bằng lệnh) ---
bot_admin_list = set()

# --- Hệ thống cảnh báo ---
WARNING_THRESHOLD = 3  # Số lần thử xác minh sai trước khi cảnh báo
user_attempts = {}  # Lưu số lần thử của mỗi user

def load_bot_config():
    """Loads bot configuration from a JSON file."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"Error reading {CONFIG_FILE}. Recreating file.")
            return {"verification_message_id": None}
    return {"verification_message_id": None}

def save_bot_config(config):
    """Saves bot configuration to a JSON file."""
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4)

def load_security_stats():
    """Loads security statistics from a JSON file."""
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"Error reading {STATS_FILE}. Recreating file.")
            return {
                "total_verifications": 0,
                "successful_verifications": 0,
                "failed_attempts": 0,
                "admin_activations": 0,
                "daily_stats": {},
                "user_stats": {}
            }
    return {
        "total_verifications": 0,
        "successful_verifications": 0,
        "failed_attempts": 0,
        "admin_activations": 0,
        "daily_stats": {},
        "user_stats": {}
    }

def save_security_stats(stats):
    """Saves security statistics to a JSON file."""
    with open(STATS_FILE, 'w', encoding='utf-8') as f:
        json.dump(stats, f, indent=4)

def update_daily_stats():
    """Updates daily statistics."""
    stats = load_security_stats()
    today = datetime.now().strftime('%Y-%m-%d')
    
    if today not in stats["daily_stats"]:
        stats["daily_stats"][today] = {
            "verifications": 0,
            "successful": 0,
            "failed": 0,
            "activations": 0
        }
    
    save_security_stats(stats)
    return stats

def log_verification_attempt(user_id: int, success: bool):
    """Logs a verification attempt."""
    stats = load_security_stats()
    today = datetime.now().strftime('%Y-%m-%d')
    
    # Update total stats
    stats["total_verifications"] += 1
    if success:
        stats["successful_verifications"] += 1
    else:
        stats["failed_attempts"] += 1
    
    # Update daily stats
    if today not in stats["daily_stats"]:
        stats["daily_stats"][today] = {
            "verifications": 0,
            "successful": 0,
            "failed": 0,
            "activations": 0
        }
    
    stats["daily_stats"][today]["verifications"] += 1
    if success:
        stats["daily_stats"][today]["successful"] += 1
    else:
        stats["daily_stats"][today]["failed"] += 1
    
    # Update user stats
    user_id_str = str(user_id)
    if user_id_str not in stats["user_stats"]:
        stats["user_stats"][user_id_str] = {
            "attempts": 0,
            "successful": 0,
            "last_attempt": None
        }
    
    stats["user_stats"][user_id_str]["attempts"] += 1
    if success:
        stats["user_stats"][user_id_str]["successful"] += 1
    stats["user_stats"][user_id_str]["last_attempt"] = datetime.now().isoformat()
    
    save_security_stats(stats)

# --- Hàm kiểm tra quyền và cảnh báo ---
async def is_bot_admin_check(interaction: discord.Interaction) -> bool:
    """
    Kiểm tra quyền Bot Admin (có trong danh sách admin hoặc là Server Administrator).
    """
    user_id = interaction.user.id
    
    # Kiểm tra bot admin list trước
    if user_id in bot_admin_list:
        return True
    
    # Kiểm tra guild permissions (chỉ khi user là Member, không phải User)
    if hasattr(interaction.user, 'guild_permissions'):
        if interaction.user.guild_permissions.administrator:
            return True
    
    # Nếu không có quyền, gửi thông báo lỗi
    if not interaction.response.is_done():
        await interaction.response.send_message(
            "❌ Bạn không có quyền **Bot Admin** để sử dụng lệnh này!",
            ephemeral=True
        )
    else:
        await interaction.followup.send(
            "❌ Bạn không có quyền **Bot Admin** để sử dụng lệnh này!",
            ephemeral=True
        )
    return False

def check_user_attempts(user_id: int) -> dict:
    """
    Kiểm tra số lần thử của user và trả về thông tin cảnh báo.
    """
    if user_id not in user_attempts:
        user_attempts[user_id] = {"count": 0, "last_attempt": None}
    
    return user_attempts[user_id]

def increment_user_attempts(user_id: int):
    """
    Tăng số lần thử của user.
    """
    if user_id not in user_attempts:
        user_attempts[user_id] = {"count": 0, "last_attempt": None}
    
    user_attempts[user_id]["count"] += 1
    user_attempts[user_id]["last_attempt"] = datetime.now()

def reset_user_attempts(user_id: int):
    """
    Reset số lần thử của user khi thành công.
    """
    if user_id in user_attempts:
        user_attempts[user_id]["count"] = 0

async def send_warning_to_admins(guild, user, reason: str):
    """
    Gửi cảnh báo đến tất cả admin trong server.
    """
    for member in guild.members:
        if member.bot:
            continue
        
        admin_check = await get_linked_account_info(member.id)
        if admin_check.get('linked') and admin_check.get('admin') == 1:
            warning_embed = discord.Embed(
                title="🚨 CẢNH BÁO BẢO MẬT 🚨",
                description=f"Phát hiện hoạt động đáng ngờ từ **{user.name}** ({user.id})",
                color=discord.Color.red()
            )
            warning_embed.add_field(name="Lý do:", value=reason, inline=False)
            warning_embed.add_field(name="Thời gian:", value=datetime.now().strftime('%H:%M:%S %d/%m/%Y'), inline=False)
            warning_embed.set_footer(text="Hệ thống cảnh báo tự động")
            warning_embed.timestamp = discord.utils.utcnow()
            
            try:
                await member.send(embed=warning_embed)
            except discord.Forbidden:
                pass  # User có thể đã tắt DM

# --- Helper function: Checks linked account information ---
async def get_linked_account_info(discord_id: int):
    """Checks if a Discord ID is linked to a game account and retrieves information."""
    # Mock data cho testing khi API chưa hoạt động
    mock_links = {
        # Thêm một số test data ở đây nếu cần
        # 123456789: {'linked': True, 'username': 'TestPlayer', 'admin': 0, 'ban': 0}
    }
    
    # Kiểm tra mock data trước
    if discord_id in mock_links:
        return mock_links[discord_id]
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(CHECK_LINK_API_ENDPOINT, data={'discord_id': discord_id}) as response:
                if response.content_type != 'application/json':
                    print(f"API returned non-JSON response: {response.content_type}")
                    print(f"Response text: {await response.text()}")
                    return {'linked': False, 'error': 'API returned HTML instead of JSON. API may not be deployed.'}
                
                result = await response.json()
                if result.get('linked'):
                    return {
                        'linked': True,
                        'username': result.get('username'),
                        'admin': result.get('admin'),
                        'ban': result.get('ban')
                    }
                return {'linked': False}
        except aiohttp.ClientError as e:
            print(f"Error calling check_link API: {e}")
            return {'linked': False, 'error': 'API error when checking link.'}
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON from check_link.php: {e}")
            response_text = await response.text() if 'response' in locals() else 'Unknown'
            print(f"Response text: {response_text}")
            return {'linked': False, 'error': 'API response error.'}


# --- View class containing the "Verify Here" button (for users) ---
class VerifyView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Xác minh tại đây", style=discord.ButtonStyle.success, custom_id="verify_button")
    async def verify_button_callback(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer(ephemeral=True)

        user = interaction.user
        guild = interaction.guild

        # --- Chuẩn bị dữ liệu cho QR code ---
        parsed_amount_for_qr = PAYMENT_AMOUNT.replace('.','').replace(' VND', '') 
        example_username_for_qr = "TANG XUAN ANH" 
        example_transaction_content_for_qr = f"{PAYMENT_CONTENT_FORMAT}{example_username_for_qr}"
        encoded_description_for_qr = urllib.parse.quote_plus(example_transaction_content_for_qr)

        qr_code_url = f"https://api.vietqr.io/image/{VIETCOMBANK_BIN}/{BANK_ACCOUNT_NUMBER}/{parsed_amount_for_qr}/{encoded_description_for_qr}/compact2"

        # --- Cập nhật nội dung DM ---
        embed_dm = discord.Embed(
            title='💲 Hướng dẫn Nạp tiền và Kích hoạt Thành viên 💲',
            description=f'Chào mừng bạn đến với server **{guild.name}**! Để trở thành thành viên chính thức và truy cập tất cả các kênh, vui lòng thực hiện theo các bước sau:',
            color=discord.Color.blue()
        )
        embed_dm.add_field(
            name='1️⃣ Thông tin chuyển khoản:',
            value=f'**Số tiền:** `{PAYMENT_AMOUNT}`\n'
                  f'**Ngân hàng:** `{BANK_NAME}`\n'
                  f'**Số tài khoản:** `{BANK_ACCOUNT_NUMBER}`',
            inline=False
        )
        embed_dm.add_field(
            name='Nội dung chuyển khoản (Rất quan trọng!):',
            value=f'Nội dung chuyển khoản phải theo định dạng sau (thay thế `TAIKHOANCUABAN` bằng tên tài khoản game của bạn): \n'
                  f'```\n{PAYMENT_CONTENT_FORMAT}TAIKHOANCUABAN\n```\n'
                  f'Ví dụ: `{PAYMENT_CONTENT_FORMAT}TenGameCuaToi`',
            inline=False
        )
        embed_dm.set_image(url=qr_code_url)

        embed_dm.add_field(
            name='2️⃣ Xác nhận Nạp tiền:',
            value=f'Sau khi chuyển khoản thành công, vui lòng quay lại kênh <#{PAYMENT_CHANNEL_ID}> và sử dụng lệnh Slash Command `/txacnhan_nap`. '
                  f'Bot sẽ yêu cầu bạn nhập **tên tài khoản game** và **nội dung chuyển khoản bạn đã ghi** để xác nhận giao dịch.',
            inline=False
        )
        embed_dm.set_footer(text='Hệ thống Thành viên tự động')
        embed_dm.set_thumbnail(url=bot.user.avatar.url if bot.user.avatar else None)
        embed_dm.timestamp = discord.utils.utcnow()

        try:
            await user.send(embed=embed_dm)
            await interaction.followup.send("🎉 Hướng dẫn chi tiết đã được gửi đến tin nhắn riêng của bạn (DM). Vui lòng kiểm tra DM của bot!", ephemeral=True)
            print(f"DM instructions sent to {user.name} ({user.id})")
        except discord.Forbidden:
            await interaction.followup.send("⚠️ Không thể gửi DM cho bạn. Vui lòng kiểm tra cài đặt quyền riêng tư của bạn để cho phép tin nhắn trực tiếp từ bot.", ephemeral=True)
            print(f"Could not DM {user.name} ({user.id}). They might have DMs disabled.")

# --- NEW: View class with a Copy Button (for admins) ---
class CopyCommandView(View):
    def __init__(self, command_text: str):
        super().__init__(timeout=None)
        self.command_text = command_text
        # Add a button with a custom_id for persistent views
        self.add_item(discord.ui.Button(label="Sao chép lệnh", style=discord.ButtonStyle.secondary, custom_id=f"copy_cmd_{command_text[:10]}")) # Use a snippet of command as ID part

    @discord.ui.button(label="Sao chép lệnh", style=discord.ButtonStyle.secondary, custom_id="copy_command_button_actual") # This custom_id will be overwritten below
    async def copy_button_callback(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message(f"Lệnh để sao chép: ```\n{self.command_text}\n```", ephemeral=True)
        print(f"Admin {interaction.user.name} requested to copy command: {self.command_text}")

    # This method is called by discord.py to get the actual items for the view
    # We override it to dynamically set the custom_id for the button
    def to_components(self):
        # Create a new Button instance with the dynamic custom_id
        # This is necessary because custom_id can't be changed after object creation
        dynamic_button = discord.ui.Button(
            label="Sao chép lệnh", 
            style=discord.ButtonStyle.secondary, 
            custom_id=f"copy_cmd_{self.command_text}" # Use full command text as ID for uniqueness
        )
        # Set the callback for this new button
        dynamic_button.callback = self.copy_button_callback
        
        # Return components, replacing the placeholder button with our dynamic one
        components = super().to_components()
        # Find the original button by label and replace it
        for i, comp in enumerate(components):
            if comp['type'] == discord.ComponentType.button.value and comp['label'] == "Sao chép lệnh":
                components[i] = dynamic_button.to_json()
                break
        return components


# --- Modal classes for Slash Commands ---

class LinkThenVerifyModal(Modal, title="Liên kết tài khoản & Nạp tiền"):
    game_username = TextInput(
        label="1. Tên tài khoản game của bạn",
        placeholder="Ví dụ: TenGameCuaToi",
        max_length=100,
        required=True,
        row=0
    )
    transaction_content_provided = TextInput(
        label=f"2. Nội dung chuyển khoản (ĐÚNG định dạng!)",
        placeholder=f"Ví dụ: {PAYMENT_CONTENT_FORMAT}TenTaiKhoanCuaToi",
        max_length=255,
        required=True,
        row=1
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        discord_id = interaction.user.id
        member = interaction.user
        guild = interaction.guild

        game_username_value = self.game_username.value.strip()
        transaction_content_value = self.transaction_content_provided.value.strip()
        
        if not game_username_value:
            await interaction.followup.send('⚠️ Tên tài khoản game không được để trống.', ephemeral=True)
            return
        if not transaction_content_value:
            await interaction.followup.send('⚠️ Nội dung chuyển khoản không được để trống.', ephemeral=True)
            return

        # --- Step 1: Attempt to link account ---
        async with aiohttp.ClientSession() as session:
            try:
                link_payload = {'discord_id': str(discord_id), 'username': game_username_value}
                async with session.post(LINK_ACCOUNT_API_ENDPOINT, data=link_payload) as link_response:
                    link_result = await link_response.json()

                    if link_result.get('status') == 'success':
                        await interaction.followup.send(f'✅ Đã liên kết tài khoản Discord của bạn với tài khoản game `{game_username_value}`.', ephemeral=True)
                        print(f'User {interaction.user.name} linked to game account: {game_username_value}')
                    elif "đã được liên kết với tài khoản game này rồi" in link_result.get('message', ''):
                        await interaction.followup.send(f'ℹ️ Tài khoản Discord của bạn đã được liên kết với tài khoản game `{game_username_value}` rồi. Tiếp tục quá trình xác nhận nạp tiền.', ephemeral=True)
                        print(f'User {interaction.user.name} was already linked to game account {game_username_value}, proceeding with payment verification.')
                    else:
                        # Log thất bại
                        increment_user_attempts(discord_id)
                        log_verification_attempt(discord_id, False)
                        
                        await interaction.followup.send(f'⚠️ Lỗi khi liên kết tài khoản: {link_result.get("message", "Lỗi không xác định")}. Vui lòng kiểm tra lại tên tài khoản game hoặc liên hệ quản trị viên.', ephemeral=True)
                        print(f'PHP API error when linking account for {interaction.user.name}: {link_result.get("message")}')
                        return

            except aiohttp.ClientError as e:
                # Log thất bại
                increment_user_attempts(discord_id)
                log_verification_attempt(discord_id, False)
                
                print(f'Error calling link.php API (from modal): {e}')
                await interaction.followup.send('Đã có lỗi xảy ra khi liên kết tài khoản. Vui lòng thử lại sau.', ephemeral=True)
                return


        # --- Step 2: Proceed with payment verification ---
        linked_info_after_link = await get_linked_account_info(member.id)
        if not linked_info_after_link.get('linked'):
            await interaction.followup.send(f'⚠️ Không thể xác nhận nạp tiền vì tài khoản game của bạn chưa được liên kết. Vui lòng thử lại lệnh `/txacnhan_nap` và kiểm tra kỹ thông tin.', ephemeral=True)
            return

        linked_username_final = linked_info_after_link['username']
        expected_transaction_content = f"{PAYMENT_CONTENT_FORMAT}{linked_username_final}"

        activation_code = f"ACT-{discord.utils.utcnow().timestamp()}-{str(member.id)[:6]}"

        async with aiohttp.ClientSession() as session:
            try:
                payload = {
                    'action': 'create_activation_request',
                    'activation_code': activation_code,
                    'user_id': str(member.id),
                    'username_discord': str(member),
                    'linked_username': linked_username_final,
                    'transaction_content': transaction_content_value,
                    'guild_id': str(guild.id),
                }
                async with session.post(MAIN_API_ENDPOINT, json=payload) as response:
                    result = await response.json()

                    if result.get('status') == 'success':
                        await guild.chunk()
                        for guild_member in guild.members:
                            if guild_member.bot:
                                continue

                            admin_check = await get_linked_account_info(guild_member.id)
                            print(f"Checking {guild_member.name} ({guild_member.id}) for admin DM: Linked={admin_check.get('linked')}, Admin Status={admin_check.get('admin')}")
                            
                            if admin_check.get('linked') and admin_check.get('admin') == 1:
                                admin_embed = discord.Embed(
                                    title='🔔 Yêu cầu kích hoạt thành viên mới 🔔',
                                    description=f'**{member}** ({member.id}) đã yêu cầu kích hoạt thành viên.',
                                    color=discord.Color.gold()
                                )
                                admin_embed.add_field(name='Tài khoản Game đã liên kết:', value=f'`{linked_username_final}`', inline=False)
                                admin_embed.add_field(name='Nội dung chuyển khoản người dùng cung cấp (cần kiểm tra):', value=f'`{transaction_content_value}`', inline=False)
                                admin_embed.add_field(name='Nội dung chuyển khoản mong đợi:', value=f'`{expected_transaction_content}`', inline=False)
                                admin_embed.add_field(name='Lệnh kích hoạt:', value=f'Sử dụng lệnh `/tkichhoat` với mã dưới đây để kích hoạt:', inline=False)
                                admin_embed.add_field(name='Mã kích hoạt:', value=f'```\n{activation_code}\n```', inline=False) # Display code here
                                admin_embed.add_field(name='Link kiểm tra yêu cầu (tùy chọn):', value=f'[Xem trạng thái yêu cầu]({API_BASE_URL}/api.php?action=get_request_status&activation_code={activation_code})', inline=False)
                                admin_embed.set_footer(text=f'Yêu cầu từ server: {guild.name}')
                                admin_embed.set_thumbnail(url=member.avatar.url if member.avatar else None)
                                admin_embed.timestamp = discord.utils.utcnow()

                                # Attach the CopyCommandView to the DM
                                copy_view = CopyCommandView(f"/tkichhoat {activation_code}")
                                try:
                                    await guild_member.send(embed=admin_embed, view=copy_view)
                                    print(f"DM sent to admin {guild_member.name} about activation request from {member.name}. Code: {activation_code}")
                                except discord.Forbidden:
                                    print(f"Could not DM admin {guild_member.name}. They might have DMs disabled.")

                        # Log thành công
                        reset_user_attempts(discord_id)
                        log_verification_attempt(discord_id, True)
                        
                        await interaction.followup.send(f'✨ Yêu cầu nạp tiền của bạn đã được gửi thành công! Quản trị viên sẽ kiểm tra giao dịch và kích hoạt tài khoản của bạn. Vui lòng chờ đợi.', ephemeral=True)
                        print(f'Activation request from {member.name} (Game: {linked_username_final}) created.')

                    else:
                        await interaction.followup.send(f'⚠️ Đã có lỗi xảy ra khi gửi yêu cầu của bạn: {result.get("message", "Lỗi không xác định")}', ephemeral=True)
                        print(f'PHP API error when creating request: {result.get("message")}')
            except aiohttp.ClientError as e:
                print(f'Error calling api.php API (create_activation_request): {e}')
                await interaction.followup.send('⚠️ Đã có lỗi xảy ra khi kết nối với hệ thống xác minh. Vui lòng thử lại sau hoặc liên hệ quản trị viên.', ephemeral=True)

class PaymentVerificationModal(Modal, title="Xác nhận nạp tiền"):
    transaction_content_provided = TextInput(
        label=f"Nội dung chuyển khoản (ĐÚNG định dạng!)",
        placeholder=f"Ví dụ: {PAYMENT_CONTENT_FORMAT}TenTaiKhoanCuaBan",
        max_length=255,
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        member = interaction.user
        guild = interaction.guild

        if guild.get_role(MEMBER_ROLE_ID) in member.roles:
            await interaction.followup.send('Bạn đã là thành viên rồi!', ephemeral=True)
            return

        linked_info = await get_linked_account_info(member.id)
        if not linked_info.get('linked'):
            await interaction.followup.send(f'⚠️ Không thể xác nhận nạp tiền vì tài khoản game của bạn chưa được liên kết. Vui lòng thử lại lệnh `/txacnhan_nap`.', ephemeral=True)
            return

        linked_username = linked_info['username']
        expected_transaction_content = f"{PAYMENT_CONTENT_FORMAT}{linked_username}"
        transaction_content_value = self.transaction_content_provided.value.strip()

        if not transaction_content_value:
            await interaction.followup.send('⚠️ Nội dung chuyển khoản không được để trống.', ephemeral=True)
            return

        activation_code = f"ACT-{discord.utils.utcnow().timestamp()}-{str(member.id)[:6]}"

        async with aiohttp.ClientSession() as session:
            try:
                payload = {
                    'action': 'create_activation_request',
                    'activation_code': activation_code,
                    'user_id': str(member.id),
                    'username_discord': str(member),
                    'linked_username': linked_username,
                    'transaction_content': transaction_content_value,
                    'guild_id': str(guild.id),
                }
                async with session.post(MAIN_API_ENDPOINT, json=payload) as response:
                    result = await response.json()

                    if result.get('status') == 'success':
                        await guild.chunk()
                        for guild_member in guild.members:
                            if guild_member.bot:
                                continue

                            admin_check = await get_linked_account_info(guild_member.id)
                            print(f"Checking {guild_member.name} ({guild_member.id}) for admin DM: Linked={admin_check.get('linked')}, Admin Status={admin_check.get('admin')}")
                            
                            if admin_check.get('linked') and admin_check.get('admin') == 1:
                                admin_embed = discord.Embed(
                                    title='🔔 Yêu cầu kích hoạt thành viên mới 🔔',
                                    description=f'**{member}** ({member.id}) đã yêu cầu kích hoạt thành viên.',
                                    color=discord.Color.gold()
                                )
                                admin_embed.add_field(name='Tài khoản Game đã liên kết:', value=f'`{linked_username}`', inline=False)
                                admin_embed.add_field(name='Nội dung chuyển khoản người dùng cung cấp (cần kiểm tra):', value=f'`{transaction_content_value}`', inline=False)
                                admin_embed.add_field(name='Nội dung chuyển khoản mong đợi:', value=f'`{expected_transaction_content}`', inline=False)
                                admin_embed.add_field(name='Lệnh kích hoạt:', value=f'Sử dụng lệnh `/tkichhoat` với mã dưới đây để kích hoạt:', inline=False)
                                admin_embed.add_field(name='Mã kích hoạt:', value=f'```\n{activation_code}\n```', inline=False) # Display code here
                                admin_embed.add_field(name='Link kiểm tra yêu cầu (tùy chọn):', value=f'[Xem trạng thái yêu cầu]({API_BASE_URL}/api.php?action=get_request_status&activation_code={activation_code})', inline=False)
                                admin_embed.set_footer(text=f'Yêu cầu từ server: {guild.name}')
                                admin_embed.set_thumbnail(url=member.avatar.url if member.avatar else None)
                                admin_embed.timestamp = discord.utils.utcnow()

                                # Attach the CopyCommandView to the DM
                                copy_view = CopyCommandView(f"/tkichhoat {activation_code}")
                                try:
                                    await guild_member.send(embed=admin_embed, view=copy_view)
                                    print(f"DM sent to admin {guild_member.name} about activation request from {member.name}. Code: {activation_code}")
                                except discord.Forbidden:
                                    print(f"Could not DM admin {guild_member.name}. They might have DMs disabled.")

                        await interaction.followup.send(f'✨ Yêu cầu nạp tiền của bạn đã được gửi thành công! Quản trị viên sẽ kiểm tra giao dịch và kích hoạt tài khoản của bạn. Vui lòng chờ đợi.', ephemeral=True)
                        print(f'Activation request from {member.name} (Game: {linked_username}) created.')

                    else:
                        await interaction.followup.send(f'⚠️ Đã có lỗi xảy ra khi gửi yêu cầu của bạn: {result.get("message", "Lỗi không xác định")}', ephemeral=True)
                        print(f'PHP API error when creating request: {result.get("message")}')
            except aiohttp.ClientError as e:
                print(f'Error calling api.php API (create_activation_request): {e}')
                await interaction.followup.send('⚠️ Đã có lỗi xảy ra khi kết nối với hệ thống xác minh. Vui lòng thử lại sau hoặc liên hệ quản trị viên.', ephemeral=True)


# --- Bot Events ---

@bot.event
async def on_ready():
    """Event when the bot is ready and successfully logged in."""
    print(f'🤖 {bot.user.name} đã sẵn sàng và đang chạy!')
    print(f'🆔 ID Bot: {bot.user.id}')
    activity = discord.Activity(type=discord.ActivityType.watching, name="hệ thống xác minh")
    await bot.change_presence(activity=activity)

    # Sync Slash Commands
    print("🔄 Syncing slash commands...")
    
    # Log tất cả commands hiện có
    all_commands = bot.tree.get_commands()
    print(f"📋 Commands hiện có ({len(all_commands)} commands):")
    for cmd in all_commands:
        print(f"  • /{cmd.name}: {cmd.description}")
    
    try:
        synced = await bot.tree.sync()
        print(f"✅ Slash Commands synchronized successfully!")
        print(f"📊 Đã sync {len(synced)} commands:")
        for cmd in synced:
            print(f"  • /{cmd.name}: {cmd.description}")
    except Exception as e:
        print(f"❌ Error syncing commands: {e}")
        print(f"Error type: {type(e)}")

    print("🔄 Starting verification message setup...")
    
    # Load bot config to get the ID of the persistent verification button message
    bot_config = load_bot_config()
    print(f"📋 Loaded bot config: {bot_config}")

    # Get the verification channel object (payment channel or fallback to welcome channel)
    payment_channel = get_verification_channel()
    if not payment_channel:
        print(f"❌ Error: No suitable channel found for verification. Please check .env file.")
        print(f"🔍 Available channels: {[f'#{c.name} (ID: {c.id})' for c in bot.get_all_channels() if isinstance(c, discord.TextChannel)]}")
        return
    
    print(f"✅ Found verification channel: #{payment_channel.name} (ID: {payment_channel.id})")

    # Initialize the View with the button and add it to the bot for interaction handling
    print("🔄 Setting up verification views...")
    view = VerifyView()
    bot.add_view(view)
    
    # NEW: Add the CopyCommandView for persistent interaction if bot restarts
    # This is important for buttons that are part of permanent messages
    # We add a generic one here, as the specific command_text is dynamic.
    # The to_components method will handle injecting the correct custom_id.
    bot.add_view(CopyCommandView(command_text="placeholder"))
    print("✅ Views initialized successfully")


    # Attempt to find and update the persistent verification message
    verification_message = None
    if bot_config["verification_message_id"]:
        try:
            verification_message = await payment_channel.fetch_message(bot_config["verification_message_id"])
            # Kiểm tra xem message có phải của bot không trước khi edit
            if verification_message.author.id == bot.user.id:
                # If the message exists and is from bot, edit it to ensure the View is updated
                embed_initial = discord.Embed(
                    title='Chào mừng đến với server của chúng tôi!',
                    description='Để có thể truy cập toàn bộ các kênh và tính năng, vui lòng xác minh tài khoản của bạn.',
                    color=discord.Color.green()
                )
                embed_initial.set_thumbnail(url="https://placehold.co/128x128/36A64F/FFFFFF?text=XAC+MINH")
                embed_initial.set_footer(text="Nhấn nút bên dưới để bắt đầu")
                embed_initial.timestamp = discord.utils.utcnow()

                await verification_message.edit(content=f"<@&{UNVERIFIED_ROLE_ID}>", embeds=[embed_initial], view=view)
                print(f"Updated verification message in #{payment_channel.name} (ID: {verification_message.id})")
            else:
                print(f"Verification message exists but is not from bot. Creating new message.")
                bot_config["verification_message_id"] = None
        except (discord.NotFound, discord.Forbidden, discord.HTTPException) as e:
            print(f"Verification message not found or inaccessible (error: {e}). Sending a new message.")
            bot_config["verification_message_id"] = None

    if not verification_message:
        # If not found or ID is invalid, send a new message
        print(f"Creating new verification message in channel: #{payment_channel.name} (ID: {payment_channel.id})")
        try:
            embed_initial = discord.Embed(
                title='Chào mừng đến với server của chúng tôi!',
                description='Để có thể truy cập toàn bộ các kênh và tính năng, vui lòng xác minh tài khoản của bạn.',
                color=discord.Color.green()
            )
            embed_initial.set_thumbnail(url="https://placehold.co/128x128/36A64F/FFFFFF?text=XAC+MINH")
            embed_initial.set_footer(text="Nhấn nút bên dưới để bắt đầu")
            embed_initial.timestamp = discord.utils.utcnow()

            print(f"Attempting to send message to channel #{payment_channel.name}...")
            new_message = await payment_channel.send(content=f"<@&{UNVERIFIED_ROLE_ID}>", embeds=[embed_initial], view=view)
            bot_config["verification_message_id"] = new_message.id
            save_bot_config(bot_config)
            print(f"✅ Successfully sent new verification message in #{payment_channel.name} with ID: {new_message.id}")
        except discord.Forbidden as e:
            print(f"❌ Bot lacks permission to send messages in #{payment_channel.name}. Error: {e}")
            print(f"Please check bot permissions for channel #{payment_channel.name}")
        except discord.HTTPException as e:
            print(f"❌ HTTP error when sending message: {e}")
        except Exception as e:
            print(f"❌ Unexpected error when creating verification message: {e}")
            print(f"Error type: {type(e)}")


@bot.event
async def on_member_join(member):
    """Event when a new member joins the server."""
    print(f'New member joined: {member.name} (ID: {member.id})')

    guild = member.guild

    linked_info = await get_linked_account_info(member.id)
    member_role = guild.get_role(MEMBER_ROLE_ID)

    if linked_info.get('linked') and member_role and member_role in member.roles:
        print(f"{member.name} is already a member in the system. Skipping initial permission restrictions.")
        for channel in guild.channels:
            if isinstance(channel, (discord.TextChannel, discord.VoiceChannel)):
                overwrite = channel.overwrites_for(member)
                if overwrite.view_channel is False:
                    try:
                        await channel.set_permissions(member, overwrite=None)
                    except discord.Forbidden:
                        print(f"Bot lacks permission to clear view permissions for channel {channel.name}.")
        return

    if UNVERIFIED_ROLE_ID and UNVERIFIED_ROLE_ID != guild.id:
        unverified_role = guild.get_role(UNVERIFIED_ROLE_ID)
        if unverified_role:
            await member.add_roles(unverified_role)
            print(f"Assigned '{unverified_role.name}' role to {member.name}")

    # Gửi tin nhắn chào mừng và hướng dẫn đến kênh xác minh qua DM
    verification_channel = get_verification_channel()
    channel_mention = f"<#{verification_channel.id}>" if verification_channel else "kênh xác minh"
    
    welcome_dm_embed = discord.Embed(
        title=f'Chào mừng đến với {guild.name}!',
        description='Để có thể truy cập toàn bộ các kênh và tính năng trong server, bạn cần xác minh tài khoản.\n\n'
                    f'Vui lòng truy cập {channel_mention} và nhấn nút "Xác minh tại đây" để nhận hướng dẫn chi tiết.',
        color=discord.Color.blue()
    )
    welcome_dm_embed.set_footer(text='Hệ thống Xác minh Thành viên')
    welcome_dm_embed.timestamp = discord.utils.utcnow()

    try:
        await member.send(embed=welcome_dm_embed)
        print(f"DM chào mừng đã được gửi đến {member.name} ({member.id}).")
    except discord.Forbidden:
        welcome_channel = guild.get_channel(WELCOME_CHANNEL_ID)
        if welcome_channel:
            verification_channel = get_verification_channel()
            channel_mention = f"<#{verification_channel.id}>" if verification_channel else "kênh xác minh"
            await welcome_channel.send(f'Chào mừng {member.mention} đã đến với server! Vui lòng truy cập {channel_mention} và nhấn nút "Xác minh tại đây" để nhận hướng dẫn chi tiết (Nếu bạn không nhận được DM, vui lòng kiểm tra cài đặt riêng tư của bạn).')
            print(f"Could not DM {member.name}, sent welcome message to channel {welcome_channel.name}.")
    except Exception as e:
        print(f"Error sending welcome DM to {member.name}: {e}")


    # Đặt quyền xem kênh mặc định cho thành viên mới (chỉ cho phép welcome và verification channels)
    verification_channel = get_verification_channel()
    allowed_channel_ids = [WELCOME_CHANNEL_ID]
    if verification_channel:
        allowed_channel_ids.append(verification_channel.id)
    
    for channel in guild.channels:
        if isinstance(channel, (discord.TextChannel, discord.VoiceChannel)):
            overwrite = channel.overwrites_for(member) 
            
            if channel.id not in allowed_channel_ids:
                overwrite.update(view_channel=False) 
                try:
                    await channel.set_permissions(member, overwrite=overwrite)
                except discord.Forbidden:
                    print(f"Bot lacks permission to set 'View Channel' for channel {channel.name}.")
            else:
                overwrite.update(view_channel=True)
                try:
                    await channel.set_permissions(member, overwrite=overwrite)
                except discord.Forbidden:
                    print(f"Bot lacks permission to set 'View Channel' for channel {channel.name}.")

# --- Slash Commands ---

@bot.tree.command(name="txacnhan_nap", description="Yêu cầu kích hoạt thành viên sau khi nạp tiền.")
async def txacnhan_nap_slash_command(interaction: discord.Interaction):
    """Lệnh Slash để người dùng bắt đầu quá trình liên kết và xác nhận nạp tiền."""
    member = interaction.user
    guild = interaction.guild

    if not guild:
        await interaction.response.send_message('Lệnh này chỉ có thể được sử dụng trong một server Discord.', ephemeral=True)
        return

    if guild.get_role(MEMBER_ROLE_ID) in member.roles:
        await interaction.response.send_message('Bạn đã là thành viên rồi!', ephemeral=True)
        return

    # Kiểm tra số lần thử và cảnh báo
    attempts_info = check_user_attempts(member.id)
    if attempts_info["count"] >= WARNING_THRESHOLD:
        # Gửi cảnh báo đến admin
        await send_warning_to_admins(guild, member, f"User đã thử xác minh {attempts_info['count']} lần liên tiếp")
        
        embed = discord.Embed(
            title="⚠️ Cảnh báo",
            description="Bạn đã thử xác minh quá nhiều lần. Vui lòng liên hệ admin để được hỗ trợ.",
            color=discord.Color.red()
        )
        embed.add_field(name="Số lần thử", value=f"`{attempts_info['count']}`", inline=True)
        embed.add_field(name="Lần cuối", value=f"`{attempts_info['last_attempt'].strftime('%H:%M:%S %d/%m/%Y') if attempts_info['last_attempt'] else 'N/A'}`", inline=True)
        embed.set_footer(text="Hệ thống cảnh báo tự động")
        embed.timestamp = discord.utils.utcnow()
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    # Defer response trước để tránh timeout
    await interaction.response.defer(ephemeral=True)
    
    linked_info = await get_linked_account_info(member.id)
    if not linked_info.get('linked'):
        embed = discord.Embed(
            title="🔗 Chưa liên kết tài khoản game",
            description="Bạn cần liên kết tài khoản game trước khi có thể xác nhận nạp tiền.",
            color=discord.Color.orange()
        )
        embed.add_field(
            name="Cách liên kết:",
            value="Sử dụng lệnh `/link <tên_tài_khoản_game>` để liên kết tài khoản game của bạn.",
            inline=False
        )
        embed.add_field(
            name="Ví dụ:",
            value="`/link PlayerName123`",
            inline=False
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
    else:
        # Gửi modal cho xác nhận nạp tiền (tạm thời sử dụng embed thay vì modal)
        embed = discord.Embed(
            title="💰 Xác nhận nạp tiền",
            description=f"Tài khoản game **{linked_info.get('username')}** đã được liên kết.\n\nVui lòng sử dụng nút 'Xác minh tại đây' trong channel để tiếp tục quá trình xác nhận nạp tiền.",
            color=discord.Color.blue()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

@bot.tree.command(name="link", description="Liên kết tài khoản Discord với tài khoản game.")
@app_commands.describe(game_username="Tên tài khoản game của bạn.")
async def link_slash_command(interaction: discord.Interaction, game_username: str):
    """Lệnh Slash để user liên kết tài khoản game."""
    await interaction.response.defer(ephemeral=True)
    
    # Kiểm tra xem user đã liên kết chưa
    existing_link = await get_linked_account_info(interaction.user.id)
    if existing_link.get('linked'):
        embed = discord.Embed(
            title="⚠️ Đã liên kết",
            description=f"Tài khoản Discord của bạn đã được liên kết với tài khoản game **{existing_link.get('username')}**.",
            color=discord.Color.yellow()
        )
        embed.add_field(
            name="Nếu muốn thay đổi:",
            value="Liên hệ admin để thay đổi liên kết.",
            inline=False
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        return
    
    # Kiểm tra tên game username
    if not game_username.strip() or len(game_username.strip()) < 3:
        await interaction.followup.send("❌ Tên tài khoản game không hợp lệ. Vui lòng nhập tên có ít nhất 3 ký tự.", ephemeral=True)
        return
    
    game_username = game_username.strip()
    
    # Tạm thời sử dụng mock data khi API chưa hoạt động
    try:
        # Lưu vào mock data (tạm thời)
        mock_links = {
            interaction.user.id: {
                'linked': True,
                'username': game_username,
                'admin': 0,
                'ban': 0
            }
        }
        
        embed = discord.Embed(
            title="✅ Liên kết thành công! (Offline Mode)",
            description=f"Tài khoản Discord của bạn đã được liên kết với tài khoản game **{game_username}**.",
            color=discord.Color.green()
        )
        embed.add_field(
            name="Bước tiếp theo:",
            value="Sử dụng lệnh `/txacnhan_nap` để xác nhận nạp tiền.",
            inline=False
        )
        embed.add_field(
            name="⚠️ Lưu ý:",
            value="Bot đang chạy ở chế độ offline. Liên kết sẽ mất khi restart bot.",
            inline=False
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        
        # Gọi API thật (nếu có thể)
        async with aiohttp.ClientSession() as session:
            try:
                payload = {
                    'discord_id': interaction.user.id,
                    'username': game_username
                }
                async with session.post(LINK_ACCOUNT_API_ENDPOINT, data=payload, timeout=aiohttp.ClientTimeout(total=5)) as response:
                    if response.content_type == 'application/json':
                        result = await response.json()
                        if result.get('status') == 'success':
                            print(f"✅ API link successful for user {interaction.user.id}")
                        else:
                            print(f"⚠️ API link failed: {result.get('message')}")
                    else:
                        print(f"⚠️ API returned non-JSON response: {response.content_type}")
            except Exception as e:
                print(f"⚠️ API call failed (expected): {e}")
                    
    except Exception as e:
        print(f"Error in link command: {e}")
        await interaction.followup.send("❌ Lỗi kết nối. Vui lòng thử lại sau.", ephemeral=True)

@bot.tree.command(name="tkichhoat", description="Kích hoạt thành viên sau khi xác nhận nạp tiền (dành cho Admin).")
@app_commands.describe(activation_code="Mã kích hoạt từ yêu cầu của người dùng.")
async def tkichhoat_slash_command(interaction: discord.Interaction, activation_code: str):
    """Lệnh Slash dành cho admin để kích hoạt thành viên."""
    await interaction.response.defer(ephemeral=True)

    guild = interaction.guild
    if not guild:
        await interaction.followup.send('Lệnh này chỉ có thể được sử dụng trong một server Discord.', ephemeral=True)
        return

    auth_result = await get_linked_account_info(interaction.user.id)
    if not auth_result.get('linked') or auth_result.get('admin') != 1:
        await interaction.followup.send('Bạn không có quyền sử dụng lệnh này hoặc tài khoản Discord của bạn chưa được liên kết với tài khoản admin trong hệ thống.', ephemeral=True)
        return

    if not activation_code.strip():
        await interaction.followup.send('Vui lòng cung cấp mã kích hoạt. Ví dụ: `ACT-1234567890-abcd`', ephemeral=True)
        return

    async with aiohttp.ClientSession() as session:
        try:
            payload = {
                'action': 'activate_request',
                'activation_code': activation_code,
            }
            async with session.post(MAIN_API_ENDPOINT, json=payload) as response:
                result = await response.json()

                if result.get('status') == 'success':
                    data = result.get('data', {})
                    user_id_str = data.get('user_id')
                    username_discord = data.get('username')
                    linked_username = data.get('linked_username')
                    guild_id_str = data.get('guild_id')

                    guild = bot.get_guild(int(guild_id_str))
                    if not guild:
                        await interaction.followup.send('Không tìm thấy server liên quan đến yêu cầu này.', ephemeral=True)
                        return

                    member = guild.get_member(int(user_id_str))
                    if not member:
                        try:
                            member = await guild.fetch_member(int(user_id_str))
                        except discord.NotFound:
                            await interaction.followup.send(f'Không tìm thấy thành viên {username_discord} liên quan đến mã kích hoạt này hoặc thành viên đã rời server.', ephemeral=True)
                            return
                        except discord.Forbidden:
                            await interaction.followup.send('Bot lacks permission to fetch this member.', ephemeral=True)
                            return

                    member_role = guild.get_role(MEMBER_ROLE_ID)

                    if member_role:
                        await member.add_roles(member_role)

                        for channel in guild.channels:
                            if isinstance(channel, (discord.TextChannel, discord.VoiceChannel)):
                                overwrite = channel.overwrites_for(member)
                                if overwrite.view_channel is False:
                                    try:
                                        await channel.set_permissions(member, overwrite=None)
                                    except discord.Forbidden:
                                        print(f"Bot lacks permission to clear view permissions for channel {channel.name}.")

                        # Cập nhật thống kê admin
                        stats = load_security_stats()
                        stats["admin_activations"] += 1
                        save_security_stats(stats)
                        
                        await interaction.followup.send(f'✅ Đã kích hoạt thành công **{member.name}** (Tài khoản game: `{linked_username}`)!', ephemeral=True)
                        try:
                            member_activated_embed = discord.Embed(
                                title="Chúc mừng! Tài khoản của bạn đã được kích hoạt!",
                                description=f"Bạn giờ là thành viên chính thức của server **{guild.name}**.",
                                color=discord.Color.green()
                            )
                            member_activated_embed.add_field(name="Tài khoản game liên kết:", value=f"`{linked_username}`", inline=False)
                            member_activated_embed.add_field(name="Quyền truy cập:", value="Bạn có thể truy cập tất cả các kênh và tính năng trong server.", inline=False)
                            member_activated_embed.set_footer(text="Cảm ơn bạn đã tham gia!")
                            member_activated_embed.timestamp = discord.utils.utcnow()
                            await member.send(embed=member_activated_embed)
                        except discord.Forbidden:
                            print(f"Could not DM {member.name}. They might have DMs disabled.")

                        print(f'Admin {interaction.user.name} activated {member.name} (Game: {linked_username}) with code {activation_code}.')
                    else:
                        await interaction.followup.send('⚠️ Không tìm thấy role "Thành viên". Vui lòng kiểm tra lại cấu hình bot.', ephemeral=True)
                        print(f'Member role not found with ID: {MEMBER_ROLE_ID}')
                else:
                    await interaction.followup.send(f'⚠️ Không thể kích hoạt: {result.get("message", "Lỗi không xác định")}', ephemeral=True)
                    print(f'PHP API error when activating: {result.get("message")}')
        except aiohttp.ClientError as e:
            print(f'Error calling api.php API (activate_request): {e}')
            await interaction.followup.send('⚠️ Đã có lỗi xảy ra khi kết nối với hệ thống xác minh. Vui lòng thử lại sau hoặc liên hệ quản trị viên.', ephemeral=True)

# --- LỆNH QUẢN LÝ ADMIN NÂNG CAO ---
@bot.tree.command(name="add_bot_admin", description="Thêm người dùng vào danh sách Bot Admin")
@app_commands.describe(user="Người dùng cần thêm vào danh sách admin")
async def add_bot_admin(interaction: discord.Interaction, user: discord.Member):
    """Lệnh thêm người dùng vào danh sách Bot Admin."""
    # Chỉ Server Administrator mới có thể thêm Bot Admin
    if not hasattr(interaction.user, 'guild_permissions') or not interaction.user.guild_permissions.administrator:
        embed = discord.Embed(
            title="❌ Không có quyền",
            description="Chỉ **Server Administrator** mới có thể thêm Bot Admin!",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    user_id = user.id
    
    if user_id in bot_admin_list:
        embed = discord.Embed(
            title="⚠️ Thông báo",
            description=f"**{user.mention}** đã có trong danh sách Bot Admin rồi!",
            color=discord.Color.yellow()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    bot_admin_list.add(user_id)
    
    embed = discord.Embed(
        title="✅ Thêm Bot Admin thành công",
        description=f"Đã thêm **{user.mention}** vào danh sách Bot Admin!",
        color=discord.Color.green()
    )
    embed.add_field(name="Người thực hiện", value=f"{interaction.user.mention}", inline=True)
    embed.add_field(name="Tổng số Bot Admin", value=f"`{len(bot_admin_list)}`", inline=True)
    embed.timestamp = discord.utils.utcnow()
    
    await interaction.response.send_message(embed=embed, ephemeral=True)
    print(f"Admin {interaction.user.name} added {user.name} to bot admin list")

@bot.tree.command(name="remove_bot_admin", description="Xóa người dùng khỏi danh sách Bot Admin")
@app_commands.describe(user="Người dùng cần xóa khỏi danh sách admin")
async def remove_bot_admin(interaction: discord.Interaction, user: discord.Member):
    """Lệnh xóa người dùng khỏi danh sách Bot Admin."""
    # Chỉ Server Administrator mới có thể xóa Bot Admin
    if not hasattr(interaction.user, 'guild_permissions') or not interaction.user.guild_permissions.administrator:
        embed = discord.Embed(
            title="❌ Không có quyền",
            description="Chỉ **Server Administrator** mới có thể xóa Bot Admin!",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    user_id = user.id
    
    if user_id not in bot_admin_list:
        embed = discord.Embed(
            title="⚠️ Thông báo",
            description=f"**{user.mention}** không có trong danh sách Bot Admin!",
            color=discord.Color.yellow()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    bot_admin_list.remove(user_id)
    
    embed = discord.Embed(
        title="✅ Xóa Bot Admin thành công",
        description=f"Đã xóa **{user.mention}** khỏi danh sách Bot Admin!",
        color=discord.Color.green()
    )
    embed.add_field(name="Người thực hiện", value=f"{interaction.user.mention}", inline=True)
    embed.add_field(name="Tổng số Bot Admin", value=f"`{len(bot_admin_list)}`", inline=True)
    embed.timestamp = discord.utils.utcnow()
    
    await interaction.response.send_message(embed=embed, ephemeral=True)
    print(f"Admin {interaction.user.name} removed {user.name} from bot admin list")

@bot.tree.command(name="list_bot_admin", description="Xem danh sách Bot Admin")
async def list_bot_admin(interaction: discord.Interaction):
    """Lệnh xem danh sách Bot Admin."""
    if not bot_admin_list:
        embed = discord.Embed(
            title="📋 Danh sách Bot Admin",
            description="Hiện tại không có Bot Admin nào trong danh sách.",
            color=discord.Color.blue()
        )
        embed.add_field(name="Lưu ý", value="Chỉ Server Administrator mới có thể thêm/xóa Bot Admin", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    admin_mentions = []
    for admin_id in bot_admin_list:
        member = interaction.guild.get_member(admin_id)
        if member:
            admin_mentions.append(f"• {member.mention} (`{member.name}`)")
        else:
            admin_mentions.append(f"• <@{admin_id}> (Không trong server)")
    
    embed = discord.Embed(
        title="📋 Danh sách Bot Admin",
        description="\n".join(admin_mentions),
        color=discord.Color.blue()
    )
    embed.add_field(name="Tổng số", value=f"`{len(bot_admin_list)}` Bot Admin", inline=True)
    embed.add_field(name="Lưu ý", value="Server Administrator luôn có quyền Bot Admin", inline=False)
    embed.timestamp = discord.utils.utcnow()
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

# --- LỆNH THỐNG KÊ VÀ BÁO CÁO ---
@bot.tree.command(name="security_stats", description="Xem thống kê bảo mật")
@app_commands.check(is_bot_admin_check)
async def security_stats(interaction: discord.Interaction):
    """Lệnh xem thống kê bảo mật."""
    stats = load_security_stats()
    
    embed = discord.Embed(
        title="📊 Thống Kê Bảo Mật",
        description="Thống kê chi tiết về hoạt động xác minh",
        color=discord.Color.blue()
    )
    
    # Thống kê tổng quan
    success_rate = (stats["successful_verifications"] / stats["total_verifications"] * 100) if stats["total_verifications"] > 0 else 0
    
    embed.add_field(
        name="📈 Tổng quan",
        value=f"**Tổng số xác minh:** `{stats['total_verifications']}`\n"
              f"**Thành công:** `{stats['successful_verifications']}`\n"
              f"**Thất bại:** `{stats['failed_attempts']}`\n"
              f"**Tỷ lệ thành công:** `{success_rate:.1f}%`",
        inline=False
    )
    
    # Thống kê hôm nay
    today = datetime.now().strftime('%Y-%m-%d')
    if today in stats["daily_stats"]:
        today_stats = stats["daily_stats"][today]
        today_success_rate = (today_stats["successful"] / today_stats["verifications"] * 100) if today_stats["verifications"] > 0 else 0
        
        embed.add_field(
            name="📅 Hôm nay",
            value=f"**Xác minh:** `{today_stats['verifications']}`\n"
                  f"**Thành công:** `{today_stats['successful']}`\n"
                  f"**Thất bại:** `{today_stats['failed']}`\n"
                  f"**Tỷ lệ thành công:** `{today_success_rate:.1f}%`",
            inline=True
        )
    
    # Thống kê admin
    embed.add_field(
        name="👑 Admin",
        value=f"**Kích hoạt:** `{stats['admin_activations']}`\n"
              f"**Bot Admin:** `{len(bot_admin_list)}`",
        inline=True
    )
    
    embed.set_footer(text="Hệ thống thống kê bảo mật")
    embed.timestamp = discord.utils.utcnow()
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="check_user", description="Kiểm tra thông tin user")
@app_commands.describe(user="Người dùng cần kiểm tra")
@app_commands.check(is_bot_admin_check)
async def check_user(interaction: discord.Interaction, user: discord.Member):
    """Lệnh kiểm tra thông tin user."""
    user_id = user.id
    
    # Kiểm tra thông tin liên kết
    linked_info = await get_linked_account_info(user_id)
    
    # Kiểm tra thống kê user
    stats = load_security_stats()
    user_stats = stats["user_stats"].get(str(user_id), {"attempts": 0, "successful": 0, "last_attempt": None})
    
    # Kiểm tra số lần thử
    attempts_info = check_user_attempts(user_id)
    
    embed = discord.Embed(
        title=f"🔍 Thông Tin User: {user.name}",
        description=f"ID: `{user_id}`",
        color=discord.Color.blue()
    )
    
    # Thông tin liên kết
    if linked_info.get('linked'):
        embed.add_field(
            name="🔗 Tài khoản liên kết",
            value=f"**Username:** `{linked_info.get('username', 'N/A')}`\n"
                  f"**Admin:** `{'Có' if linked_info.get('admin') == 1 else 'Không'}`\n"
                  f"**Banned:** `{'Có' if linked_info.get('ban') == 1 else 'Không'}`",
            inline=True
        )
    else:
        embed.add_field(
            name="🔗 Tài khoản liên kết",
            value="❌ Chưa liên kết",
            inline=True
        )
    
    # Thống kê xác minh
    success_rate = (user_stats["successful"] / user_stats["attempts"] * 100) if user_stats["attempts"] > 0 else 0
    embed.add_field(
        name="📊 Thống kê xác minh",
        value=f"**Tổng lần thử:** `{user_stats['attempts']}`\n"
              f"**Thành công:** `{user_stats['successful']}`\n"
              f"**Tỷ lệ thành công:** `{success_rate:.1f}%`",
        inline=True
    )
    
    # Thông tin cảnh báo
    if attempts_info["count"] >= WARNING_THRESHOLD:
        embed.add_field(
            name="🚨 Cảnh báo",
            value=f"**Số lần thử gần đây:** `{attempts_info['count']}`\n"
                  f"**Lần cuối:** `{attempts_info['last_attempt'].strftime('%H:%M:%S %d/%m/%Y') if attempts_info['last_attempt'] else 'N/A'}`",
            inline=False
        )
        embed.color = discord.Color.red()
    
    # Vai trò trong server
    roles = [role.mention for role in user.roles if role.name != "@everyone"]
    embed.add_field(
        name="🎭 Vai trò",
        value=", ".join(roles) if roles else "Không có vai trò đặc biệt",
        inline=False
    )
    
    embed.set_footer(text=f"Kiểm tra bởi {interaction.user.name}")
    embed.timestamp = discord.utils.utcnow()
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

# Run the bot
if DISCORD_TOKEN:
    bot.run(DISCORD_TOKEN)
else:
    print("Error: DISCORD_TOKEN not found in .env file. Please check.")

