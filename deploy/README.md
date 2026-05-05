# 非 Docker 在线部署说明

本目录用于把系统部署成“点击链接即可访问”的在线网页。推荐第一阶段使用一台云服务器、Python 虚拟环境、systemd 和 Nginx，不依赖 Docker。

## 推荐服务器

- 测试最低配置：2 核 4G
- 小范围课题组推荐：4 核 8G
- BERTopic 数据量较大：4 核 16G 或更高
- 系统：Ubuntu 22.04 LTS 或 24.04 LTS
- 硬盘：至少 80GB，建议 100GB 以上

## 目录约定

```text
/opt/literature-screening-app       # GitHub 拉取的代码
/opt/literature-screening-data      # 数据库、上传文件、导出结果
/etc/literature-screening           # 服务器环境变量
```

`/opt/literature-screening-data` 不进入 Git 仓库，需要单独备份。

## 首次部署

安装系统依赖：

```bash
sudo apt update
sudo apt install -y git nginx python3 python3-venv python3-pip
```

创建运行用户和目录：

```bash
sudo useradd --system --create-home --shell /usr/sbin/nologin literature
sudo mkdir -p /opt/literature-screening-app
sudo mkdir -p /opt/literature-screening-data/uploads /opt/literature-screening-data/exports
sudo mkdir -p /etc/literature-screening
sudo chown -R literature:literature /opt/literature-screening-app /opt/literature-screening-data
```

拉取代码：

```bash
sudo -u literature git clone <your-github-repo-url> /opt/literature-screening-app
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
sudo ln -s /etc/nginx/sites-available/literature-screening.conf /etc/nginx/sites-enabled/literature-screening.conf
sudo nginx -t
sudo systemctl reload nginx
```

将 `your-domain.com` 替换成你的域名。HTTPS 建议使用云厂商证书或 Certbot 配置。

## GitHub 上传原则

GitHub 仓库只保存代码、配置模板和文档，不保存运行数据。

不要提交：

- `.env`
- API Key
- `data/`
- `uploads/`
- `exports/`
- `*.db`
- `.venv/`

## 备份

至少备份这些路径：

```text
/opt/literature-screening-data/app.db
/opt/literature-screening-data/uploads
/opt/literature-screening-data/exports
```

SQLite 适合第一阶段小范围使用。长期多人在线使用时，建议迁移到 PostgreSQL，并把上传文件迁移到对象存储。
