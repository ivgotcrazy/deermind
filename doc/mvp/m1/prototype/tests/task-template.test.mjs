import assert from 'node:assert/strict';
import test from 'node:test';
import { mkdir } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { chromium, expect as baseExpect } from '@playwright/test';
import { createPreviewServer } from '../scripts/serve.mjs';

const expect=baseExpect.configure({timeout:8000});
test('task authoring distinguishes givens, inquiry and discussion; examples remain editable',async t=>{
  const server=createPreviewServer();await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const base='http://127.0.0.1:'+server.address().port;
  const browser=await chromium.launch({headless:true});
  t.after(async()=>{await browser.close();await new Promise(resolve=>server.close(resolve));});
  const page=await browser.newPage({viewport:{width:1440,height:1000},locale:'zh-CN'});page.setDefaultTimeout(8000);
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  const output=fileURLToPath(new URL('../test-results/task-template/',import.meta.url));await mkdir(output,{recursive:true});
  const btn=name=>page.getByRole('button',{name,exact:true});
  const label=name=>page.getByLabel(name,{exact:true});
  const state=()=>page.evaluate(()=>JSON.parse(localStorage.getItem('deermind-m1-domain-v1')));
  const open=async(domain,task,tab='definition')=>page.goto(base+'/admin/#/domain?'+new URLSearchParams({domain,kind:'task',id:task,tab}));
  const fixtures={};
  await t.test('three complete examples include two methods, KC, instance and separated roles',async()=>{
    for(const key of ['junior','senior','k8s']){
      await page.goto(base+'/admin/#/domain');await btn('载入示例领域').click();await btn('打开示例 '+key).click();
      const data=await state(),domain=data.domains.find(d=>d.exampleKey===key),task=data.tasks.find(x=>x.domainId===domain.id),q=data.instances.find(x=>x.taskId===task.id);
      fixtures[key]={domain,task,q};
      await btn(task.name).click();
      await expect(page.locator('.preparation')).toHaveCount(0);
      await expect(page.getByRole('table',{name:'完成要求',exact:true}).locator('tbody tr')).toHaveCount(3);
      await expect(page.getByRole('table',{name:'允许的变化',exact:true}).locator('tbody tr')).toHaveCount(2);
      await page.screenshot({path:output+key+'-requirements.png'});
      await page.getByRole('table',{name:'对象与变量',exact:true}).screenshot({path:output+key+'-variables.png'});
      assert.equal(task.methods.length,2);assert.equal(q.solutions.length,2);
      assert.deepEqual(Object.keys(q.bindings).sort(),task.parameters.filter(p=>p.role==='题目已给定').map(p=>p.symbol).sort());
      await page.getByRole('navigation',{name:'任务内容'}).getByRole('button',{name:'方法',exact:true}).click();
      await expect(page.locator('.data-table tbody tr')).toHaveCount(2);
      const method=data.methods.find(m=>m.id===task.methods[0]);await btn(method.name).click();
      await expect(page.getByRole('heading',{name:method.name,exact:true})).toBeInViewport();
      await expect(page.locator('.callout.amber')).toHaveCount(0);await btn(task.name+' →').click();
      await page.getByRole('navigation',{name:'任务内容'}).getByRole('button',{name:'知识',exact:true}).click();
      await expect(page.locator('.data-table tbody tr')).toHaveCount(key==='junior'?4:3);
      await page.getByRole('navigation',{name:'任务内容'}).getByRole('button',{name:'实例',exact:true}).click();
      await expect(page.locator('.data-table')).toContainText('可用（mock）');
      await btn('编辑题目 '+q.id).click();
      const unbound=task.parameters.filter(p=>p.role!=='题目已给定');
      for(const p of unbound)await expect(label('绑定参数 '+p.symbol)).toHaveCount(0);
      await expect(page.getByRole('table',{name:'待研究与待查信息'}).locator('tbody tr')).toHaveCount(unbound.length);
      await btn('预览学生题面').click();await expect(page.getByRole('dialog')).not.toContainText('参考答案');
      if(key==='k8s'){
        await expect(page.getByTestId('student-question')).not.toContainText('app=frontend');
        await expect(page.getByTestId('student-question')).not.toContainText('8000');
      }
      await page.screenshot({path:output+key+'-student-preview.png'});await btn('返回编辑').click();
      await btn('检查并保存为可用题').click();await expect(page.locator('.data-table')).toContainText('可用（mock）');
      await page.reload();await expect(page.locator('.data-table')).toContainText('可用（mock）');
    }
  });
  await t.test('list edits, cancel, incomplete requirement feedback and repeat loading preserve data',async()=>{
    const {domain,task,q}=fixtures.senior;
    await open(domain.id,task.id);await btn('编辑任务与完成要求').click();
    await btn('添加完成要求').click();await label('要求4交付内容').fill('临时检查项');await label('要求4完成条件').fill('暂存检查');await btn('移除要求 4').click();
    await label('要求3完成条件').fill('');await btn('保存修改').click();
    await page.locator('.preparation summary').click();await expect(page.locator('.preparation')).toContainText('完成条件需要补齐');
    await open(domain.id,task.id,'instances');await btn('编辑题目 '+q.id).click();await btn('检查并保存为可用题').click();
    await expect(page.getByRole('alert')).toContainText('完成条件需要补齐');await btn('关闭对话框').click();
    await open(domain.id,task.id);await btn('编辑任务与完成要求').click();await label('要求3完成条件').fill(task.requirements[2].criterion);await btn('保存修改').click();
    await btn('编辑对象与变量').click();await label('对象4用途').selectOption('题目已给定');await btn('取消').click();
    assert.equal((await state()).tasks.find(x=>x.id===task.id).parameters[3].role,'需要研究或求解');
    await btn('编辑允许的变化').click();await btn('添加变化').click();await label('变化3对象').fill('新增表示检查');await label('变化3范围').fill('等价符号');await label('变化3条件').fill('保持全参数讨论');await btn('保存修改').click();await page.reload();
    await expect(page.getByRole('table',{name:'允许的变化',exact:true}).locator('tbody tr')).toHaveCount(3);
    await btn('编辑允许的变化').click();await btn('移除变化 3').click();await btn('保存修改').click();
    await page.goto(base+'/admin/#/domain');await btn('载入示例领域').click();await btn('打开示例 senior').click();
    assert.equal((await state()).domains.filter(d=>d.exampleKey==='senior').length,1);
    assert.equal((await state()).tasks.find(x=>x.id===task.id).requirements[2].criterion,task.requirements[2].criterion);
  });
  await t.test('old mock drafts retain identity, text, bindings and associations without inventing criteria',async()=>{
    const legacy={domains:[{id:'DOM-OLD',name:'旧领域',scope:'旧范围',description:'',version:1}],tasks:[{id:'TT-OLD',domainId:'DOM-OLD',name:'原有任务',version:3,summary:'旧说明',goal:'旧目标',responsibility:'旧责任',output:'旧输出第一行\n旧输出第二行',parameters:[{symbol:'V',name:'原量',role:'已知量',condition:'正数'},{symbol:'W',name:'结果',role:'最终输出',condition:'正数'}],relations:'旧关系',variations:'旧变化全文\n不能丢失',exclusions:'旧边界',methods:['ST-OLD']}],methods:[],knowledge:[],instances:[{id:'TI-OLD',domainId:'DOM-OLD',taskId:'TT-OLD',version:2,question:'旧题目',bindings:{V:'40'},table:null,answer:'旧答案',solutions:[{methodId:'ST-OLD',working:'旧解答'}],source:'人工编写',sourceNote:'旧来源',checkedAt:'旧时间',checkedSignature:'old'}]};
    const isolated=await browser.newContext();const old=await isolated.newPage();
    await old.goto(base+'/admin/#/domain');await old.evaluate(value=>localStorage.setItem('deermind-m1-domain-v1',JSON.stringify(value)),legacy);await old.reload();
    await old.goto(base+'/admin/#/domain?domain=DOM-OLD&kind=task&id=TT-OLD');
    await expect(old.getByRole('table',{name:'完成要求',exact:true})).toContainText('旧输出第一行');
    await expect(old.getByRole('table',{name:'完成要求',exact:true})).toContainText('待补充完成条件');
    await expect(old.getByRole('table',{name:'对象与变量',exact:true})).toContainText('题目已给定');
    await expect(old.getByRole('table',{name:'允许的变化',exact:true})).toContainText('旧变化全文');
    await old.getByRole('button',{name:'编辑任务与完成要求',exact:true}).click();await old.getByRole('button',{name:'保存修改',exact:true}).click();await old.reload();
    const result=await old.evaluate(()=>JSON.parse(localStorage.getItem('deermind-m1-domain-v1')));
    assert.equal(result.tasks[0].requirements[0].deliverable,legacy.tasks[0].output);assert.equal(result.tasks[0].requirements[0].criterion,'');
    assert.equal(result.tasks[0].variations[0].range,legacy.tasks[0].variations);
    assert.deepEqual(result.tasks[0].methods,['ST-OLD']);assert.deepEqual(result.instances,legacy.instances);
    await isolated.close();
  });
  await page.setViewportSize({width:1280,height:900});await open(fixtures.k8s.domain.id,fixtures.k8s.task.id);
  assert.equal(await page.locator('.page-container').evaluate(el=>el.scrollWidth>el.clientWidth+1),false);
  assert.deepEqual(errors,[]);
});
