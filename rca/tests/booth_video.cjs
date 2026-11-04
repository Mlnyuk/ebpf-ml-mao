const fs=require('fs'),path=require('path'),assert=require('assert'),{pathToFileURL}=require('url');
const {chromium}=require(process.env.RCA_PLAYWRIGHT_MODULE||'playwright');
const dir=path.resolve(process.argv[2]||'booth-demo'),out=path.resolve(process.argv[3]||'artifacts/booth-video-check');
fs.mkdirSync(out,{recursive:true});
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.RCA_CHROMIUM_EXECUTABLE,args:['--no-sandbox']});
 const context=await browser.newContext({offline:true,viewport:{width:1366,height:768}});
 const page=await context.newPage(),report={networkRequests:[],pageErrors:[],tests:[]};
 page.on('request',r=>{if(/^https?:/.test(r.url()))report.networkRequests.push(r.url());});
 page.on('pageerror',e=>report.pageErrors.push(String(e)));
 try{
  await page.goto(pathToFileURL(path.join(dir,'WATCH.html')).href);
  await page.waitForFunction(()=>{const v=document.querySelector('video');if(v.error)throw Error('Video error '+v.error.code);return v.readyState>=2&&v.currentTime>0;},{},{timeout:15000});
  const meta=await page.locator('video').evaluate(v=>({duration:v.duration,width:v.videoWidth,height:v.videoHeight,loop:v.loop,muted:v.muted,source:v.currentSrc}));
  assert(meta.duration>40&&meta.duration<46);assert(meta.loop);assert(meta.muted);report.video=meta;
  await page.locator('video').evaluate(v=>v.currentTime=v.duration-.3);await page.waitForTimeout(1200);
  assert(await page.locator('video').evaluate(v=>v.currentTime<3&&!v.paused));
  report.tests.push('offline local video playback and actual loop PASS');
  await page.goto(pathToFileURL(path.join(dir,'START.html')).href);await page.waitForSelector('#demo-investigate');
  await page.locator('#demo-investigate').focus();await page.keyboard.press('Enter');
  assert(await page.locator('#demo-evidence').evaluate(e=>e.getBoundingClientRect().bottom<=innerHeight));
  await page.locator('#demo-evidence').focus();await page.keyboard.press('Enter');
  const rect=await page.locator('#demo-comparison').evaluate(e=>({bottom:e.getBoundingClientRect().bottom,height:innerHeight}));
  assert(rect.bottom<=rect.height,'comparison must fit 1366x768 without scrolling');
  await page.screenshot({path:path.join(out,'laptop-1366x768.png')});
  await page.locator('#demo-reset').focus();await page.keyboard.press('Enter');assert(await page.locator('#demo-investigate').isVisible());
  report.tests.push('1366x768 two-click flow, visible comparison, keyboard and reset PASS');
  assert.deepStrictEqual(report.networkRequests,[]);assert.deepStrictEqual(report.pageErrors,[]);report.result='PASS';
 }catch(e){report.result='FAIL';report.error=String(e);throw e;}
 finally{fs.writeFileSync(path.join(out,'result.json'),JSON.stringify(report,null,2));await browser.close();}
 console.log(JSON.stringify(report,null,2));
})().catch(e=>{console.error(e);process.exitCode=1;});
