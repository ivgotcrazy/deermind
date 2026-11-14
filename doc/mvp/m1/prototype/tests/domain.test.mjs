import assert from 'node:assert/strict';
import test from 'node:test';
import { setup,expect } from './domain-test-support.mjs';
test('domain CRUD preserves records and separates Task, Solution and KC',async t=>{
 const {page,base,btn,state,open,dvt,errors}=await setup(t);
 await page.goto(base+'/admin/#/domain');await btn('新建领域').click();await page.getByLabel('领域名称',{exact:true}).fill('保留的自建领域');await btn('创建并进入').click();
 const legacyId=(await state()).domains[0].id;
 await btn('新建任务').click();await page.getByLabel('任务名称',{exact:true}).fill('我的原有任务');await btn('创建任务').click();
 const before=await state();const data=await dvt();assert.ok(data.domains.some(x=>x.id===legacyId));assert.deepEqual(data.tasks.find(x=>x.id===before.tasks[0].id),before.tasks[0]);
 const domain=data.domains.find(x=>x.exampleKey==='dvt-v1'),task=data.tasks.find(x=>x.domainId===domain.id&&x.name==='理解 d=v×t');
 await open(domain.id,'task',task.id,'knowledge');await expect(page.getByRole('table')).toBeVisible();assert.equal(await page.locator('tbody tr').count(),6);
 await page.reload();assert.equal((await state()).domains.length,2);
 await dvt();assert.equal((await state()).domains.length,2);
 await open(domain.id,'kc',data.knowledge.find(x=>x.domainId===domain.id).id);await btn('编辑知识').click();await expect(btn('添加先修知识')).toHaveCount(0);
 assert.deepEqual(errors,[]);
});
