import assert from 'node:assert/strict';
import test from 'node:test';
import { mkdir, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { chromium, expect as baseExpect } from '@playwright/test';
import { createPreviewServer } from '../scripts/serve.mjs';

const expect=baseExpect.configure({timeout:8000});
test('solution authoring expresses decomposition, all cases, conditional checks and endings',async t=>{
  const server=createPreviewServer();await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const base='http://127.0.0.1:'+server.address().port;
  const browser=await chromium.launch({headless:true});
  const context=await browser.newContext({viewport:{width:1440,height:1000},locale:'zh-CN'});
  const page=await context.newPage();page.setDefaultTimeout(8000);
  t.after(async()=>{await browser.close();await new Promise(resolve=>server.close(resolve));});
  const errors=[],api=[],screens=[];
  page.on('pageerror',e=>errors.push(e.message));await context.route('**/api/**',r=>{api.push(r.request().url());return r.abort();});
  const output=fileURLToPath(new URL('../test-results/solution-template/',import.meta.url));await mkdir(output,{recursive:true});
  const btn=name=>page.getByRole('button',{name,exact:true}),label=name=>page.getByLabel(name,{exact:true});
  const state=()=>page.evaluate(()=>JSON.parse(localStorage.getItem('deermind-m1-domain-v1')));
  const open=async(d,id)=>page.goto(base+'/admin/#/domain?'+new URLSearchParams({domain:d,kind:'solution',id}));
  const shot=async(name,locator)=>{await page.evaluate(()=>document.fonts.ready);await (locator||page).screenshot({path:output+name+'.png',animations:'disabled'});screens.push(name);};
  const samples={};
  await t.test('all example methods and recursively linked children have complete authoring fields',async()=>{
    for(const key of ['junior','senior','k8s']){
      await page.goto(base+'/admin/#/domain');await btn('载入示例领域').click();await btn('打开示例 '+key).click();
      const data=await state(),domain=data.domains.find(d=>d.exampleKey===key),task=data.tasks.find(t=>t.domainId===domain.id);
      samples[key]={domain,task,method:data.methods.find(m=>m.id===task.methods[0])};
      for(const m of data.methods.filter(m=>m.domainId===domain.id)){
        await open(domain.id,m.id);await expect(page.getByRole('heading',{name:m.name,exact:true})).toBeVisible();
        await expect(page.locator('.callout.amber')).toHaveCount(0);
        assert.ok(m.ending.success&&m.ending.stop);assert.ok(m.steps.every(s=>s.inputs&&s.output&&s.key));
      }
    }
  });
  await t.test('junior method opens two levels of subtasks and returns; KC are derived without duplicates',async()=>{
    const {domain,method}=samples.junior;await open(domain.id,method.id);
    const data=await state(),alternative=data.methods.find(m=>m.id===samples.junior.task.methods[1]);
    assert.equal(method.steps[1].taskId,alternative.steps[1].taskId);
    assert.notEqual(method.steps[1].solutionId,alternative.steps[1].solutionId);
    assert.equal(data.tasks.find(t=>t.id===method.steps[1].taskId).methods.length,2);
    await expect(label('步骤1详情')).toContainText('供步骤2和步骤3共同使用');
    await shot('junior-parent');
    await btn('面积加减后调用最值方法').click();await expect(page.getByRole('heading',{name:'面积加减后调用最值方法',exact:true})).toBeVisible();
    await expect(label('步骤2详情')).toContainText('将 S(t) 传为子方法的 S');
    await btn('配方并核对顶点位置').click();await expect(page.getByRole('heading',{name:'配方并核对顶点位置',exact:true})).toBeVisible();
    await expect(page.getByRole('table',{name:'步骤2分支'})).toContainText('u<t₀<v');
    await shot('junior-nested',label('步骤2详情'));
    await btn('面积加减后调用最值方法 →').click();await btn(method.name+' →').click();
    await expect(page.getByRole('heading',{name:method.name,exact:true})).toBeVisible();
    const table=page.getByRole('heading',{name:'知识依据',exact:true}).locator('..').locator('table');
    await expect(table.locator('tbody tr')).toHaveCount(4);await expect(table).toContainText('配方并核对顶点位置');
    await btn('结束条件').click();await expect(page.locator('#method-ending')).toBeInViewport();
  });
  await t.test('senior exposes all parameter cases and retains boundaries after edit, cancel and reload',async()=>{
    const {domain,method}=samples.senior;await open(domain.id,method.id);
    const table=page.getByRole('table',{name:'步骤2分支'});await expect(table.locator('tbody tr')).toHaveCount(3);
    for(const value of ['a<α','a=α','a>α','2 个不同实根'])await expect(table).toContainText(value);
    await expect(table).not.toContainText('之后去哪');await expect(label('步骤2详情')).toContainText('全部情况都要处理');
    await shot('senior-all-cases',label('步骤2详情'));
    await btn('编辑方法').click();await label('步骤2分支2条件').fill('不应保存');await btn('取消').click();
    assert.equal((await state()).methods.find(m=>m.id===method.id).steps[1].routes[1].condition,'a=α');
    await btn('编辑方法').click();await expect(label('步骤2分支1去向')).toHaveCount(0);
    await label('步骤2分支说明').fill('α>0；三类完整覆盖 R，临界值单列，汇总后进入位置研究。');
    await btn('步骤2添加分支').click();await label('步骤2分支4条件').fill('临时');await btn('移除步骤2分支4').click();
    await btn('保存方法').click();await page.reload();await expect(label('步骤2详情')).toContainText('临界值单列');
  });
  await t.test('K8s rechecks original path, explicitly returns on new evidence and stops unresolved otherwise',async()=>{
    const {domain,method}=samples.k8s;await open(domain.id,method.id);
    const review=page.getByRole('table',{name:'步骤6分支'});await expect(review.locator('tbody tr')).toHaveCount(4);
    await expect(review).toContainText('步骤 2 · 判断后端选择关系');await expect(review).toContainText('步骤 4 · 判断转发端口');
    await expect(review).toContainText('未解决，停止当前方法');await shot('k8s-recheck',label('步骤6详情'));
    await review.getByRole('button',{name:'步骤 4 · 判断转发端口 →',exact:true}).click();await expect(label('步骤4详情').getByRole('heading')).toBeInViewport();
    await page.locator('summary').filter({hasText:'展开实例走查'}).click();
    await expect(page.getByRole('heading',{name:'具体实例',exact:true}).locator('..')).toContainText('修正 selector 后出现三个后端，但原地址仍失败');
    await btn('结束条件').click();await shot('k8s-ending');
  });
  await t.test('references survive reordering; deleting a destination and incomplete branches are reported',async()=>{
    const {domain,method}=samples.k8s;await open(domain.id,method.id);await btn('编辑方法').click();
    await btn('上移步骤5').click();await btn('保存方法').click();
    let saved=(await state()).methods.find(m=>m.id===method.id);
    assert.equal(saved.steps.find(s=>s.key==='verify').routes[2].next,'port');
    await expect(page.getByRole('table',{name:'步骤6分支'})).toContainText('步骤 5 · 判断转发端口');
    await btn('编辑方法').click();await btn('上移步骤5').click();await btn('保存方法').click();
    await btn('编辑方法').click();await btn('移除步骤 5').click();await btn('保存方法').click();
    await expect(page.getByRole('status').filter({hasText:'方法尚未完整'})).toContainText('分支去向已不存在');
    await btn('编辑方法').click();await label('步骤4分支1去向').selectOption('$stop');
    await label('步骤4分支1条件').fill('');await btn('保存方法').click();
    await expect(page.getByRole('status').filter({hasText:'方法尚未完整'})).toContainText('条件、处理和结果需要补齐');
    await shot('missing-branch-feedback');
    // Restore this isolated test browser's fixture for further review.
    await page.evaluate(m=>{const s=JSON.parse(localStorage.getItem('deermind-m1-domain-v1'));s.methods[s.methods.findIndex(x=>x.id===m.id)]=m;localStorage.setItem('deermind-m1-domain-v1',JSON.stringify(s));},method);await page.reload();
    await expect(page.locator('.callout.amber')).toHaveCount(0);
  });
  await t.test('old definitions remain untouched and newest examples are loaded separately',async()=>{
    const isolated=await browser.newContext();const old=await isolated.newPage();
    await old.goto(base+'/admin/#/domain');
    const legacy={domains:[{id:'OLD-D',name:'我改过的旧示例',scope:'旧范围',description:'',version:1,exampleKey:'junior'}],tasks:[],knowledge:[],instances:[],methods:[{id:'OLD-M',domainId:'OLD-D',name:'旧方法',version:3,description:'不能覆盖的思路',conditions:'旧条件',inputs:'原输入',output:'原输出',kc:[],steps:[{title:'原步骤',detail:'原处理内容',divided:false,taskId:'',solutionId:''}]}]};
    await old.evaluate(s=>localStorage.setItem('deermind-m1-domain-v1',JSON.stringify(s)),legacy);await old.reload();
    await old.goto(base+'/admin/#/domain?domain=OLD-D&kind=solution&id=OLD-M');
    await expect(old.getByText('原处理内容',{exact:true})).toBeVisible();await expect(old.locator('#method-ending')).toContainText('尚未补充');
    assert.deepEqual(await old.evaluate(()=>JSON.parse(localStorage.getItem('deermind-m1-domain-v1'))),legacy);
    await old.goto(base+'/admin/#/domain');await old.getByRole('button',{name:'载入示例领域',exact:true}).click();await old.getByRole('button',{name:'新版方法示例 junior',exact:true}).click();
    const saved=await old.evaluate(()=>JSON.parse(localStorage.getItem('deermind-m1-domain-v1')));
    assert.equal(saved.domains.length,2);assert.deepEqual(saved.methods.find(m=>m.id==='OLD-M'),legacy.methods[0]);
    await old.goto(base+'/admin/#/domain');await old.getByRole('button',{name:'载入示例领域',exact:true}).click();await old.getByRole('button',{name:'新版方法示例 junior',exact:true}).click();
    assert.equal(await old.evaluate(()=>JSON.parse(localStorage.getItem('deermind-m1-domain-v1')).domains.length),2);
    await isolated.close();
  });
  await t.test('method editing stays usable at laptop width without external model calls',async()=>{
    const {domain,method}=samples.k8s;await page.setViewportSize({width:1280,height:900});await open(domain.id,method.id);
    assert.equal(await page.locator('.page-container').evaluate(e=>e.scrollWidth>e.clientWidth+1),false);
    await btn('编辑方法').click();await label('步骤6类型').scrollIntoViewIfNeeded();await shot('k8s-edit');
    assert.equal(await page.locator('.page-container').evaluate(e=>e.scrollWidth>e.clientWidth+1),false);
    await btn('取消').click();assert.deepEqual(errors,[]);assert.deepEqual(api,[]);
  });
  await writeFile(output+'review.json',JSON.stringify({screens,errors,api,scope:'Authoring UI and mock examples only; no execution or formal documentation changes'},null,2));
});
