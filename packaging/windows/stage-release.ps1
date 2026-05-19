# 将 ChallengeDemo.exe 与 Docker 运行所需文件打入便携 ZIP
param(
    [string]$ExePath = "",
    [string]$OutDir = "",
    [string]$Version = ""
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path

if (-not $ExePath) {
    $ExePath = Join-Path $RepoRoot "dist\ChallengeDemo.exe"
}
if (-not (Test-Path $ExePath)) {
    throw "找不到启动器: $ExePath"
}

if (-not $Version) {
    $Version = (git -C $RepoRoot describe --tags --always 2>$null)
}
if (-not $Version) { $Version = "dev" }
$Version = $Version -replace '^v', '' -replace '[\\/:*?"<>|]', '-'

if (-not $OutDir) {
    $OutDir = Join-Path $RepoRoot "dist"
}
$StageName = "challenge-demo-windows-$Version"
$StageRoot = Join-Path $OutDir $StageName
$ZipPath = "$StageRoot.zip"

if (Test-Path $StageRoot) { Remove-Item $StageRoot -Recurse -Force }
if (Test-Path $ZipPath) { Remove-Item $ZipPath -Force }
New-Item -ItemType Directory -Path $StageRoot | Out-Null

Copy-Item $ExePath (Join-Path $StageRoot "ChallengeDemo.exe")

$CopyItems = @(
    "docker-compose.yml",
    "docker-compose.backend.yml",
    "docker-compose.frontend.yml",
    "docker-compose.kafka.yml",
    "Dockerfile",
    "main.py",
    "requirements.txt",
    ".env.dev",
    ".env.prod",
    "README.md"
)

foreach ($item in $CopyItems) {
    $src = Join-Path $RepoRoot $item
    if (Test-Path $src) {
        Copy-Item $src (Join-Path $StageRoot $item)
    }
}

# 后端与前端源码（Docker 构建用）
$RoboDirs = @(
    @{ Src = "backend"; Dst = "backend" },
    @{ Src = "frontend"; Dst = "frontend" }
)

$excludeDirNames = @(
    "node_modules", "dist", ".git", "__pycache__", ".pytest_cache",
    ".mypy_cache", ".venv", "venv", "build"
)

function Copy-ProjectTree {
    param([string]$SrcRoot, [string]$DstRoot)
    New-Item -ItemType Directory -Force -Path $DstRoot | Out-Null
    Get-ChildItem -Path $SrcRoot -Force | ForEach-Object {
        if ($excludeDirNames -contains $_.Name) { return }
        $target = Join-Path $DstRoot $_.Name
        if ($_.PSIsContainer) {
            Copy-ProjectTree -SrcRoot $_.FullName -DstRoot $target
        } else {
            Copy-Item -LiteralPath $_.FullName -Destination $target -Force
        }
    }
}

foreach ($pair in $RoboDirs) {
    $srcPath = Join-Path $RepoRoot $pair.Src
    $dstPath = Join-Path $StageRoot $pair.Dst
    if (-not (Test-Path $srcPath)) { continue }
    Copy-ProjectTree -SrcRoot $srcPath -DstRoot $dstPath
}

$ReadmeWin = Join-Path $PSScriptRoot "README-WINDOWS.txt"
if (Test-Path $ReadmeWin) {
    Copy-Item $ReadmeWin (Join-Path $StageRoot "README-WINDOWS.txt")
}

Compress-Archive -Path $StageRoot -DestinationPath $ZipPath -Force
Write-Host "==> 便携包: $ZipPath"
Write-Host "    解压后双击 ChallengeDemo.exe 即可（需已安装 Docker Desktop）"
