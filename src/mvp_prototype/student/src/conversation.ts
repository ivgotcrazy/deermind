import type { StudentCourse, ActivityView, QuestionView } from './student-pages';

export type ActivityKind = '讲解' | '检测' | '答疑';
export interface ConversationActivity {
  id:string; title:string; kind:ActivityKind; chapters:string[]; status:'进行中'|'已保留'|'已结束';
  at:string; lastAt:string; endedAt?:string; detail:string; submitted?:boolean; answer?:string;
}
export interface ConversationMessage {
  id:string; at:string; role:'user'|'assistant'|'event'; text:string; activityId?:string;
  reference?:string; action?:'offer'|'question';
}
export interface ConversationRequest { kind:ActivityKind|'交流'; title:string; chapters:string[]; text:string; resumeId?:string; reference?:string }
export interface Conversation {
  spaceId:string; messages:ConversationMessage[]; activities:ConversationActivity[]; currentId:string;
  draft:string; referenceId:string; pending?:ConversationRequest; offer?:ConversationRequest;
}
export const conversationStorageKey='deermind-space-conversations-v1';
export const now=()=>new Date().toLocaleString('sv-SE',{timeZone:'Asia/Shanghai'}).slice(0,16);
const id=()=>crypto.randomUUID();
export const currentActivity=(c:Conversation)=>c.activities.find(a=>a.id===c.currentId && a.status==='进行中');

export function append(c:Conversation,role:ConversationMessage['role'],text:string,activityId?:string,extra:Partial<ConversationMessage>={}) {
  const message={id:id(),at:now(),role,text,activityId,...extra};c.messages.push(message);return message;
}
export function seedConversation(course:StudentCourse):Conversation {
  const c:Conversation={spaceId:course.id,messages:[],activities:[],currentId:'',draft:'',referenceId:''};
  for(const a of [...course.activities].reverse()){
    c.activities.push({id:a.id,title:a.title,kind:a.kind,chapters:[a.chapterId],status:a.finished?'已结束':'已保留',at:a.at,lastAt:a.endedAt||a.at,endedAt:a.endedAt,detail:a.detail});
    append(c,'event',a.title,a.id,{at:a.at});
    append(c,'user',a.kind==='检测'?'我想检测一下。':'请讲讲'+a.title+'。',a.id,{at:a.at});
    const qs=course.questions.filter(q=>q.attempts.some(t=>t.activityId===a.id));
    for(const q of qs){
      append(c,'assistant',q.text,a.id,{at:q.attempts.find(t=>t.activityId===a.id)?.at||a.at});
      for(const t of q.attempts.filter(t=>t.activityId===a.id))append(c,'user',t.answer,a.id,{at:t.at||a.at});
    }
    append(c,'assistant',a.id==='DEMO-L2'?'图里的原长是80米，新增段是原长的四分之一，也就是20米。你觉得20米表示新增段，还是整条的总长？':a.detail,a.id,{at:a.endedAt||a.at});
  }
  return c;
}

export function finishActivity(c:Conversation,reason='本次先到这里') {
  c.offer=undefined;
  const a=currentActivity(c);if(!a)return;
  a.status='已结束';a.endedAt=now();a.lastAt=now();
  a.detail=a.kind==='检测'?(a.submitted?'已提交作答；'+reason:'未提交作答；'+reason+'，不计为答错。'):reason+'，保留已经发生的交流，不据此认定掌握。';
  append(c,'event',a.detail,a.id);c.currentId='';c.offer=undefined;
}
function pauseCurrent(c:Conversation) {
  const a=currentActivity(c);if(!a)return;
  a.status='已保留';a.lastAt=now();a.detail='进度已保留，可从历史或首页继续。';
  append(c,'event','已保留：'+a.title,a.id);c.currentId='';
}
function lessonReply(title:string,chapters:string[]) {
  if(chapters.includes('c4-3')||title==='增加量与总量')return '增加四分之一，增加的是原来的四分之一。以80本书为例：80 × 1/4 = 20本是新增的，原有80本还在，所以总量是80 + 20 = 100本。你想先分清“增加量”和“总量”，还是换一个例子？';
  if(chapters.includes('c3-2'))return '圆柱的表面积包括两个底面和一个侧面。把侧面沿高展开，会得到一个长方形，长等于底面周长，宽等于圆柱的高。我们先看展开图为什么会有这三部分。';
  if(chapters.includes('c1-1'))return '可以把0℃作为参照：零下3℃记作−3℃。温度升高5℃，从−3向上移动5格，得到2℃。先分清起点和变化方向。';
  return '已收到“'+title+'”。这个章节暂未编写完整教学示例；可以在同一对话中继续表达问题，原有学习进度已保留。';
}
export function performRequest(c:Conversation,r:ConversationRequest) {
  c.pending=undefined;c.offer=undefined;
  const old=currentActivity(c);
  if(old && old.id!==r.resumeId && r.kind!=='检测')pauseCurrent(c);
  if(r.kind==='交流') {append(c,'user',r.text,undefined,{reference:r.reference});append(c,'assistant','我在。你可以说说想学什么，或从右侧选择内容。');return;}
  if(r.kind==='检测'){
    c.offer=r;append(c,'user',r.text,undefined,{reference:r.reference});
    append(c,'assistant','本次检查：区分增加量与总量。1题，约3分钟。上文仍可回看，实际接触的帮助需要保留；求助会先结束检测。准备好后再开始。',undefined,{action:'offer'});return;
  }
  let a=c.activities.find(a=>a.id===r.resumeId && a.status!=='已结束');
  const resumed=!!a;
  if(!a){a={id:id(),title:r.title,kind:r.kind,chapters:r.chapters,status:'进行中',at:now(),lastAt:now(),detail:'正在交流，尚未形成新的能力判断。'};c.activities.push(a);}
  a.status='进行中';a.lastAt=now();c.currentId=a.id;
  append(c,'event',(resumed?'继续：':'开始：')+a.title,a.id);
  append(c,'user',r.text,a.id,{reference:r.reference});
  const previous=c.messages.filter(m=>m.activityId===a.id&&m.role==='assistant').slice(-1)[0];
  append(c,'assistant',resumed?'接着上次的内容：'+(previous?.text||a.detail):lessonReply(r.title,r.chapters),a.id);
}
export function requestActivity(c:Conversation,r:ConversationRequest) {
  if(currentActivity(c)?.kind==='检测'){c.pending=r;return false;}
  performRequest(c,r);return true;
}
export function confirmSwitch(c:Conversation) {
  const r=c.pending;if(!r)return;finishActivity(c,'为切换内容而结束检测');performRequest(c,r);
}
export function beginCheck(c:Conversation) {
  const r=c.offer;if(!r || currentActivity(c)?.kind==='检测')return;
  pauseCurrent(c);c.offer=undefined;
  const a:ConversationActivity={id:id(),title:r.title,kind:'检测',chapters:r.chapters,status:'进行中',at:now(),lastAt:now(),detail:'1题，尚未提交。'};
  c.activities.push(a);c.currentId=a.id;
  append(c,'event','开始检测：'+a.title,a.id);
  append(c,'assistant','图书角原有120本书，又增加了原有数量的四分之一。现在共有多少本？请写出答案和理由。',a.id,{action:'question'});
}
export function submitCheck(c:Conversation,text:string) {
  const a=currentActivity(c);if(a?.kind!=='检测')return;
  append(c,'user',text,a.id);a.submitted=true;a.answer=text;c.draft='';
  finishActivity(c,'已提交1／1题，检测结束');
  append(c,'assistant',text===sampleAnswer?'示例反馈：150本。120 × 1/4 = 30本是增加量，加回原来的120本得到150本。本题答案与理由符合预设参考；当前仅记录这一次表现，不自动改写学习要求达标状态，也不宣称持久掌握。':'已收到答案和理由。当前 mock 尚未编写这份回答的判定，保留为待判定，不计错，也不自动改变学习状态。',a.id);
}
export const sampleAnswer='150本。120 × 1/4 = 30本是增加的，再加回原有120本。';
export function helpDuringCheck(c:Conversation) {
  const a=currentActivity(c);if(a?.kind!=='检测')return;
  const chapters=[...a.chapters];append(c,'user','请讲解这道题。',a.id);finishActivity(c,'请求讲解，先结束检测');
  performRequest(c,{kind:'答疑',title:'检测后的题目讲解',chapters,text:'讲讲刚才的检测题'});
  append(c,'assistant','这题原有120本，增加120 × 1/4 = 30本，所以现在有150本。刚才未提交的输入仍是草稿，不作为正式作答。',c.currentId);
}

// Only the explicitly authored examples below select a mock branch. This is not a semantic classifier.
export function sendConversation(c:Conversation,text:string,course:StudentCourse) {
  const ref=c.messages.find(m=>m.id===c.referenceId);const activity=ref&&c.activities.find(a=>a.id===ref.activityId);
  if(ref){
    const r:ConversationRequest={kind:'答疑',title:'追问：'+(activity?.title||'历史交流'),chapters:activity?.chapters||[],text,reference:ref.id};
    if(text==='继续上次进度' && activity?.kind!=='检测' && activity?.status!=='已结束')Object.assign(r,{kind:activity?.kind||'答疑',title:activity?.title||r.title,resumeId:activity?.id});
    c.referenceId='';c.draft='';requestActivity(c,r);return;
  }
  const a=currentActivity(c);
  if(text==='今天先到这里'){append(c,'user',text,a?.id);finishActivity(c);c.draft='';return;}
  if(text==='请讲解这道题。'&&a?.kind==='检测'){helpDuringCheck(c);return;}
  if(text==='为什么增加四分之一还要加原量？'){
    requestActivity(c,{kind:'讲解',title:'增加量与总量',chapters:course.chapters.some(ch=>ch.id==='c4-3')?['c4-3']:[],text});c.draft='';return;
  }
  if(text==='先讲圆柱的表面积' && course.chapters.some(ch=>ch.id==='c3-2')){requestActivity(c,{kind:'讲解',title:'圆柱的表面积',chapters:['c3-2'],text});c.draft='';return;}
  if(text==='出一道题检测一下' && course.chapters.some(ch=>ch.id==='c4-3')){requestActivity(c,{kind:'检测',title:'增加量与总量检测',chapters:['c4-3'],text});c.draft='';return;}
  if(a?.kind==='检测'){submitCheck(c,text);return;}
  append(c,'user',text,a?.id);c.draft='';
  if(text==='换个例子' && a?.chapters.includes('c4-3'))append(c,'assistant','换成48米绳子：增加48 × 1/4 = 12米，总长是48 + 12 = 60米。12米是增加量，60米才是总量。',a.id);
  else if(text==='你好')append(c,'assistant','我在。想接着学，还是有新的问题？');
  else append(c,'assistant','这条输入已保留。当前使用预写内容演示交互，尚未接入自由问答判断；可用“试用示例”继续走查，也可以从右侧选择学习内容。',a?.id);
}

export function courseWithConversation(course:StudentCourse,c:Conversation):StudentCourse {
  const messageOrder=c.messages.map(m=>m.activityId);
  const activities:ActivityView[]=c.activities.filter(a=>a.kind!=='答疑').map(a=>({id:a.id,chapterId:a.chapters[0]||'',title:a.title,detail:a.detail,at:a.at,endedAt:a.endedAt,kind:a.kind as '讲解'|'检测',finished:a.status==='已结束',
    learningDates:[...new Set([...(course.activities.find(old=>old.id===a.id)?.learningDates||[]),...c.messages.filter(m=>m.activityId===a.id && m.role!=='event').map(m=>m.at.slice(0,10))])],partial:a.kind==='检测'&&a.status==='已结束'&&!a.submitted&&!course.activities.some(old=>old.id===a.id)})).sort((a,b)=>{
      return messageOrder.lastIndexOf(b.id)-messageOrder.lastIndexOf(a.id);
    });
  const questions:QuestionView[]=c.activities.filter(a=>a.kind==='检测'&&a.submitted).map(a=>({id:'CHECK-'+a.id,chapterId:a.chapters[0]||'',text:'图书角原有120本书，又增加了原有数量的四分之一。现在共有多少本？请写出答案和理由。',source:'检测',attempts:[{id:a.id,at:a.endedAt,answer:a.answer!,result:a.answer===sampleAnswer?'正确':'待判定',help:'帮助情况未确认',detail:'连续对话中上文可见，未核实独立条件；不自动更新能力判断。',activityId:a.id,ended:true}]}));
  return {...course,activities,questions:[...course.questions,...questions],asOf:now().slice(0,10)};
}
