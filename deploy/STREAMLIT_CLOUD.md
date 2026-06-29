# Streamlit Community Cloud 测试部署说明

本说明用于把当前系统作为测试版部署到 Streamlit Community Cloud。该方案不需要云服务器，但测试期仍使用 SQLite 和本地文件目录，因此不适合作为正式长期数据平台。

## 1. 部署前确认

GitHub 仓库：

```text
https://github.com/shisheng329/ai-assisted-review-system
```

部署参数：

```text
Branch: main
Main file path: app/main.py
Python version: 3.11
```

依赖文件：

```text
requirements.txt
```

Secrets 测试期可以先不填。当前系统由用户在页面里配置 API Key。

## 2. 部署步骤

1. 打开：

   ```text
   https://share.streamlit.io/
   ```

2. 使用 GitHub 登录。

3. 点击 `Create app` 或 `Deploy app`。

4. 选择仓库：

   ```text
   shisheng329/ai-assisted-review-system
   ```

5. 选择分支：

   ```text
   main
   ```

6. 设置入口文件：

   ```text
   app/main.py
   ```

7. Python 版本选择：

   ```text
   3.11
   ```

8. App URL 可自定义，例如：

   ```text
   ai-assisted-review-system
   ```

9. 点击 `Deploy`。

## 3. 测试范围

部署完成后，先只做小数据测试：

- 注册测试账号。
- 登录。
- 创建测试项目。
- 上传一个小 CSV/XLSX 文件。
- 配置低额度或临时 API Key。
- 小批量测试筛选。
- 测试导出按钮。

不要上传正式研究数据、敏感 PDF 或高额度 API Key。

## 4. 数据风险

Community Cloud 的本地文件不保证长期持久化。当前测试版仍会把数据写到：

```text
data/app.db
uploads/
exports/
```

这些数据可能在 app 重启、redeploy、休眠唤醒或平台维护后丢失。

## 5. 后续正式化改造

测试版跑通后，正式长期使用建议按顺序改造：

1. API Key 改为不落库，或加密后保存。
2. SQLite 改为外部 PostgreSQL。
3. `uploads/exports` 改为对象存储。

推荐候选：

- PostgreSQL：Supabase、Neon、阿里云 RDS。
- 对象存储：Cloudflare R2、阿里云 OSS、AWS S3。
- 密钥管理：Streamlit secrets + Fernet/AES 主密钥。
