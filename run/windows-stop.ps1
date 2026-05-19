# 停止 Windows 上的 Docker Compose 全栈
# 用法: .\run\windows-stop.ps1

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $RepoRoot

$EnvFile = Join-Path $RepoRoot ".env.dev"
docker compose --env-file $EnvFile down
