import { fixturePlan, questions, spaces } from './data';
import { current, questionStatus, state } from './store';

// Read-only counts of authored prototype records, never a semantic assessment.
export function chapterViews() {
  const item = current();
  const ready = item.imported && !item.processing && !item.failure;
  return spaces[state.space].chapters.map((name, index) => {
    const indexes = fixturePlan(state.space, [name]);
    const records = indexes
      .filter((i) => ready && (item.kind === 'exam' || i === 2))
      .map((i) => ({ index: i, question: questions[state.space][i]!, result: questionStatus(i) }));
    const correct = records.filter((r) => r.result === 'correct').length;
    const wrong = records.filter((r) => r.result === 'wrong').length;
    const unclear = records.filter((r) => r.result === 'unclear').length;
    const judged = correct + wrong;
    const submitted = item.test.questionIndexes.filter(
      (i, answerIndex) => answerIndex < item.test.answers.length && indexes.includes(i),
    ).length;
    const helped = indexes.filter((i) =>
      item.helps.some((help) => help.startsWith(`${questions[state.space][i]!.id}:`)),
    ).length;
    const hasRecord = records.length > 0 || submitted > 0 || helped > 0;
    const corrected =
      ready &&
      item.kind === 'exam' &&
      item.corrected &&
      indexes.includes(1) &&
      state.space === 'school';
    return {
      index,
      name,
      indexes,
      records,
      correct,
      wrong,
      unclear,
      judged,
      submitted,
      helped,
      hasRecord,
      corrected,
      rate: judged ? Math.round((correct / judged) * 100) : null,
      tone: wrong ? 'attention' : unclear ? 'pending' : judged ? 'supported' : 'unknown',
      label: wrong
        ? '有待回顾'
        : unclear
          ? '有待确认'
          : judged
            ? '当次答对'
            : hasRecord
              ? '待进一步了解'
              : '暂无记录',
      summary: wrong
        ? `当前资料有 ${wrong} 题需要回顾，先看看具体卡在哪里。`
        : unclear
          ? `有 ${unclear} 题尚待确认，先核对材料再判断。`
          : judged
            ? '当前已判定的题目均答对，可以继续了解理由和不同题目的表现。'
            : submitted
              ? `已收到 ${submitted} 次检测作答，结果尚待核验。`
              : helped
                ? '已查看过教学帮助，尚无新的独立作答结果。'
                : '这里还没有可用的作答记录，不代表没有学过。',
    };
  });
}
export type ChapterView = ReturnType<typeof chapterViews>[number];

export function chapterExplanation(chapter: ChapterView) {
  return `${chapter.name}：${chapter.summary}\n\n资料中答对 ${chapter.correct} 题、待回顾 ${chapter.wrong} 题、待确认 ${chapter.unclear} 题。${chapter.judged ? `已判定 ${chapter.judged} 题，资料答对率 ${chapter.rate}%。` : '尚无可计算答对率的已判定作答。'}\n\n原资料作答时有无外部帮助尚不明确，这个比例不能当作独立作答正确率或整章掌握程度。${chapter.helped ? `本章已有 ${chapter.helped} 道题查看过帮助；查看帮助不表示已经独立完成。` : ''}\n\n还需了解关键理由、不同题目和间隔后的独立表现。${chapter.corrected ? '\n最近的记录变化来自识别纠正，不表示刚刚学会。' : ''}`;
}
