import { readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';
import { setup, expect } from '../tests/domain-test-support.mjs';

let cleanup;
const { page, btn, open, dvt }=await setup({after:fn=>{cleanup=fn;}});
try {
 const data=await dvt(),domain=data.domains.find(d=>d.exampleKey==='dvt-v1');
 const task=data.tasks.find(t=>t.domainId===domain.id&&t.name==='理解 d=v×t');
 const question=data.instances.find(q=>q.taskId===task.id);
 await open(domain.id,'task',task.id,'instances');
 await btn(question.question).click();
 await expect(page.getByRole('dialog')).toContainText('参考解法');
 await expect(page.getByRole('dialog')).not.toContainText('需重新检查');
 await page.evaluate(()=>document.fonts.ready);
 const assets=new URL('../../design/assets/domain-model-v0.1/',import.meta.url);
 const file='D04-question-references.png';
 await page.screenshot({path:fileURLToPath(new URL(file,assets)),fullPage:true,animations:'disabled'});
 const manifest=JSON.parse(await readFile(new URL('capture-manifest.json',assets),'utf8'));
 Object.assign(manifest.screens.find(s=>s.file===file),{route:new URL(page.url()).hash,source:'capture-domain-revision-question.mjs',capturedAt:new Date().toISOString(),sha256:createHash('sha256').update(await readFile(new URL(file,assets))).digest('hex')});
 await writeFile(new URL('capture-manifest.json',assets),JSON.stringify(manifest,null,2));
 console.log('Captured fresh question and two reference solutions');
} finally { await cleanup(); }
