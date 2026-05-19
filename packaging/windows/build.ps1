# 在 Windows 本地构建 ChallengeDemo.exe 与便携发行 ZIP
# 用法（PowerShell，仓库根目录）:
#   .\packaging\windows\build.ps1
#   .\packaging\windows\build.ps1 -SkipZip

param(
    [switch]$SkipZip
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $RepoRoot

Write-Host "==> 仓库根: $RepoRoot"

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "未找到 python。请安装 Python 3.10+ 并加入 PATH。"
}

python -m pip install --upgrade pip
python -m pip install -r (Join-Path $PSScriptRoot "requirements-build.txt")

$DistExe = Join-Path $RepoRoot "dist\ChallengeDemo.exe"
if (Test-Path $DistExe) { Remove-Item $DistExe -Force }

pyinstaller --noconfirm --clean (Join-Path $PSScriptRoot "challenge-demo.spec")

if (-not (Test-Path $DistExe)) {
    throw "构建失败：未生成 $DistExe"
}

Write-Host "==> 已生成: $DistExe"

if ($SkipZip) { exit 0 }

& (Join-Path $PSScriptRoot "stage-release.ps1") -ExePath $DistExe
