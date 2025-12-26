#!/bin/bash

# ==========================================================
# 🚀 THIEN LAM BOT - AUTO RELOAD SCRIPT (TRIỆT ĐỂ)
# ==========================================================

BOT_FILE="bot.py"
WATCH_EXTENSIONS=".*\.py$|.*\.sh$"
EXCLUDE_PATTERN="\.git/|.*\.json|cache/|__pycache__/|\.log|\.env"

# 1. Kiểm tra "pháp bảo" (Dependencies)
check_deps() {
    if ! command -v inotifywait &> /dev/null; then
        echo -e "\e[1;31m[!] Thiếu inotify-tools. Đang tự động cài đặt...\e[0m"
        sudo apt update && sudo apt install inotify-tools -y
    fi
    
    if ! command -v python3 &> /dev/null; then
        echo -e "\e[1;31m[!] Thiếu python3. Vui lòng kiểm tra lại VPS!\e[0m"
        exit 1
    fi
}

# 2. Quản lý linh lực (Processes)
run_bot() {
    # Kiểm tra xem có instance nào đang chạy không để dọn dẹp
    pkill -f "python3 $BOT_FILE" > /dev/null 2>&1
    
    echo -e "\e[1;32m[$(date +'%H:%M:%S')]\e[0m ⚔️ Đang khởi động pháp trận $BOT_FILE..."
    # Chạy bot và lưu PID
    python3 "$BOT_FILE" &
    BOT_PID=$!
}

stop_bot() {
    if [ ! -z "$BOT_PID" ]; then
        echo -e "\e[1;31m[$(date +'%H:%M:%S')]\e[0m 🛡️ Thu hồi pháp lực (PID: $BOT_PID)..."
        kill $BOT_PID 2>/dev/null
        wait $BOT_PID 2>/dev/null
        BOT_PID=""
    fi
    # Dọn dẹp triệt để các session python thừa
    pkill -f "python3 $BOT_FILE" > /dev/null 2>&1
}

# 3. Lễ nghi kết thúc (Cleanup)
trap "stop_bot; echo -e '\n\e[1;35m[!] Pháp trận đã đóng.\e[0m'; exit" SIGINT SIGTERM

# --- KHỞI ĐẦU ---
clear
echo -e "\e[1;36m====================================================\e[0m"
echo -e "\e[1;36m🛡️  THIÊN LAM TÔNG - HỆ THỐNG TỰ ĐỘNG TÁI THIẾT v2.0\e[0m"
echo -e "\e[1;36m====================================================\e[0m"

check_deps
run_bot

echo -e "\e[1;34m[$(date +'%H:%M:%S')]\e[0m 👀 Đang rình rập biến động (.py, .sh)..."

# 4. Vòng lặp quan sát (Watcher Loop)
while true; do
    # Chờ đợi sự kiện, debounce 2 giây để tránh bão sự kiện (như git pull)
    inotifywait -r -e modify,create,delete,move --exclude "$EXCLUDE_PATTERN" . > /dev/null 2>&1
    
    # Khi có thay đổi
    echo -e "\e[1;33m[$(date +'%H:%M:%S')]\e[0m ✨ Linh địa biến động! Đang chờ linh khí ổn định (3s)..."
    sleep 3
    
    stop_bot
    run_bot
    echo -e "\e[1;34m[$(date +'%H:%M:%S')]\e[0m 👀 Tiếp tục theo dõi..."
done

