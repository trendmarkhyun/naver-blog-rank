# GitHub에 place-rank 저장소로 업로드
# 사용: powershell -ExecutionPolicy Bypass -File scripts\push_to_github.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$Remote = "https://github.com/trendmarkhyun/place-rank.git"

Write-Host "프로젝트 경로: $Root"
Write-Host "원격 저장소: $Remote"

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host "Git이 설치되어 있지 않습니다. https://git-scm.com/download/win"
    exit 1
}

if (-not (Test-Path ".git")) {
    git init
}

$remoteExists = git remote 2>$null | Select-String -Pattern "^origin$"
if ($remoteExists) {
    git remote set-url origin $Remote
} else {
    git remote add origin $Remote
}

git add .
git status

$status = git status --porcelain
if (-not $status) {
    Write-Host "커밋할 변경 사항이 없습니다."
} else {
    git commit -m "Add naver place rank monitor"
}

git branch -M main
git push -u origin main

Write-Host ""
Write-Host "완료: https://github.com/trendmarkhyun/place-rank"
