export type SpaceId = 'school' | 'extension';
export type Role = 'student' | 'parent' | 'admin';
export interface Question {
  id: string;
  topic: string;
  prompt: string;
  work: string;
  correct: string;
  status: 'correct' | 'wrong' | 'unclear';
  explanation: string[];
  hint: string;
}
export const spaces = {
  school: {
    name: '校内数学',
    short: '校内',
    subtitle: '六年级 · 示例课程',
    chapter: '百分数的应用',
    chapters: ['分数除法', '百分数的应用'],
    book: '六年级数学 · 示例教材',
    tag: '把数量关系看清楚',
    theme: '百分数',
  },
  extension: {
    name: '校外数学',
    short: '校外',
    subtitle: '进阶数学 · 示例课程',
    chapter: '整除与余数',
    chapters: ['整除与余数', '数的规律'],
    book: '进阶数学 · 示例教材',
    tag: '从规律开始思考',
    theme: '整除',
  },
} satisfies Record<SpaceId, object>;
export const questions: Record<SpaceId, Question[]> = {
  school: [
    {
      id: 'S-Q1',
      topic: '百分数与分数',
      prompt: '把 25% 化成最简分数。',
      work: '25% = 25/100 = 1/4',
      correct: '1/4',
      status: 'correct',
      explanation: [
        '百分数表示每一百份里有多少份。',
        '25% = 25/100，分子分母同时除以 25，得到 1/4。',
      ],
      hint: '先把百分数写成分母为 100 的分数。',
    },
    {
      id: 'S-Q2',
      topic: '分数除法',
      prompt: '计算：3/4 ÷ 1/2。',
      work: '3/4 ÷ 1/2 = 3/8',
      correct: '3/2',
      status: 'wrong',
      explanation: [
        '这道除法问的是：3/4 中有几个 1/2？',
        '一个 1/2 是 2/4。3 个 1/4 是它的 1.5 倍。',
        '所以 3/4 ÷ 1/2 = 3/4 × 2 = 3/2。',
      ],
      hint: '想一想：3/4 比 1/2 大，商应该大于 1 还是小于 1？',
    },
    {
      id: 'S-Q3',
      topic: '已知部分求整体',
      prompt: '一件上衣打八折后售价 160 元。这件上衣原价多少元？',
      work: '160 × 80% = 128（元）',
      correct: '200 元',
      status: 'wrong',
      explanation: [
        '八折的意思是：现价是原价的 80%。把原价看作完整的一份。',
        '已知的是其中 80% 对应 160 元，所以 1% 对应 160 ÷ 80 = 2 元。',
        '原价对应 100%，因此原价是 2 × 100 = 200 元。也可以列式：160 ÷ 80% = 200。',
        '检查一下：200 × 80% = 160，与题目中的现价相同。',
      ],
      hint: '160 元对应的是原价的 80%，还是完整的 100%？先找出哪一个量是整体。',
    },
  ],
  extension: [
    {
      id: 'E-Q1',
      topic: '整除',
      prompt: '写出 12 的所有正因数。',
      work: '1、2、3、4、6、12',
      correct: '1、2、3、4、6、12',
      status: 'correct',
      explanation: [
        '因数可以配对寻找：1×12，2×6，3×4。',
        '每对中的数都列出，就得到 1、2、3、4、6、12。',
      ],
      hint: '试着把相乘等于 12 的两个正整数配成一对。',
    },
    {
      id: 'E-Q2',
      topic: '余数的范围',
      prompt: '一个整数除以 5，余数可能是哪些数？',
      work: '1、2、3、4、5',
      correct: '0、1、2、3、4',
      status: 'wrong',
      explanation: [
        '余数必须小于除数，否则还能再分出一份。',
        '整除时余数是 0，所以可能的余数是 0、1、2、3、4。',
      ],
      hint: '正好除尽时，余数是多少？如果余下 5 个，还能不能再分一份？',
    },
    {
      id: 'E-Q3',
      topic: '公倍数',
      prompt: '一盏灯每 3 秒闪一次，另一盏灯每 5 秒闪一次。现在同时闪，几秒后首次再次同时闪？',
      work: '3 + 5 = 8（秒）',
      correct: '15 秒',
      status: 'wrong',
      explanation: [
        '分别列出两盏灯下一次闪的时刻。',
        '第一盏：3、6、9、12、15 秒；第二盏：5、10、15 秒。',
        '两列首次相同的是 15，所以 15 秒后再次同时闪。',
      ],
      hint: '把两盏灯分别闪烁的时刻写成两行，找第一个相同的时刻。',
    },
  ],
};
export const statusText = { correct: '本题答对', wrong: '需要回顾', unclear: '待确认' };
// Authored fixture mapping only; this is not a semantic matching algorithm.
export function fixturePlan(space: SpaceId, chapters: string[]) {
  const mapping = space === 'school' ? [[1], [0, 2]] : [[0, 1], [2]];
  return [
    ...new Set(
      spaces[space].chapters.flatMap((chapter, i) =>
        chapters.includes(chapter) ? mapping[i]! : [],
      ),
    ),
  ];
}
export const navs: Record<Role, { key: string; label: string; icon: string }[]> = {
  student: [
    { key: 'home', label: '学习首页', icon: 'home' },
    { key: 'materials', label: '我的资料', icon: 'folder' },
    { key: 'book', label: '我的教材', icon: 'book' },
    { key: 'learning', label: '学习情况', icon: 'chart' },
    { key: 'settings', label: '账号与设置', icon: 'user' },
  ],
  parent: [
    { key: 'overview', label: '学习概况', icon: 'chart' },
    { key: 'consult', label: '我的咨询', icon: 'chat' },
    { key: 'notices', label: '更正通知', icon: 'bell' },
    { key: 'settings', label: '账号与关联', icon: 'user' },
  ],
  admin: [
    { key: 'dashboard', label: '工作概览', icon: 'home' },
    { key: 'content', label: '教材与内容', icon: 'book' },
    { key: 'domain', label: '模型与映射', icon: 'nodes' },
    { key: 'issues', label: '反馈与纠错', icon: 'chat' },
    { key: 'tasks', label: '失败任务', icon: 'refresh' },
    { key: 'accounts', label: '账号与关联', icon: 'user' },
    { key: 'config', label: '模型服务', icon: 'settings' },
    { key: 'usage', label: '用量与费用', icon: 'chart' },
  ],
};
