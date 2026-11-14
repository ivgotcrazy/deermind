import assert from 'node:assert/strict';
import test from 'node:test';
import { setup,expect } from './domain-test-support.mjs';
test('Task has semantic responsibility without mandatory parameters and method-specific prerequisites',async t=>{
 const {page,btn,state,open,dvt,errors}=await setup(t);const data=await dvt();
 const domain=data.domains.find(x=>x.exampleKey==='dvt-v1'),task=data.tasks.find(x=>x.domainId===domain.id&&x.name==='理解 d=v×t');
 assert.equal(task.parameters.length,0);assert.equal(task.methods.length,2);assert.equal(task.prerequisites.length,5);
 await open(domain.id,'task',task.id);await expect(page.locator('.preparation')).toHaveCount(0);await expect(page.getByRole('table',{name:'先导任务'})).toBeVisible();
 await btn('编辑先导任务').click();const modal=page.getByRole('dialog');await expect(modal).toBeVisible();await modal.getByLabel('先导理由',{exact:true}).first().fill('');await modal.getByRole('button',{name:'保存先导关系',exact:true}).click();await expect(modal.getByRole('alert')).toContainText('请说明先导理由');await modal.getByRole('button',{name:'取消',exact:true}).click();
 const part=task.prerequisites[0].taskId;await open(domain.id,'task',part);await btn('编辑先导任务').click();await page.getByLabel('选择任务',{exact:true}).selectOption(task.id);await btn('添加先导任务').click();await page.getByLabel('先导理由',{exact:true}).fill('制造环用于检验');await btn('保存先导关系').click();await expect(page.getByRole('alert')).toContainText('循环');await page.getByRole('dialog').getByRole('button',{name:'取消',exact:true}).click();
 assert.equal((await state()).tasks.find(x=>x.id===part).prerequisites.length,0);assert.deepEqual(errors,[]);
});
