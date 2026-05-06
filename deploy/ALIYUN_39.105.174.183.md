# 阿里云 ECS 部署清单：39.105.174.183

服务器信息：

```text
公网 IP: 39.105.174.183
系统: Ubuntu 22.04 64位
配置: 2 vCPU / 4 GiB
系统盘: 40 GiB
区域: 华北2 北京
```

先用公网 IP 测试：

```text
http://39.105.174.183
```

域名和 HTTPS 等系统跑通后再配置。

## 1. 安全组

阿里云控制台入方向规则：

```text
TCP 22   来源：你的本机公网 IP，或临时 0.0.0.0/0
TCP 80   来源：0.0.0.0/0
TCP 443  来源：0.0.0.0/0
```

不要开放 `8502`。Streamlit 只监听 `127.0.0.1:8502`。

## 2. 登录服务器

PowerShell：

```powershell
ssh root@39.105.174.183
```

也可以使用阿里云控制台“远程连接”。

## 3. 如果 GitHub 仓库是 public

服务器上执行：

```bash
apt update
apt install -y git
git clone https://github.com/shisheng329/ai-assisted-review-system.git /tmp/ai-assisted-review-system
cd /tmp/ai-assisted-review-system
bash deploy/scripts/bootstrap_ubuntu.sh
```

## 4. 如果 GitHub 仓库是 private

推荐用 deploy key。

服务器上生成密钥：

```bash
ssh-keygen -t ed25519 -C "aliyun-ai-assisted-review-system" -f ~/.ssh/ai_review_deploy -N ""
cat ~/.ssh/ai_review_deploy.pub
```

把输出的公钥添加到：

```text
GitHub repo -> Settings -> Deploy keys -> Add deploy key
```

只勾选 read-only。

配置 SSH：

```bash
cat > ~/.ssh/config <<'EOF'
Host github.com
  HostName github.com
  User git
  IdentityFile ~/.ssh/ai_review_deploy
  IdentitiesOnly yes
EOF

chmod 600 ~/.ssh/config
ssh -T git@github.com
```

部署：

```bash
git clone git@github.com:shisheng329/ai-assisted-review-system.git /tmp/ai-assisted-review-system
cd /tmp/ai-assisted-review-system
REPO_URL=git@github.com:shisheng329/ai-assisted-review-system.git bash deploy/scripts/bootstrap_ubuntu.sh
```

## 5. 检查服务

```bash
systemctl status literature-screening
curl http://127.0.0.1:8502
nginx -t
systemctl status nginx
```

浏览器打开：

```text
http://39.105.174.183
```

如果打不开：

```bash
journalctl -u literature-screening -n 100 --no-pager
systemctl status nginx
ss -lntp | grep -E '80|8502'
```

## 6. 备份

手动备份：

```bash
bash /opt/literature-screening-app/deploy/scripts/backup_data.sh
```

建议每天备份：

```bash
crontab -e
```

加入：

```cron
0 3 * * * /bin/bash /opt/literature-screening-app/deploy/scripts/backup_data.sh >> /var/log/literature-screening-backup.log 2>&1
```

## 7. 后续域名和 HTTPS

备案完成并配置 DNS 后，把 Nginx 里的：

```nginx
server_name _;
```

改成你的域名：

```nginx
server_name your-domain.com;
```

然后：

```bash
nginx -t
systemctl reload nginx
apt install -y certbot python3-certbot-nginx
certbot --nginx
```
