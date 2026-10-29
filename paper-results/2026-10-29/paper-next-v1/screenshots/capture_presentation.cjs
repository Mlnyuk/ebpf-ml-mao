// Screenshot existing replay UI; preserve frozen HTML, answers and evidence.
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const {pathToFileURL} = require('url');
const {chromium} = require(process.argv[2]);
const root = path.resolve(__dirname, '..');
const source = path.join(root,'artifacts/paper-next-v1-20261029/viewer/index.html');
const out = path.resolve(process.argv[3]);
const hash = value => crypto.createHash('sha256').update(value).digest('hex');
const original = fs.readFileSync(source);
const eid = 'ev-38df04e8afda1aa76af2';
(async()=>{
 const browser = await chromium.launch({headless:true,args:['--no-sandbox']});
 const page = await browser.newPage({viewport:{width:1600,height:1150},deviceScaleFactor:2});
 const requests=[];const errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 await page.route(/^https?:/,route=>{requests.push(route.request().url());return route.abort();});
 await page.goto(pathToFileURL(source).href);
 const font=fs.readFileSync('/tmp/rca-screen-tools/NotoSansKR.ttf').toString('base64');
 await page.addStyleTag({content:`@font-face{font-family:CaptureKorean;src:url(data:font/ttf;base64,${font})}body,select,button,input,pre{font-family:CaptureKorean,sans-serif} html{scroll-behavior:auto!important}`});
 await page.evaluate(()=>document.fonts.ready);
 await page.selectOption('#case','186d14f5c49446d4-wide');
 await page.selectOption('#left','604fd0107e743ecfc792');
 await page.selectOption('#right','61001361d065868158f7');
 await page.evaluate(()=>{document.getElementById('mode').textContent='저장 기록 재생 · 새 API 호출 없음';});
 if(!await page.locator('#live').isDisabled())throw Error('live must be disabled');
 // Reference capture: original comparison layout, only font and replay badge changed.
 await page.screenshot({path:path.join(out,'01-comparison-original.png'),fullPage:true});
 // Presentation crop/reflow: retain actual claim/evidence DOM text verbatim.
 await page.addStyleTag({content:`
 header{padding:20px 32px} header h1{font-size:25px}header p{font-size:16px;margin-top:7px}
 main{padding:18px 28px;max-width:none}.warn{padding:12px 16px}.warn p{display:none}.badge{font-size:19px}
 #owner>.card,#owner>.live{display:none}.toolbar{margin:8px 0}.toolbar label:not(:first-child){display:none}
 .toolbar label{font-size:15px}.toolbar select{font-size:15px;max-width:1250px}
 .grid{display:block;margin-top:10px!important}#paneLeft{display:none}
 #paneRight{display:grid;grid-template-columns:1fr 1fr;column-gap:24px;row-gap:0;padding:20px 24px}
 #paneRight>h2,#paneRight>p{grid-column:1/-1;margin:0 0 10px}#paneRight>h2{font-size:24px}#paneRight>p{font-size:16px}
 #paneRight>.claim{grid-column:1;margin:6px 0;padding:13px;font-size:19px;line-height:1.6}
 #paneRight>.claim p{font-size:13px;margin:4px 0;color:#526575}#paneRight>.claim button{font-size:14px;padding:6px 8px}
 #paneRight>.claim:nth-of-type(n+5){display:none}
 #paneRight>details{display:none}
 #paneRight>details[data-evidence="${eid}"]{display:block;grid-column:2;grid-row:3/span 4;margin:6px 0;background:#f2f6f8;padding:14px;border-radius:8px;min-width:0}
 #paneRight>details[data-evidence="${eid}"] summary{font-size:16px;line-height:1.6;overflow-wrap:anywhere}
 #paneRight>details[data-evidence="${eid}"] pre{font-size:16px;line-height:1.65;margin:10px 0 0;padding:4px;max-height:none;height:620px;overflow:auto}
 `});
 const proof = page.locator(`#paneRight details[data-evidence="${eid}"]`);
 await proof.evaluate(e=>e.open=true);
 // Scroll the real JSON pane to its network section; retain complete JSON in DOM.
 const visible = await proof.locator('pre').evaluate(pre=>{
   const lines=pre.textContent.split('\n');const n=lines.findIndex(x=>x.includes('"network":'));
   pre.scrollTop=Math.max(0,n*parseFloat(getComputedStyle(pre).lineHeight));
   return {networkLine:n,scrollTop:pre.scrollTop,fullEvidence:JSON.parse(pre.textContent)};
 });
 const claims=await page.locator('#paneRight>.claim').allTextContents();
 await page.evaluate(()=>window.scrollTo(0,0));
 const box=await page.locator('main').boundingBox();
 await page.screenshot({path:path.join(out,'02-analysis-evidence-ppt.png'),clip:{x:0,y:0,width:1600,height:Math.ceil(box.y+box.height)}});
 const metadata={created_at:new Date().toISOString(),source:'artifacts/paper-next-v1-20261029/viewer/index.html',source_sha256:hash(original),case_id:'186d14f5c49446d4-wide',batch_run:'604fd0107e743ecfc792',selective_run:'61001361d065868158f7',evidence_id:eid,browser:browser.version(),device_scale_factor:2,external_requests:requests,page_errors:errors,live_disabled:true,
   capture_notes:['01: existing comparison layout, Korean font and replay badge only.','02: presentation CSS reflows actual selected-run claims 1–4 beside its actual expanded eBPF evidence; other UI sections hidden, evidence pane scrolled to network.','Answer/evidence text and frozen source unchanged. No model calls.'],evidence_sha256:hash(JSON.stringify(visible.fullEvidence)),claims_sha256:hash(JSON.stringify(claims)),scroll:visible.scrollTop};
 if(hash(fs.readFileSync(source))!==hash(original))throw Error('frozen source changed');
 if(requests.length||errors.length)throw Error('unexpected network/page error');
 fs.writeFileSync(path.join(out,'capture-metadata.json'),JSON.stringify(metadata,null,2));
 await browser.close();console.log(JSON.stringify(metadata));
})().catch(e=>{console.error(e);process.exit(1);});
