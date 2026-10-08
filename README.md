# 小学科学 AI 教师工作台

面向小学科学教师的浏览器工作台。项目希望把课表、待办和科学教学工具集中在一个界面中，逐步接入 AI 备课、实验设计与报告批改能力。

> **当前版本：v0.1.0 前端基线。** 目前是可交互的前端演示，没有后端服务、数据库或真实 AI 接口。适合作为后续迭代的原始版本保存。

## 当前功能

- 首页展示欢迎信息、快捷入口、本周课表和每日待办。
- 课表按周一至周五及时间段排列，标出当天所在列；支持大课间、午餐、午管、延时服务等分区。
- 欢迎信息中的科学课节数来自当天课表，不计入大课间、午餐、午管、延时服务、升旗仪式和教研；任务数来自当天未完成的待办。
- 待办支持按日期查看、新增、编辑、完成、删除、全部完成和清除已完成。数据仅保存在当前浏览器的 `localStorage` 中。
- 默认使用青绿科学主题，可在右上角头像菜单切换到原紫红配色。主题选择同样保存在浏览器本地。
- 其他 AI 和管理入口目前只展示预览提示，尚未实现实际业务功能。

## 技术栈

| 当前使用 | 已安装、为后续预留 | 后续计划，尚未接入 |
| --- | --- | --- |
| Vue 3、JavaScript、Vite、Element Plus | Pinia、Axios | FastAPI、SQLAlchemy、MySQL、Redis、Celery、大模型 API |

前端使用 JavaScript，不使用 TypeScript。AI API Key 将来应只存放在后端环境变量中，不能写入前端源码。

## 本地运行

需要预先安装 Node.js 和 npm。在项目根目录运行：

```bash
npm ci
npm run dev
```

在浏览器打开终端显示的本地地址，通常是 `http://localhost:5173/`。Vite 需要启动开发服务器来处理 Vue 文件和 npm 依赖，因此**不能通过双击 `index.html` 直接打开页面**。

检查生产构建：

```bash
npm run build
npm run preview
```

构建产物位于 `dist/`，该目录和 `node_modules/` 不提交到 Git；他人克隆仓库后运行 `npm ci` 即可重新安装依赖。

## 项目结构

```text
.
├─ src/
│  ├─ data/timetable.js   # 演示课表、课程与非课程事件标记
│  ├─ App.vue             # 首页结构和演示交互
│  ├─ style.css           # 原紫红主题及基础布局
│  ├─ timetable.css       # 课表布局与原配色
│  ├─ theme-science.css   # 青绿科学主题覆盖样式
│  └─ main.js             # Vue 应用入口
├─ index.html
├─ package.json
├─ package-lock.json
└─ vite.config.js
```

### 修改演示内容

- **教师姓名**：修改 `src/App.vue` 中的 `teacherName`。
- **课表**：修改 `src/data/timetable.js`。`lesson('课次', true)` 会给课次加标记，去掉 `true` 即取消标记；升旗仪式、教研等非课程事件使用 `event(...)`。
- **待办**：初始演示数据在 `src/App.vue` 的 `starterTodos` 中。首次进入后，新增或修改的待办保存在浏览器 `localStorage`；它不会跨浏览器同步，也不会随 Git 提交。
- **主题**：在头像菜单切换。紫红主题保留在 `style.css` / `timetable.css`，青绿主题位于 `theme-science.css`。

## 后续迭代方向

1. 建立 FastAPI + MySQL 后端及用户、待办等数据表，用 Axios 对接待办接口。
2. 接入身份认证、班级和实验报告管理。
3. 在后端封装 AI 服务，并使用 Redis + Celery 处理耗时生成任务。
4. 扩展科学绘图、虚拟实验、教学视频及实验数据分析功能。

以上为规划，并非当前版本已实现的功能。

## 版本与许可证

建议将本版标记为 `v0.1.0-frontend-baseline`，后续功能在新分支开发，方便随时从标签查看原始版本。目标 GitHub 仓库已有 [GPL-3.0 许可证](https://github.com/taojunliang1/Basic-Software-and-Open-Source-Systems/blob/main/LICENSE)，上传时应保留该文件。
