#!/bin/bash

# ==========================================================
# 🚀 THIEN LAM BOT - AUTO RELOAD SCRIPT (UBUNTU VPS)
# ==========================================================
# Yêu cầu: sudo apt install inotify-tools
# Cách chạy: chmod +x autoload.sh && ./autoload.sh

BOT_FILE="bot.py"
# Loại trừ các file database và git để tránh loop vô tận khi bot ghi file
EXCLUDE_PATTERN="\.git|\.json|cache/|__pycache__|\.log"

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
    fi
}

# Xử lý khi nhấn Ctrl+C
trap "stop_bot; exit" SIGINT SIGTERM

# Khởi động lần đầu
run_bot

echo -e "\e[1;34m[$(date +'%H:%M:%S')]\e[0m 👀 Đang theo dõi thay đổi trong linh địa..."

while true; do
    # Chờ đợi sự thay đổi trong thư mục (trừ các file bị loại trừ)
    inotifywait -r -e modify,create,delete,move --exclude "$EXCLUDE_PATTERN" . > /dev/null 2>&1
    
    echo -e "\e[1;33m[$(date +'%H:%M:%S')]\e[0m ✨ Pháp trận có biến động! Đang tái thiết..."
    stop_bot
    sleep 2
    run_bot
done
