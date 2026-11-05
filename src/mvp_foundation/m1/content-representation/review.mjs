import { createRequire } from 'node:module';
import { readFile, mkdir, writeFile } from 'node:fs/promises';
const require=createRequire(new URL('../../../../doc/mvp/m1/prototype/package.json',import.meta.url));
const { chromium }=require('@playwright/test');
const root=new URL('./',import.meta.url),reference=JSON.parse(await readFile(new URL('reference.json',root),'utf8'));
await mkdir(new URL('review/',root),{recursive:true});
const browser=await chromium.launch({headless:true}),page=await browser.newPage({viewport:{width:1440,height:1050},locale:'zh-CN'}),errors=[];
page.on('pageerror',e=>errors.push(e.message));
const checks=[];
try{
 for(const c of reference.cases){
  await page.goto('http://127.0.0.1:5183/#'+c.id);await page.locator('#question').waitFor();
  await page.waitForFunction(()=>Array.from(document.images).every(i=>i.complete&&i.naturalWidth>0));
  if(await page.locator('#question [data-solution]').count())throw new Error('Solution in question');
  if(c.id==='C01'&&await page.locator('#question math mfrac').count()!==8)throw new Error('Fraction rendering missing');
  if(c.id==='C03'&&!(await page.locator('#question').innerText()).includes('32'))throw new Error('Original wrong result missing');
  if(c.id==='C04'&&await page.locator('#question .blank').count()!==3)throw new Error('Response blanks missing');
  if(c.id==='C05'&&await page.locator('#question svg').count()!==3)throw new Error('Charts missing');
  for(const s of await page.locator('details.solution').all())await s.locator('summary').click();
  if(c.id==='C08'&&await page.locator('.view-item').count()!==4)throw new Error('Source views changed');
  await page.screenshot({path:new URL('review/'+c.id+'.png',root).pathname.replace(/^\/([A-Za-z]:)/,'$1'),fullPage:true});
  checks.push({id:c.id,loaded:true,sourceImageLoaded:true,questionsAndSolutionsSeparated:true});
 }
 await page.setViewportSize({width:800,height:1000});await page.goto('http://127.0.0.1:5183/#C05');await page.locator('#question svg').first().waitFor();
 const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth);if(overflow)throw new Error('Viewport overflow');
 await page.setViewportSize({width:1440,height:1050});
 for(const c of reference.cases){
  await page.goto('http://127.0.0.1:5183/?trial=1#'+c.id);await page.locator('#trial-output').waitFor();
  await page.waitForFunction(()=>Array.from(document.images).every(i=>i.complete&&i.naturalWidth>0));
  if(c.id==='C05'&&await page.locator('#trial-output svg').count()!==3)throw new Error('Returned charts not rendered');
  if(c.id==='C08'&&await page.locator('#trial-output article').count()!==0)throw new Error('Invalid JSON was silently repaired');
  if(['C01','C05','C06','C08'].includes(c.id))await page.screenshot({path:new URL('review/LLM-'+c.id+'.png',root).pathname.replace(/^\/([A-Za-z]:)/,'$1'),fullPage:true});
 }
 if(errors.length)throw new Error(errors.join('\n'));
 await writeFile(new URL('review/browser-review.json',root),JSON.stringify({status:'passed',cases:checks,rawResultViews:8,narrowWidth:800,errors,scope:'Browser behavior only; author separately inspects screenshots. Failed LLM output stays failed.'},null,2));console.log(JSON.stringify({cases:checks.length,rawResultViews:8,status:'passed',screenshots:'review/'}));
}finally{await browser.close()}
