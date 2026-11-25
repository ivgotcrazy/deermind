// 本页签内的评审数据。活动运行和课程检查继续读取服务端配置。
import { ref } from 'vue';

export const activities = [
  { id: 'explanation', name: '讲解' },
  { id: 'question', name: '答疑' },
  { id: 'detection', name: '检测' },
  { id: 'chat', name: '自由交谈' },
] as const;
export type Activity = (typeof activities)[number]['id'];
export type Choices = Partial<Record<Activity, string>>;
export type Guide = {
  id: string;
  family: string;
  activity: Activity;
  name: string;
  version: number;
  status: 'draft' | 'published' | 'retired';
  body: string;
};
export const statusNames = { draft: '草稿', published: '已发布', retired: '已停用' };

const general = [
  '## 目标\n帮助学生理解当前主题的关键概念、关系或方法。结合本次请求，判断学生想要概览、深入理解，还是看一次完整示范。',
  '## 范围\n确认对象是整本书、一章、一节、一个知识点，还是一道题。学生明确引用教材时，依据实际内容讲解。',
  '## 规划\n短问题直接讲。长任务先交代路线，随后开始第一部分。记录已覆盖的内容、尚未解决的问题和下次的起点。',
  '## 规则\n学生可以跳过、暂停或提出检测。追问结束后接回原来的位置；正式检测由程序准备题单，并由学生确认。',
  '## 策略\n概念易混时用对比例子；公式难懂时从现象、单位或成立条件切入。依据学生本次回应调整讲法。',
].join('\n\n');

function seed(): Guide[] {
  function guide(
    activity: Activity,
    family: string,
    name: string,
    version: number,
    body: string,
    status: Guide['status'] = 'published',
  ): Guide {
    return { id: family + '-' + version, activity, family, name, version, body, status };
  }
  return [
    guide('explanation', 'concept', '概念优先讲解', 2, general),
    guide(
      'explanation',
      'example',
      '例题驱动讲解',
      1,
      '## 方法\n先完整示范一道典型例题，讲清每个关键选择的理由，再邀请学生在相似问题上尝试。',
    ),
    guide(
      'explanation',
      'concept',
      '概念优先讲解',
      1,
      '## 方法\n从学生已知的例子出发，说明概念的含义，再给一个反例检验其适用范围。',
    ),
    guide(
      'explanation',
      'model',
      '从现象建立模型',
      1,
      '## 方法\n邀请学生预测结果，再用图示或数量关系检验预测。',
      'draft',
    ),
    guide(
      'question',
      'clarify',
      '围绕疑点答疑',
      1,
      '## 目标\n回应学生提出的具体疑问。\n\n## 方法\n能直接说明时先回答。存在多种解释时，先澄清分歧点。',
    ),
    guide(
      'detection',
      'independent',
      '独立检测',
      1,
      '## 方法\n说明本轮任务。学生求助时区分重看题目与实质帮助，待程序确认轮次结束后再提供提示。',
    ),
    guide(
      'chat',
      'open',
      '开放交流',
      1,
      '## 方法\n自然回应学生。出现明确的学习诉求时，衔接到对应活动。',
    ),
  ];
}

function createPreview() {
  return { guides: ref(seed()), bindings: new Map<string, Choices>() };
}
let current: ReturnType<typeof createPreview> | undefined;
let currentSession = '';

export function promptPreview(session: string) {
  if (!current || currentSession !== session) {
    current = createPreview();
    currentSession = session;
  }
  return current;
}
