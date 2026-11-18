# 后端运行说明

从项目根目录执行以下操作。实际运行使用 MySQL；SQLite 仅用于开发或隔离测试。

1. 在 MySQL 8 中创建空数据库 `science_workbench`，编码用 `utf8mb4`，为项目创建专用账号并授予该库的权限。不要使用 MySQL 管理员账号连接应用。
2. 将根目录的 `.env.example` 复制为 `.env`，填写 `DATABASE_URL` 和随机生成的 `JWT_SECRET`。数据库密码包含特殊字符时，在 URL 中进行百分号编码。环境文件不提交到 Git。
3. 安装依赖、迁移数据库、创建一个教师账号并启动：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m backend.create_user teacher --name "张老师"
.\.venv\Scripts\python.exe -m uvicorn backend.main:create_app --factory --host 127.0.0.1 --port 8000
```

教师密码由创建账号命令交互读取。没有预置通用密码，也没有公开注册接口。JWT 登录有效期为 8 小时；退出会清除当前标签页的登录状态。

启动 Vite 后在 `http://127.0.0.1:5173/` 登录。若已经执行 `npm run build`，也可以直接从 FastAPI 的 `http://127.0.0.1:8000/` 打开构建后的网页。两种地址的浏览器本地数据分开存放。

接口文档：`http://127.0.0.1:8000/docs`。先调用 `POST /api/v1/auth/login` 获取 JWT，再在文档的 **Authorize** 中填入 `access_token`。

| 路径（前缀 `/api/v1`） | 用途 |
| --- | --- |
| `GET /health` | 检查 API 能否连接数据库 |
| `POST /auth/login`、`GET /auth/me` | 登录、查看当前账号 |
| `GET /todos?date=YYYY-MM-DD`、`POST /todos` | 按日期读取、创建待办 |
| `GET /todos/{id}`、`PATCH /todos/{id}`、`DELETE /todos/{id}` | 读取、修改、删除单条待办 |
| `POST /todos/complete?date=...`、`DELETE /todos/completed?date=...` | 批量完成、清除指定日期已完成待办 |
| `POST /todos/import` | 导入浏览器旧待办，保留浏览器原记录 |
| `GET /chat/skills` | 查看当前账号可用的本机技能和 ppt-master 是否就绪 |
| `POST /chat/stream` | 实时接收回复、工具进度及下载信息 |
| `POST /chat/completions` | 一次性返回完整回复和工具结果 |
| `GET /chat/artifacts/{id}` | 下载当前账号由技能生成的 PPTX |

迁移同时建立课表、班级、学生、AI 任务、实验报告和科创作品的基础表。这些模块的业务接口后续按需接入。

在项目根目录的本地 `.env` 设置 `DEEPSEEK_API_KEY`，重启 FastAPI。在首页登录后进入「AI 对话」发送文字，即可使用 DeepSeek。会话历史保存在浏览器，请求发送近期文字和本轮选中的图片。Flash 支持图片分析，其他附件保存在本地预览。密钥由后端读取，FastAPI 需要能直接通过 HTTPS 访问 `api.deepseek.com`。

### 技能调用与 ppt-master

FastAPI 直接连接 DeepSeek，并调用项目内置工具。运行网站只需项目的 Python 环境和原有后端配置。

- `search_images` 从 Bing 图片搜索获取配图和来源提示。
- `draw_image` 默认绘制本地示意图。可在 `.env` 配置 `IMAGE_API_KEY`、`IMAGE_API_BASE` 和 `IMAGE_MODEL`，使用兼容的图片生成服务。
- 明确要求生成课件时，后端用所选 DeepSeek 模型逐页策划、编写结构化内容和审稿，检查页数、板书密度、图解标注和教师备注后才导出可编辑的 16:9 PPTX。支持可编辑原理图、过程、对照、实验、重点数值和课堂迁移等版式。开启「联网搜索」后，观察页可以查找公开配图；找图失败时保留观察文字并在回复中说明。
- `search_web` 仅在聊天界面勾选「联网搜索」时可用。成功请求按 DeepSeek 搜索用量计费。

PPTX 和配图分别默认保存到 `backend/artifacts/<教师ID>/` 与 `backend/media/<教师ID>/`。可用 `SKILL_ARTIFACT_DIR` 和 `SKILL_MEDIA_DIR` 自定义存放目录。

运行接口测试：

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend/requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest backend/tests
```

默认测试使用临时 SQLite。设置 `WORKBENCH_TEST_DATABASE_URL` 可在 MySQL 中运行同一套测试，必须指向专用、空的 `*_test` 数据库。测试会在该库运行迁移和回滚。
