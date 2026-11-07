export type LessonCard = 'example' | 'diagram' | 'formula' | 'offer' | 'check' | 'finish';
export type Check = { item:number; status:'answering'|'submitted'|'help'|'stopped'; answer:string; reason:string };
export type Turn = { question:string; reply:string; chapter:string; page:string; card?:LessonCard; check?:Check; exampleItem?:number };

export const items = [
  {text:'图书角原有 120 本书，又增加了原来数量的四分之一。现在共有多少本？', base:120, unit:'本', total:150, steps:'120 ÷ 4 = 30（本），120 + 30 = 150（本）。'},
  {text:'水箱原有 48 升水，又加入原有水量的四分之一。现在共有多少升水？', base:48, unit:'升', total:60, steps:'48 ÷ 4 = 12（升），48 + 12 = 60（升）。'},
];
export const cardReply:Record<LessonCard,string> = {
  example:'用一个图书角的例子看：“增加四分之一”里的四分之一，指原有书的四分之一。',
  diagram:'换个看法。原来的 80 本平均分成四份，新增的书正好是一份。',
  formula:'你问的是两种写法为什么相等。两个加数都用 80 作基准，可以把 80 提到括号外。',
  offer:'来一道新题：自己求出新量，再说说四分之一指哪个量。你准备好时再开始。',
  check:'', finish:'今天先到这里。下次可以从这段对话接着学。',
};
export function chooseCard(text:string, previous?:Turn):LessonCard | undefined {
  if (/先到这|结束讲解|不学了/.test(text)) return 'finish';
  if (/检测|测验|测一下|试一题|出.*题/.test(text)) return 'offer';
  if (!previous?.card && !/四分之一|增加|1\s*\/\s*4/.test(text)) return;
  if (/乘法|括号|合并|为什么.*乘|为什么.*加.*1/.test(text)) return 'formula';
  if (/没懂|不懂|换|画|四格/.test(text) && previous?.card) return 'diagram';
  if (/四分之一|增加|1\s*\/\s*4/.test(text)) return 'example';
}
