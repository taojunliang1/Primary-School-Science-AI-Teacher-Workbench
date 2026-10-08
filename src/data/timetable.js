// 演示课表取自用户提供的样例图片。后续接入课表 API 时替换此文件中的数据即可。
export const timetableDays = ['周一', '周二', '周三', '周四', '周五']

const empty = () => ({})
const lesson = (text, important = false) => ({ text, important, isClass: true })
const event = (text, options = {}) => ({ text, isClass: false, ...options })
const skip = () => ({ skip: true })

export const timetableRows = [
  {
    time: '08:30–09:10',
    slots: [event('升旗仪式'), empty(), empty(), empty(), event('教研', { rowSpan: 5, type: 'research' })],
  },
  {
    section: '大课间', time: '09:10–09:45', band: 'break',
    slots: [lesson('4.25（双）'), empty(), lesson('4.25'), lesson('4.25'), skip()],
  },
  {
    time: '09:45–10:25',
    slots: [empty(), lesson('4.21', true), empty(), lesson('4.25'), skip()],
  },
  {
    time: '10:40–11:20',
    slots: [empty(), empty(), empty(), empty(), skip()],
  },
  {
    time: '11:35–12:15',
    slots: [lesson('4.24'), lesson('4.26'), lesson('4.25'), empty(), skip()],
  },
  { time: '12:15–13:00', band: 'lunch', merged: '午餐（3.25）' },
  {
    section: '午管', time: '13:00–13:40', band: 'care',
    slots: [empty(), empty(), lesson('3.25 午管'), lesson('3.26 午管'), empty()],
  },
  {
    time: '14:00–14:40',
    slots: [lesson('4.20'), lesson('4.22'), empty(), lesson('4.26'), lesson('4.21', true)],
  },
  {
    time: '14:55–15:35',
    slots: [lesson('4.22'), lesson('4.23', true), lesson('4.20'), lesson('4.24'), lesson('4.23', true)],
  },
  {
    section: '延时服务', sectionRowspan: 3, time: '15:45–16:15', band: 'extended',
    slots: [empty(), lesson('无人机足球训练'), empty(), lesson('4.20'), empty()],
  },
  {
    sectionContinue: true, time: '16:25–16:55', band: 'extended',
    slots: [lesson('4.26 运动时空'), lesson('无人机足球训练'), empty(), empty(), lesson('4.26')],
  },
  {
    sectionContinue: true, time: '17:10–17:40', band: 'extended',
    slots: [empty(), lesson('无人机足球训练'), empty(), empty(), lesson('4.26')],
  },
]
