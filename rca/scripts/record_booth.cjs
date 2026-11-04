/* Capture actual offline browser interactions; no generated diagnosis/audio. */
const fs=require('fs'),path=require('path'),{pathToFileURL}=require('url');
const {chromium}=require(process.env.RCA_PLAYWRIGHT_MODULE||'playwright');
const source=path.resolve(process.argv[2]||'booth-demo'),output=path.resolve(process.argv[3]||'artifacts/booth-recording');
fs.mkdirSync(output,{recursive:false});
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.RCA_CHROMIUM_EXECUTABLE,args:['--no-sandbox']});
 const ctx=await browser.newContext({viewport:{width:1600,height:900},offline:true,recordVideo:{dir:output,size:{width:1600,height:900}}});
 const page=await ctx.newPage(),errors=[],requests=[],events=[];
 page.on('pageerror',e=>errors.push(String(e)));page.on('request',r=>{if(/^https?:/.test(r.url()))requests.push(r.url());});
 try{
  await page.goto(pathToFileURL(path.join(source,'viewer/index.html')).href+'?demo=1');
  await page.waitForSelector('#demo-investigate');
  const started=Date.now();
  const until=async sec=>{const ms=sec*1000-(Date.now()-started);if(ms>0)await page.waitForTimeout(ms);};
  const click=async selector=>{await page.locator(selector).hover();await page.waitForTimeout(200);await page.locator(selector).click();events.push({seconds:(Date.now()-started)/1000,selector});};
  await until(8);await click('#demo-investigate');
  await until(20);await click('#demo-evidence');
  await until(31);await click('#demo-observed details summary');
  await page.locator('#demo-observed pre').scrollIntoViewIfNeeded();
  await until(38);await click('#demo-observed details summary');await page.evaluate(()=>scrollTo(0,0));
  await until(41);await click('#demo-reset');await until(44);
  if(errors.length||requests.length)throw Error('Unexpected error/network request');
  const video=page.video();await ctx.close();await video.saveAs(path.join(output,'screen.webm'));
  fs.writeFileSync(path.join(output,'recording.json'),JSON.stringify({source,events,externalRequests:requests,pageErrors:errors,mode:'actual offline browser screen recording; archived AI output',audio:'none',paidCalls:0},null,2));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
