export type Role = 'student' | 'parent' | 'admin';
export type RecordItem = { id:string; learner:string; space:string; chapter:string; title:string; problem?:string; date:string; source:string; outcome:string; answer:string; help:string; kind:string; practice?:{problem:string;answer:string} };
export const learners = Array.from({length:1000},(_,i)=>({id:`S${String(i+1).padStart(4,'0')}`,name:i===0?'林同学':i===41?'周同学':`${['陈','李','王','刘','周'][i%5]}同学 ${Math.floor(i/5)+1}`,role:'学生'}));
export const parents = Array.from({length:1500},(_,i)=>({id:`P${String(i+1).padStart(4,'0')}`,name:`${['陈','李','王','刘','周'][i%5]}家长 ${Math.floor(i/5)+1}`,role:'家长'}));
export const accounts=[...learners,...parents];
export const chapters = [
 {id:'fractions',position:4,name:'分数的应用',order:'第四单元',goal:'看清比较中的标准量，再解释为什么这样计算',requirements:['找出比较中的标准量','解释相差的分数','用图与算式表达数量关系','求增加或减少后的量','处理分数混合运算','检查结果是否符合条件'],
  segments:[{title:'先找清楚：和谁比？',body:'甲有 12 张卡片，乙有 9 张。想知道“甲比乙多几分之几”，要把乙的 9 张看成比较标准。先找多出的部分，再与标准量比较。',formula:'多出 12 − 9 = 3 张；标准量是乙的 9 张。'},
   {title:'同样相差 3 张，为什么答案不同？',body:'“甲比乙多”的标准是乙；“乙比甲少”的标准是甲。相差的数量相同，比较标准不同，所占的分数也会不同。',formula:'甲比乙多：3 ÷ 9 = 1/3；乙比甲少：3 ÷ 12 = 1/4。'},
   {title:'把你的判断说完整',body:'先说“把谁看作标准”，再说“相差多少”，最后解释为什么用这个数量作除数。图上的整段、算式的除数和语言中的标准应当一致。',formula:'相差的分数 = 相差量 ÷ 标准量'}],
  question:'小青有 15 张卡片，小雨有 12 张。小青比小雨多几分之几？请说明比较标准。',reference:'以小雨的 12 张为标准，相差 3 张，3 ÷ 12 = 1/4。'},
 {id:'circle',position:1,name:'圆',order:'第一单元',goal:'理解半径和直径怎样决定圆的大小',requirements:['辨认圆心、半径与直径','解释直径与半径的关系','运用周长公式','解释面积公式的意义'],
  segments:[{title:'圆心到圆周有多远？',body:'圆心到圆上任意一点的线段都是半径。同一个圆中，半径的长度相等。',formula:'同一个圆中，所有半径相等。'},
   {title:'直径为什么等于两条半径？',body:'一条通过圆心、两端都在圆上的线段是直径。圆心把它分成两条半径。',formula:'直径 d = 2r'},
   {title:'说明条件，再使用关系',body:'使用直径与半径的关系时，要确认讨论的是同一个圆。两条任意弦相加并不一定是一条直径。',formula:'同一个圆：r = d ÷ 2'}],
  question:'一个圆的直径是 10 厘米，它的半径是多少？为什么？',reference:'半径是 5 厘米。通过圆心的直径由两条半径组成。'},
 {id:'ratio',position:6,name:'比的认识',order:'第六单元',goal:'理解比的顺序与实际意义',requirements:['解释比的前后项','联系除法理解比值','保持比的顺序'],
  segments:[{title:'先说谁与谁比较',body:'红球 6 个、蓝球 4 个。红球与蓝球的数量比是 6∶4；交换比较顺序，比的前后项也交换。',formula:'红∶蓝 = 6∶4'},
   {title:'比值表示怎样的关系？',body:'用红球数量除以蓝球数量，得到红球数量是蓝球的几倍。',formula:'6 ÷ 4 = 3/2'},
   {title:'带上对象解释结果',body:'单独写一个比不足以说明对象和顺序。完整表达应说明比较的两个量。',formula:'红球数量是蓝球的 3/2 倍。'}],
  question:'红球 8 个、蓝球 6 个，红球与蓝球的数量比是多少？请说明顺序。',reference:'红球与蓝球是 8∶6，也可化为 4∶3。'}
].sort((a,b)=>a.position-b.position);
export const chapterOf=(id:string)=>chapters.find(c=>c.id===id);
export const spaceName=(id:string)=>id==='school'?'校内数学':'校外数学';
export const learnerName=(id:string)=>learners.find(x=>x.id===id)?.name||id;
export function requirementState(learner:string,index:number){return ['已达标','需加强','待确认'][(index+(learner==='S0042'?1:0))%3]!;}
export function historicalRecords(learner:string,space:string):RecordItem[]{
 if(space!=='school')return [];
 return Array.from({length:1000},(_,i)=>{const c=chapters[i%chapters.length]!;return {id:`R-${learner}-${i+1}`,learner,space,chapter:c.id,title:i%5===0?c.question:`${c.name} · ${['解释理由','比较方法','计算并检查','图形与数量关系'][i%4]} ${Math.floor(i/3)+1}`,date:i%37===0?'':new Date(Date.UTC(2026,9,16-Math.floor(i/5))).toISOString().slice(0,10),source:['讲解练习','检测','外部录入'][Math.floor(i/3)%3]!,outcome:['正确','错误','尚未判定','未作答'][i%4]!,answer:i%4===3?'':i%3===0?c.reference:'这是一条预写作答资料，供检查记录组织。',help:i%3===0?'已看过本段讲解':'本次记录未记载额外帮助；不据此保证独立',kind:'题目'};});
}
export const activityIndex=Array.from({length:10000},(_,i)=>({id:`ACT-${String(i+1).padStart(5,'0')}`,learner:learners[i%1000]!.id,title:`${chapters[i%3]!.name} · ${['章节讲解','问题求助','范围检测'][Math.floor(i/3)%3]}`,chapter:chapters[i%3]!.id,space:'school',status:['已结束','待核对','处理中'][i%3]!,date:`2026-10-${String(17-i%17).padStart(2,'0')}`}));
export const modelIndex=Array.from({length:5000},(_,i)=>({id:`OBJ-${String(i+1).padStart(5,'0')}`,title:`${['比较量与标准量','分数运算','圆的关系','结果解释','帮助条件'][i%5]} ${Math.floor(i/5)+1}`,space:['Domain','Domain','Domain','Evaluation','Interaction','Evolution','Learning'][i%7]!,type:['ProblemTemplate','SolutionTemplate','KC','Claim','交互规则','维护规则','目标定义'][i%7]!,version:`v${1+i%3}`,status:i%4===0?'候选':'有效'}));
export const materialIndex=Array.from({length:20},(_,i)=>({id:`MAT-${String(i+1).padStart(3,'0')}`,title:i===0?'六年级上册 · 校内数学':`数学课程材料 ${i+1}`,version:`v${i%3+1}`,status:i%3===0?'部分就绪':'待核对'}));
export const taskIndex=Array.from({length:200},(_,i)=>({id:`JOB-${String(i+1).padStart(4,'0')}`,title:['输入处理','教材识别','评价更新','版本影响处理'][i%4]!,status:['待核对','处理中','已完成','失败'][i%4]!,date:`2026-10-${String(17-i%17).padStart(2,'0')}`}));
