$ErrorActionPreference = "Stop"

# Tự động cấp quyền chạy script cho Process hiện tại (tránh lỗi UnauthorizedAccess tạm thời)
try {
    Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process -Force -ErrorAction SilentlyContinue
} catch {}

# Chỉ chạy trên Windows
if ($IsWindows -or $env:OS -match "Windows_NT") {
    $VenvName = "venv"
    $ReqFile = "requirements.txt"
    $VenvPath = Join-Path $PSScriptRoot $VenvName
    $ActivateScript = Join-Path $VenvPath "Scripts\Activate.ps1"

    # Kiểm tra xem folder venv có tồn tại không
    if (-not (Test-Path $VenvPath)) {
        Write-Host "⚠️ Chưa tìm thấy môi trường ảo ($VenvName). Đang tự động khởi tạo..." -ForegroundColor Yellow
        
        # Tạo venv
        try {
            python -m venv $VenvName
            Write-Host "✅ Đã tạo venv thành công!" -ForegroundColor Green
        } catch {
            Write-Host "❌ Lỗi không thể tạo venv: $_" -ForegroundColor Red
            return
        }

        # Cài đặt requirements nếu có
        if (Test-Path $ReqFile) {
            Write-Host "📦 Đang cài đặt thư viện từ $ReqFile..." -ForegroundColor Cyan
            $PipPath = Join-Path $VenvPath "Scripts\pip.exe"
            & $PipPath install -r $ReqFile
            Write-Host "✅ Cài đặt thư viện hoàn tất!" -ForegroundColor Green
        }
    }

    # Kích hoạt venv
    if (Test-Path $ActivateScript) {
        if (-not $env:VIRTUAL_ENV) {
            Write-Host "🔌 Đang kích hoạt môi trường ảo..." -ForegroundColor Cyan
            # Dùng Dot-Sourcing để activate trong scope hiện tại
            . $ActivateScript
            Write-Host "✨ Môi trường ảo đã sẵn sàng: $env:VIRTUAL_ENV" -ForegroundColor Green
        }
    } else {
        Write-Host "❌ Không tìm thấy script kích hoạt: $ActivateScript" -ForegroundColor Red
    }
}
