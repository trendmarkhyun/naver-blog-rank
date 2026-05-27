# Windows 작업 스케줄러 등록 스크립트
# 사용: powershell -ExecutionPolicy Bypass -File scripts/install_scheduler.ps1

param(
    [string]$TaskName = "NaverPlaceRankCollector",
    [string]$ScheduleTime = "09:00",
    [string]$ProjectRoot = ""
)

$ErrorActionPreference = "Stop"

if (-not $ProjectRoot) {
    $ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
}

$ProjectRoot = (Resolve-Path $ProjectRoot).Path
$PythonExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$ScriptPath = Join-Path $ProjectRoot "scripts\run_collector.py"
$LogDir = Join-Path $ProjectRoot "logs"

if (-not (Test-Path $PythonExe)) {
    Write-Host "가상환경 Python을 찾을 수 없습니다: $PythonExe"
    Write-Host "먼저 python -m venv .venv && pip install -r requirements.txt 를 실행하세요."
    exit 1
}

if (-not (Test-Path $ScriptPath)) {
    Write-Host "수집 스크립트를 찾을 수 없습니다: $ScriptPath"
    exit 1
}

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

$ActionArgs = "`"$ScriptPath`" --config `"$ProjectRoot\config\targets.yaml`""
$Action = New-ScheduledTaskAction `
    -Execute $PythonExe `
    -Argument $ActionArgs `
    -WorkingDirectory $ProjectRoot

$Trigger = New-ScheduledTaskTrigger -Daily -At $ScheduleTime

$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2)

$Existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($Existing) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "기존 작업 '$TaskName'을(를) 제거했습니다."
}

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Description "네이버 플레이스 순위 자동 수집" | Out-Null

Write-Host "작업 스케줄러 등록 완료"
Write-Host "  작업 이름 : $TaskName"
Write-Host "  실행 시각 : 매일 $ScheduleTime"
Write-Host "  프로젝트  : $ProjectRoot"
Write-Host ""
Write-Host "수동 테스트: $PythonExe $ScriptPath"
