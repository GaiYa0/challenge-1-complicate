Challenge Demo — Windows 便携版
================================

前置条件
--------
1. 安装 Docker Desktop for Windows（WSL2 后端推荐）
   https://www.docker.com/products/docker-desktop/
2. 启动 Docker Desktop，等待托盘图标显示 “Engine running”
3. 本机建议至少 8GB 内存；首次启动会拉取镜像，耗时较长

快速开始
--------
1. 将整个文件夹解压到任意路径（路径尽量不要含中文或空格）
2. 双击 ChallengeDemo.exe
3. 等待控制台显示 “服务已就绪”，浏览器将打开 http://127.0.0.1:8080
4. 演示登录（.env.dev 默认 DEBUG=true）：用户名 admin，密码 admin

其它命令（在文件夹内打开 cmd）
------------------------------
  ChallengeDemo.exe --stop        停止所有容器
  ChallengeDemo.exe --logs        查看后端日志
  ChallengeDemo.exe --no-browser  启动但不自动打开浏览器

排错
----
- 提示 Docker 未就绪：先打开 Docker Desktop
- 8080 端口被占用：关闭占用程序，或修改 docker-compose.yml 中 web 的 ports
- 查看容器状态：docker compose --env-file .env.dev ps
- 查看日志：docker compose --env-file .env.dev logs -f backend

从源码构建 exe（开发者）
------------------------
  PowerShell 于仓库根目录：
    .\packaging\windows\build.ps1

GitHub 上 clone 后也可不用 exe，直接：
  docker compose --env-file .env.dev up -d --build
然后访问 http://127.0.0.1:8080
