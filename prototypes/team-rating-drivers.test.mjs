import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {JSDOM} from 'jsdom';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const html=readFileSync(path.join(root,'public/team-seasons.html'),'utf8');
const template=readFileSync(path.join(root,'prototypes/team-seasons.html'),'utf8');
function page(){return new JSDOM(html,{runScripts:'dangerously',url:'https://example.test/teams/SEA'});}
function sort(w,value){const control=w.document.querySelector('#driver-sort');control.value=value;control.dispatchEvent(new w.Event('change'));}
test('published presentation matches template and its recorded checksum',()=>{
 let expected=template;
 for(const [name,marker] of [['DATA','/*SNAPSHOTS*/{}'],['MODEL','/*MODEL*/null'],['POWER','/*POWER*/{}'],['EVIDENCE','/*EVIDENCE*/null'],['SCHEDULE_AUDIT','/*SCHEDULE_AUDIT*/null'],['WEEKLY','/*WEEKLY*/null']]){
  const value=html.match(new RegExp('^const '+name+'=(.*);$','m'))[1];
  expected=expected.replace(marker,()=>value);
 }
 assert.equal(html,expected);
 const provenance=JSON.parse(readFileSync(path.join(root,'public/team-data/publication.json')));
 assert.equal(createHash('sha256').update(html).digest('hex'),provenance.htmlSha256);
});
test('both sorts preserve each component value and rating for all teams',()=>{
 const dom=page(),w=dom.window;
 try{for(const team of w.eval('DATA[year].teams')){
  w.location.hash='team/'+team.id;w.eval('render()');
  const rating=w.eval('powerTeam('+JSON.stringify(team.id)+')');
  for(const mode of ['contribution','influence']){
   sort(w,mode);const rows=[...w.document.querySelectorAll('#team-report .row')];assert.equal(rows.length,10);
   const scores=rows.map(row=>{const key=row.dataset.component;assert.equal(row.querySelector('.number').textContent,w.eval('signed('+rating.contributions[key]+')'));return mode==='contribution'?Math.abs(rating.contributions[key]):w.eval('power().componentWeights['+JSON.stringify(key)+'].weightPercent');});
   assert.ok(scores.every((v,i)=>!i||v<=scores[i-1]));
   assert.equal(w.document.querySelector('#team-report .total .number').textContent,w.eval('signed('+rating.rating+')'));
  }
 }}finally{w.close();}
});
test('season and route changes retain notices, controls and sort state',()=>{
 const dom=page(),w=dom.window;
 try{
  sort(w,'influence');
  w.location.hash='power';w.eval('render()');assert.equal(w.document.querySelectorAll('#season').length,1);
  w.location.hash='team/GB';w.eval('render()');assert.equal(w.document.querySelector('#driver-sort').value,'influence');
  assert.equal(w.document.querySelectorAll('#freshness').length,1);assert.ok(w.document.querySelector('#team-source-slot #freshness'));
  w.eval("year='2025';render()");assert.equal(w.document.querySelector('#driver-sort'),null);assert.match(w.document.body.textContent,/No frozen-model rating/);
  w.eval("year='2026';render()");assert.equal(w.document.querySelectorAll('#driver-sort').length,1);assert.equal(w.document.querySelectorAll('#season').length,1);
  w.eval("WEEKLY.status={status:'failed',error:'fixture failure'};render()");assert.match(w.document.querySelector('.source summary').textContent,/Latest refresh failed/);
  w.eval("delete power().componentWeights.success_rate;render()");sort(w,'influence');const last=[...w.document.querySelectorAll('#team-report .row')].at(-1);assert.equal(last.dataset.component,'success_rate');assert.match(last.textContent,/Unavailable/);
 }finally{w.close();}
});
