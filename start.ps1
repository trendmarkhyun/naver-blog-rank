$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$venvStreamlit = Join-Path $PSScriptRoot ".venv\Scripts\streamlit.exe"
$cloudflared = Join-Path $PSScriptRoot "bin\cloudflared.exe"
$logFile = Join-Path $PSScriptRoot "tunnel.log"
$urlFile = Join-Path $PSScriptRoot "접속주소.txt"

if (-not (Test-Path $venvStreamlit)) {
    Write-Host ""
    Write-Host " [오류] setup.bat 을 먼저 실행하세요." -ForegroundColor Red
    Read-Host "Enter 키를 누르면 종료"
    exit 1
}

if (-not (Test-Path $cloudflared)) {
    Write-Host ""
    Write-Host " [오류] cloudflared 가 없습니다. setup.bat 을 다시 실행하세요." -ForegroundColor Red
    Read-Host "Enter 키를 누르면 종료"
    exit 1
}

$env:STREAMLIT_BROWSER_GATHER_USAGE_STATS = "false"
$env:STREAMLIT_SERVER_HEADLESS = "true"

# .env 에서 터널 토큰 읽기 (있으면 고정 도메인 사용)
$tunnelToken = $null
$envFile = Join-Path $PSScriptRoot ".env"
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        if ($_ -match '^\s*CLOUDFLARE_TUNNEL_TOKEN\s*=\s*(.+)\s*$') {
            $tunnelToken = $matches[1].Trim().Trim('"').Trim("'")
        }
    }
}

Write-Host ""
Write-Host " 서버 시작 중..." -ForegroundColor Cyan

$streamlit = Start-Process -FilePath $venvStreamlit `
    -ArgumentList "run", "app.py", "--server.port", "8501", "--server.headless", "true", "--server.address", "127.0.0.1" `
    -WindowStyle Hidden -PassThru

Start-Sleep -Seconds 4

if ($streamlit.HasExited) {
    Write-Host " [오류] Streamlit 실행 실패" -ForegroundColor Red
    Read-Host "Enter 키를 누르면 종료"
    exit 1
}

Remove-Item $logFile -ErrorAction SilentlyContinue

if ($tunnelToken) {
    Write-Host " 고정 도메인 터널 연결 중..." -ForegroundColor Cyan
    $cfArgs = @("tunnel", "run", "--token", $tunnelToken)
} else {
    Write-Host " 공개 접속 주소 생성 중..." -ForegroundColor Cyan
    $cfArgs = @("tunnel", "--url", "http://127.0.0.1:8501")
}

$cf = Start-Process -FilePath $cloudflared `
    -ArgumentList $cfArgs `
    -RedirectStandardError $logFile `
    -WindowStyle Hidden -PassThru

$publicUrl = $null
$deadline = (Get-Date).AddSeconds(45)

while ((Get-Date) -lt $deadline) {
    Start-Sleep -Seconds 1

    if ($tunnelToken -and (Test-Path $envFile)) {
        Get-Content $envFile | ForEach-Object {
            if ($_ -match '^\s*PUBLIC_URL\s*=\s*(https?://\S+)') {
                $publicUrl = $matches[1].Trim().Trim('"').Trim("'")
            }
        }
        if ($publicUrl) { break }
    }

    if (Test-Path $logFile) {
        $log = Get-Content $logFile -Raw -ErrorAction SilentlyContinue
        if ($log -match '(https://[a-z0-9-]+\.trycloudflare\.com)') {
            $publicUrl = $matches[1]
            break
        }
    }

    if ($cf.HasExited) { break }
}

Write-Host ""
Write-Host " ============================================" -ForegroundColor Green
if ($publicUrl) {
    Write-Host "  접속 주소: $publicUrl" -ForegroundColor Green
    Write-Host " ============================================" -ForegroundColor Green
    Set-Content -Path $urlFile -Value $publicUrl -Encoding UTF8
    Start-Process $publicUrl
} elseif ($tunnelToken) {
    Write-Host "  고정 도메인 터널 실행 중" -ForegroundColor Green
    Write-Host "  .env 의 PUBLIC_URL 로 접속하세요" -ForegroundColor Green
    Write-Host " ============================================" -ForegroundColor Green
} else {
    Write-Host "  접속 주소 생성 실패" -ForegroundColor Yellow
    Write-Host "  PC에서 http://localhost:8501 로 접속하세요" -ForegroundColor Yellow
    Write-Host " ============================================" -ForegroundColor Green
    Start-Process "http://localhost:8501"
}

Write-Host ""
Write-Host " 종료: 이 창을 닫거나 Ctrl+C" -ForegroundColor DarkGray
Write-Host ""

try {
    Wait-Process -Id $cf.Id
} finally {
    if (-not $streamlit.HasExited) {
        Stop-Process -Id $streamlit.Id -Force -ErrorAction SilentlyContinue
    }
    if (-not $cf.HasExited) {
        Stop-Process -Id $cf.Id -Force -ErrorAction SilentlyContinue
    }
}
