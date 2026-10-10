import { current, state, questionStatus } from './store';
import { questions, spaces } from './data';

// These are explicitly authored UI fixtures, not an inference or scoring model.
export function learnerViews() {
  const item = current();
  return questions[state.space].map((q, index) => {
    const available =
      item.imported && !item.processing && !item.failure && (item.kind === 'exam' || index === 2);
    const assisted = item.helps.some((key) => key.startsWith(`${q.id}:`));
    const result = available ? questionStatus(index) : 'unknown';
    const chapter =
      spaces[state.space].chapters[
        state.space === 'school' ? (index === 1 ? 0 : 1) : index === 2 ? 1 : 0
      ]!;
    const title =
      state.space === 'school'
        ? ['把百分数转成分数', '理解并完成分数除法', '根据折后价求原价'][index]!
        : ['有序找出一个数的因数', '解释余数的取值范围', '在周期中寻找共同发生的时刻'][index]!;
    return {
      index,
      title,
      chapter,
      available,
      assisted,
      tone: result === 'correct' ? 'supported' : result === 'wrong' ? 'attention' : 'unknown',
      label:
        result === 'correct'
          ? '有当次表现支持'
          : result === 'wrong'
            ? '有一处值得回顾'
            : result === 'unclear'
              ? '材料需要核对'
              : '还不了解',
      assessment:
        result === 'correct'
          ? '这次题目的结果得到支持，尚不能据此确认同类任务已稳定掌握。'
          : result === 'wrong'
            ? '这次作答有问题，原因与当前能否独立完成还需要了解。'
            : result === 'unclear'
              ? '原作答尚未识别清楚，暂不据此判断会或不会。'
              : '本空间尚无可用于这项判断的已处理作答；没有记录不代表不会。',
      basis: available
        ? item.corrected && index === 1
          ? '原件复核后，先前的错误识别已纠正。当题反馈随之更新。'
          : '依据当前示例资料中的一次作答；还没有足够的跨题、延后表现。'
        : '目前没有适用的已处理资料。',
      conditions: assisted
        ? '原作答和后来看过的帮助分别保留；尚未取得帮助后的独立验证。'
        : '没有本原型提供帮助的记录；原卷作答时有无外部帮助尚不明确。',
      missing: '关键理由、不同条件下的独立应用，以及过一段时间后的表现，仍需适用证据。',
      change:
        item.corrected && index === 1
          ? '变化来自识别纠正，不表示孩子刚刚学会。'
          : assisted
            ? '新增的是看过帮助的记录，尚不意味着已经掌握。'
            : '尚无可确认的能力变化。',
    };
  });
}
