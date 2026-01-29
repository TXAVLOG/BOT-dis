
class CultivationData:
    """Dữ liệu nhiệm vụ và tài nguyên cốt truyện Luyện Khí Mười Vạn Năm"""
    
    # --- MISSIONS ---
    MISSIONS = [
        "Quét dọn lá rụng tại Thiên Lam Phong",
        "Chăm sóc vườn linh dược của đệ tử ngoại môn",
        "Tiếp đón khách nhân đến thăm Tông Môn",
        "Xuống núi mua rượu cho Từ Dương Lão Tổ",
        "Nghe giảng đạo tại Chân Truyền Điện",
        "Luyện tập Ngự Kiếm Thuật căn bản",
        "Sao chép Thiên Lam Tâm Pháp 100 lần",
        "Tu sửa tường bao quanh Tông Môn",
        "Cho linh thú ăn tại Ngự Thú Viên",
        "Vận chuyển linh thạch từ hầm mỏ",
        "Tham gia tuần tra đêm quanh Tông Môn",
        "Giúp đỡ sư tỷ luyện chế Trúc Cơ Đan",
        "Tìm kiếm tung tích của Thiên Bồng Tông",
        "Điều tra dị tượng tại Hắc Phong Lâm",
        "Thu thập Thiên Lôi Trúc",
        "Săn bắt Yêu thú cấp thấp quấy nhiễu dân làng",
        "Tìm lại ngọc bội bị mất cho Tiểu Sư Muội",
        "Thử thuốc cho Luyện Đan Sư (Nguy hiểm nhẹ)",
        "Thiền định dưới thác nước Thiên Sơn",
        "Lau chùi tượng Tổ Sư Khai Sơn",
        "Mang thư tín đến Vạn Kiếm Tông",
        "Thu thập sương sớm trên lá sen",
        "Bắt đom đóm linh quang vào ban đêm",
        "Trồng thêm Trúc Tím ở hậu sơn",
        "Pha trà mời các vị Trưởng Lão",
        "Sắp xếp lại Tàng Kinh Các",
        "Mài kiếm cho các sư huynh đệ",
        "Hái nấm linh chi ngàn năm (Giả)",
        "Thách đấu lôi đài với đệ tử cùng cấp",
        "Quan sát tinh tượng dự đoán thời tiết",
        "Nấu ăn cho nhà bếp Tông Môn",
        "Vớt cá tại Hồ Bán Nguyệt",
        "Tìm kiếm nguyên liệu cho trận pháp hộ tông",
        "Hộ tống xe hàng của thương hội",
        "Giải quyết mâu thuẫn giữa các đệ tử mới",
        "Đuổi khỉ trộm đào tiên",
        "Vẽ bùa chú trừ tà cơ bản",
        "Rèn luyện thể lực: Chạy quanh núi 10 vòng",
        "Học cách nhận biết các loại thảo dược",
        "Tìm hiểu lịch sử 10 vạn năm của Lão Tổ",
        "Thăm hỏi các vị tiền bối ẩn cư",
        "Bảo trì phi thuyền của Tông Môn",
        "Chế tạo pháo hoa cho lễ hội",
        "Viết báo cáo tu luyện hàng tháng",
        "Dọn dẹp tuyết đọng trên mái nhà",
        "Trông coi cổng sơn môn 2 canh giờ",
        "Luyện tập điều khiển hơi thở",
        "Hỗ trợ đệ tử bị thương tại Dược Đường",
        "Tìm kiếm quặng sắt tinh tại khe núi",
        "Đối thơ với sư huynh văn hay chữ tốt"
    ]

    # --- SHOP ITEMS ---
    ITEMS = {
        "ruou_ngon": {"name": "Rượu Tiên Thiên Lam", "price": 500, "desc": "Rượu ngon tăng 1000 EXP. Hạn dùng: 1 giờ.", "effect": {"exp": 1000}, "emoji": "🍶", "duration": 3600},
        "dan_truc_co": {"name": "Trúc Cơ Đan", "price": 2000, "desc": "Đan dược tăng 5000 EXP. Hạn dùng: 2 giờ.", "effect": {"exp": 5000}, "emoji": "💊", "duration": 7200},
        "linh_thach_tiny": {"name": "Linh Thạch Vụn", "price": 100, "desc": "Tăng 200 EXP. Hạn dùng: 30 phút.", "effect": {"exp": 200}, "emoji": "💎", "duration": 1800},
        "tu_tieu_hac": {"name": "Linh Thú Tiểu Hắc", "price": 50000, "desc": "Tăng 20% tỉ lệ thành công nhiệm vụ. Hạn dùng: 5 phút.", "effect": {"mission_buff": 20}, "emoji": "🦅", "duration": 300},
        "kiem_ri_set": {"name": "Kiếm Rỉ Sét", "price": 100000, "desc": "Tăng x2 sát thương khi đấu pháp. Hạn dùng: 10 phút.", "effect": {"combat_buff": 1.0}, "emoji": "🗡️", "duration": 600},
        "thien_am_cam": {"name": "Thiên Âm Cầm", "price": 25000, "desc": "Cổ cầm ngàn năm, tăng 20% EXP khi nghe nhạc. Hạn dùng: 3 giờ.", "effect": {"music_buff": 0.2}, "emoji": "🎻", "duration": 10800},
        "khi_van_phu": {"name": "Tiên Thiên Khí Vận", "price": 50000, "desc": "Tăng 20% may mắn nhận Linh Thạch khi nghe nhạc. Hạn dùng: 1 giờ.", "effect": {"luck_buff": 20}, "emoji": "🍀", "duration": 3600},
    }

    # --- KUNG FU (CÔNG PHÁP) ---
    KUNG_FU = {
        "thien_lam_tam_phap": {
            "name": "Thiên Lam Tâm Pháp", 
            "desc": "Công pháp trấn phái Thiên Lam Tông, tăng 20% EXP khi tu luyện.", 
            "buff": {"exp_mult": 1.2}, 
            "price": 0, # Mặc định có sẵn cho Thiên Lam Tông
            "emoji": "🧘"
        },
        "cuu_u_kiem_phap": {
            "name": "Cửu U Kiếm Pháp", 
            "desc": "U minh kiếm ý, tăng 30% sát thương Đấu Pháp.", 
            "buff": {"dmg_mult": 1.3}, 
            "price": 10000,
            "emoji": "⚔️"
        },
        "van_tuong_quy_nguyen": {
            "name": "Vạn Tượng Quy Nguyên", 
            "desc": "Thu nạp vạn vật, tăng 50% Linh Thạch kiếm được.", 
            "buff": {"stone_mult": 1.5}, 
            "price": 20000,
            "emoji": "🌀"
        },
        "bat_bien_kiem_the": {
            "name": "Bất Biến Kiếm Thế", 
            "desc": "Thủ như bàn thạch, giảm 20% sát thương nhận vào.", 
            "buff": {"def_mult": 0.8}, 
            "price": 15000,
            "emoji": "🛡️"
        }
    }

    # --- COMBAT FALLBACKS ---
    COMBAT_NARRATIVES = [
        "{a} tung một chưởng lực mãnh liệt, khí thế như rồng bay phượng múa hướng về {b}!",
        "{a} sử dụng ngự kiếm thuật, thanh kiếm hóa thành vệt sáng xé toạc không gian tấn công {b}!",
        "{a} vận chuyển linh lực toàn thân, tạo ra một cơn lốc xoáy quanh {b}!",
        "{a} xuất hiện chớp nhoáng sau lưng {b}, tung một đòn đánh hiểm hóc!",
        "{a} niệm chú, hàng loạt băng tiễn lao vút về phía {b}!"
    ]

    @staticmethod
    def get_random_mission():
        import random
        return random.choice(CultivationData.MISSIONS)
