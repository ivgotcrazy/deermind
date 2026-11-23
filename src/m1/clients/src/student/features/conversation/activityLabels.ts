import type { components } from '../../../../../contracts/generated/http/schema';

/** 目录和当前路径共用活动类型文案。 */
export const activityLabels: Record<components['schemas']['ActivityType'], string> = {
  explanation: '讲解',
  question_answer: '答疑',
  detection: '检测',
  free_chat: '自由交谈',
};
