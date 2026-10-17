import { test, expect } from '@playwright/test';
import { calculateHomeStatistics, referenceEvents, referenceProblems, type ActivityEvent } from '../src/structure/homeStatistics';

test('event accounting excludes logins, duplicates, unknown dates, future events and cross-space records',()=>{
 const seed=referenceEvents[0]!;
 const added:ActivityEvent[]=[
  {...seed,id:'future',activity:'future',day:'2026-10-18'},
  {...seed,id:'external',activity:'external',space:'external',day:'2026-10-13'},
  {...seed,id:'other-child',activity:'other-child',learner:'S0042',day:'2026-10-13'},
  {...seed,id:'invalid',activity:'invalid',day:'2026-02-30'},
  ...referenceEvents,
 ];
 const week=calculateHomeStatistics([...referenceEvents,...added],referenceProblems,7);
 expect(week.from).toBe('2026-10-11');
 expect(week.studyDays).toEqual(['2026-10-12','2026-10-14','2026-10-16','2026-10-17']);
 expect(week.lessons.map(e=>e.activity)).toEqual(['lesson-a','lesson-b','lesson-c']);
 expect(week.checks.map(e=>e.activity)).toEqual(['check-a','check-b']);
 expect(week.undated).toBe(2);
 const month=calculateHomeStatistics(referenceEvents,referenceProblems,30);
 expect(month.from).toBe('2026-09-18');
 expect(month.studyDays).toHaveLength(5);expect(month.lessons).toHaveLength(4);
});

test('inclusive natural-day boundaries and same-activity continuation have distinct meanings',()=>{
 const base=referenceEvents[0]!;
 const events:ActivityEvent[]=[
  {...base,id:'older',activity:'continued',day:'2026-10-10'},
  {...base,id:'continued',activity:'continued',day:'2026-10-11'},
  {...base,id:'start',activity:'start',day:'2026-10-11'},
  {...base,id:'last-day',activity:'start',day:'2026-10-17'},
 ];
 const result=calculateHomeStatistics(events,[],7);
 expect(result.studyDays).toEqual(['2026-10-11','2026-10-17']);
 expect(result.lessons.map(e=>e.activity)).toEqual(['start']);
});

test('wrong inventory counts problem identities, retains corrected history, and ignores unresolved or hidden records',()=>{
 const result=calculateHomeStatistics(referenceEvents,[...referenceProblems,referenceProblems[0]!],7);
 expect(result.wrongProblems.map(p=>p.id)).toEqual(['HP-01','HP-02','HP-03','HP-04','HP-05','HP-06']);
 expect(result.wrongProblems.find(p=>p.id==='HP-02')?.attempts.some(a=>a.outcome==='correct')).toBeTruthy();
 expect(calculateHomeStatistics(referenceEvents,referenceProblems,30).wrongProblems).toHaveLength(6);
 expect(calculateHomeStatistics(referenceEvents,referenceProblems,7,undefined,'S0001','external').wrongProblems).toHaveLength(0);
});

test('homepage statistics reconcile to their own details; assessment page contains no activity dashboard',async({page})=>{
 await page.goto('/structure.html?role=student#/home');
 const stats=page.getByRole('region',{name:'学习活动统计'});
 await expect(stats).toContainText('统计示例');
 await expect(stats.locator('.statistic strong')).toHaveText(['4天','3次','2次','6题']);
 await stats.getByRole('button',{name:/开展讲解/}).click();
 await expect(page.getByRole('region',{name:'讲解活动明细'}).locator('li')).toHaveCount(3);
 await page.getByRole('button',{name:'收起明细',exact:true}).click();
 await expect(stats.getByRole('button',{name:/开展讲解/})).toBeFocused();
 await stats.getByRole('button',{name:/开展讲解/}).click();
 await page.getByLabel('活动统计时段').selectOption('30');
 await expect(stats.locator('.statistic strong')).toHaveText(['5天','4次','2次','6题']);
 await expect(page.getByRole('region',{name:'讲解活动明细'}).locator('li')).toHaveCount(4);
 await stats.getByRole('button',{name:/当前错题/}).click();
 await expect(page.getByRole('region',{name:'当前错题明细'}).locator('li')).toHaveCount(6);
 await expect(page.getByRole('region',{name:'当前错题明细'})).toContainText('已有一次订正答对');
 await page.getByLabel('当前学习空间',{exact:true}).selectOption('external');
 await expect(stats.locator('.statistic strong')).toHaveText(['—','—','—','—']);
 await expect(page.locator('#home-statistic-detail')).toHaveCount(0);
 await page.getByRole('navigation',{name:'主导航'}).getByRole('button',{name:'学习情况',exact:true}).click();
 await expect(stats).toHaveCount(0);
});

test('home chapter link returns to home and local activity never changes the statistical fixture',async({page})=>{
 await page.goto('/structure.html?role=student&preview=scripted#/home');
 await page.getByRole('button',{name:'查看本章学习情况 →',exact:true}).click();
 await expect(page.getByRole('heading',{name:'分数的应用',exact:true})).toBeVisible();
 await page.getByRole('button',{name:'← 返回首页',exact:true}).click();
 await expect(page).toHaveURL(/#\/home$/);
 await page.getByRole('button',{name:'从这里开始讲解 →',exact:true}).click();
 await page.getByRole('button',{name:'← 暂离并保留进度',exact:true}).click();
 await expect(page.locator('.statistic strong')).toHaveText(['4天','3次','2次','6题']);
 await expect(page.getByRole('region',{name:'学习情况摘要'})).toContainText('本轮 1 项活动');
});

for(const viewport of [{width:834,height:1112},{width:390,height:844},{width:1024,height:600}]){
 test(`homepage primary action is visible without scrolling at ${viewport.width}x${viewport.height}`,async({page})=>{
  await page.setViewportSize(viewport);
  await page.goto('/structure.html?role=student&preview=scripted#/home');
  const main=await page.locator('main').boundingBox();
  const action=await page.getByRole('button',{name:'从这里开始讲解 →',exact:true}).boundingBox();
  expect(action!.y).toBeGreaterThanOrEqual(main!.y);
  expect(action!.y+action!.height).toBeLessThanOrEqual(main!.y+main!.height);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
 });
}
