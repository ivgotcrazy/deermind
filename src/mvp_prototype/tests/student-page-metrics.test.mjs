import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import vm from 'node:vm';
const require=createRequire(import.meta.url);
const ts=require('../student/node_modules/typescript');
const source=readFileSync(new URL('../student/src/student-pages.ts',import.meta.url),'utf8');
const exports={};
vm.runInNewContext(ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText,{exports,require:()=>({textbookData:{units:[]}}),Date,Intl,Set});
const {demoCourse,activityStats,answerStats,inPeriod,wasWrong,counts}=exports;
test('calendar window includes today, excludes future and does not substitute upload date',()=>{
  assert.equal(inPeriod('2026-10-23 00:00',7,'2026-10-29'),true);
  assert.equal(inPeriod('2026-10-22 23:59',7,'2026-10-29'),false);
  assert.equal(inPeriod('2026-10-30',7,'2026-10-29'),false);
  assert.equal(inPeriod(undefined,7,'2026-10-29'),false);
  assert.equal(inPeriod(undefined,0,'2026-10-29'),true);
});
test('continuing across days increases learning dates without duplicating lecture count',()=>{
  const s=activityStats(demoCourse('math-6b','demo'),7);
  assert.equal(s.dates.length,6);assert.equal(s.lectures.length,3);assert.equal(s.tests.length,2);assert.equal(s.wrong.length,2);
});
test('answer denominator excludes help, unresolved judgment and unknown dates',()=>{
  const c=demoCourse('math-6b','demo'),s=answerStats(c,'c4-3',7);
  assert.equal(s.eligible.length,4);assert.equal(s.correct.length,3);assert.equal(s.excluded.length,1);
  assert.equal(answerStats(c,'c4-3',0).attempts.some(a=>a.id==='A7'),true);
  assert.equal(s.attempts.some(a=>a.id==='A7'),false);
});
test('a correction remains an error-history question; invalid evidence does not count',()=>{
  const q=structuredClone(demoCourse('math-6b','demo').questions[0]);
  assert.equal(wasWrong(q),true);assert.equal(q.attempts[1].result,'正确');
  q.attempts[0].invalid='题目缺陷';assert.equal(wasWrong(q),false);
  const c=structuredClone(demoCourse('math-6b','demo'));c.questions[1].attempts[0].invalid='已作废';
  assert.equal(answerStats(c,'c4-3',7).eligible.length,3);
});
test('requirement counts deduplicate identity and other spaces have no borrowed results',()=>{
  assert.equal(counts([{id:'shared',status:'待确认'},{id:'shared',status:'待确认'}])[2].count,1);
  assert.equal(demoCourse('english-6b','英语').questions.length,0);
  assert.equal(answerStats(demoCourse('english-6b','英语'),'',7).eligible.length,0);
});
