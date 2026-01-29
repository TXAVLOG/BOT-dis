$ErrorActionPreference = "Continue"

# --- CONFIG ---
$BotFile = "bot.py"
$VenvDir = "venv"
$PythonExe = "python.exe"
if (Test-Path "$VenvDir\Scripts\python.exe") {
    $PythonExe = "$VenvDir\Scripts\python.exe"
}

# --- SETUP VENV (Nếu chưa có) ---
if (-not (Test-Path $VenvDir)) {
    Write-Host "⚠️ Đang khởi tạo môi trường ($VenvDir)..." -ForegroundColor Yellow
    python -m venv $VenvDir
    if (Test-Path "requirements.txt") {
        Write-Host "📦 Đang cài library..." -ForegroundColor Cyan
        & "$VenvDir\Scripts\pip.exe" install -r requirements.txt
    }
}

# --- RUN LOOP ---
Function Start-Bot {
    Write-Host "Running $BotFile..." -ForegroundColor Green
    $proc = Start-Process -FilePath $PythonExe -ArgumentList $BotFile -PassThru -NoNewWindow
    return $proc
}

Clear-Host
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "🛡️  THIÊN LAM TÔNG - WIN AUTO RELOAD" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

$botProcess = Start-Bot

# Watcher
$watcher = New-Object System.IO.FileSystemWatcher
$watcher.Path = $PSScriptRoot
$watcher.IncludeSubdirectories = $true
$watcher.EnableRaisingEvents = $true
$watcher.NotifyFilter = [System.IO.NotifyFilters]::LastWrite -bor [System.IO.NotifyFilters]::FileName

# Extensions to watch
$validExt = @(".py", ".json")

while ($true) {
    $result = $watcher.WaitForChanged([System.IO.WatcherChangeTypes]::All, 1000)
    if ($result.TimedOut) {
        # Check if bot died
        if ($botProcess.HasExited) {
            Write-Host "⚠️ Bot đã tắt. Đang khởi động lại..." -ForegroundColor Red
            $botProcess = Start-Bot
        }
        continue
    }
    
    # Filter extension
    $ext = [System.IO.Path]::GetExtension($result.Name)
    if ($validExt -contains $ext -and $result.Name -notmatch "venv|__pycache__|\.git") {
        Write-Host "✨ Phát hiện thay đổi: $($result.Name)" -ForegroundColor Yellow
        Write-Host "🔄 Reloading..." -ForegroundColor Magenta
        
        if (-not $botProcess.HasExited) {
            Stop-Process -Id $botProcess.Id -Force -ErrorAction SilentlyContinue
        }
        Start-Sleep -Milliseconds 500
        Clear-Host
        $botProcess = Start-Bot
    }
}
