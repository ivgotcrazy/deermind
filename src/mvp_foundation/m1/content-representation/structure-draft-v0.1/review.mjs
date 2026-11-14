import {createRequire} from 'node:module';
import {mkdir, writeFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
const require = createRequire(new URL('../../../../../doc/mvp/m1/prototype/package.json', import.meta.url));
const {chromium} = require('@playwright/test');
const root = new URL('./', import.meta.url);
const url = process.env.REVIEW_URL || 'http://127.0.0.1:5184/structure-draft-v0.1/';
await mkdir(new URL('review/', root), {recursive:true});
const browser = await chromium.launch({headless:true, channel:'chrome'});
const page = await browser.newPage({viewport:{width:1500, height:1000}});
const errors = [], results = [];
page.on('pageerror', error => errors.push(error.message));
page.on('console', msg => {if (msg.type() === 'error') errors.push(msg.text());});

function assert(value, message) {if (!value) throw new Error(message);}
async function capture(name) {await page.screenshot({path:fileURLToPath(new URL(`review/${name}.png`, root)), fullPage:true});}
try {
  for (const cid of ['C02', 'C03', 'C05', 'C06']) {
    await page.goto(url + '#' + cid);
    await page.waitForFunction(id => document.body.dataset.loaded === id, cid);
    await page.waitForFunction(() => [...document.images].every(i => i.complete && i.naturalWidth > 0));
    assert(await page.locator('#rendered [data-role="statement"]').count() === 1, cid + ' missing question');
    assert(await page.locator('#rendered [data-role="reference"],#rendered [data-role="teaching_aid"],#rendered [data-role="derived_view"]').count() === 0, 'Non-question material leaked');
    if (cid === 'C02') {
      assert(await page.locator('#rendered math').count() === 2, 'inline fractions missing');
      assert(await page.locator('#rendered [data-blank]').count() === 1, 'answer blank missing');
      assert(await page.locator('#rendered table').count() === 0, 'answer blank falsely turned into a source table');
      await capture('C02-question');
      await page.locator('[data-role-tab="reference"]').click();
      assert(await page.locator('#rendered [data-role="reference"]').count() === 2, 'two textbook methods missing');
      assert(await page.locator('[data-cancellation]').count() === 6, 'cancellation marks missing');
      assert(await page.locator('.math-line').count() === 6, 'intermediate source lines missing');
      await capture('C02-references');
      await page.locator('[data-role-tab="statement"]').click();
      assert(await page.locator('#rendered [data-cancellation]').count() === 0, 'reference remained in question DOM');
    } else if (cid === 'C03') {
      const work = await page.locator('#rendered').innerText();
      assert(work.includes('÷') && await page.locator('.math-line').count() === 3, 'source calculation altered');
      assert(await page.locator('[data-cancellation]').count() === 2, 'error exercise cancellation marks missing');
      const lastNumbers = await page.locator('.math-line').last().locator('mn').allTextContents();
      assert(lastNumbers.join('/') === '7/32', 'original wrong result replaced');
      assert(!work.includes('63'), 'corrected answer leaked');
      await capture('C03-question');
    } else if (cid === 'C05') {
      assert(await page.locator('[data-chart]').count() === 3, 'chart omission');
      assert(await page.locator('#rendered table').count() === 0, 'derived table leaked into source question');
      await capture('C05-question');
      await page.locator('[data-role-tab="derived_view"]').click();
      assert(await page.locator('#rendered table').count() === 2, 'data table views missing');
      assert(await page.locator('#rendered tbody tr').count() === 7, 'data rows changed');
      assert((await page.locator('#rendered').innerText()).includes('1.30'), 'source numeric precision lost');
      await capture('C05-tables');
      await page.locator('[data-role-tab="teaching_aid"]').click();
      assert(await page.locator('#rendered .content-block').count() === 3, 'source hints missing');
      await capture('C05-aids');
    } else {
      assert(await page.locator('[data-shape]').count() === 6, 'shape omission');
      assert(await page.locator('[data-mark]').count() === 6, 'point omission');
      const square = page.locator('[data-square]');
      assert(await square.getAttribute('width') === await square.getAttribute('height'), 'square distorted');
      assert(!(await page.locator('#rendered').innerText()).includes('圆心'), 'invented center assertion');
      await capture('C06-question');
    }
    assert(!await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), cid + ' horizontal overflow');
    results.push({case_id:cid, sources_loaded:true, question_isolated:true, reconstructed:true});
  }
  await page.setViewportSize({width:900, height:1000});
  await page.goto(url + '#C05');
  await page.waitForFunction(() => document.body.dataset.loaded === 'C05');
  assert(!await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), 'narrow browser overflow');
  await capture('C05-browser-900');
  assert(errors.length === 0, errors.join('\n'));
  const report = {version:'0.1', status:'passed', url, checks:results, browser_widths:[1500,900], errors,
    scope:'Standalone four-case renderer. Not product prototype, model extraction, or full-book semantic acceptance.'};
  await writeFile(new URL('review/browser-review.json', root), JSON.stringify(report, null, 2) + '\n');
  console.log(JSON.stringify({status:'passed', cases:results.length, screenshots:8, errors}));
} finally {await browser.close();}
