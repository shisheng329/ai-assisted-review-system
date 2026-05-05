# 非 Docker 在线部署说明

本目录用于把系统部署成“点击链接即可访问”的在线网页。第一阶段推荐使用一台云服务器、Python 虚拟环境、systemd 和 Nginx，不依赖 Docker。

代码仓库：

```text
https://github.com/shisheng329/ai-assisted-review-system
```

## 1. 服务器选择

推荐配置：

- 测试最低配置：2 核 4G
- 小范围课题组推荐：4 核 8G
- BERTopic 数据量较大：4 核 16G 或更高
- 系统：Ubuntu 22.04 LTS 或 24.04 LTS
- 硬盘：至少 80GB，建议 100GB 以上

安全组需要开放：

- `22`：SSH 登录
- `80`：HTTP
- `443`：HTTPS

不要开放 `8502`。Streamlit 只监听服务器本机 `127.0.0.1:8502`，由 Nginx 对外代理。

## 2. 目录约定

```text
/opt/literature-screening-app       # GitHub 拉取的代码
/opt/literature-screening-data      # 数据库、上传文件、导出结果
/etc/literature-screening           # 服务器环境变量
/opt/literature-screening-backups   # 数据备份
```

`/opt/literature-screening-data` 不进入 Git 仓库，需要单独备份。

## 3. 快速部署

登录服务器后执行：

```bash
sudo apt update
sudo apt install -y git
git clone https://github.com/shisheng329/ai-assisted-review-system.git /tmp/ai-assisted-review-system
cd /tmp/ai-assisted-review-system
sudo bash deploy/scripts/bootstrap_ubuntu.sh
```

如果 GitHub 仓库是 private，需要先在服务器配置 GitHub 访问权限。推荐用 deploy key，也可以临时用 GitHub personal access token 克隆。不要把 token 写进仓库或部署文档。

如果已经有域名，例如 `review.example.com`，执行：

```bash
sudo DOMAIN=review.example.com bash deploy/scripts/bootstrap_ubuntu.sh
```

如果暂时没有域名，脚本会把 Nginx 配置成默认站点，可先用服务器公网 IP 访问：

```text
http://服务器公网IP
```

## 4. 手动部署

如不使用脚本，可按下面步骤手动执行。

安装系统依赖：

```bash
sudo apt update
sudo apt install -y git nginx python3 python3-venv python3-pip curl
```

创建运行用户和目录：

```bash
sudo useradd --system --create-home --shell /usr/sbin/nologin literature
sudo mkdir -p /opt/literature-screening-app
sudo mkdir -p /opt/literature-screening-data/uploads /opt/literature-screening-data/exports
sudo mkdir -p /etc/literature-screening
sudo chown -R literature:literature /opt/literature-screening-app /opt/literature-screening-data
```

拉取代码并安装 Python 依赖：

```bash
sudo -u literature git clone https://github.com/shisheng329/ai-assisted-review-system.git /opt/literature-screening-app
cd /opt/literature-screening-app
sudo -u literature python3 -m venv .venv
sudo -u literature .venv/bin/pip install --upgrade pip
sudo -u literature .venv/bin/pip install -r requirements.txt
```

复制环境变量：

```bash
sudo cp deploy/literature-screening.env.example /etc/literature-screening/literature-screening.env
sudo chmod 600 /etc/literature-screening/literature-screening.env
```

安装 systemd 服务：

```bash
sudo cp deploy/systemd/literature-screening.service /etc/systemd/system/literature-screening.service
sudo systemctl daemon-reload
sudo systemctl enable --now literature-screening
sudo systemctl status literature-screening
```

安装 Nginx 反向代理：

```bash
sudo cp deploy/nginx/literature-screening.conf /etc/nginx/sites-available/literature-screening.conf
sudo ln -sfn /etc/nginx/sites-available/literature-screening.conf /etc/nginx/sites-enabled/literature-screening.conf
sudo nginx -t
sudo systemctl reload nginx
```

如果有域名，把 `/etc/nginx/sites-available/literature-screening.conf` 中的 `your-domain.com` 改成你的域名。

## 5. HTTPS

先确认 HTTP 能打开，再配置 HTTPS。

Certbot + Nginx 常用命令：

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx
```

中国大陆服务器绑定域名通常需要 ICP 备案。未备案前可先用公网 IP 做技术验证。

## 6. 部署检查

```bash
cd /opt/literature-screening-app
sudo bash deploy/scripts/check_deployment.sh
```

也可手动检查：

```bash
sudo systemctl status literature-screening
curl http://127.0.0.1:8502
sudo nginx -t
```

浏览器访问：

```text
http://服务器公网IP
```

或：

```text
https://你的域名
```

## 7. 备份

手动备份：

```bash
sudo bash /opt/literature-screening-app/deploy/scripts/backup_data.sh
```

建议至少备份：

```text
/opt/literature-screening-data/app.db
/opt/literature-screening-data/uploads
/opt/literature-screening-data/exports
```

可以加入 crontab 每天备份一次：

```bash
sudo crontab -e
```

示例：

```cron
0 3 * * * /bin/bash /opt/literature-screening-app/deploy/scripts/backup_data.sh >> /var/log/literature-screening-backup.log 2>&1
```

## 8. GitHub 上传原则

GitHub 仓库只保存代码、配置模板和文档，不保存运行数据。

不要提交：

- `.env`
- API Key
- `data/`
- `uploads/`
- `exports/`
- `*.db`
- `.venv/`

SQLite 适合第一阶段小范围使用。长期多人在线使用时，建议迁移到 PostgreSQL，并把上传文件迁移到对象存储。
