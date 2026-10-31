# ==============================================================================
# ReconHub — Windows Service Installation Script (NSSM)
# Yêu cầu: Quyền Administrator (Run as Administrator)
# ==============================================================================

[CmdletBinding()]
param (
    [string]$Port = "8050",
    [string]$Threads = "4",
    [string]$NssmPath = ""
)

$ErrorActionPreference = "Stop"

# 1. Kiểm tra quyền Administrator
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Error "LỖI: Bạn phải chạy PowerShell với quyền Administrator (Run as Administrator)."
    exit 1
}

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path (Join-Path $ScriptDir "..\..") | Select-Object -ExpandProperty Path
$LogsDir = Join-Path $ProjectRoot "logs"
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

Write-Host "======================================================" -ForegroundColor Cyan
Write-Host " ReconHub — Cài đặt Windows Services" -ForegroundColor Cyan
Write-Host " Project Root: $ProjectRoot" -ForegroundColor White
Write-Host " Web Port:     $Port" -ForegroundColor White
Write-Host " Logs Dir:     $LogsDir" -ForegroundColor White
Write-Host "======================================================" -ForegroundColor Cyan

# Kiểm tra VirtualEnv
if (-not (Test-Path $VenvPython)) {
    Write-Error "Không tìm thấy môi trường Python tại '$VenvPython'. Vui lòng chạy 'uv sync --extra prod' trước khi cài đặt service."
    exit 1
}

# Tạo thư mục log nếu chưa có
if (-not (Test-Path $LogsDir)) {
    New-Item -ItemType Directory -Path $LogsDir -Force | Out-Null
    Write-Host "-> Đã tạo thư mục logs: $LogsDir" -ForegroundColor Green
}

# Tìm công cụ nssm
if ([string]::IsNullOrWhiteSpace($NssmPath)) {
    $nssmCmd = Get-Command "nssm.exe" -ErrorAction SilentlyContinue
    if ($nssmCmd) {
        $NssmPath = $nssmCmd.Source
    } elseif (Test-Path (Join-Path $ScriptDir "nssm.exe")) {
        $NssmPath = (Join-Path $ScriptDir "nssm.exe")
    } elseif (Test-Path (Join-Path $ProjectRoot "nssm.exe")) {
        $NssmPath = (Join-Path $ProjectRoot "nssm.exe")
    }
}

if (-not $NssmPath -or -not (Test-Path $NssmPath)) {
    Write-Host ""
    Write-Host "CHÚ Ý: Không tìm thấy nssm.exe trên hệ thống!" -ForegroundColor Yellow
    Write-Host "Vui lòng tải NSSM (Non-Sucking Service Manager) từ https://nssm.cc/download" -ForegroundColor Yellow
    Write-Host "và đặt file nssm.exe (bản win64) vào thư mục deploy\windows\ hoặc thêm vào PATH." -ForegroundColor Yellow
    Write-Host "Hoặc chạy lại lệnh kèm tham số: .\install-services.ps1 -NssmPath C:\path\to\nssm.exe" -ForegroundColor Yellow
    Write-Host ""
    exit 1
}

Write-Host "-> Sử dụng NSSM: $NssmPath" -ForegroundColor Green

# 2. Cài đặt Dịch vụ Web: ReconHub-Web
$WebServiceName = "ReconHub-Web"
Write-Host "`n[1/2] Đang cài đặt dịch vụ $WebServiceName..." -ForegroundColor Cyan

# Dừng và gỡ nếu đã tồn tại
& $NssmPath stop $WebServiceName 2>$null
& $NssmPath remove $WebServiceName confirm 2>$null

$WaitressArgs = "-m waitress --port=$Port --threads=$Threads app.wsgi:server"
& $NssmPath install $WebServiceName $VenvPython $WaitressArgs
& $NssmPath set $WebServiceName AppDirectory $ProjectRoot
& $NssmPath set $WebServiceName Description "ReconHub Web Application Server (Dash/Waitress)"
& $NssmPath set $WebServiceName Start SERVICE_AUTO_START
& $NssmPath set $WebServiceName AppStdout (Join-Path $LogsDir "web.log")
& $NssmPath set $WebServiceName AppStderr (Join-Path $LogsDir "web_error.log")
& $NssmPath set $WebServiceName AppRotateFiles 1
& $NssmPath set $WebServiceName AppRotateOnline 1
& $NssmPath set $WebServiceName AppRotateBytes 10485760 # 10MB
& $NssmPath set $WebServiceName AppRestartDelay 5000 # 5s restart on crash

Write-Host "-> Đã cài đặt dịch vụ $WebServiceName thành công!" -ForegroundColor Green

# 3. Cài đặt Dịch vụ Worker: ReconHub-Worker
$WorkerServiceName = "ReconHub-Worker"
Write-Host "`n[2/2] Đang cài đặt dịch vụ $WorkerServiceName..." -ForegroundColor Cyan

& $NssmPath stop $WorkerServiceName 2>$null
& $NssmPath remove $WorkerServiceName confirm 2>$null

$WorkerArgs = "-m worker"
& $NssmPath install $WorkerServiceName $VenvPython $WorkerArgs
& $NssmPath set $WorkerServiceName AppDirectory $ProjectRoot
& $NssmPath set $WorkerServiceName Description "ReconHub Background Job Worker"
& $NssmPath set $WorkerServiceName Start SERVICE_AUTO_START
& $NssmPath set $WorkerServiceName AppStdout (Join-Path $LogsDir "worker.log")
& $NssmPath set $WorkerServiceName AppStderr (Join-Path $LogsDir "worker_error.log")
& $NssmPath set $WorkerServiceName AppRotateFiles 1
& $NssmPath set $WorkerServiceName AppRotateOnline 1
& $NssmPath set $WorkerServiceName AppRotateBytes 10485760 # 10MB
& $NssmPath set $WorkerServiceName AppRestartDelay 5000 # 5s restart on crash

Write-Host "-> Đã cài đặt dịch vụ $WorkerServiceName thành công!" -ForegroundColor Green

# 4. Khởi động các dịch vụ
Write-Host "`n-> Khởi động các dịch vụ..." -ForegroundColor Cyan
& $NssmPath start $WebServiceName
& $NssmPath start $WorkerServiceName

Start-Sleep -Seconds 2

Get-Service -Name $WebServiceName, $WorkerServiceName | Format-Table -AutoSize

Write-Host "`nHoàn tất! Truy cập ứng dụng tại http://localhost:$Port" -ForegroundColor Green

