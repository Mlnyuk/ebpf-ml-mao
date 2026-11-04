/* Functional console checks on actual stored data, disconnected from all servers. */
const fs=require('fs'),path=require('path'),assert=require('assert'),{pathToFileURL}=require('url');
const {chromium}=require(process.env.RCA_PLAYWRIGHT_MODULE||'playwright');
const folder=path.resolve(process.argv[2]),out=path.resolve(process.argv[3]);fs.mkdirSync(out,{recursive:true});
const html=fs.readFileSync(path.join(folder,'viewer/index.html'),'utf8');const d=JSON.parse(html.match(/<script id="dataset" type="application\/json">(.*?)<\/script>/s)[1]);
const run=d.runs[0],log=run.evidence.find(e=>e.tool==='get_logs');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.RCA_CHROMIUM_EXECUTABLE,args:['--no-sandbox']});
 const context=await browser.newContext({offline:true,viewport:{width:1366,height:768}}),page=await context.newPage();
 const result={requests:[],errors:[],checks:[]};page.on('pageerror',e=>result.errors.push(String(e)));page.on('request',r=>{if(/^https?:/.test(r.url()))result.requests.push(r.url());});
 try{
  await page.goto(pathToFileURL(path.join(folder,'START.html')).href);await page.waitForSelector('#demo-investigate');
  assert.equal(await page.locator('.log-row').count(),log.lines.length);
  const failures=log.lines.filter(s=>s.includes('status=503')).length;
  assert.equal(await page.locator('#log-histogram').getAttribute('data-total'),String(failures));
  const tooltipCounts=await page.locator('#log-histogram rect title').allTextContents();assert.equal(tooltipCounts.reduce((n,s)=>n+Number(s.match(/· (\d+)줄/)[1]),0),failures);
  await page.keyboard.press('/');assert.equal(await page.locator('#log-search').evaluate(e=>e===document.activeElement),true);
  await page.locator('#log-search').fill('status=503');assert.equal(await page.locator('.log-row').count(),failures);
  await page.locator('.log-row').first().click();assert.equal(await page.locator('#inspector-json').textContent(),log.lines.find(s=>s.includes('status=503'))+'\n');
  await page.keyboard.press('Escape');assert.equal(await page.locator('[role=dialog]').count(),0);
  await page.locator('#log-search').fill('does-not-exist');assert.equal(await page.locator('.log-row').count(),0);
  await page.keyboard.press('Escape');await page.keyboard.press('r');assert.equal(await page.locator('.log-row').count(),log.lines.length);
  result.checks.push('actual log filtering, original line, histogram counts, slash shortcut and reset PASS');
  await page.keyboard.press('2');assert.equal(await page.locator('#booth').getAttribute('data-mode'),'1');
  assert.deepStrictEqual(await page.locator('#demo-timeline li').evaluateAll(ns=>ns.map(n=>n.dataset.source)),run.retrievals.map(r=>r.source));
  const visibility=await page.locator('#demo-timeline').evaluate(e=>({scroll:e.scrollHeight,client:e.clientHeight}));
  result.timeline_size=visibility;
  await page.screenshot({path:path.join(out,'console-investigation-1366x768.png')});
  assert(visibility.scroll<=visibility.client+1,'all six recorded queries must fit without hidden rows');
  assert(await page.locator('#demo-evidence').evaluate(e=>e.getBoundingClientRect().bottom<=innerHeight));
  await page.screenshot({path:path.join(out,'console-investigation-1366x768.png')});
  await page.locator('.citation').filter({hasText:'연결 시도'}).click();
  const net=run.evidence.find(e=>e.tool==='get_ebpf_summary');assert.deepStrictEqual(JSON.parse(await page.locator('#inspector-json').textContent()),net);
  assert((await page.locator('#inspector-json .code-match').textContent()).includes(String(net.network.tcp_connect_attempts[0].destination_port)));
  const visible=await page.locator('#inspector-json .code-match').evaluate(e=>{const r=e.getBoundingClientRect(),p=e.parentElement.getBoundingClientRect();return r.top>=p.top&&r.bottom<=p.bottom;});assert(visible,'cited port should be scrolled into view');
  await page.screenshot({path:path.join(out,'console-evidence-inspector.png')});
  await page.keyboard.press('Tab');assert.equal(await page.locator('#inspector-close').evaluate(e=>e===document.activeElement),true);
  await page.keyboard.press('Escape');await page.keyboard.press('3');
  assert(await page.locator('#demo-comparison').evaluate(e=>e.getBoundingClientRect().bottom<=innerHeight));
  const comparisonContents=await page.locator('#demo-comparison').evaluate(e=>({scroll:e.scrollHeight,client:e.clientHeight}));
  result.comparison_size=comparisonContents;
  assert(comparisonContents.scroll<=comparisonContents.client+1,'comparison text, both original-answer links and scope note must not be clipped');
  await page.screenshot({path:path.join(out,'console-comparison-1366x768.png')});
  result.checks.push('six-query timeline, keyboard navigation, citation inspector exact data and focus, comparison visible PASS');
  assert.deepStrictEqual(result.requests,[]);assert.deepStrictEqual(result.errors,[]);result.result='PASS';
 }catch(e){result.result='FAIL';result.error=String(e);throw e;}
 finally{fs.writeFileSync(path.join(out,'result.json'),JSON.stringify(result,null,2));await browser.close();}
 console.log(JSON.stringify(result,null,2));
})().catch(e=>{console.error(e);process.exitCode=1;});
