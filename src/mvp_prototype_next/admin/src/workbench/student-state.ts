import { learningSpaces,spaceRequirements,assessmentFor,spaceClaims,type MockLearningSpace } from './learning-space-mock';
import { auditActivities } from './activity-review-mock';

// Read-only projections of the existing shared examples; no scoring or inference.
export const studentRoster=()=>[...new Map(learningSpaces.map(s=>[s.studentId,{id:s.studentId,name:s.studentName}])).values()];
export const learnerSpaces=(id:string)=>learningSpaces.filter(s=>s.studentId===id);
export const learnerActivities=(id:string)=>auditActivities().filter(r=>r.space.studentId===id).sort((a,b)=>b.activity.at.localeCompare(a.activity.at));
export const latestLearning=(id:string)=>learnerActivities(id)[0]?.activity.at||'';
export const manualQuestions=(id:string)=>learnerActivities(id).filter(r=>r.audit?.review==='question');
export function targetCounts(s:MockLearningSpace,claimId='',chapterId=''){
  return spaceRequirements(s).filter(r=>(!claimId||r.selection.claimId===claimId)&&(!chapterId||r.requirement.chapterIds.includes(chapterId))).reduce((out,r)=>{out[assessmentFor(s,r.requirement.id).status]++;return out;},{已达标:0,需加强:0,待确认:0});
}
export function beliefUpdates(s:MockLearningSpace){
  return auditActivities().filter(row=>row.space.id===s.id).flatMap(({activity,audit})=>audit?.rounds.filter(r=>r.changes.length).map(round=>({id:activity.id+':'+round.id,activity,audit,round,claim:audit.snapshot.claims.find(c=>c.id===audit.claimId)}))||[]).sort((a,b)=>b.activity.at.localeCompare(a.activity.at));
}
export function aspectChangedAt(s:MockLearningSpace,claimId:string,aspectId:string){
  const claim=spaceClaims(s).find(c=>c.id===claimId);
  return beliefUpdates(s).find(r=>r.claim?.id===claimId&&r.claim.version===claim?.version&&r.round.changes.some(c=>c.aspect===aspectId&&c.before!==c.after))?.activity.at||'';
}
export const currentJudgment=(s:MockLearningSpace,claimId:string,aspectId:string)=>s.judgments.find(j=>j.claimId===claimId&&j.aspectId===aspectId);
export function aspectText(s:MockLearningSpace,claimId:string,aspectId:string){
  const a=spaceClaims(s).find(c=>c.id===claimId)?.aspects.find(a=>a.id===aspectId);
  return !a?'未定义':!a.applicable?'不适用':currentJudgment(s,claimId,aspectId)?.judgment||'尚未形成判断';
}
