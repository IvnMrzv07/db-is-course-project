// UI-only acceptance with explicit HTTP fixtures; not a database integration test.
const fs = require('node:fs');
const assert = require('node:assert/strict');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
(async()=>{
 const browser=await chromium.launch({headless:true, ...(process.env.CHROME_PATH?{executablePath:process.env.CHROME_PATH}:{})});
 const page=await browser.newPage({viewport:{width:1440,height:1000}});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 const documents=fs.readFileSync('data/prepared/kaggle-cs.jsonl','utf8').trim().split('\n').slice(0,40).map(JSON.parse);
 const job={id:'11111111-1111-4111-8111-111111111111',status:'running',total:20675,attempted:1000,inserted:900,duplicates:0,rejected:0,validation_rejected:1,backlog:100,target_rate:100,updated_at:new Date().toISOString()};
 const requests=[];
 await page.route('**/api/v1/**',async route=>{
   const req=route.request();const url=new URL(req.url());requests.push({path:url.pathname,method:req.method(),body:req.postData()});
   let data;
   if(url.pathname.endsWith('/corpus/statistics'))data={stored_documents:900,durable_documents_per_second:85,sampled_at:new Date().toISOString()};
   else if(url.pathname.endsWith('/snapshots'))data=[{id:'kaggle-cs',documents:20675,validation_rejected:1}];
   else if(url.pathname.includes('/replays')){
     if(req.method()==='PATCH')job.target_rate=JSON.parse(req.postData()).target_rate;
     if(url.pathname.endsWith('/pause'))job.status='paused';
     if(url.pathname.endsWith('/resume'))job.status='running';
     data=req.method()==='GET'?{items:[job],total:1}:job;
   }else if(/\/documents\//.test(url.pathname))data=documents.find(d=>url.pathname.endsWith(d.id));
   else {const q=(url.searchParams.get('q')||'').toLowerCase();const items=documents.filter(d=>(d.title+' '+d.text).toLowerCase().includes(q));data={items:items.slice(0,20),total:items.length,page:1,page_size:20};}
   await route.fulfill({json:data});
 });
 try{
 await page.goto(process.env.UI_BASE_URL||'http://127.0.0.1:5173');
 await page.locator('.document').first().waitFor();
 fs.mkdirSync('artifacts/test-results',{recursive:true});
 await page.screenshot({path:'artifacts/test-results/ui-corpus-desktop.png',fullPage:true});
 await page.locator('.document').first().click();await page.locator('dialog[open]').waitFor();
 assert((await page.locator('.full-text').innerText()).includes('played'));
 await page.getByRole('button',{name:'Закрити документ'}).click();
 await page.getByLabel('Пошук у тексті').fill('NONEXISTENT_MARKER');await page.getByRole('button',{name:'Знайти'}).click();
 await page.getByText('Документів не знайдено',{exact:true}).waitFor();
 await page.getByRole('button',{name:'Імпорт та моніторинг'}).click();
 await page.getByLabel('Токен',{exact:true}).fill('test-only-token-xxxxxxxxxxxxxxxx');await page.getByRole('button',{name:'Підключитися'}).click();
 await page.locator('.job').waitFor();
 await page.getByLabel('Темп, док/с',{exact:true}).fill('500');await page.getByRole('button',{name:'Застосувати',exact:true}).click();
 await page.getByRole('button',{name:'Призупинити'}).click();await page.getByRole('button',{name:'Продовжити'}).waitFor();
 assert(requests.some(r=>r.method==='PATCH'&&JSON.parse(r.body).target_rate===500));
 await page.screenshot({path:'artifacts/test-results/ui-import-desktop.png',fullPage:true});
 await page.setViewportSize({width:390,height:844});
 assert(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth));
 await page.screenshot({path:'artifacts/test-results/ui-import-mobile.png',fullPage:true});
 assert.deepEqual(errors,[]);
 console.log('UI fixtures: desktop, detail, empty search, auth, rate, pause, mobile PASS');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
