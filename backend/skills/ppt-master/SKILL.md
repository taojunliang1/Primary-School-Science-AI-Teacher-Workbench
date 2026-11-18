---
name: ppt-master
description: 将小学科学教学大纲、配图和教师备注导出为可编辑的 16:9 PowerPoint。
---

调用 `create_ppt_with_ppt_master` 生成课件。按课堂任务选择版式。观察真实图片用 `figure`，对照用 `compare`，步骤与过程用 `process`，实验任务用 `inquiry`，并列概念用 `concepts`。用户明确指定页数时，以总页数为准。给封面或观察页配图时，先用 `search_images` 找图片或用 `draw_image` 绘图，再传入资源编号。照片可裁切填充，带标签的示意图应完整显示。投影保留课堂短句，把操作、证据和纠错提示写入教师备注。
