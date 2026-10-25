import { reactive } from 'vue';
import { readFlow, subscribeFlow, applyCourse, type CourseSnapshot } from '../../../shared/learning-flow';
import { textbookMock } from './textbook-mock';
import { targetMock } from './target-mock';
import { domainMock } from './domain-mock';
import { evaluationMock } from './evaluation-mock';

export const flow=reactive(readFlow());
subscribeFlow(s=>Object.assign(flow,s));
// Only explicitly applied mock content survives a reload; unfinished catalog edits remain local.
for(const course of flow.courses){
  const b=course.snapshot;
  for(const [items,value] of [[textbookMock.books,b.book],[targetMock.targets,b.target]] as const){
    const list=items as {id:string}[],index=list.findIndex(x=>x.id===value.id);
    if(index<0)list.push(value);else list[index]=value;
  }
  for(const key of ['domains','tasks','methods','knowledge'] as const){
    const list=domainMock[key] as {id:string}[];for(const value of b.domain[key]){const index=list.findIndex(x=>x.id===value.id);if(index<0)list.push(value);else list[index]=value;}
  }
  for(const c of b.claims){const i=evaluationMock.claims.findIndex(x=>x.id===c.id);if(i<0)evaluationMock.claims.push(c);else evaluationMock.claims[i]=c;}
}
export function applyTargets(bookId:string,targetId?:string){
  const book=textbookMock.books.find(b=>b.id===bookId);if(!book)throw Error('教材不存在。');
  const targets=targetMock.targets.filter(t=>t.bookId===bookId&&(!targetId||t.id===targetId));
  if(!targets.length)throw Error('请先为教材建立学习目标。');
  for(const target of targets){
    const snapshot:CourseSnapshot={book,target,domain:domainMock,claims:evaluationMock.claims.filter(c=>target.claims.some(t=>t.claimId===c.id))};
    applyCourse(snapshot);
  }
  return targets.length;
}
