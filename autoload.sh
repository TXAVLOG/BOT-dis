#!/bin/bash

# ==========================================================
# 🚀 THIEN LAM BOT - AUTO RELOAD SCRIPT (UBUNTU VPS)
# ==========================================================
# Yêu cầu: sudo apt install inotify-tools
# Cách chạy: chmod +x autoload.sh && ./autoload.sh

BOT_FILE="bot.py"
# Chỉ theo dõi các file thực sự quan trọng
WATCH_EXTENSIONS=".*\.py$|.*\.sh$"
# Loại trừ tuyệt đối các thư mục dữ liệu và git
EXCLUDE_PATTERN="\.git/|.*\.json|cache/|__pycache__/|\.log|\.env"

run_bot() {
    echo -e "\e[1;32m[$(date +'%H:%M:%S')]\e[0m ⚔️ Đang khởi động pháp trận..."
    python3 "$BOT_FILE" &
    BOT_PID=$!
}

stop_bot() {
    if [ ! -z "$BOT_PID" ]; then
        echo -e "\e[1;31m[$(date +'%H:%M:%S')]\e[0m 🛡️ Đang thu hồi pháp lực (PID: $BOT_PID)..."
        kill $BOT_PID 2>/dev/null
        wait $BOT_PID 2>/dev/null
        BOT_PID=""
    fi
}

# Xử lý khi nhấn Ctrl+C
trap "stop_bot; exit" SIGINT SIGTERM

# Khởi động lần đầu
run_bot

echo -e "\e[1;34m[$(date +'%H:%M:%S')]\e[0m 👀 Đang theo dõi biến động (.py, .sh)..."

while true; do
    # Chờ đợi sự thay đổi, chỉ lọc những file kết thúc bằng .py hoặc .sh
    # Sử dụng ống dẫn để xử lý sự kiện tránh bị lỡ
    inotifywait -r -e modify,create,delete,move --exclude "$EXCLUDE_PATTERN" . | while read line; do
        # Kiểm tra xem file thay đổi có phải là code không
        if [[ "$line" =~ \.py|\.sh ]]; then
            echo -e "\e[1;33m[$(date +'%H:%M:%S')]\e[0m ✨ Phát hiện thay đổi: $line"
            echo -e "\e[1;33m[$(date +'%H:%M:%S')]\e[0m ⏳ Đợi linh khí ổn định (2s)..."
            sleep 2
            stop_bot
            run_bot
            echo -e "\e[1;34m[$(date +'%H:%M:%S')]\e[0m 👀 Tiếp tục theo dõi..."
            break # Thoát vòng lặp while read để quay lại inotifywait mới
        fi
    done
done

