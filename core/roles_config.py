# Danh sách tất cả quyền Discord có thể gán cho Role
# Tham khảo: https://discord.com/developers/docs/topics/permissions
ALL_DISCORD_PERMISSIONS = [
    # General Server Permissions
    "view_channel",             # Xem kênh
    "manage_channels",          # Quản lý kênh
    "manage_roles",             # Quản lý vai trò/quyền
    "manage_emojis_and_stickers", # Quản lý emoji & sticker
    "manage_webhooks",          # Quản lý webhook
    "manage_guild",             # Quản lý server
    "create_instant_invite",    # Tạo lời mời
    "change_nickname",          # Đổi biệt danh
    "manage_nicknames",         # Quản lý biệt danh người khác
    "kick_members",             # Kick thành viên
    "ban_members",              # Ban thành viên
    "moderate_members",         # Timeout thành viên (Muted)
    "view_audit_log",           # Xem nhật ký kiểm toán

    # Text Permissions
    "send_messages",            # Gửi tin nhắn
    "send_messages_in_threads", # Gửi tin trong thread
    "create_public_threads",    # Tạo thread công khai
    "create_private_threads",   # Tạo thread riêng tư
    "embed_links",              # Nhúng liên kết
    "attach_files",             # Đính kèm file
    "add_reactions",            # Thêm reaction
    "use_external_emojis",      # Dùng emoji server khác
    "use_external_stickers",    # Dùng sticker server khác
    "mention_everyone",         # Mention @everyone
    "manage_messages",          # Xóa/ghim tin nhắn người khác
    "manage_threads",           # Quản lý thread
    "read_message_history",     # Đọc lịch sử tin nhắn
    "send_tts_messages",        # Gửi tin Text-to-Speech
    "use_application_commands", # Dùng lệnh slash

    # Voice Permissions
    "connect",                  # Kết nối voice
    "speak",                    # Nói trong voice
    "stream",                   # Phát video/stream
    "use_embedded_activities",  # Hoạt động nhúng (Discord Activity)
    "use_voice_activation",     # Dùng Voice Activity Detection
    "priority_speaker",         # Nói ưu tiên
    "mute_members",             # Tắt mic người khác
    "deafen_members",           # Tắt tai người khác
    "move_members",             # Di chuyển thành viên voice
    "request_to_speak",         # Yêu cầu nói (Stage)

    # Events & Stage
    "manage_events",            # Quản lý sự kiện

    # Admin
    "administrator",            # Toàn quyền
]

# Cấu hình Role theo Cảnh Giới - Quyền hạn tăng dần
# daily_xp_limit: Giới hạn XP kiếm được mỗi ngày (từ nhiệm vụ, tu luyện, điểm danh...)
# permissions: Quyền Discord được cấp khi đạt cảnh giới này (Kế thừa từ cảnh dưới)
DEFAULT_RANKS = {
    "Phàm Nhân": {
        "min": 1, "max": 9,
        "color": 0x808080, "emoji": "🌱",
        "daily_xp_limit": 500,
        "permissions": {
            "view_channel": True,
            "read_message_history": True,
            "use_application_commands": True,
        }
    },
    "Luyện Khí": {
        "min": 10, "max": 19,
        "color": 0x00FF00, "emoji": "💨",
        "daily_xp_limit": 800,
        "permissions": {
            "send_messages": True,
            "add_reactions": True,
        }
    },
    "Trúc Cơ": {
        "min": 20, "max": 29,
        "color": 0x00FFFF, "emoji": "🔷",
        "daily_xp_limit": 1200,
        "permissions": {
            "attach_files": True,
            "embed_links": True,
            "use_external_emojis": True,
        }
    },
    "Kim Đan": {
        "min": 30, "max": 39,
        "color": 0xFFD700, "emoji": "💊",
        "daily_xp_limit": 1600,
        "permissions": {
            "connect": True,
            "speak": True,
            "use_voice_activation": True,
        }
    },
    "Nguyên Anh": {
        "min": 40, "max": 49,
        "color": 0xFF00FF, "emoji": "👶",
        "daily_xp_limit": 2000,
        "permissions": {
            "stream": True,
            "use_embedded_activities": True,
        }
    },
    "Hóa Thần": {
        "min": 50, "max": 69,
        "color": 0xFF0000, "emoji": "🔥",
        "daily_xp_limit": 2500,
        "permissions": {
            "change_nickname": True,
            "create_instant_invite": True,
            "priority_speaker": True,
        }
    },
    "Luyện Hư": {
        "min": 70, "max": 89,
        "color": 0x9400D3, "emoji": "🌌",
        "daily_xp_limit": 3000,
        "permissions": {
            "create_public_threads": True,
            "send_messages_in_threads": True,
        }
    },
    "Hợp Thể": {
        "min": 90, "max": 109,
        "color": 0xFF1493, "emoji": "⚡",
        "daily_xp_limit": 3500,
        "permissions": {
            "use_external_stickers": True,
            "mention_everyone": True,
        }
    },
    "Đại Thừa": {
        "min": 110, "max": 149,
        "color": 0xFFFFFF, "emoji": "✨",
        "daily_xp_limit": 4000,
        "permissions": {
            "create_private_threads": True,
            "manage_threads": True,
        }
    },
    "Độ Kiếp": {
        "min": 150, "max": 199,
        "color": 0x8B0000, "emoji": "⚔️",
        "daily_xp_limit": 5000,
        "permissions": {
            "manage_messages": True,
            "request_to_speak": True,
        }
    },
    "Chân Tiên": {
        "min": 200, "max": 299,
        "color": 0x00CED1, "emoji": "🌟",
        "daily_xp_limit": 6000,
        "permissions": {
            "mute_members": True,
            "deafen_members": True,
        }
    },
    "Huyền Tiên": {
        "min": 300, "max": 499,
        "color": 0x4169E1, "emoji": "💫",
        "daily_xp_limit": 7000,
        "permissions": {
            "move_members": True,
            "manage_events": True,
        }
    },
    "Kim Tiên": {
        "min": 500, "max": 999,
        "color": 0xFFD700, "emoji": "👑",
        "daily_xp_limit": 8000,
        "permissions": {
            "manage_nicknames": True,
            "moderate_members": True,
        }
    },
    "Đại La Kim Tiên": {
        "min": 1000, "max": 9999,
        "color": 0xFF4500, "emoji": "🔱",
        "daily_xp_limit": 9000,
        "permissions": {
            "manage_channels": True,
            "view_audit_log": True,
        }
    },
    "Chuẩn Thánh": {
        "min": 10000, "max": 99999,
        "color": 0xF0E68C, "emoji": "🌞",
        "daily_xp_limit": 10000,
        "permissions": {
            "kick_members": True,
            "manage_webhooks": True,
            "manage_emojis_and_stickers": True,
        }
    },
    "Thánh Nhân": {
        "min": 100000, "max": 999999,
        "color": 0xFFFFFF, "emoji": "☀️",
        "daily_xp_limit": 999999,
        "permissions": {
            "ban_members": True,
            "manage_roles": True,
            "manage_guild": True,
            "administrator": True,
        }
    },
}


class RoleConfig:
    """Class quản lý cấu hình Role theo Cảnh Giới"""
    
    @staticmethod
    def get_role_data(rank_name: str) -> dict:
        """Lấy dữ liệu Role cho một cảnh giới cụ thể"""
        return DEFAULT_RANKS.get(rank_name, DEFAULT_RANKS["Phàm Nhân"])
    
    @staticmethod
    def get_all_roles() -> dict:
        """Lấy toàn bộ cấu hình Role"""
        return DEFAULT_RANKS

    @staticmethod
    def get_cumulative_permissions(rank_name: str, ranks_dict: dict = None) -> dict:
        """
        Lấy tổng hợp tất cả quyền từ cảnh thấp đến cảnh hiện tại.
        Cảnh cao hơn kế thừa quyền từ cảnh thấp hơn.
        """
        if ranks_dict is None:
            ranks_dict = DEFAULT_RANKS
            
        target_info = ranks_dict.get(rank_name)
        if not target_info:
            return {}
        
        target_min = target_info["min"]
        cumulative_perms = {}
        
        # Sắp xếp theo min layer tăng dần
        sorted_ranks = sorted(ranks_dict.items(), key=lambda x: x[1]["min"])
        
        for rname, rinfo in sorted_ranks:
            if rinfo["min"] <= target_min:
                cumulative_perms.update(rinfo.get("permissions", {}))
        
        return cumulative_perms
    
    @staticmethod
    def get_all_permission_names() -> list:
        """Lấy danh sách tên tất cả quyền Discord hỗ trợ"""
        return ALL_DISCORD_PERMISSIONS
