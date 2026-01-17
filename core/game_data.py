
class CultivationData:
    """Dữ liệu nhiệm vụ và tài nguyên cốt truyện Luyện Khí Mười Vạn Năm"""
    
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

    @staticmethod
    def get_random_mission():
        import random
        return random.choice(CultivationData.MISSIONS)
