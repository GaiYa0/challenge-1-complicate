"""
Challenge Demo — Windows 启动器。

在包含 docker-compose.yml 的项目根目录运行，检测 Docker Desktop、
执行 `docker compose up`，就绪后打开 http://127.0.0.1:8080 。

用法:
  ChallengeDemo.exe           启动全栈
  ChallengeDemo.exe --stop    停止 Compose 服务
  ChallengeDemo.exe --logs    跟踪后端日志（Ctrl+C 退出）
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

APP_TITLE = "Challenge Demo"
DEFAULT_URL = "http://127.0.0.1:8080"
ENV_FILE = ".env.dev"
START_TIMEOUT_SEC = 900
POLL_INTERVAL_SEC = 5


def _pause_on_error() -> None:
    if sys.platform == "win32" and sys.stdin and sys.stdin.isatty():
        input("\n按 Enter 键退出…")


def _log(msg: str) -> None:
    print(f"[{APP_TITLE}] {msg}", flush=True)


def resolve_project_root() -> Path:
    """定位含 docker-compose.yml 的项目根（发行包根或仓库根）。"""
    candidates: list[Path] = []
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).resolve().parent)
    else:
        candidates.append(Path(__file__).resolve().parents[2])

    seen: set[Path] = set()
    for start in candidates:
        p = start.resolve()
        for _ in range(8):
            if p in seen:
                break
            seen.add(p)
            if (p / "docker-compose.yml").is_file():
                return p
            if p.parent == p:
                break
            p = p.parent

    _log("错误：未找到 docker-compose.yml。")
    _log("请将 ChallengeDemo.exe 放在完整项目/发行包根目录后重试。")
    _log("或从 GitHub Releases 下载 challenge-demo-windows-*.zip 并解压后运行。")
    _pause_on_error()
    sys.exit(1)


def ensure_docker() -> None:
    if not shutil.which("docker"):
        _log("未检测到 docker 命令。请先安装 Docker Desktop for Windows：")
        _log("  https://www.docker.com/products/docker-desktop/")
        _pause_on_error()
        sys.exit(1)

    probe = subprocess.run(
        ["docker", "info"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if probe.returncode != 0:
        _log("Docker 未就绪。请启动 Docker Desktop 并等待引擎运行后再试。")
        if probe.stderr:
            _log(probe.stderr.strip())
        _pause_on_error()
        sys.exit(1)


def compose_base_cmd(root: Path) -> list[str]:
    env_path = root / ENV_FILE
    if not env_path.is_file():
        _log(f"警告：缺少 {ENV_FILE}，将使用 Compose 默认环境变量。")
        return ["docker", "compose"]
    return ["docker", "compose", "--env-file", str(env_path)]


def run_compose_up(root: Path) -> None:
    cmd = compose_base_cmd(root) + ["up", "-d", "--build"]
    _log("正在构建并启动容器（首次可能需 10–30 分钟，取决于网络）…")
    _log("命令: " + " ".join(cmd))
    subprocess.run(cmd, cwd=str(root), check=True)


def run_compose_down(root: Path) -> None:
    cmd = compose_base_cmd(root) + ["down"]
    _log("正在停止服务…")
    subprocess.run(cmd, cwd=str(root), check=True)
    _log("已停止。")


def run_compose_logs(root: Path) -> None:
    cmd = compose_base_cmd(root) + ["logs", "-f", "backend"]
    _log("跟踪 backend 日志（Ctrl+C 结束）…")
    subprocess.run(cmd, cwd=str(root))


def wait_for_http(url: str, timeout_sec: int) -> bool:
    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=5) as resp:
                if 200 <= resp.status < 500:
                    return True
        except (urllib.error.URLError, TimeoutError, OSError):
            pass
        _log(f"等待服务就绪: {url} …")
        time.sleep(POLL_INTERVAL_SEC)
    return False


def open_browser(url: str) -> None:
    _log(f"打开浏览器: {url}")
    webbrowser.open(url)


def main() -> None:
    parser = argparse.ArgumentParser(description=APP_TITLE)
    parser.add_argument("--stop", action="store_true", help="停止 docker compose 服务")
    parser.add_argument("--logs", action="store_true", help="查看 backend 日志")
    parser.add_argument("--no-browser", action="store_true", help="启动后不自动打开浏览器")
    args = parser.parse_args()

    root = resolve_project_root()
    _log(f"项目目录: {root}")
    os.chdir(root)

    ensure_docker()

    if args.stop:
        run_compose_down(root)
        return
    if args.logs:
        run_compose_logs(root)
        return

    run_compose_up(root)
    if wait_for_http(DEFAULT_URL, START_TIMEOUT_SEC):
        _log("服务已就绪。")
        if not args.no_browser:
            open_browser(DEFAULT_URL)
        _log(f"访问地址: {DEFAULT_URL}  （演示账号 DEBUG=true: admin / admin）")
    else:
        _log("超时：站点未在预期时间内响应，请检查 Docker 日志：")
        _log(f'  docker compose --env-file "{root / ENV_FILE}" logs backend web')
        _pause_on_error()
        sys.exit(1)


if __name__ == "__main__":
    main()
