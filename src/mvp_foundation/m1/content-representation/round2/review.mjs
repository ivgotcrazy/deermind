import {createRequire} from 'node:module';
import {mkdir,writeFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
const require=createRequire(new URL('../../../../../doc/mvp/m1/prototype/package.json',import.meta.url));
const {chromium}=require('@playwright/test');
const root=new URL('./',import.meta.url);await mkdir(new URL('review/',root),{recursive:true});
const browser=await chromium.launch({headless:true}),page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[],checks=[];
page.on('pageerror',e=>errors.push(e.message));
try{
 for(const cid of ['C02','C03','C05','C06']){
  await page.goto('http://127.0.0.1:5183/round2/#'+cid);await page.locator('#mode').waitFor();
  await page.waitForFunction(()=>[...document.images].every(i=>i.complete&&i.naturalWidth>0));
  const rawCharts=await page.locator('#content .question svg').count();
  if(cid==='C05'&&rawCharts!==0)throw new Error('Raw chart omission was hidden');
  for(const mode of ['raw','reviewed']){
   await page.locator('#mode').selectOption(mode);
   for(const d of await page.locator('#content details.solution').all())await d.locator('summary').click();
   if(cid==='C02'&&mode==='raw'&&await page.locator('#content .error').count()!==2)throw new Error('Invalid raw formulas were rendered');
   if(cid==='C02'&&mode==='reviewed'&&await page.locator('#content details.solution').count()!==2)throw new Error('Two source methods not separated');
   if(cid==='C05'&&mode==='reviewed'&&await page.locator('#content .question svg').count()!==3)throw new Error('Corrected charts missing');
   if(cid==='C06'){
    if(await page.locator('[data-shape]').count()!==6||await page.locator('[data-dot]').count()!==6)throw new Error('Shape/mark missing');
    const square=page.locator('[data-square]');if(await square.getAttribute('width')!==await square.getAttribute('height'))throw new Error('Square distorted');
   }
   if(mode==='reviewed'&&await page.locator('.question details.solution,.question details.aids').count())throw new Error('Help leaked into question');
   await page.screenshot({path:fileURLToPath(new URL(`review/${cid}-${mode}.png`,root)),fullPage:true});
  }
  if(await page.locator('#mapping tbody tr').count()!==(cid==='C02'?3:1))throw new Error('Graph not shown');
  checks.push({caseId:cid,sourceLoaded:true,rawAndReviewedSeparated:true,graphShown:true});
 }
 await page.setViewportSize({width:800,height:1000});await page.goto('http://127.0.0.1:5183/round2/#C05');await page.locator('#mode').selectOption('reviewed');
 if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw new Error('Viewport overflow');
 if(errors.length)throw new Error(errors.join('\n'));
 await writeFile(new URL('review/browser-review.json',root),JSON.stringify({status:'passed',checks,errors,narrowWidth:800,scope:'Display and provenance paths; not automatic semantic validation'},null,2));console.log(JSON.stringify({status:'passed',cases:4,modes:2}));
}finally{await browser.close()}
