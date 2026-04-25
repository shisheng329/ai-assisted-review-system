# 20260423 Streamlit Literature Screening SaaS Demo

独立实现的多用户文献筛选 SaaS demo，采用 `Streamlit + SQLite + Docker Compose`。

## 主要能力

- 公开注册、登录、私有项目隔离
- 多项目管理
- API 配置库
- 题录数据导入与多文件切换
- 基于固定 prompt 骨架的文献筛选
- BERTopic 聚类分析
- 基于模板的 PDF 提取
- 中英文界面

## 本地运行

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app/main.py --server.port 8502
```

访问：`http://localhost:8502`

## Docker 运行

```powershell
docker compose build --no-cache
docker compose up -d
```

访问：`http://localhost:8503`

健康检查：`http://localhost:8503/health`

## 热更新

`docker-compose.yml` 已将本地项目目录挂载到容器内，并启用 Streamlit `runOnSave + poll` 文件监听。修改本地源码后，浏览器页面会自动刷新。

## Docker Hub 拉取失败排查

如果你在 `docker compose build --no-cache` 时看到类似下面的错误：

```text
failed to fetch oauth token: Post "https://auth.docker.io/token"
```

这不是项目代码错误，而是当前机器访问 `auth.docker.io` / `registry-1.docker.io` 失败，导致 Docker 无法拉取基础镜像 `python:3.11-slim`。

当前项目已经支持通过环境变量切换基础镜像。你可以在项目根目录创建 `.env`，例如：

```env
PYTHON_BASE_IMAGE=python:3.11-slim
```

如果你本机 Docker 已配置了可用镜像源，或者你有一个可访问的代理前缀镜像，也可以改成对应地址，然后重新执行：

```powershell
docker compose build --no-cache
docker compose up -d
```

当前仓库默认已经附带一个可直接使用的 `.env`：

```env
PYTHON_BASE_IMAGE=m.daocloud.io/docker.io/library/python:3.11-slim
PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
```

也就是：

1. 基础镜像不再直接从 Docker Hub 拉，而是走 `m.daocloud.io`
2. `pip install` 走清华 PyPI 镜像

如果仍然失败，优先检查：

1. Docker Desktop 是否能正常访问外网
2. `auth.docker.io:443` 是否可达
3. 是否需要配置代理
4. 是否需要在 Docker Desktop 的 `Settings -> Docker Engine` 中配置 `registry-mirrors`
5. 是否已有可访问的企业内网镜像仓库可替代 `python:3.11-slim`

## 默认算法

BERTopic 模块默认使用：

- `SentenceTransformer("all-MiniLM-L6-v2")`
- `UMAP(random_state=42, n_neighbors=15, n_components=5, min_dist=0.0, metric="cosine")`
- `CountVectorizer(stop_words="english")`

## 目录

- `app/main.py`：入口
- `app/modules/`：页面模块
- `app/services/`：数据库、认证、LLM、BERTopic、PDF、导出
- `app/i18n/`：中英文文案
