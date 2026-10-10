export const gradeOptions = ['一年级', '二年级', '三年级', '四年级', '五年级', '六年级']

export const preparationModes = {
  inquiry: {
    title: '科学探究设计', kicker: 'INQUIRY LAB',
    description: '把一个科学问题拆解为可执行、可记录、可讨论的课堂探究活动。',
    collection: '我的探究方案', itemName: '探究方案', preview: '探究活动流程',
    hint: '六步探究流程只是备课框架，实验操作与安全要求请结合真实器材核对。',
    fields: [
      { key: 'title', label: '探究主题', placeholder: '例如：不同材料在水中的沉浮', required: true, wide: true },
      { key: 'grade', label: '适用年级', type: 'grade', placeholder: '选择年级' },
      { key: 'duration', label: '活动时长', type: 'duration' },
      { key: 'materials', label: '器材与材料', placeholder: '记录单、透明容器、待测物体等', wide: true },
      { key: 'safety', label: '安全与组织提醒', placeholder: '根据实验实际情况补充安全事项、分组方式', wide: true },
    ],
    sections: [
      { key: 'question', label: '提出问题', hint: '学生将研究什么？问题是否可以通过观察或实验回答？' },
      { key: 'hypothesis', label: '作出假设', hint: '让学生写出预测，并说出预测依据。' },
      { key: 'plan', label: '制定计划', hint: '写清变量、分工、步骤和记录方式。' },
      { key: 'evidence', label: '搜集证据', hint: '将记录哪些现象、数据或照片？' },
      { key: 'analysis', label: '处理信息', hint: '如何整理、比较和解释证据？' },
      { key: 'conclusion', label: '得出结论', hint: '依据证据回答问题，并提出新的疑问。' },
    ],
    examples: [{ title: '不同材料在水中的沉浮', tag: '四年级 · 示例', data: {
      title: '不同材料在水中的沉浮', grade: '四年级', duration: '40 分钟', materials: '透明水槽、木块、塑料块、金属块、记录单。', safety: '检查器材边缘；每组安排操作员和记录员；及时擦干桌面。',
      question: '哪些材料制成的物体会浮在水面上？', hypothesis: '学生按已有经验预测各物体的沉浮，并说明理由。', plan: '保持同一水槽和水位；逐个轻放物体；每次观察后记录结果。', evidence: '用“浮/沉”表格记录各物体的表现，并标出与预测不符的结果。', analysis: '比较不同材料的实验结果，讨论“材料”是否足以解释所有现象。', conclusion: '依据记录回答探究问题；提出物体大小、形状等可能影响结果的新问题。',
    } }],
  },
  cases: {
    title: '科学教学案例', kicker: 'CLASSROOM STORIES',
    description: '整理真实课堂中的情境、教学处理与学生证据，积累可复用的科学教学经验。',
    collection: '我的教学案例', itemName: '教学案例', preview: '案例阅读',
    hint: '示例案例为虚构教学情境；正式记录学生作品和照片前，请先处理个人信息。',
    fields: [
      { key: 'title', label: '案例标题', placeholder: '例如：从“种子为什么没发芽”开始的追问', required: true, wide: true },
      { key: 'grade', label: '适用年级', type: 'grade', placeholder: '选择年级' },
      { key: 'topic', label: '对应课题 / 单元', placeholder: '例如：植物的生长' },
      { key: 'keywords', label: '关键词', placeholder: '例如：证据、对照实验、讨论', wide: true },
    ],
    sections: [
      { key: 'context', label: '课堂情境', hint: '描述课题、学生已有认识和当时发生的情境。' },
      { key: 'challenge', label: '关键问题', hint: '记录学生的疑问、误解或教学中的难点。' },
      { key: 'response', label: '教学处理', hint: '教师如何追问、组织活动或调整教学？' },
      { key: 'evidence', label: '学生表现与证据', hint: '记录学生的话语、观察记录或作品，不写真实姓名。' },
      { key: 'insight', label: '分析与启示', hint: '分析做法的效果、局限与可迁移经验。' },
    ],
    examples: [
      { title: '种子发芽条件的追问', tag: '四年级 · 示例', data: {
        title: '种子发芽条件的追问', grade: '四年级', topic: '植物的生长', keywords: '对照实验、证据', context: '学生讨论种子发芽时，有同学认为“多浇水一定长得更快”。', challenge: '学生把“有水”和“水越多越好”混为一谈。', response: '教师请各组设计两个只改变浇水量的对照方案，并预测结果。', evidence: '学生在记录表中发现过量积水组的变化与原先预测不一致。', insight: '先保留不同预测，再让学生用持续观察修正解释，有助于形成证据意识。',
      } },
      { title: '简易电路为什么没有亮', tag: '四年级 · 示例', data: {
        title: '简易电路为什么没有亮', grade: '四年级', topic: '电路', keywords: '故障排查、合作探究', context: '小组完成简易电路连接后，灯泡没有亮。', challenge: '学生急于更换电池，忽略了连接点和闭合回路。', response: '教师引导学生按“电源—导线—灯泡—开关”的顺序逐一检查。', evidence: '小组在检查记录中圈出了松动的连接点，并再次验证。', insight: '把故障排查变成有顺序的证据搜集过程，比直接告知答案更能帮助学生理解回路。',
      } },
      { title: '月相观察中的连续记录', tag: '六年级 · 示例', data: {
        title: '月相观察中的连续记录', grade: '六年级', topic: '地球与宇宙', keywords: '长期观察、记录', context: '学生带来的月相记录日期不连续，难以比较变化。', challenge: '单次观察难以支持月相变化的解释。', response: '教师组织学生汇总不同日期的记录，并统一记录时间和观察方向。', evidence: '班级共同制作了按日期排列的月相观察图。', insight: '统一记录规范后，分散的个人观察才能成为可比较的证据。',
      } },
    ],
  },
  papers: {
    title: '教研论文', kicker: 'RESEARCH NOTES',
    description: '围绕教学问题搭建论文结构，记录研究方法、课堂证据与实践反思。',
    collection: '我的论文草稿', itemName: '论文草稿', preview: '文章预览',
    hint: '本页仅提供写作结构和本地草稿；引用、数据与结论请在正式投稿前逐一核实。',
    fields: [
      { key: 'title', label: '论文题目', placeholder: '例如：小学科学探究活动中的证据表达策略', required: true, wide: true },
      { key: 'author', label: '作者署名', placeholder: '选填' },
      { key: 'keywords', label: '关键词', placeholder: '用分号分隔，例如：小学科学；科学探究', wide: true },
    ],
    sections: [
      { key: 'abstract', label: '摘要', hint: '简述研究问题、方法、发现与启示。' },
      { key: 'background', label: '一、问题提出', hint: '说明教学情境、问题与研究价值。' },
      { key: 'method', label: '二、研究方法', hint: '交代对象、材料、过程和证据来源。' },
      { key: 'practice', label: '三、教学实践与结果', hint: '按真实过程呈现课堂实践和观察结果。' },
      { key: 'discussion', label: '四、讨论与启示', hint: '解释结果、说明局限并提出可改进之处。' },
      { key: 'references', label: '参考文献', hint: '逐条填写已核实的来源，不要编造文献。' },
    ],
    examples: [{ title: '证据表达策略写作框架', tag: '结构示例', data: {
      title: '小学科学探究活动中的证据表达策略', author: '', keywords: '小学科学；探究活动；证据表达', abstract: '写明研究问题、课堂实践方法与主要发现。此处为写作提示，并非研究结论。', background: '描述学生在科学探究中表达观察证据时遇到的具体困难。', method: '说明研究对象、课例选择、观察记录方式与分析过程。', practice: '按课例记录教师支持策略和学生表现，插入经核实的数据或作品描述。', discussion: '结合证据讨论策略的作用、适用条件与研究局限。', references: '请填写实际阅读并核实过的文献。',
    } }],
  },
  reflections: {
    title: '心得体会', kicker: 'TEACHING JOURNAL',
    description: '把课堂中的亮点、困惑与下一步行动及时记录下来，形成持续改进的教学日志。',
    collection: '我的教学反思', itemName: '反思记录', preview: '反思卡片',
    hint: '教学反思只保存在当前浏览器；不要在演示阶段录入学生真实姓名或敏感信息。',
    fields: [
      { key: 'title', label: '记录标题', placeholder: '例如：四年级浮力实验课后反思', required: true, wide: true },
      { key: 'date', label: '授课日期', type: 'date' },
      { key: 'className', label: '班级', placeholder: '例如：四（1）班' },
      { key: 'topic', label: '对应课题', placeholder: '例如：浮力实验探究', wide: true },
    ],
    sections: [
      { key: 'highlights', label: '课堂亮点', hint: '哪些活动引发了有效讨论或新的发现？' },
      { key: 'evidence', label: '目标达成证据', hint: '学生的记录、发言或作品反映了什么？' },
      { key: 'difficulties', label: '遇到的问题', hint: '记录课堂中未解决的疑问或组织困难。' },
      { key: 'analysis', label: '原因分析', hint: '哪些教学设计、材料或时间安排影响了结果？' },
      { key: 'nextAction', label: '下次改进', hint: '写下一项具体、可执行的改进动作。' },
    ],
    examples: [{ title: '浮力实验课后反思', tag: '记录示例', data: {
      title: '浮力实验课后反思', date: '', className: '四（1）班', topic: '浮力实验探究', highlights: '学生愿意在操作前先提出预测，并主动比较不同小组的结果。', evidence: '多数小组完成了沉浮观察表，有小组能指出与预测不同的记录。', difficulties: '讨论环节部分学生只说结论，没有解释依据。', analysis: '记录表留给“证据说明”的空间不足；讨论时间也偏短。', nextAction: '下次在记录表增加“我依据什么判断”一栏，并预留 5 分钟小组互评。',
    } }],
  },
}
