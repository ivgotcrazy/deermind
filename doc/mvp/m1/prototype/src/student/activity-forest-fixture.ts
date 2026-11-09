import type { Activity, Turn } from './quarter';

// Isolated demonstration history; never merged into the learner's existing records.
export function activityForestFixture() {
  const time=(days:number,minutes:number)=>{
    const date=new Date();date.setDate(date.getDate()-days);
    if(days)date.setHours(18,minutes,0,0);
    else date.setMinutes(date.getMinutes()-20+minutes);
    return date.toISOString();
  };
  const activities:Activity[]=[
    {id:'DEMO-FREE',kind:'自由交谈',title:'今天想学什么',startedAt:time(2,0),status:'已结束',state:'结束'},
    {id:'DEMO-LESSON',kind:'讲解',title:'增加四分之一是什么意思',startedAt:time(2,5),status:'已结束',state:'结束'},
    {id:'DEMO-WHY',parentId:'DEMO-LESSON',kind:'答疑',title:'为什么还要加回原来的数量',startedAt:time(2,7),status:'已结束',state:'结束'},
    {id:'DEMO-DRAW',parentId:'DEMO-WHY',kind:'讲解',title:'用四格图看原量与新增量',startedAt:time(2,9),status:'已结束',state:'结束'},
    {id:'DEMO-CHECK',kind:'检测',title:'用新题检查四分之一',startedAt:time(1,0),status:'已结束',state:'结束',plan:2,used:2,helped:true},
    {id:'DEMO-HELP',parentId:'DEMO-CHECK',kind:'讲解',title:'48 升水增加四分之一',startedAt:time(1,5),status:'已结束',state:'结束',triggerRound:'DEMO-ROUND-2'},
    {id:'DEMO-BASE',parentId:'DEMO-HELP',kind:'答疑',title:'四分之一是按哪个量算的',startedAt:time(1,7),status:'已结束',state:'结束'},
    {id:'DEMO-CURRENT',kind:'讲解',title:'把两步计算写成一个算式',startedAt:time(0,0),status:'暂停',state:'回应中'},
    {id:'DEMO-BRACKET',parentId:'DEMO-CURRENT',kind:'答疑',title:'括号里的 1 代表什么',startedAt:time(0,2),status:'进行中',state:'回应中'},
  ];
  const turns:Turn[]=[
    {activityId:'DEMO-FREE',question:'今天想学分数，但不知道从哪里开始。',reply:'可以先弄清“增加四分之一”，再试一道题。过程中有疑问随时问。',card:'free'},
    {activityId:'DEMO-LESSON',question:'那就讲讲增加四分之一吧。',reply:'原有 80 本书，增加原来数量的四分之一。先求新增的 20 本，再求现在的总数。',card:'example'},
    {activityId:'DEMO-WHY',question:'算出 20 本，为什么还要加回 80 本？',reply:'20 本只是新增加的书，原来的 80 本还在。“现在共有多少本”问的是两部分合起来。'},
    {activityId:'DEMO-DRAW',question:'还是有点绕，可以画出来吗？',reply:'先把原来的书画成四格，新增的是同样大小的一格。',card:'diagram'},
    {activityId:'DEMO-WHY',question:'明白了，20 本只是第五格。',reply:'对，原来的四格没有消失，所以现在共有五格。这个疑问先解决了。'},
    {activityId:'DEMO-LESSON',question:'所以是 80 + 80 ÷ 4 = 100。',reply:'是的。这段讲解结束；是否能独立运用，还需要看新题中的表现。'},
    {activityId:'DEMO-CHECK',roundId:'DEMO-ROUND-1',question:'我想用新题测一下。',reply:'先独立求出结果，再写出理由。',card:'check',check:{item:0,status:'submitted',answer:'150',reason:'原有 120 本，新增 120 ÷ 4 = 30 本，共 150 本。'},feedback:true},
    {activityId:'DEMO-CHECK',roundId:'DEMO-ROUND-2',question:'再来一道。',reply:'这一轮换成水量。',card:'check',check:{item:1,status:'help',answer:'12',reason:'48 ÷ 4 = 12，但不知道是否还需要加。'}},
    {activityId:'DEMO-HELP',question:'这轮先结束，给我讲讲。',reply:'独立检测轮已经结束，现在开始讲解。48 升是原来的四份，增加的一份是 12 升。',card:'diagram',exampleItem:1},
    {activityId:'DEMO-BASE',question:'四分之一是 48 的，还是增加以后的？',reply:'题目说“原有水量的四分之一”，所以以原来的 48 升为基准。'},
    {activityId:'DEMO-HELP',question:'那就应该是 48 + 12 = 60 升。',reply:'对。这是讲解后的回答，不能算作刚才那轮的独立作答。'},
    {activityId:'DEMO-CHECK',question:'今天这次检测先到这里。',reply:'已保留第一题的作答和第二题的求助记录。本次检测结束，不据此宣称所有方面已经掌握。'},
    {activityId:'DEMO-CURRENT',question:'想学一下怎么把两步合成一个算式。',reply:'仍用原有 80 本书的例子。原量和新增量都以 80 为基准，可以合并为乘法。',card:'formula'},
    {activityId:'DEMO-BRACKET',question:'括号里的 1 是什么？为什么不是只乘四分之一？',reply:'1 表示原来的全部，四分之一表示新增加的部分。只乘四分之一，求到的只有新增量。这个疑问解决后，我们再回到合并算式。',card:'formula'},
  ];
  const notices=[
    {at:0,startId:'DEMO-FREE',text:'开始自由交谈 · 今天想学什么'},
    {at:1,text:'自由交谈结束，开始讲解',startId:'DEMO-LESSON',detail:'增加四分之一是什么意思'},
    {at:2,text:'先解答 · 为什么还要加回原来的数量',startId:'DEMO-WHY',detail:'讲解进度已保留。'},
    {at:3,text:'用图讲解 · 用四格图看原量与新增量',startId:'DEMO-DRAW',detail:'讲完后回到刚才的疑问。'},
    {at:4,text:'图解结束，回到答疑'},
    {at:5,text:'答疑结束，继续原来的讲解'},
    {at:6,text:'本次讲解已结束'},
    {at:6,text:'开始检测 · 用新题检查四分之一',startId:'DEMO-CHECK'},
    {at:7,text:'第一轮已提交，开始第二轮'},
    {at:8,text:'第二轮因求助结束，草稿已保留'},
    {at:8,text:'开始讲解 · 48 升水增加四分之一',startId:'DEMO-HELP',detail:'讲解结束后回到本次检测；旧检测轮不会重新开启。'},
    {at:9,text:'先解答 · 四分之一是按哪个量算的',startId:'DEMO-BASE'},
    {at:10,text:'答疑结束，继续水量题的讲解'},
    {at:11,text:'讲解结束，回到检测，查看本轮结果'},
    {at:12,text:'本次检测已结束'},
    {at:12,text:'开始讲解 · 把两步计算写成一个算式',startId:'DEMO-CURRENT'},
    {at:13,text:'先解答 · 括号里的 1 代表什么',startId:'DEMO-BRACKET',detail:'讲解主线已保留，答疑后可继续。'},
  ];
  return {activities,turns,notices,activeId:'DEMO-BRACKET',expandedActivities:['DEMO-CURRENT','DEMO-LESSON','DEMO-WHY','DEMO-CHECK','DEMO-HELP']};
}
