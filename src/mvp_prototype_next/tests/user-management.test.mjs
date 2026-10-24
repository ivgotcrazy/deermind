import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdir} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {build} from '../admin/node_modules/esbuild/lib/main.js';
import {chromium} from '../../mvp_prototype/node_modules/playwright/index.mjs';
import {expect} from '../../mvp_prototype/node_modules/@playwright/test/index.mjs';
import {createPrototypeServer} from '../scripts/serve.mjs';
const output=fileURLToPath(new URL('../../../.tmp/mvp-prototype-next/user-management-review-20261024/',import.meta.url));
await mkdir(output,{recursive:true});

test('account validation and recovery preserve identity and isolate direct relations',async()=>{
  const bundle=await build({stdin:{contents:"export * from './user-management-mock'; export {learningSpaces} from './learning-space-mock';",resolveDir:fileURLToPath(new URL('../admin/src/workbench/',import.meta.url)),loader:'ts'},bundle:true,write:false,format:'esm',platform:'browser',define:{'process.env.NODE_ENV':'"production"'}});
  const m=await import('data:text/javascript;base64,'+Buffer.from(bundle.outputFiles[0].text).toString('base64'));
  const before=JSON.stringify(m.learningSpaces),beforeRecords=JSON.stringify(m.userMock.operations),count=m.userMock.accounts.length;
  assert.throws(()=>m.createAccount('student','同名学生','student.d',false,'已核实'),/系统外核实/);
  assert.throws(()=>m.createAccount('student','同名学生','student.d',true,''),/系统外核实/);
  assert.throws(()=>m.createAccount('student','同名学生','ＳＴＵＤＥＮＴ.a',true,'已核实'),/已存在/);
  assert.throws(()=>m.createAccount('admin','管理者','admin.2',true,'已核实'),/部署初始化/);
  assert.equal(m.userMock.accounts.length,count);assert.equal(JSON.stringify(m.userMock.operations),beforeRecords);
  const student=m.createAccount('student','学生 A','new.student',true,'系统外核实本人');
  assert.notEqual(student.learnerId,'LEARNER-A');assert.equal(m.accountSpaces(student).length,0);assert.equal(m.relationsFor(student.id).length,0);
  assert.throws(()=>m.linkAccounts('ACC-ADMIN',student.id,true,'已核实'),/必须选择/);
  assert.throws(()=>m.linkAccounts('ACC-PARENT-A','ACC-STUDENT-A',true,'已核实'),/已经有关联/);
  assert.throws(()=>m.unlinkAccounts('REL-AA',false,'已核实'),/系统外核实/);
  m.unlinkAccounts('REL-AA',true,'仅解除这一段关系');
  assert.deepEqual(m.visibleSpaces(m.findAccount('ACC-PARENT-A')).map(s=>s.id),['SPACE-003']);
  assert.deepEqual(m.visibleSpaces(m.findAccount('ACC-PARENT-B')).map(s=>s.id),['SPACE-001','SPACE-002']);
  assert.equal(JSON.stringify(m.learningSpaces),before);
  m.linkAccounts('ACC-PARENT-A','ACC-STUDENT-A',true,'重新核实');assert.equal(m.relationsFor('ACC-STUDENT-A').length,2);
  const relations=JSON.stringify(m.userMock.relations),confirmations=JSON.stringify(m.userMock.confirmations),learner=m.findAccount('ACC-STUDENT-A').learnerId;
  assert.throws(()=>m.recoverAccount('ACC-STUDENT-A',true,''),/系统外核实/);
  m.recoverAccount('ACC-STUDENT-A',true,'已核实原账号本人');m.recoverAccount('ACC-ADMIN',true,'已系统外核实管理身份');
  assert.equal(m.findAccount('ACC-STUDENT-A').learnerId,learner);assert.equal(m.findAccount('ACC-STUDENT-A').credentialVersion,2);
  assert.equal(JSON.stringify(m.learningSpaces),before);assert.equal(JSON.stringify(m.userMock.relations),relations);assert.equal(JSON.stringify(m.userMock.confirmations),confirmations);
  m.renameAccount('ACC-STUDENT-A','学生 A 新名称','修正显示名称');assert.equal(m.learningSpaces[0].studentName,'学生 A 新名称');assert.equal(m.learningSpaces[0].studentId,'LEARNER-A');
});

test('user management supports independent accounts relations and recovery in mock UI',async t=>{
  const server=createPrototypeServer({directory:output,config:{key:'test',model:'fixture'},provider:async()=>{throw Error('No model calls expected');}});
  await new Promise(r=>server.listen(0,'127.0.0.1',r));
  const base=`http://127.0.0.1:${server.address().port}/admin/`,browser=await chromium.launch({headless:true,channel:'msedge'});
  t.after(async()=>{await browser.close();await new Promise(r=>server.close(r));});
  const btn=(p,name)=>p.getByRole('button',{name,exact:true}),tab=(p,name)=>p.getByRole('tab',{name,exact:true}),dialog=p=>p.getByRole('dialog');
  async function verify(p,reason='已在系统外核实本人及本次操作所需关系（示例）。'){await dialog(p).getByRole('checkbox',{name:'已完成本次操作所需的系统外核实'}).check();await dialog(p).getByLabel('核实依据',{exact:true}).fill(reason);}
  async function grant(p){if(await btn(p,'记录用途并查看').count()){await p.getByLabel('用途',{exact:true}).fill('核对账号关联的学习档案示例');await btn(p,'记录用途并查看').click();}}
  async function journey(name,run,hash='users'){
    await t.test(name,async()=>{
      const ctx=await browser.newContext({viewport:{width:1440,height:1000},locale:'zh-CN',timezoneId:'Asia/Shanghai'}),p=await ctx.newPage(),errors=[],calls=[];
      p.setDefaultTimeout(7000);p.on('pageerror',e=>errors.push(e.message));p.on('request',r=>{if(r.url().includes('/api/'))calls.push(r.url());});
      try{await p.goto(base+'#/'+hash);await run(p);assert.deepEqual(errors,[]);assert.deepEqual(calls,[]);}
      catch(e){await p.screenshot({path:output+'/failure-'+name.slice(0,28).replace(/\W/g,'-')+'.png',fullPage:true});throw e;}
      finally{await ctx.close();}
    });
  }
  await journey('list roles independent roster and preserved filters',async p=>{
    await expect(p.locator('.user-table tbody tr')).toHaveCount(6);await expect(p.locator('.user-table')).not.toContainText('教师');await expect(p.locator('.user-table')).not.toContainText('掌握度');
    await expect(p.locator('.workbench-context')).toContainText('刷新后恢复初始内容');await p.getByLabel('角色筛选').selectOption('student');await expect(p.locator('.user-table tbody tr')).toHaveCount(3);
    await p.getByLabel('关联筛选').selectOption('unlinked');await expect(p.locator('.user-table tbody tr')).toHaveCount(1);await btn(p,'查看账号 ACC-STUDENT-C').click();await tab(p,'学习关联').click();await expect(p.locator('.account-learning')).toContainText('尚未创建学习空间');
    await btn(p,'← 返回账号列表').click();await expect(p.getByLabel('角色筛选')).toHaveValue('student');await expect(p.getByLabel('关联筛选')).toHaveValue('unlinked');
    await btn(p,'重置筛选').click();await p.getByLabel('查找账号',{exact:true}).fill('parent.b');await expect(p.locator('.user-table tbody tr')).toHaveCount(1);await btn(p,'重置筛选').click();await p.screenshot({path:output+'/users-desktop.png',fullPage:true});
  });
  await journey('creation validates and does not invent learning state',async p=>{
    await btn(p,'新增账号').click();await dialog(p).getByLabel('姓名或显示名称').fill('新学生');await dialog(p).getByLabel('账号名',{exact:true}).fill('new.learner');await btn(dialog(p),'确认开户').click();await expect(dialog(p).getByRole('alert')).toContainText('系统外核实');
    await verify(p);await dialog(p).getByLabel('账号名',{exact:true}).fill('STUDENT.A');await btn(dialog(p),'确认开户').click();await expect(dialog(p).getByRole('alert')).toContainText('已存在');
    await dialog(p).getByLabel('账号名',{exact:true}).fill('new.learner');await btn(dialog(p),'确认开户').click();await expect(p.locator('.account-profile')).toContainText('new.learner');await expect(p.locator('.account-summary')).toContainText('0 名有效关联家长');
    await tab(p,'学习关联').click();await expect(p.locator('.account-learning tbody tr')).toHaveCount(0);await tab(p,'首次确认').click();await expect(p.locator('.account-confirmations')).toContainText('尚未记录');await tab(p,'操作记录').click();await expect(p.locator('.account-history')).toContainText('开户');
    await btn(p,'← 返回账号列表').click();await expect(p.locator('.user-table tbody tr')).toHaveCount(7);await btn(p,'新增账号').click();await dialog(p).getByLabel('姓名或显示名称').fill('取消的账号');await btn(dialog(p),'取消').click();await expect(p.locator('.user-table tbody tr')).toHaveCount(7);
  });
  await journey('new parent relation uses explicit selection and duplicate checks',async p=>{
    await btn(p,'新增账号').click();await dialog(p).getByLabel('账号角色').selectOption('parent');await dialog(p).getByLabel('姓名或显示名称').fill('新家长');await dialog(p).getByLabel('账号名',{exact:true}).fill('new.parent');await verify(p);await btn(dialog(p),'确认开户').click();
    await btn(p,'关联孩子').click();await expect(dialog(p).locator('.candidate-row')).toHaveCount(0);await dialog(p).getByLabel('查找关联账号').fill('student.a');await dialog(p).getByRole('radio',{name:'选择账号 ACC-STUDENT-A'}).check();await btn(dialog(p),'保存关联').click();await expect(dialog(p).getByRole('alert')).toContainText('系统外核实');await verify(p);await btn(dialog(p),'保存关联').click();
    await tab(p,'亲子关系').click();await expect(p.locator('.account-relations tbody tr')).toHaveCount(1);await expect(p.locator('.account-relations')).toContainText('学生 A');
    await btn(p,'关联孩子').click();await dialog(p).getByLabel('查找关联账号').fill('student.a');await expect(dialog(p).getByRole('radio',{name:'选择账号 ACC-STUDENT-A'})).toBeDisabled();await btn(dialog(p),'取消').click();
    await tab(p,'学习关联').click();await expect(p.locator('.account-learning tbody tr')).toHaveCount(2);await tab(p,'首次确认').click();await expect(p.locator('.account-confirmations')).toContainText('尚未记录');await expect(p.locator('.account-confirmations')).toContainText('孩子参与确认');
  });
  await journey('unlink affects only one edge and restoration keeps history',async p=>{
    await tab(p,'学习关联').click();await expect(p.locator('.account-learning tbody tr')).toHaveCount(3);await tab(p,'亲子关系').click();await btn(p,'解除关联 REL-AA').click();await expect(dialog(p)).toContainText('其他家长');await verify(p,'只解除家长 A 与学生 A 的关系');await btn(dialog(p),'确认解除').click();
    await expect(p.locator('.account-relations tbody tr')).toHaveCount(1);await p.getByRole('checkbox',{name:'包含已解除关系'}).check();await expect(p.locator('.account-relations tbody tr')).toHaveCount(2);await expect(p.locator('.account-relations')).toContainText('已解除');
    await tab(p,'学习关联').click();await expect(p.locator('.account-learning tbody tr')).toHaveCount(1);await expect(p.locator('.account-learning')).toContainText('SPACE-003');
    await p.goto(base+'#/users?id=ACC-PARENT-B&tab=learning');await expect(p.locator('.account-learning tbody tr')).toHaveCount(2);
    await p.goto(base+'#/users?id=ACC-PARENT-A&tab=relations');await btn(p,'关联孩子').click();await dialog(p).getByLabel('查找关联账号').fill('student.a');await expect(dialog(p)).toContainText('已解除，可重新核实后关联');await dialog(p).getByRole('radio',{name:'选择账号 ACC-STUDENT-A'}).check();await verify(p,'重新核实本人与亲子关系');await btn(dialog(p),'保存关联').click();await expect(p.locator('.account-relations tbody tr')).toHaveCount(2);
    await tab(p,'操作记录').click();await expect(p.locator('.account-history')).toContainText('解除亲子关联');await expect(p.locator('.account-history')).toContainText('恢复亲子关联');
  },'users?id=ACC-PARENT-A');
  await journey('recovery retains identity spaces and existing confirmation',async p=>{
    await tab(p,'学习关联').click();const original=await p.locator('.account-learning').innerText();await btn(p,'找回原账号').click();await expect(dialog(p)).toContainText('LEARNER-A');await btn(dialog(p),'记录找回').click();await expect(dialog(p).getByRole('alert')).toContainText('系统外核实');await verify(p);await btn(dialog(p),'记录找回').click();assert.equal(await p.locator('.account-learning').innerText(),original);
    await tab(p,'基本信息').click();await expect(p.locator('.account-profile')).toContainText('v2');await expect(p.locator('.account-profile')).toContainText('ACC-STUDENT-A');await tab(p,'首次确认').click();await expect(p.locator('.account-confirmations')).toContainText('MOCK-NOTICE-1');await tab(p,'操作记录').click();await expect(p.locator('.account-history')).toContainText('凭据记录 v1 → v2');
    await p.goto(base+'#/users?id=ACC-ADMIN');await expect(tab(p,'亲子关系')).toHaveCount(0);await expect(btn(p,'关联孩子')).toHaveCount(0);await btn(p,'找回原账号').click();await expect(dialog(p)).toContainText('不要求另一位管理员');await verify(p,'在系统外核实本人及管理身份');await btn(dialog(p),'记录找回').click();await expect(p.locator('.account-profile')).toContainText('v2');
  },'users?id=ACC-STUDENT-A');
  await journey('current learning and student pages return to exact account context',async p=>{
    await tab(p,'学习关联').click();await btn(p,'查看空间 SPACE-001').click();await expect(p.locator('.space-header')).toContainText('SPACE-001');await btn(p,'← 返回用户管理').click();await expect(tab(p,'学习关联')).toHaveAttribute('aria-selected','true');
    await btn(p,'查看学生状态 SPACE-002').click();await grant(p);await expect(p.locator('.student-state-header')).toContainText('SPACE-002');await expect(p.locator('.student-beliefs')).not.toContainText('对明确给定底高的计算有支持');await btn(p,'← 返回用户管理').click();
    await tab(p,'基本信息').click();await btn(p,'编辑显示名称').click();await dialog(p).getByLabel('姓名或显示名称').fill('学生 A 更正姓名');await dialog(p).getByLabel('修改原因').fill('更正展示姓名，身份不变');await btn(dialog(p),'保存').click();await tab(p,'学习关联').click();await expect(p.locator('.account-learning')).toContainText('学生 A 更正姓名');await btn(p,'查看学生状态 SPACE-001').click();await expect(p.locator('.student-state-header')).toContainText('学生 A 更正姓名');await btn(p,'← 返回用户管理').click();
  },'users?id=ACC-STUDENT-A');
  await journey('first confirmations remain read only and attributable',async p=>{
    await expect(p.locator('.account-confirmations tbody tr')).toHaveCount(3);await expect(p.locator('.account-confirmations')).toContainText('家长 B');await expect(p.locator('.account-confirmations')).toContainText('尚未记录');await expect(p.locator('.account-confirmations button')).toHaveCount(0);
    await p.goto(base+'#/users?id=ACC-PARENT-A&tab=confirmations');await expect(p.locator('.account-confirmations tbody tr')).toHaveCount(4);await expect(p.locator('.account-confirmations')).not.toContainText('家长 B');await expect(p.locator('.account-confirmations')).toContainText('学生 B');
    await p.screenshot({path:output+'/confirmations-desktop.png',fullPage:true});
  },'users?id=ACC-STUDENT-A&tab=confirmations');
  await journey('layout invalid ids and mock real separation',async p=>{
    await p.setViewportSize({width:1024,height:900});assert.equal(await p.locator('.page-container').evaluate(el=>el.scrollWidth<=el.clientWidth+1),true);await p.screenshot({path:output+'/users-1024.png',fullPage:true});
    await btn(p,'查看账号 ACC-STUDENT-A').click();await tab(p,'亲子关系').click();await btn(p,'关联家长').click();await dialog(p).getByLabel('查找关联账号').fill('parent');await p.screenshot({path:output+'/link-1024.png',fullPage:true});await btn(dialog(p),'取消').click();
    await p.goto(base+'#/users?id=ST-001');await expect(p.getByRole('alert')).toContainText('不按名称自动合并');await expect(p.locator('.account-summary')).toHaveCount(0);
    await p.getByLabel('数据来源',{exact:true}).selectOption('real');await expect(p.getByRole('heading',{name:'尚未接入真实模型数据',exact:true})).toBeVisible();await expect(p.locator('.user-table')).toHaveCount(0);
  });
  await journey('pagination preserves query and new records reset on refresh',async p=>{
    for(let i=0;i<5;i++){await btn(p,'新增账号').click();await dialog(p).getByLabel('姓名或显示名称').fill('分页家长 '+i);await dialog(p).getByLabel('账号角色').selectOption('parent');await dialog(p).getByLabel('账号名',{exact:true}).fill('page.parent.'+i);await verify(p);await btn(dialog(p),'确认开户').click();await btn(p,'← 返回账号列表').click();}
    await expect(p.locator('.user-table tbody tr')).toHaveCount(10);await btn(p,'下一页').click();await expect(p.locator('.user-table tbody tr')).toHaveCount(1);await p.locator('.user-table tbody tr .text-link').first().click();await btn(p,'← 返回账号列表').click();await expect(p.locator('.pagination')).toContainText('第 2 / 2 页');
    await p.reload();await expect(p.locator('.user-table tbody tr')).toHaveCount(6);await expect(p.locator('.pagination')).toHaveCount(0);
  });
});
