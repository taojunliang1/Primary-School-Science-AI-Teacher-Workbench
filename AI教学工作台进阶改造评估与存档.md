# 小学科学 AI 教师工作台进阶改造评估与存档

日期 2026-11-18  
评估材料 `ai建议2.md`  
本次交付 单页 AI 改写与教材照片识读

## 方案评估

建议把 AI 放到教师原本就要操作的位置。单页改写解决了整套课件生成后只想改一页的问题，照片识读则减少了从纸质教材手工录入实验步骤的时间。两项都可以复用现有备课包、教师权限、课件结构化源和 PPTX 导出流程，适合优先落地。

| 建议 | 可行性与开发判断 |
| --- | --- |
| 单页 AI 指令改写 | 现有课件源、逐页预览和修订号都能复用。本次实现先比对、再采纳、最后保存，适合教师核对科学表述。 |
| 教材照片识读 | Flash 可以按图片提取备课要点。本次交付可编辑草稿，模糊信息放到「待核对」，由教师确认后加入参考资料。 |
| 平行班独立版本 | 可行。应先定义主备课包、班级派生版及关联课时之间的关系，再补复制、恢复和下载的版本规则。 |
| 全站自然语言指令 | 有价值，宜先让 AI 生成拟执行清单，展示具体课时、待办和修改页。课表冲突检查、跨模块执行失败处理和撤销需要单独实现。 |
| 晨间教学简报 | 适合下一阶段。课节数、版本和任务状态以 MySQL 查询为准，AI 根据这些已核对的数据润色和排序；数据缺失时展示可用的事实。 |
| 对话中的器材卡片与分组组件 | 可行。前端应只接受预定义的数据结构；器材清单可预览并由教师确认入待办，分组规则需能手动修改。 |
| 大屏放映与双屏提词 | 可先用现有矢量预览、页码和教师备注实现单屏放映。双屏需要配对、权限、断线恢复和页码同步，可独立验收。 |
| 课堂即时绘图与实验照片诊断 | 适合先做教师端预览，再确认投屏。生成耗时受模型与网络影响，先量测课堂实际延迟。具体接线判断和图片坐标需用真实样本校准，安全结论由教师核对。 |
| H5 互动科学仿真 | 建议由教师指令选择经过验证的弹簧、斜面等实验组件并配置参数。自由生成 HTML 的运行隔离、物理正确性和课堂稳定性需另行验证。 |
| 图文报告批改与跨课记忆 | 业务价值高，应先有经教师核对的批改量表、可追溯错因和班级权限。跨课预警应标明样本数、统计时间和课程来源。 |

## 本次网站改造

入口是「AI 备课中心」`/#prep`。首页、侧栏、课表、待办、AI 对话和已有关联页面沿用原入口。数据库迁移版本沿用 `0003`。

### AI 改写本页

1. 打开已有可编辑 PPTX 的备课包，在「课件精修」选中一页。若当前已有人工修改，先保存。
2. 在预览旁选「AI 改写本页」，输入具体要求或选一条快捷指令。
3. 查看原文和建议。采纳后，内容进入当前页草稿。点击「保存并更新课件」后生成新修订和 PPTX。

DeepSeek V4 Pro 接收当前页可编辑内容、课题、年级以及相邻页的标题和小结。服务端校验允许编辑的字段和文本长度，图解改写只涉及现有标签文字。改写接口返回建议时会复查修订号；原有保存接口处理正式更新和版本冲突。旧的下载文件继续由原来的文件记录服务。

### AI 识读教材照片

1. 在「备课信息」选「AI 识读教材照片」，上传 JPEG、PNG 或 WebP。浏览器会将图像压缩为 JPEG 后发送给 DeepSeek Flash。
2. 核对可编辑的识读草稿，包括课题、目标、器材、步骤、插图要点和待核对内容。
3. 选「加入参考资料」将文本追加到当前草稿，再选「保存备课信息」。参考资料和新增摘录合计上限为 4,000 字符；需要缩短时界面会提示。

文档文字摘录入口仍可处理文本层 PDF、DOCX 和 UTF-8 TXT。此次图片验证使用合成教材文字样例，实拍场景中的反光、手写、密集跨页及复杂图解识别率还需要更多样本验证。

浏览器回归还修复了备课表单的课时校验。默认 40 分钟可以正常提交，页面接受 1–240 分钟的整数，与后端约束一致。

## 接口与代码索引

| 文件或接口 | 改动 |
| --- | --- |
| `POST /api/v1/prep/lessons/{lesson_id}/deck/slides/{page}/ai-edit` | 接收当前修订号和改写指令，返回单页改写建议。 |
| `POST /api/v1/prep/materials/extract-image` | 接收处理后的教材图像，返回可核对的摘录草稿。 |
| `backend/prep.py`、`backend/prep_ai.py` | 教师权限、修订检查、可编辑字段校验和课件渲染校验。 |
| `backend/prep_materials.py`、`backend/chat.py`、`backend/main.py` | 图片校验与结构化识读、模型请求及路由配置。 |
| `src/components/AiPrepWorkspace.vue`、`src/data/chatApi.js` | 改写对照、照片识读草稿、图片压缩及应用后分步保存。 |
| `backend/tests/test_prep.py`、`backend/tests/test_prep_materials.py` | 教师权限、修订冲突、单页修改、图片校验和待核对提示。 |

## 验证记录

- 后端回归测试 42 项全部通过，前端生产构建成功。
- 真实 DeepSeek V4 Pro 验证两页课件，生成建议后原修订未变化。采纳并保存后修订号递增，第二页不变，新旧 PPTX 均可下载且通过 ZIP 完整性检查。
- 真实 DeepSeek Flash 识别合成教材图片中的课题和实验器材。识读后备课记录保持原样，提交编辑后可以重新读取保存的参考资料。
- 使用 Chrome 和模拟备课数据验证了改写对照、采纳与保存，以及图片转码、草稿编辑与参考资料保存。
- 本机 FastAPI 的健康检查返回 MySQL 正常，生产首页和两个新增路由均已通过 HTTP 检查。
- 将备份解压到独立目录后，旧版备课与资料摘录回归测试 6 项全部通过，测试使用临时数据库。

## 备份和回退

改造前源码压缩包位于 `.runtime/site-backups/before-ai-p1a-20261118-193119.zip`，包含 79 个项目源码文件及逐文件 SHA-256 清单 `_snapshot_manifest.json`。压缩包 SHA-256 为 `3d0915061fa6034f491e524e0c3ef2dc285f77ef0431803a61b3646361136dfd`。环境变量、数据库、课件制品、依赖和构建产物按原目录单独保管。

需要回退时，先在独立目录运行旧版进行核对。下面的 PowerShell 示例会在项目的 `.runtime` 中解包，使用当前项目虚拟环境和本地配置，在 8001 端口启动。

```powershell
$root = 'G:\Basic-Software-and-Open-Source-Systems'
$archive = Join-Path $root '.runtime\site-backups\before-ai-p1a-20261118-193119.zip'
$expected = '3d0915061fa6034f491e524e0c3ef2dc285f77ef0431803a61b3646361136dfd'
if ((Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash -ne $expected) {
    throw '备份校验失败'
}
$rollback = Join-Path $root ('.runtime\rollback-p1a-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
Expand-Archive -LiteralPath $archive -DestinationPath $rollback
Copy-Item -LiteralPath (Join-Path $root '.env') -Destination (Join-Path $rollback '.env')
Set-Location -LiteralPath $rollback
npm ci
if ($LASTEXITCODE -ne 0) { throw '前端依赖安装失败' }
npm run build
if ($LASTEXITCODE -ne 0) { throw '前端构建失败' }
```

接下来在同一 PowerShell 窗口中，先把课件和配图目录指回当前项目，再启动旧版。以下为项目默认目录。自定义部署时填入正在使用的两个存储路径。

```powershell
$env:SKILL_ARTIFACT_DIR = Join-Path $root 'backend\artifacts'
$env:SKILL_MEDIA_DIR = Join-Path $root 'backend\media'
& (Join-Path $root '.venv\Scripts\python.exe') -m uvicorn backend.main:create_app --factory --host 127.0.0.1 --port 8001
```

打开 `http://127.0.0.1:8001/` 检查旧版。确认后，如需恢复原访问地址，先停止 8000 上正在运行的工作台，再用相同命令以 8000 启动旧版。本次无数据库迁移，使用旧版源码时会继续读取现有 MySQL 教学数据与已保存的修订。
