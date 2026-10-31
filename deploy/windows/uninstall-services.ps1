# ==============================================================================
# ReconHub — Windows Service Uninstallation Script
# ==============================================================================

[CmdletBinding()]
param (
    [string]$NssmPath = ""
)

$ErrorActionPreference = "Stop"

$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Error "LỖI: Bạn phải chạy PowerShell với quyền Administrator."
    exit 1
}

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path (Join-Path $ScriptDir "..\..") | Select-Object -ExpandProperty Path

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
    Write-Error "Không tìm thấy nssm.exe để gỡ bỏ dịch vụ."
    exit 1
}

Write-Host "Đang gỡ bỏ dịch vụ ReconHub-Web..." -ForegroundColor Cyan
& $NssmPath stop "ReconHub-Web" 2>$null
& $NssmPath remove "ReconHub-Web" confirm 2>$null

Write-Host "Đang gỡ bỏ dịch vụ ReconHub-Worker..." -ForegroundColor Cyan
& $NssmPath stop "ReconHub-Worker" 2>$null
& $NssmPath remove "ReconHub-Worker" confirm 2>$null

Write-Host "Đã gỡ bỏ toàn bộ dịch vụ ReconHub trên Windows." -ForegroundColor Green

