# 小学科学 AI 教师工作台 · AI 备课中心改造存档

**日期**　2026-11-16  
**方案来源**　用户提供的《AI 原生改造设计方案》  
**改造范围**　共享备课包、周课表与账号同步、可编辑课件、教材文字摘录

## 1. 方案评估

课表记录时间、班级和常规课或专项活动，备课包记录学期、年级和课题。把两者独立保存后，平行班可指向同一个主备课包，教师也可以按班级决定什么时候采用。现有 DeepSeek 规划、结构化编排和 PowerPoint 渲染流程可以复用，保留结构化源后即可用网页修改再导出。

本次实施第一期可独立操作的功能。周课表仍用现有表格，教师选择是否同步当前浏览器课表。备课包必须由教师主动创建、关联和发起生成。修改 PPTX 时先保存结构化源，再由现有渲染器输出新文件。重绘耗时依实际页数和素材而变化。

## 2. 操作方式

1. 登录教师工作台，从首页快捷入口或侧栏「教学筹备」打开「AI 备课中心」。也可从周课表普通课程格的「AI 备课」打开对应课时。
2. 新建备课包，填写年级、学期、课题、课时、教学目标和材料。按当前账号、年级、学期及课题限制同名重复。
3. 从课表打开时，可将已保存的备课包关联到当前课时。切到其他平行班的课程格，可以重复选用同一备课包，共享同一份最新课件。
4. 选择页数、模型和是否联网，主动生成。生成阶段沿用原 AI 课件流程，进度显示在备课页和当前标签页的顶部提示。
5. 打开生成结果，根据需要修改标题、投影要点、讲稿备注和现有图解标注，也可增删和调整页面顺序。点击保存后获取新的 SVG 预览和 PPTX 下载。保存编辑走本地渲染，无需再次调用 DeepSeek。
6. 可导入具有文本层的 PDF、DOCX 或 UTF-8 TXT。服务端提取文字供教师核对，保存时写入备课包的参考材料字段。扫描 PDF 仍需要 OCR。 [pypdf 文本提取说明](https://pypdf.readthedocs.io/en/latest/user/extract-text.html)

旧版「科学课件生成」和「科学探究设计」页面继续提供本地草稿和原有导出功能，也增加了将当前内容带入新备课包的入口。

首页的「同步到账号」会将当前浏览器周课表复制到 MySQL。首次同步后，该账号的课表修改及课程标记保存到服务器。浏览器的原课表副本仍可由旧版网站使用。样例中的无人机足球等专项活动不加入常规课程关联入口。

## 3. 工程改动

| 位置 | 职责 |
| --- | --- |
| [src/App.vue](src/App.vue) | 在原菜单和首页增加备课中心入口，显示课表关联和本标签页的备课进度 |
| [src/components/AiPrepWorkspace.vue](src/components/AiPrepWorkspace.vue) | 管理备课包、关联课时、发起生成，预览和精修课件 |
| [src/data/scheduleApi.js](src/data/scheduleApi.js) | 账号课表请求、浏览器课表转换及课时关联键 |
| [backend/weekly_schedule.py](backend/weekly_schedule.py) | `GET/PUT /api/v1/courses`，课表快照、账号隔离及冲突校验 |
| [backend/prep.py](backend/prep.py) | `/api/v1/prep/lessons`、`/api/v1/prep/links`、课件关联及结构化编辑接口 |
| [backend/prep_materials.py](backend/prep_materials.py) | `POST /api/v1/prep/materials/extract` 提取最多 5 MiB 文件中的正文。PDF 取前 20 页，摘录最多 4,000 字符 |
| [backend/artifacts.py](backend/artifacts.py)、[backend/skill_runtime/ppt_master.py](backend/skill_runtime/ppt_master.py) | 新生成的 PPTX 在原文件和元数据之外保存规范化的 `.source.json`，供项目精修 |
| [数据库迁移目录](backend/migrations/versions) | `0002` 新增 `lesson_units`、`prep_slot_links` 和 `courseware_projects`；`0003` 为 `courses` 增加可空的课型和标记列 |

一个备课包保存一个当前课件版本。多人或多标签页用同一账号修改时，后端检查修订号，拒绝提交过时的课件内容。重绘成功后才更新项目所指向的成果，老 PPTX 文件仍可通过原文件标识下载。此前生成且缺少结构化源的历史课件可以照常打开或下载，如需在备课包内精修，须重新生成结构化版本。

课表关联使用星期、时间和课程格的班级文本标识。同一班级更名或换到不同课时后，需要核对并重新关联。当前以周课表进行关联，学期进度轴和一次性调课尚待实现。

## 4. 备份与回退

改造前备份在本机项目的 `.runtime/site-backups/`。源码快照覆盖当时已有的未提交改动，重新解压便可检查各文件；可按压缩包内的 `_snapshot_manifest.json` 核对完整性。

| 文件 | 内容 |
| --- | --- |
| `.runtime/site-backups/before-ai-p0-20261116-154339.zip` | 改造前 64 个源码与项目配置模板，不含本机凭据、依赖、浏览器数据和运行产物 |
| `.runtime/site-backups/before-ai-p0-20261116-154339.mysql.sql` | 改造前本机 MySQL 逻辑备份，含账号哈希和业务数据，作为私有备份保留 |
| `.runtime/site-backups/before-ai-p0-deploy-20261116-160258.mysql.sql` | 应用数据库迁移前重新保存的私有 MySQL 快照 |
| `.runtime/site-backups/ai-prep-p0-release-20261116.zip` | 本次启用后的源码和存档，供下一次改造前比较或回退 |

源码快照的 SHA-256 为 `24810de53448882f4f72461d6ddd74d3c82030d694b924e1ae884e775d7a8498`。
迁移前数据库快照的 SHA-256 为 `5612b0b203bd4ab1c11593f0ed2040267e9360ad308b34dc8af62f63e39634f2`。

### 推荐回退方式

建议解压到独立目录并用旧版启动。这样新版源码、现有数据库和新版备课记录仍可保留。以下示例使用同一台电脑和当前项目的 Python 环境，MySQL 应处于运行状态。

```powershell
$workbench = 'G:\Basic-Software-and-Open-Source-Systems'
$snapshot = Join-Path $workbench '.runtime/site-backups/before-ai-p0-20261116-154339.zip'
$old = Join-Path $workbench '.runtime/rollback/before-ai-p0-20261116-154339'
Expand-Archive -LiteralPath $snapshot -DestinationPath $old
Copy-Item -LiteralPath (Join-Path $workbench '.env') -Destination (Join-Path $old '.env')
Set-Location -LiteralPath $old
npm ci
if ($LASTEXITCODE -ne 0) { throw '旧版依赖安装失败，请先修复安装' }
npm run build
if ($LASTEXITCODE -ne 0) { throw '旧版构建失败，请先修复构建' }
$env:SKILL_ARTIFACT_DIR = Join-Path $workbench 'backend/artifacts'
$env:SKILL_MEDIA_DIR = Join-Path $workbench 'backend/media'
& (Join-Path $workbench '.venv/Scripts/python.exe') -m uvicorn backend.main:create_app --factory --host 127.0.0.1 --port 8001
```

打开 `http://127.0.0.1:8001/` 检查旧版。如果你的旧站点把文件存到了其他目录，将上面的两个环境变量设为实际值。浏览器按网站来源保存课表草稿、主题和聊天。要在旧版读取原来 `8000` 端口的浏览器数据，先停止当前在 `8000` 监听的项目 FastAPI 进程，将示例最后一条命令端口改成 `8000`，并使用完全相同的访问地址。

回退网页不需要复制旧数据覆盖当前数据库，也不需要执行 Alembic 降级。若要核对改造前数据库，先新建空的独立数据库，再通过 MySQL 或 Navicat 导入私有 SQL 备份。

## 5. 验证与当前启用状态

- 2026-11-16 已应用 MySQL 迁移 `0002` 和 `0003`，当前数据库版本为 `0003 (head)`。已重启本机 FastAPI，新版入口为 [AI 备课中心](http://127.0.0.1:8000/#prep)。
- 最终前端构建和 32 项后端回归测试全部通过。浏览器验证教师登录、原首页和待办区、从普通课程格进入 AI 备课中心并带入课时。使用实际本地服务验证 MySQL 健康、旧待办读接口和 TXT 摘录接口。
- 实际模型调用曾返回空提纲，已加入一次直接生成提纲的重试。首次审稿无有效结果时也可重试。自动化回归覆盖这两个分支，生成结果仍须通过内容和版式检查。
- 修复后用隔离账号调用真实 DeepSeek Flash，生成两页《空气占据空间》，将文件关联到备课包，修改第二页并重新保存。确认第一页和原 PPTX 保留，新版第二页可预览，带两页教师备注的新版 PPTX 可通过下载凭据取得。验收数据未进入当前教师账号。
- 从改造前源码压缩包解压到独立目录，重新构建旧版前端并检查旧版 API 路由成功。回退演练使用当前机器上锁文件相同的已安装前端依赖。
- 日常只需从项目目录运行 `.\start-workbench.ps1`。在新环境还原此版本时，先按说明安装依赖和构建前端，再运行 `.\.venv\Scripts\python.exe -m alembic upgrade head`。

## 6. 后续范围

- 学期进度轴、单班或全年级顺延、预约预生成、竞赛专项教练工作流。
- 课件单页 AI 指令改写、图形拖拽与任意照片替换、按班级派生独立课件版本。
- 独立四件套文件、教材图片识别及扫描文档 OCR、教师标准与校本资料检索。
- 可靠的后台任务队列、浏览器关闭后的任务恢复，以及报告批改、学情复盘和交互实验。

## 7. 课件生成质量修订

改版后，服务端会一次列出问题页并分组修订。审稿建议只有通过对应页的检查才会应用。长课件初稿不完整时可按原页码分段生成。仍有问题时，提示具体页码及原因。

课件新增原生 PowerPoint 观察记录表和有参考来源的原理图。自定义图解的标注可自动重新排布，保留原来的指向。家蚕章节的整体结构、生命周期及独立阶段观察优先使用校验后的可编辑图解。

本轮前端构建、40 项后端测试和本地 FastAPI 健康检查通过。真实 DeepSeek Flash 生成 12 页《蚕宝宝探秘局》，含 6 张图解页、1 张原生观察记录表及 12 页教师备注。已查看整套网页预览并校验 PPTX 下载字节。此样本用于对照家蚕主题，尚不足以说明其它课题或 23 页长课件与桌面 Harness 具备相同的版式丰富度。
