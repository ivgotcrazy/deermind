import type { components } from '../../../../../contracts/generated/http/schema';

/** 目录和当前路径共用活动类型文案。 */
export const activityLabels: Record<components['schemas']['ActivityType'], string> = {
  explanation: '讲解',
  question_answer: '答疑',
  detection: '检测',
  free_chat: '自由交谈',
};

const day = new Intl.DateTimeFormat('zh-CN', { year: 'numeric', month: 'numeric', day: 'numeric' });
export const activityClock = new Intl.DateTimeFormat('zh-CN', {
  hour: '2-digit',
  minute: '2-digit',
  hourCycle: 'h23',
});

export function activityDay(value: string) {
  const today = new Date();
  const yesterday = new Date(today);
  yesterday.setDate(today.getDate() - 1);
  const label = day.format(new Date(value));
  if (label === day.format(today)) return '今天';
  if (label === day.format(yesterday)) return '昨天';
  return label;
}
