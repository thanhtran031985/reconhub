# ==============================================================================
# ReconHub — Backup Scheduled Task Setup (Task Scheduler)
# Tự động sao lưu SQLite database mỗi ngày lúc 01:00 AM (giữ 14 bản sao lưu)
# ==============================================================================

[CmdletBinding()]
param (
    [string]$Time = "01:00",
    [switch]$Uninstall
)

$ErrorActionPreference = "Stop"

$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Error "LỖI: Bạn phải chạy PowerShell với quyền Administrator."
    exit 1
}

$TaskName = "ReconHub-Daily-Backup"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path (Join-Path $ScriptDir "..\..") | Select-Object -ExpandProperty Path
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if ($Uninstall) {
    Write-Host "Đang hủy đăng ký tác vụ $TaskName..." -ForegroundColor Cyan
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "Đã gỡ bỏ tác vụ sao lưu tự động." -ForegroundColor Green
    exit 0
}

Write-Host "======================================================" -ForegroundColor Cyan
Write-Host " ReconHub — Thiết lập Tác vụ Sao lưu Tự động" -ForegroundColor Cyan
Write-Host " Tác vụ:       $TaskName" -ForegroundColor White
Write-Host " Thời gian:    Hàng ngày lúc $Time" -ForegroundColor White
Write-Host " Lệnh:         $VenvPython -m app.cli backup" -ForegroundColor White
Write-Host " Thư mục gốc:  $ProjectRoot" -ForegroundColor White
Write-Host "======================================================" -ForegroundColor Cyan

# Tạo Action
$Action = New-ScheduledTaskAction -Execute $VenvPython -Argument "-m app.cli backup" -WorkingDirectory $ProjectRoot

# Tạo Trigger (Hàng ngày lúc $Time)
$Trigger = New-ScheduledTaskTrigger -Daily -At $Time

# Cấu hình Settings
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 2)

# Đăng ký tác vụ chạy dưới tài khoản SYSTEM hoặc user hiện tại
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue 2>$null
Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Description "Tự động sao lưu cơ sở dữ liệu ReconHub hàng ngày (giữ 14 bản sao lưu)" -User "NT AUTHORITY\SYSTEM" | Out-Null

Write-Host "-> Đã đăng ký tác vụ '$TaskName' thành công!" -ForegroundColor Green
Get-ScheduledTask -TaskName $TaskName | Format-Table -AutoSize

