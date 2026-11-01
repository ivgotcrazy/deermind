import { chapterReady, type FlowState } from '../../shared/learning-flow';
import { fractionAssessment, isFractionLesson, correctionFor } from '../../shared/fraction-assessment';
import { chainAssessment, isChainLesson } from '../../shared/fraction-chain';
import { original, type TeachingSession } from './teaching-session';
import type { StudentCourse, QuestionView, ActivityView, RequirementView, LearningJudgment } from './student-pages';

export function flowCourse(state:FlowState, spaceId:string):StudentCourse {
  const space=state.spaces.find(s=>s.id===spaceId)!;
  const course=state.courses.find(c=>c.id===space.courseId)!;
  const lessons=state.lessons.filter(a=>a.spaceId===spaceId);
  const uses=state.uses.filter(u=>u.spaceId===spaceId);
  const questions:QuestionView[]=[];
  for(const u of uses){
    let q=questions.find(q=>q.id===u.question.id);
    if(!q){q={id:u.question.id,chapterId:lessons.find(a=>a.id===u.activityId)?.chapterId||'',text:u.question.question,source:u.purpose==='检测'?'检测':'讲解练习',attempts:[],quantity:u.question.quantity,figure:u.question.figure==='length'?'length':undefined};questions.push(q);}
    const onlyNumber=lessons.find(a=>a.id===u.activityId)?.fractionCase==='bare';
    if(u.answer)q.attempts.push({id:u.id,at:u.at,answer:u.answer,result:u.result==='错误'?'错误':u.result==='正确'&&!onlyNumber?'正确':'待判定',help:u.purpose==='练习'?'受助作答':'帮助情况未确认',detail:(onlyNumber?'数值正确，解释尚未确认；':'')+u.help,activityId:u.activityId,ended:lessons.find(a=>a.id===u.activityId)?.stage==='finished',invalid:correctionFor(state,u)?.reason});
  }
  const activities:ActivityView[]=[];
  for(const a of lessons){
    const shown=uses.filter(u=>u.activityId===a.id),taught=shown.find(u=>u.purpose==='讲解'),tested=shown.filter(u=>u.purpose==='检测');
    const title=a.snapshot.book.units.flatMap(u=>u.chapters).find(c=>c.id===a.chapterId)?.name||'学习';
    const end=a.stage==='finished'?a.messages[a.messages.length-1]?.at:undefined;
    if(taught)activities.push({id:a.id,chapterId:a.chapterId,title,kind:'讲解',detail:a.stage==='finished'?'本次已结束，可以回看对话与作答。':'进度和草稿已保留。',at:taught.at,finished:a.stage==='finished',endedAt:end,learningDates:[...new Set([taught.at,...shown.filter(u=>u.answer&&u.purpose!=='检测').map(u=>u.at)].map(t=>t.slice(0,10)))]});
    if(tested.length)activities.push({id:taught?a.id+':test':a.id,chapterId:a.chapterId,title:title+' · 检测',kind:'检测',detail:a.stage==='finished'?'检测已结束，保留实际作答与帮助条件。':'检测进行中，尚未计入已结束次数。',at:tested[0]!.at,finished:a.stage==='finished',endedAt:end,partial:a.endReason!=='完成',learningDates:[...new Set(tested.map(u=>u.at.slice(0,10)))]});
    if(taught)for(const q of questions)for(const t of q.attempts){if(t.activityId===a.id&&tested.some(u=>u.id===t.id))t.activityId=a.id+':test';}
  }
  const chapters=course.snapshot.book.units.flatMap(unit=>unit.chapters.map(ch=>{
    const ready=chapterReady(course.snapshot,ch.id);
    const finished=lessons.filter(a=>a.chapterId===ch.id&&a.stage==='finished'&&a.snapshot.target.revision===course.snapshot.target.revision&&a.snapshot.book.revision===course.snapshot.book.revision);
    const rows=finished.flatMap<{id:string;status:LearningJudgment;belief:string;reason:string}>(a=>isFractionLesson(a)?fractionAssessment(state,a):isChainLesson(a)?chainAssessment(state,a).rows:[]);
    const requirements:RequirementView[]=course.snapshot.target.claims.flatMap(c=>c.requirements).filter(r=>r.chapterIds.includes(ch.id)).map(r=>{
      const relevant=rows.filter(x=>r.aspectIds.includes(x.id));
      const judgments=new Set(relevant.map(x=>x.status));
      const conflict=judgments.has('已达标')&&judgments.has('需加强');
      const status:LearningJudgment=conflict?'待确认':judgments.has('需加强')?'需加强':relevant.length&&relevant.every(x=>x.status==='已达标')?'已达标':'待确认';
      const reason=conflict?'不同有效记录的判断有冲突，需要进一步确认。':relevant.length?[...new Set(relevant.map(x=>x.belief+' '+x.reason))].join(' '):'尚无足够的有效学习表现，不代表不会。';
      return {id:r.id,name:r.name,status,standard:r.standard.replace(/Claim/g,'本项要求'),reason,questionIds:questions.filter(q=>q.chapterId===ch.id&&q.attempts.some(t=>!t.invalid&&finished.some(a=>t.activityId?.replace(/:test$/,'')===a.id))).map(q=>q.id)};
    });
    const weak=requirements.find(r=>r.status==='需加强');
    return {id:ch.id,name:ch.name,unit:unit.name,description:ch.content||ch.name,conclusion:weak?weak.name+'还需要帮助。':requirements.length?'已保留当前表现；未满足的证据条件仍待确认。':'本章尚无可用的评价要求。',requirements,explain:ready.explain,test:ready.test,unavailable:ready.reason,items:ch.items?.filter(i=>i.reviewed)};
  }));
  return {id:spaceId,title:course.snapshot.book.name,target:course.snapshot.target.name,asOf:new Intl.DateTimeFormat('sv-SE',{timeZone:'Asia/Shanghai'}).format(new Date()),chapters,questions,activities:activities.sort((a,b)=>b.at.localeCompare(a.at)),note:'Mock 学习记录与预设评价；不代表真实能力推断。'};
}

export function teachingCourse(session:TeachingSession):StudentCourse {
  const texts:Record<string,string>={basic:'18人的三分之一是多少人？请解释。',original,contrast:'比较摄影组的四分之三与气象组的四分之三，为什么不同？',practice:'手工社团24人，折纸组占1/3，纸花组占折纸组的3/4。纸花组有多少人？','CHAIN-TEXT@1':'30本书中，科普书占2/5，动物书占科普书的1/2。动物书有多少本？','CHAIN-DIAGRAM@1':'40平方米苗圃中，花区占3/5，月季占花区的1/2。月季有多少平方米？'};
  const questions:QuestionView[]=[];
  for(const [i,a] of session.state.attempts.entries()){
    let q=questions.find(q=>q.id===a.item);
    if(!q){q={id:a.item,chapterId:'chain',text:texts[a.item]||a.item,source:a.purpose==='检测'?'检测':'讲解练习',attempts:[]};questions.push(q);}
    q.attempts.push({id:'TEACH-'+i,answer:a.answer,result:['参照量错误','需继续讲解'].includes(a.result)?'错误':a.result==='正确且理由充分'||a.result==='本次回答符合预设要求'?'正确':'待判定',help:a.purpose==='练习'?'受助作答':'帮助情况未确认',detail:a.help+'；'+a.basis,activityId:'teaching',ended:session.state.testFinished});
  }
  const requirements:RequirementView[]=session.summary.value.map((r,i)=>({id:'TEACH-R'+i,name:['说明两层分数各对应谁','从嵌套区域图中找出两层关系','不借助讲解完成同类问题','间隔后仍能完成同类问题'][i]!,status:r.target==='需加强'?'需加强':'待确认',standard:r.judgment,reason:r.target==='需加强'?r.judgment:r.judgment+'。局部支持仍不足以确认达标。',questionIds:questions.map(q=>q.id)}));
  return {id:'teaching-'+session.state.scenario,title:'北师大版六年级上册数学',target:'分清两层分数各对应谁',asOf:'2026-10-29',note:'固定教学情境；未记录真实日期与用时，不计入近期使用统计。',chapters:[{id:'chain',name:'分数的应用',unit:'第五单元 分数的应用',description:'连续求一个量的几分之几',conclusion:'查看已有表现及尚待确认的要求。',requirements,explain:true,test:true}],questions,activities:[{id:'teaching',chapterId:'chain',title:'分清两层分数各对应谁',detail:'原对话与输入进度保留。',kind:'讲解',at:'',finished:session.state.step==='summary',learningDates:[]}]};
}
