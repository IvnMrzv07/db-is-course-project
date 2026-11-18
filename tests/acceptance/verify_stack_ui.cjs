// Real Compose browser acceptance. No HTTP interception or fixture responses.
const fs = require('node:fs');
const assert = require('node:assert/strict');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
(async()=>{
 const browser=await chromium.launch({headless:true, ...(process.env.CHROME_PATH?{executablePath:process.env.CHROME_PATH}:{})});
 const page=await browser.newPage({viewport:{width:1440,height:1000}});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 const base=process.env.UI_BASE_URL||'http://127.0.0.1:8080';
 try {
  await page.goto(base);
  await page.locator('.document').first().waitFor();
  assert.equal(await page.locator('.document').count(),20);
  await page.screenshot({path:'docs/coursework/stages/stage12-summary/ui-corpus.png',fullPage:true});
  await page.locator('.document').first().click();
  await page.locator('dialog[open]').waitFor();
  assert((await page.locator('.full-text').innerText()).length>50);
  await page.screenshot({path:'docs/coursework/stages/stage12-summary/ui-document.png',fullPage:true});
  await page.getByRole('button',{name:'Закрити документ'}).click();
  await page.getByLabel('Пошук у тексті').fill('UNLIKELY_ABSENT_UI_MARKER');
  await page.getByRole('button',{name:'Знайти'}).click();
  await page.getByText('Документів не знайдено',{exact:true}).waitFor();
  await page.getByRole('button',{name:'Імпорт та моніторинг'}).click();
  await page.getByLabel('Токен',{exact:true}).fill(process.env.OPERATOR_TOKEN);
  await page.getByRole('button',{name:'Підключитися'}).click();
  await page.getByLabel('Підготовлений набір').locator('option').waitFor({state:'attached'});
  await page.getByLabel('Цільовий темп, док/с').fill('10');
  const created=page.waitForResponse(r=>r.url().endsWith('/api/v1/replays')&&r.request().method()==='POST');
  await page.getByRole('button',{name:'Почати імпорт'}).click();
  const response=await created; assert.equal(response.status(),202); const job=await response.json();
  const card=page.locator('.job').filter({hasText:job.id.slice(0,8)});
  await card.getByRole('button',{name:'Призупинити'}).click();
  await card.locator('.status.paused').waitFor();
  await card.getByLabel('Темп, док/с',{exact:true}).fill('500');
  const rateChanged=page.waitForResponse(r=>r.url().endsWith('/rate')&&r.request().method()==='PATCH');
  await card.getByRole('button',{name:'Застосувати'}).click();
  assert.equal((await rateChanged).status(),200);
  await card.getByRole('button',{name:'Продовжити'}).click();
  await card.locator('.status.completed').waitFor({timeout:600000});
  await page.screenshot({path:'docs/coursework/stages/stage12-summary/ui-import.png',fullPage:true});
  const final=await (await page.request.get(base+'/api/v1/replays/'+job.id,{headers:{Authorization:'Bearer '+process.env.OPERATOR_TOKEN}})).json();
  assert.equal(final.inserted,0);assert.equal(final.duplicates,20675);assert.equal(final.backlog,0);
  assert.deepEqual(errors,[]);
  fs.writeFileSync('docs/coursework/stages/stage12-summary/compose-browser-check.json',JSON.stringify({verified_at:new Date().toISOString(),http_mocking:false,checks:['real_corpus','detail','empty_search','operator_login','start_import','pause','rate_10_to_500','resume','completed_duplicate_import'],job:final,page_errors:errors},null,2)+'\n');
  console.log('Real Compose browser acceptance passed');
 } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
