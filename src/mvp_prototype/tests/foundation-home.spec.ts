import { test, expect, type Page } from '@playwright/test';
async function create(page:Page,name='同名课程'){
 await page.getByRole('button',{name:'教材与检测',exact:true}).click();
 if(await page.getByRole('button',{name:'创建另一个空间'}).count())await page.getByRole('button',{name:'创建另一个空间'}).click();
 await page.getByLabel('空间名称',{exact:true}).fill(name);await page.getByRole('button',{name:'创建演示空间',exact:true}).click();
 await page.getByRole('button',{name:'学习',exact:true}).click();
 return await page.getByLabel('当前学习空间',{exact:true}).inputValue();
}
test('进入首页不提前展示教学，发送不展开历史，继续恢复段落',async({page})=>{
 await page.goto('/phase4.html');await expect(page.getByRole('heading',{name:'今天，想学什么？'})).toBeVisible();
 expect(await page.evaluate(()=>JSON.parse(localStorage.getItem('deermind-phase4-lesson-v1')||'{"shown":[]}').shown)).toEqual([]);
 await page.getByLabel(/随时说说你的想法/).fill('帮我弄清三角形');await page.getByRole('button',{name:'发送',exact:true}).click();
 await expect(page.getByLabel('首页对话历史',{exact:true})).toHaveCount(0);
 await expect(page.getByRole('status')).toContainText('尚未理解或执行');
 await page.getByRole('button',{name:'开始章节讲解',exact:true}).click();await page.getByRole('button',{name:'继续下一段'}).click();
 await page.getByLabel('向 DeerMind 提问',{exact:true}).fill('第二段草稿');await page.getByRole('button',{name:'返回学习',exact:false}).click();await page.reload();
 await page.getByRole('button',{name:'继续本次讲解',exact:true}).click();await expect(page.getByLabel('向 DeerMind 提问',{exact:true})).toHaveValue('第二段草稿');
 await expect(page.getByRole('heading',{name:'底和高，要配成一对'})).toBeVisible();
});
test('同名空间的求助、草稿和记录按标识隔离，空空间不借用判断',async({page})=>{
 await page.goto('/phase4.html');const first=await create(page);
 await page.getByLabel(/随时说说你的想法/).fill('第一空间草稿');await page.getByRole('button',{name:'问题求助',exact:true}).click();
 await page.getByLabel('求助题目',{exact:true}).fill('第一空间的问题');await page.getByRole('button',{name:'提交求助',exact:true}).click();
 await page.getByRole('button',{name:'另提一个问题',exact:false}).click();await page.getByLabel('求助题目',{exact:true}).fill('第一空间求助草稿');
 const second=await create(page);expect(second).not.toEqual(first);
 await expect(page.getByLabel(/随时说说你的想法/)).toHaveValue('');await page.getByRole('button',{name:'问题求助',exact:true}).click();
 await expect(page.getByLabel('求助题目',{exact:true})).toHaveValue('');await expect(page.locator('.f-record-link')).toHaveCount(0);
 await page.getByRole('button',{name:'题目记录',exact:true}).click();await expect(page.locator('.f-record-link')).toHaveCount(0);
 await page.getByRole('button',{name:'学习情况',exact:true}).click();await expect(page.getByRole('heading',{name:'当前空间还没有正式评价'})).toBeVisible();await expect(page.getByLabel('当前学习要求项数')).toHaveCount(0);
 await page.getByRole('button',{name:'学习',exact:true}).click();await page.getByLabel('当前学习空间',{exact:true}).selectOption(first);await page.reload();
 await expect(page.getByLabel(/随时说说你的想法/)).toHaveValue('第一空间草稿');await page.getByRole('button',{name:'问题求助',exact:true}).click();await expect(page.getByLabel('求助题目',{exact:true})).toHaveValue('第一空间求助草稿');await expect(page.locator('.f-record-link')).toHaveCount(1);
 await page.getByRole('button',{name:'题目记录',exact:true}).click();await expect(page.locator('.f-record-link')).toHaveCount(1);await page.getByLabel('记录所属空间',{exact:true}).selectOption(second);await expect(page.locator('.f-record-link')).toHaveCount(0);
});
test('输入材料预览不跨空间，切回后原草稿可继续',async({page})=>{
 await page.goto('/phase4.html?view=help');await page.getByText('图片、PDF、手写与语音输入',{exact:true}).click();
 await page.getByRole('button',{name:'载入两页合成材料',exact:true}).click();
 await page.getByRole('button',{name:'学习',exact:true}).click();await create(page);
 await page.getByRole('button',{name:'问题求助',exact:true}).click();await page.getByText('图片、PDF、手写与语音输入',{exact:true}).click();
 await expect(page.getByRole('button',{name:'载入两页合成材料',exact:true})).toBeVisible();
 await page.getByRole('button',{name:'学习',exact:true}).click();await page.getByLabel('当前学习空间',{exact:true}).selectOption('demo');
 await page.getByRole('button',{name:'问题求助',exact:true}).click();await page.getByText('图片、PDF、手写与语音输入',{exact:true}).click();
 await expect(page.getByText('图片 1 · 自编原材料',{exact:true})).toBeVisible();
});
test('配置保存不等于可用，改动后必须重新核对，重试保留任务标识',async({page})=>{
 await page.goto('/phase4.html?role=admin&view=operations');await page.getByRole('button',{name:'查看 TASK-DEMO-FAILED',exact:true}).click();
 const retry=page.getByRole('button',{name:'重试原任务',exact:true});await expect(retry).toBeDisabled();
 await page.getByRole('button',{name:'保存演示配置',exact:true}).click();await expect(retry).toBeDisabled();
 await page.getByRole('button',{name:'载入预写连接检查结果',exact:true}).click();await expect(retry).toBeEnabled();
 await page.getByLabel('模型标记',{exact:true}).fill('第二版演示模型');await expect(retry).toBeDisabled();
 await page.getByRole('button',{name:'保存演示配置',exact:true}).click();await page.getByRole('button',{name:'载入预写连接检查结果',exact:true}).click();await retry.click();
 await expect(page.getByLabel('任务处理详情',{exact:true})).toContainText('TASK-DEMO-FAILED · 结果已确认 · 尝试 2 次');await page.reload();await page.getByRole('button',{name:'查看 TASK-DEMO-FAILED',exact:true}).click();await expect(page.getByLabel('任务处理详情',{exact:true})).toContainText('尝试 2 次');
 expect(await page.evaluate(()=>JSON.parse(localStorage.getItem('deermind-phase4-product-flows-v1')||'{"requests":[]}').requests)).toEqual([]);
});
test('结果未知先核对，恢复已有结果不重试，语义未决不当传输失败',async({page})=>{
 await page.goto('/phase4.html?role=admin&view=operations');await expect(page.getByRole('button',{name:'重试原任务',exact:true})).toHaveCount(0);
 await page.getByRole('button',{name:'核对原任务结果',exact:true}).click();await expect(page.getByLabel('任务处理详情',{exact:true})).toContainText('仍然无法确定');
 await page.getByLabel('预写原提交查询',{exact:true}).selectOption('found');await page.getByRole('button',{name:'核对原任务结果',exact:true}).click();await expect(page.getByLabel('任务处理详情',{exact:true})).toContainText('尝试 1 次');await expect(page.getByRole('button',{name:'重试原任务',exact:true})).toHaveCount(0);
 await page.getByRole('button',{name:'查看 TASK-DEMO-PENDING',exact:true}).click();await page.getByLabel('预写原提交查询',{exact:true}).selectOption('absent');await page.getByRole('button',{name:'核对原任务结果',exact:true}).click();await expect(page.getByRole('button',{name:'重试原任务',exact:true})).toBeDisabled();
 await page.getByRole('button',{name:'查看 TASK-DEMO-UNRESOLVED',exact:true}).click();await expect(page.getByLabel('任务处理详情',{exact:true})).toContainText('网络已经返回');await expect(page.getByRole('button',{name:'重试原任务',exact:true})).toHaveCount(0);
});
test('首页输入常驻且不遮挡正文，后台表格局部滚动',async({page},testInfo)=>{
 const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
 for(const view of ['home','operations']){await page.goto(`/phase4.html?role=${view==='home'?'student':'admin'}&view=${view}`);
  for(const width of [1280,834,390]){await page.setViewportSize({width,height:900});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
   if(view==='home'){await expect(page.getByLabel(/随时说说你的想法/)).toBeInViewport();const b=await page.evaluate(()=>({main:document.querySelector('main')!.getBoundingClientRect().bottom,composer:document.querySelector('.f-inline-composer')!.getBoundingClientRect().top}));expect(b.main).toBeLessThanOrEqual(b.composer+1);}
   await page.screenshot({path:testInfo.outputPath(`${view}-${width}.png`),fullPage:true});
  }
 }expect(errors).toEqual([]);
});
