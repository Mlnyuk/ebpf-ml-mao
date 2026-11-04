/* Actual offline console recording. No subtitle overlays or model execution. */
const fs=require('fs'),path=require('path'),{pathToFileURL}=require('url');
const {chromium}=require(process.env.RCA_PLAYWRIGHT_MODULE||'playwright');
const source=path.resolve(process.argv[2]),output=path.resolve(process.argv[3]);fs.mkdirSync(output,{recursive:false});
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.RCA_CHROMIUM_EXECUTABLE,args:['--no-sandbox']});
 const context=await browser.newContext({viewport:{width:1600,height:900},offline:true,recordVideo:{dir:output,size:{width:1600,height:900}}});
 const page=await context.newPage(),events=[],requests=[],errors=[];
 page.on('request',r=>{if(/^https?:/.test(r.url()))requests.push(r.url());});page.on('pageerror',e=>errors.push(String(e)));
 try{
  await page.goto(pathToFileURL(path.join(source,'viewer/index.html')).href+'?demo=1');await page.waitForSelector('#demo-investigate');
  // Playwright video omits the system pointer; render the actual mouse position.
  await page.evaluate(()=>{const s=document.createElementNS('http://www.w3.org/2000/svg','svg');s.setAttribute('viewBox','0 0 24 32');s.style.cssText='position:fixed;width:18px;height:24px;pointer-events:none;z-index:1000;opacity:0';const p=document.createElementNS(s.namespaceURI,'path');p.setAttribute('d','M2 2L2 25L8 19L13 30L18 28L13 18L22 18Z');p.setAttribute('fill','#f3f6f8');p.setAttribute('stroke','#101318');p.setAttribute('stroke-width','1.5');s.append(p);document.body.append(s);addEventListener('mousemove',e=>{s.style.left=e.clientX+'px';s.style.top=e.clientY+'px';s.style.opacity=1;});addEventListener('mousedown',()=>p.setAttribute('fill','#79d6c7'));addEventListener('mouseup',()=>p.setAttribute('fill','#f3f6f8'));});
  const started=Date.now();const until=async sec=>{const ms=sec*1000-(Date.now()-started);if(ms>0)await page.waitForTimeout(ms);};
  const click=async selector=>{const e=page.locator(selector),b=await e.boundingBox();await page.mouse.move(b.x+b.width/2,b.y+b.height/2,{steps:24});await page.waitForTimeout(180);await e.click();events.push({seconds:(Date.now()-started)/1000,selector});};
  await until(5);await click('#log-search');await page.locator('#log-search').pressSequentially('status=503',{delay:75});
  await until(10);await click('#demo-investigate');
  await until(21);await click('.citation:first-child');
  await until(28);await click('#inspector-close');
  await until(29);await click('#demo-evidence');
  await until(41);await click('#demo-reset');await until(44);
  if(requests.length||errors.length)throw Error('Unexpected external request or page error');
  const video=page.video();await context.close();await video.saveAs(path.join(output,'screen.webm'));
  fs.writeFileSync(path.join(output,'recording.json'),JSON.stringify({events,requests,errors,mode:'actual offline UI interactions; stored RCA records',subtitle_overlay:false,audio:false,cursor:'visualizes real recorded mouse coordinates',paidCalls:0},null,2));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
