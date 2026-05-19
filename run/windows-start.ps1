# 在 Windows 上启动全栈（无需 exe，需 Docker Desktop）
# 用法（PowerShell，仓库根目录）: .\run\windows-start.ps1

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $RepoRoot

$Launcher = Join-Path $RepoRoot "packaging\windows\launcher.py"
if (Test-Path $Launcher) {
    python $Launcher @args
    exit $LASTEXITCODE
}

$EnvFile = Join-Path $RepoRoot ".env.dev"
if (-not (Test-Path $EnvFile)) {
    Write-Error "缺少 .env.dev"
}
docker compose --env-file $EnvFile up -d --build
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "打开 http://127.0.0.1:8080"
Start-Process "http://127.0.0.1:8080"
