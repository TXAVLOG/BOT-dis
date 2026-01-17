"""
TXAFormat - Thiên Lam Tông Formatting Utilities
Chuẩn hóa hiển thị số, thời gian, ngày tháng theo phong cách tu tiên.
"""
from datetime import datetime
import pytz

VN_TZ = pytz.timezone('Asia/Ho_Chi_Minh')

class TXAFormat:
    """Công cụ định dạng chuẩn Thiên Lam Tông"""
    
    @staticmethod
    def pad2(num: int) -> str:
        """Format số thành 2 chữ số (00-99)"""
        return f"{int(num):02d}"
    
    @staticmethod
    def number(num: int, sep: str = ",") -> str:
        """Format số có dấu phân cách hàng nghìn"""
        return f"{int(num):,}".replace(",", sep)
    
    @staticmethod
    def time(seconds: int) -> str:
        """Format giây thành HH:MM:SS hoặc MM:SS"""
        if seconds is None or seconds < 0:
            return "--:--"
        
        h, remainder = divmod(int(seconds), 3600)
        m, s = divmod(remainder, 60)
        
        if h > 0:
            return f"{TXAFormat.pad2(h)}:{TXAFormat.pad2(m)}:{TXAFormat.pad2(s)}"
        return f"{TXAFormat.pad2(m)}:{TXAFormat.pad2(s)}"
    
    @staticmethod
    def duration_detail(seconds: int) -> str:
        """Format thời gian chi tiết: X giờ Y phút Z giây"""
        if seconds is None or seconds < 0:
            return "Không xác định"
        
        h, remainder = divmod(int(seconds), 3600)
        m, s = divmod(remainder, 60)
        
        parts = []
        if h > 0:
            parts.append(f"{TXAFormat.pad2(h)} giờ")
        if m > 0:
            parts.append(f"{TXAFormat.pad2(m)} phút")
        parts.append(f"{TXAFormat.pad2(s)} giây")
        
        return " ".join(parts)

    @staticmethod
    def remaining_detail(seconds: int) -> str:
        """Format thời gian còn lại: X phút Y giây hoặc còn Z giây"""
        if seconds is None or seconds <= 0:
            return "Hoàn tất"
        
        m, s = divmod(int(seconds), 60)
        if m > 0:
            return f"{TXAFormat.pad2(m)} phút {TXAFormat.pad2(s)} giây"
        return f"còn {TXAFormat.pad2(s)} giây"
    
    @staticmethod
    def date(dt: datetime = None) -> str:
        """Format ngày theo chuẩn Việt Nam: DD/MM/YYYY"""
        if dt is None:
            dt = datetime.now(VN_TZ)
        return dt.strftime("%d/%m/%Y")
    
    @staticmethod
    def datetime_full(dt: datetime = None) -> str:
        """Format đầy đủ: HH:MM:SS DD/MM/YYYY"""
        if dt is None:
            dt = datetime.now(VN_TZ)
        return dt.strftime("%H:%M:%S %d/%m/%Y")
    
    @staticmethod
    def relative_time(target_dt: datetime) -> str:
        """Tính thời gian còn lại/đã qua so với hiện tại"""
        now = datetime.now(VN_TZ)
        if target_dt.tzinfo is None:
            target_dt = VN_TZ.localize(target_dt)
        
        diff = target_dt - now
        total_seconds = int(diff.total_seconds())
        
        if total_seconds < 0:
            return "Đã qua"
        
        return TXAFormat.duration_detail(total_seconds)
    
    @staticmethod
    def progress_bar(percent: float, length: int = 12, style: str = "default") -> str:
        """Tạo thanh tiến trình động với màu sắc thay đổi"""
        percent = max(0, min(100, percent))
        filled = int(length * percent / 100)
        
        if style == "music":
            # Thanh nhạc: Đỏ trên Tím theo ý đạo hữu
            return "🟥" * filled + "💜" * (length - filled)
        else:
            # Mặc định: Xanh -> Vàng -> Cam -> Đỏ
            if percent < 25:
                emoji = "🟩"
            elif percent < 50:
                emoji = "🟨"
            elif percent < 75:
                emoji = "🟧"
            else:
                emoji = "🟥"
            return emoji * filled + "⬜" * (length - filled)
    
    @staticmethod
    def truncate(text: str, max_len: int = 50, suffix: str = "...") -> str:
        """Cắt ngắn text nếu quá dài"""
        if len(text) <= max_len:
            return text
        return text[:max_len - len(suffix)] + suffix

    @staticmethod
    def data_speed(speed_in_bytes: float) -> str:
        """Format tốc độ dữ liệu: B/s, KB/s, MB/s, GB/s"""
        if not speed_in_bytes:
            return "--"
        
        for unit in ['B/s', 'KB/s', 'MB/s', 'GB/s']:
            if speed_in_bytes < 1024.0:
                return f"{speed_in_bytes:.1f} {unit}"
            speed_in_bytes /= 1024.0
        
        return f"{speed_in_bytes:.1f} GB/s"
