/* Browser acceptance test: actual HTML, offline file + loopback HTTP, no LLM. */
const fs=require('fs'),path=require('path'),http=require('http'),assert=require('assert');
const {pathToFileURL}=require('url');
const {chromium}=require(process.env.RCA_PLAYWRIGHT_MODULE||'playwright');
const dir=path.resolve(process.argv[2]||'booth-demo'),out=path.resolve(process.argv[3]||'artifacts/booth-browser');
fs.mkdirSync(out,{recursive:true});
const html=fs.readFileSync(path.join(dir,'viewer/index.html'),'utf8');
const data=JSON.parse(html.match(/<script id="dataset" type="application\/json">(.*?)<\/script>/s)[1]);
const run=data.runs.find(r=>r.run_id===data.demo.primary_run_id);
const expected=JSON.parse(run.evidence.find(e=>e.tool==='get_workload_status').data.declared_dependency);
const observed=run.evidence.find(e=>e.tool==='get_ebpf_summary');
(async()=>{
  const server=http.createServer((req,res)=>{const file=req.url.startsWith('/viewer/index.html')?'viewer/index.html':'START.html';res.setHeader('Content-Type','text/html; charset=utf-8');res.end(fs.readFileSync(path.join(dir,file)));});
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  let browser;
  const report={tests:[],externalRequests:[],apiRequests:[],pageErrors:[],paidCalls:0};
  try{
    browser=await chromium.launch({headless:true,executablePath:process.env.RCA_CHROMIUM_EXECUTABLE,args:['--no-sandbox']});
    for(const mode of ['file','http']){
      const ctx=await browser.newContext({viewport:{width:1366,height:900},offline:mode==='file'});
      const page=await ctx.newPage();
      page.on('pageerror',e=>report.pageErrors.push(String(e)));
      page.on('request',r=>{if(r.url().includes('/api/'))report.apiRequests.push(r.url());if(/^https?:/.test(r.url())&&!r.url().startsWith('http://127.0.0.1:'))report.externalRequests.push(r.url());});
      await page.route('**/*',route=>/^(file:|http:\/\/127\.0\.0\.1:)/.test(route.request().url())?route.continue():route.abort());
      await page.goto(mode==='file'?pathToFileURL(path.join(dir,'START.html')).href:`http://127.0.0.1:${server.address().port}/START.html`);
      await page.waitForSelector('#demo-investigate');
      await ctx.setOffline(true);
      assert((await page.locator('#booth').innerText()).includes('저장된 조사 기록 재생'));
      assert(!(await page.locator('#booth').innerText()).includes(run.run_id),'internal run ID must be collapsed');
      if(mode==='file')await page.screenshot({path:path.join(out,'01-incident.png'),fullPage:true});
      await page.locator('#demo-investigate').click();
      assert.deepStrictEqual(await page.locator('#demo-timeline li').evaluateAll(nodes=>nodes.map(n=>n.dataset.source)),run.retrievals.map(r=>r.source));
      assert(await page.locator('#demo-evidence').evaluate(e=>e.getBoundingClientRect().bottom<=innerHeight),'second button must be visible without scrolling');
      if(mode==='file')await page.screenshot({path:path.join(out,'02-investigation.png'),fullPage:true});
      await page.locator('#demo-evidence').click();
      assert.equal(await page.locator('#demo-expected .port-value').innerText(),String(expected.expected_port));
      assert.equal(await page.locator('#demo-observed .port-value').first().innerText(),String(observed.network.tcp_connect_attempts[0].destination_port));
      assert((await page.locator('#demo-comparison').innerText()).includes('AI는 원인을 보류'));
      if(mode==='file')await page.screenshot({path:path.join(out,'03-evidence-comparison.png'),fullPage:true});
      for(const id of run.answer.claims[data.demo.claim_index].evidence_ids){
        const detail=page.locator(`details[data-evidence="${id}"]`);await detail.locator('summary').click();
        assert.deepStrictEqual(JSON.parse(await detail.locator('pre').innerText()),run.evidence.find(e=>e.evidence_id===id));
      }
      await page.locator('#booth .booth-footer summary').click();
      await page.locator('#demo-reset').click();
      assert(await page.locator('#demo-investigate').isVisible());
      assert.equal(await page.locator('#booth details[open]').count(),0);
      assert.equal(await page.evaluate(()=>scrollY),0);
      await page.locator('#demo-investigate').click();await page.locator('#demo-evidence').click();
      assert(await page.locator('#demo-comparison').isVisible());
      report.tests.push(mode+': offline start, 2-click flow, real retrieval order, exact cited evidence, reset and second visitor PASS');
      if(mode==='file'){
        await page.setViewportSize({width:390,height:844});await page.locator('#demo-reset').click();
        assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
        report.tests.push('390px narrow viewport: no horizontal overflow PASS');
        await page.setViewportSize({width:1366,height:900});
        const fallback=JSON.parse(JSON.stringify(data));fallback.runs=fallback.runs.filter(r=>r.run_id===fallback.demo.primary_run_id);fallback.demo.baseline_run_id=null;
        await page.evaluate(d=>{document.querySelector('#booth').remove();window.RCABooth(d);},fallback);
        await page.locator('#demo-investigate').click();await page.locator('#demo-evidence').click();
        assert((await page.locator('#demo-stage').innerText()).includes('eBPF 제외 실행이 없어'));
        const missing=JSON.parse(JSON.stringify(data));missing.runs[0].evidence=[];
        await page.evaluate(d=>{document.querySelector('#booth').remove();window.RCABooth(d);},missing);
        assert((await page.locator('#demo-stage').innerText()).includes('저장 기록이 부족'));
        report.tests.push('missing pair fallback and missing evidence message PASS');
        await page.goto(pathToFileURL(path.join(dir,'viewer/index.html')).href+'?demo=0');
        assert(await page.locator('#owner').isVisible());assert.equal(await page.locator('#case option').count(),1);
        assert.equal(await page.locator('#left option').count(),2);
        report.tests.push('original replay viewer with same two runs PASS');
      }
      await ctx.close();
    }
    assert.deepStrictEqual(report.externalRequests,[]);assert.deepStrictEqual(report.apiRequests,[]);assert.deepStrictEqual(report.pageErrors,[]);
    report.result='PASS';
  }catch(e){report.result='FAIL';report.error=String(e);throw e;}
  finally{fs.writeFileSync(path.join(out,'result.json'),JSON.stringify(report,null,2));if(browser)await browser.close();await new Promise(r=>server.close(r));}
  console.log(JSON.stringify(report,null,2));
})().catch(e=>{console.error(e);process.exitCode=1;});
