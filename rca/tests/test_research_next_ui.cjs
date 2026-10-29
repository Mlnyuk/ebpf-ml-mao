// DOM interaction tests only. Synthetic test ratings are never written as study scores.
const fs=require('fs'),path=require('path'),assert=require('assert');
const {JSDOM,VirtualConsole}=require(process.argv[2]);
const folder=process.argv[3];
function load(name){
  const errors=[],alerts=[],exports=[];const vc=new VirtualConsole();vc.on('jsdomError',e=>errors.push(e.message));
  const dom=new JSDOM(fs.readFileSync(path.join(folder,name),'utf8'),{url:'http://localhost:8765/'+name,runScripts:'dangerously',virtualConsole:vc,beforeParse(w){
    w.fetch=async()=>({ok:true,json:async()=>({live_enabled:false,csrf:'test-only'})});
    w.alert=x=>alerts.push(x);w.HTMLElement.prototype.scrollIntoView=function(){};w.CSS={escape:x=>x};
    w.URL.createObjectURL=blob=>{exports.push(blob);return 'blob:test-only';};w.URL.revokeObjectURL=()=>{};
    w.HTMLAnchorElement.prototype.click=function(){};
  }});return {dom,errors,alerts,exports};
}
async function main(){
 const owner=load('index.html');await new Promise(r=>setTimeout(r,20));let d=owner.dom.window.document;
 assert.equal(owner.errors.length,0,owner.errors.join('\n'));assert(d.querySelector('#paneLeft h2'));assert(d.querySelector('#paneRight h2'));assert(d.getElementById('live').disabled);
 const incident=d.getElementById('incident').textContent;d.getElementById('case').selectedIndex=1;d.getElementById('case').dispatchEvent(new owner.dom.window.Event('change'));
 assert.notEqual(d.getElementById('incident').textContent,incident);const evidence=d.querySelector('#paneLeft .claim button');if(evidence)evidence.click();assert.equal(owner.alerts.length,0);
 const review=load('review.html');d=review.dom.window.document;assert.equal(review.errors.length,0,review.errors.join('\n'));
 const dataset=JSON.parse(d.getElementById('dataset').textContent);assert(!JSON.stringify(dataset).includes('"arm":'));
 const packet=dataset.packets.find(p=>p.accepted_output&&p.answer?.claims?.length);assert(packet);
 d.getElementById('reviewCase').value=packet.review_id;d.getElementById('reviewCase').dispatchEvent(new review.dom.window.Event('change'));
 d.getElementById('reviewer').value='TEST_NOT_A_REAL_REVIEWER';d.getElementById('independent').checked=true;
 for(const key of ['destination','affected_target','cause_type'])d.getElementById('score-'+key).value='2';
 for(const key of ['time_confusion','container_confusion'])d.getElementById('score-'+key).value='false';
 d.getElementById('score-abstention').value='not_applicable';
 packet.answer.claims.forEach((_,i)=>{d.getElementById('claim-'+i).value='unassessable';d.getElementById('claim-reason-'+i).value='DOM test only; not a real rating.';});
 d.getElementById('rationale').value='DOM test only; not a real independent review.';d.getElementById('save').click();
 const key='rca-review-'+dataset.dataset_hash;assert.equal(JSON.parse(review.dom.window.localStorage.getItem(key)).length,1);
 d.getElementById('save').click();assert.equal(JSON.parse(review.dom.window.localStorage.getItem(key)).length,1);assert(review.alerts.at(-1).includes('덮어쓰지'));
 d.getElementById('export').click();assert.equal(review.exports.length,1);
 owner.dom.window.close();review.dom.window.close();
 console.log(JSON.stringify({tests:['incident-switch','side-by-side','claim-evidence-link','default-live-disabled','arm-masked-packet','rating-save','no-rating-overwrite','export'],passed:8,real_human_ratings_created:0,scope:'jsdom interaction tests; not full browser rendering tests'}));
}
main().catch(e=>{console.error(e);process.exit(1)});
