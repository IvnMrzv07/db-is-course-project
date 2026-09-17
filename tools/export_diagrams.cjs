// Render local Mermaid sources to PNG. See tools/README.md for setup.
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const root = path.resolve(__dirname, '..');
const assets = path.join(root, '.diagram-renderer', 'node_modules');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || path.join(assets, 'playwright'));
const output = path.join(root, 'diagrams', 'images');

async function main() {
  fs.mkdirSync(output, { recursive: true });
  const server = http.createServer((req, res) => {
    if (req.url === '/') {
      res.setHeader('Content-Type', 'text/html');
      res.end('<html><body style="margin:0;background:white"><div id="diagram" style="display:inline-block;padding:24px"></div></body></html>');
      return;
    }
    const file = path.resolve(assets, '.' + decodeURIComponent(req.url));
    if (!file.startsWith(assets + path.sep) || !fs.existsSync(file)) {
      res.writeHead(404); res.end(); return;
    }
    res.setHeader('Content-Type', file.endsWith('.js') || file.endsWith('.mjs') ? 'text/javascript' : 'application/octet-stream');
    fs.createReadStream(file).pipe(res);
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  let browser;
  try {
    browser = await chromium.launch({...(process.env.CHROME_PATH ? {executablePath: process.env.CHROME_PATH} : {}), headless:true});
    const page = await browser.newPage({viewport:{width:2000,height:1400},deviceScaleFactor:2});
    await page.goto(`http://127.0.0.1:${server.address().port}/`);
    await page.evaluate(async () => {
      const {default:mermaid} = await import('/mermaid/dist/mermaid.esm.min.mjs');
      mermaid.initialize({startOnLoad:false,theme:'neutral',fontFamily:'Arial',securityLevel:'strict',
        flowchart:{htmlLabels:false,useMaxWidth:false,curve:'linear',nodeSpacing:25,rankSpacing:55},
        class:{useMaxWidth:false},sequence:{useMaxWidth:false}});
      window.renderer = mermaid;
    });
    const results=[];
    for(const filename of fs.readdirSync(path.join(root,'diagrams')).filter(f=>f.endsWith('.mmd')).sort()) {
      const source=fs.readFileSync(path.join(root,'diagrams',filename),'utf8');
      const stem=path.basename(filename,'.mmd');
      await page.evaluate(async ({source})=>{
        const container=document.getElementById('diagram'); container.innerHTML='';
        const result=await window.renderer.render('exported_diagram',source);
        container.innerHTML=result.svg;
        await document.fonts.ready;
        const svg=container.querySelector('svg');
        const bounds=svg.viewBox.baseVal;
        svg.style.maxWidth='none';
        svg.style.width=Math.ceil(bounds.width)+'px';
        svg.style.height=Math.ceil(bounds.height)+'px';
        svg.setAttribute('width',Math.ceil(bounds.width));
        svg.setAttribute('height',Math.ceil(bounds.height));
      },{source});
      await page.locator('#diagram').screenshot({path:path.join(output,stem+'.png')});
      const box=await page.locator('#diagram').boundingBox();
      results.push({name:stem,width:Math.ceil(box.width*2),height:Math.ceil(box.height*2)});
      console.log(stem,Math.ceil(box.width*2)+'x'+Math.ceil(box.height*2));
    }
    fs.writeFileSync(path.join(output,'manifest.json'),JSON.stringify(results,null,2)+'\n');
  } finally {
    if(browser) await browser.close();
    await new Promise(resolve=>server.close(resolve));
  }
}
main().catch(error=>{console.error(error);process.exitCode=1;});
