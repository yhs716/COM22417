// 화면 버튼과 API 요청입니다. 모델 생성은 sql/classifier.sql의 CREATE_MODEL2를 수정하세요.
"use strict";
// 웹은 결과를 표시합니다. 전처리·모델 수정은 sql/의 독립 파일에서 합니다.
const $ = id => document.getElementById(id);
const on = (id, event, fn) => $(id)?.addEventListener(event, fn);
// 두 작업 중 현재 열어 둔 실행 대상을 읽습니다. 전환만으로 실행하지 않습니다.
const selectedMode = id => $(id)?.querySelector('.mode-option[aria-pressed="true"]')?.value || 'RAW';
function setWorkMode(id,mode){
  for(const button of $(id)?.querySelectorAll('.mode-option')||[]){
    const active=button.value===mode;button.setAttribute('aria-pressed',String(active));
    button.querySelector('.mode-current').textContent=active?'현재 작업':'작업 열기';
  }
}
document.addEventListener('click',event=>{
  const button=event.target.closest('.mode-option');if(!button||button.matches(':disabled'))return;
  const group=button.closest('.mode-choice');if(selectedMode(group.id)===button.value)return;
  setWorkMode(group.id,button.value);group.dispatchEvent(new Event('change',{bubbles:true}));
});
let page = document.body.dataset.page;
const basicWorkspace=document.body.dataset.basic==='true';
const mainWorkspace=page==='main';
let loginView=mainWorkspace&&new URLSearchParams(location.search).get('login')==='1',loginAt=null;
const basicScreens=['home','data','models','predictions'];
const initialBasicScreen=page;
if(basicWorkspace&&basicScreens.includes(location.hash.slice(1)))page=location.hash.slice(1);
const fields = ['case_id','return_pct','range_pct','volume_change_pct','close_price','stock','signal','week_ending','split','use_yn'];
const labels = ['사례번호','이번 주 등락률(%)','고저폭(%)','거래량 증감률(%)','종가(USD)','종목','다음 주 신호','기준 주 마감일','구분','사용 여부'];
const experimentLabels = {baseline:'기본 입력',reordered:'순서 변경',renamed:'이름 변경',numeric_text:'숫자 문자열',wrong_type:'변환 불가 문자열',with_target:'타겟 포함',extra:'추가 컬럼',missing:'컬럼 누락'};
let labHistory=[],labSeen=new Set(),previousPrediction=null;
let authenticationPending=true;
let csrf='', person=null, state={}, models=[], rows=[], selectedFile=null, history=[], baseline=null, initialized=false, storage=null;
let instructorLectureUrl=null;
let predictionChoice=null;
let predictionStorage=null, selectedPrediction=null, predictionImporting=false, predictionRunning=false, modelBusy=false, refreshing=false, predictionContext='';
let preparation={},preparedStorage=null,preparing=false,preparedRequest=0;
let statusPhase='auth', statusCheckedAt=null, identityOrigin=null;
let basicObjects=[];
let dictionaryRequest=0,dictionaryStamp='',dictionaryBusy=false;
let signingOut=false,identityConfigured=true;
let sessionDeadline=0,sessionObservedAt=0,sessionChecking=false,sessionEnding=false,sessionGeneration=0;
function observeSession(data,response){
  if(data?.session?.logged_at)loginAt=data.session.logged_at;
  const expiry=Number(data?.session?.expires_at||response?.headers.get('X-Session-Expires-At'));
  const server=Number(data?.session?.server_time||response?.headers.get('X-Session-Server-Time'));
  if(expiry>0&&server>0&&expiry>=sessionObservedAt){
    sessionObservedAt=expiry;sessionDeadline=Date.now()+Math.max(0,expiry-server)*1000;
  }
}
function endSession(timeout=true){
  if(sessionEnding||signingOut)return;
  sessionEnding=true;window.RequestProgress?.reset();++sessionGeneration;sessionDeadline=0;sessionObservedAt=0;
  dismissMessage();
  if(typeof finishLayerConfirmation==='function')finishLayerConfirmation(false);
  for(const dialog of document.querySelectorAll('dialog[open]'))HelpWindow.close(dialog);
  text('session-expired-title',timeout?'로그인 세션 만료':'로그인 상태 종료');
  text('session-expired-description',timeout?'일정 시간 동안 이용하지 않아 로그인 세션이 만료되었습니다. 로그인 화면으로 이동합니다. 다시 로그인해 주세요.':'로그아웃, 계정 전환 또는 서버 재시작으로 로그인 상태가 종료되었습니다. 로그인 화면으로 이동합니다. 다시 로그인해 주세요.');
  person=null;loginView=false;renderPerson();
  HelpWindow.open($('session-expired-dialog'),{reset:true});
  $('session-expired-accept').focus({preventScroll:true});
}
async function checkSession(){
  if(!person||sessionChecking||sessionEnding||signingOut)return;
  sessionChecking=true;const generation=sessionGeneration;
  try{const result=await api('/api/session');if(generation===sessionGeneration&&!result.identity)endSession(result.session?.expired!==false);}
  catch(error){if(!sessionEnding){text('session-remaining','확인 필요');$('session-remaining').title='서버 연결을 확인한 뒤 시간 연장을 누르세요.';}}
  finally{sessionChecking=false;}
}
function renderSessionTime(){
  if(!$('session-tools'))return;
  $('session-tools').hidden=!person;
  if(!person||sessionEnding)return;
  if(!sessionDeadline){text('session-remaining','확인 중');return;}
  const seconds=Math.max(0,Math.ceil((sessionDeadline-Date.now())/1000));
  text('session-remaining',String(Math.floor(seconds/60)).padStart(2,'0')+':'+String(seconds%60).padStart(2,'0'));
  $('session-tools').dataset.urgent=String(seconds<=60);
  if(seconds===0&&!sessionChecking&&Date.now()-sessionLastCheck>10000){sessionLastCheck=Date.now();checkSession();}
}
let sessionLastCheck=0;
setInterval(renderSessionTime,1000);
window.addEventListener('focus',()=>checkSession());
document.addEventListener('visibilitychange',()=>{if(!document.hidden)checkSession();});
on('extend-session','click',async event=>{
  const button=event.currentTarget;if(sessionEnding)return;
  button.disabled=true;
  try{await api('/api/session/extend',{});renderSessionTime();notice('로그인 시간이 30분 연장되었습니다.');}
  catch(error){if(!sessionEnding)notice(error.message,true);}
  finally{button.disabled=false;}
});
on('session-expired-accept','click',()=>HelpWindow.close($('session-expired-dialog')));
on('session-expired-dialog','close',()=>{if(sessionEnding)location.replace('/');});

let messageRevision=0,messageDetailsRevision=0,messageOrigin=null,messageAnchor=null;
const predictionColumns=fields.slice(0,8).map((key,i)=>[key,i===6?'비교용 실제 값':labels[i]]);
const esc = value => String(value??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'",'&#39;');
function objectDisplay(value){
  if(typeof value!=='string'||!person?.db_user)return value;
  return value.replace(/(?<![A-Z0-9_$#])(?:[A-Z][A-Z0-9_$#]*\.)?OML_(?:BASIC|MISSION|CREATIVE)_[A-Z0-9_]+/g,name=>person.db_user+'.'+name.split('.').pop());
}
function renderObjectOwners(){
  for(const input of document.querySelectorAll('.object-name-fields input')){
    input.dataset.logicalName ||= input.value.split('.').pop();input.value=objectDisplay(input.dataset.logicalName);
  }
  for(const node of document.querySelectorAll('.object-line code,.model-target code,.lab-source code,.mode-option code,.assignment-call-contract code,.object-naming-guide code,.execution-condition code,#assignment-predict-call')){
    node.textContent=objectDisplay(node.textContent);
  }
  text('object-owner-note',person?'DB 객체 소유 계정: '+person.db_user+' · 학번과 구분하여 발급 DB 계정으로만 실행하세요.':'로그인 후 발급 DB 계정을 표시합니다.');
}
const text = (id,value) => { if($(id)) $(id).textContent=objectDisplay(value)??'—'; };
const number = value => value==null?'—':Number(value).toLocaleString('ko-KR');
const date = value => value ? new Intl.DateTimeFormat('ko-KR',{dateStyle:'short',timeStyle:'short',timeZone:'Asia/Seoul'}).format(new Date(value)) : '—';
// 버튼의 잠금 조건과 바로 보이는 사유를 같은 값으로 갱신합니다.
function controlState(id,reason='',available='',description=''){
  const button=$(id);if(!button)return;
  button.disabled=Boolean(reason);button.title=reason||available;
  if(description)button.setAttribute('aria-describedby',description);
  text(id+'-status',reason?'사용 불가 · '+reason:available||'실행 가능');
}
function basicUnavailable(){
  if(!person)return '로그인 후 상태를 확인하세요.';
  if(activeMutations)return 'DB 변경 작업 중입니다.';
  if(statusPhase==='loading'||refreshing)return 'DB 상태 확인 중입니다. 완료 후 사용할 수 있습니다.';
  if(statusPhase==='error')return 'DB 조회 실패 · 새로고침으로 다시 확인하세요.';
  if(statusPhase!=='ready')return 'DB 상태 확인 전 · 새로고침으로 확인하세요.';
  if(!initialized)return '테이블·프로시저 준비 필요 · 현황에서 준비하세요.';
  return '';
}
function renderBasicControls(){
  if(!basicWorkspace)return;
  const pending=statusPhase==='loading'||refreshing;
  const locked=!person?'로그인이 필요합니다.':activeMutations?'DB 변경 작업 중입니다. 완료 후 사용할 수 있습니다.':pending?'DB 상태 확인 중입니다. 완료 후 사용할 수 있습니다.':'';
  const known=statusPhase==='ready';
  const missing=basicObjects.filter(o=>o.status!=='VALID').map(o=>o.object_name+' ('+o.status+')');
  for(const name of ['OML_BASIC_DATA','OML_BASIC_PREPARED','OML_BASIC_PREDICT','OML_BASIC_RUN'])if(!basicObjects.some(o=>o.object_name===name))missing.push(name+' (미생성)');
  text('basic-objects-state',!person?'로그인 필요':pending?'확인 중':!known?'확인 미완료':initialized?'준비 완료':'준비 필요');
  $('basic-objects-state')?.classList.toggle('good',known&&initialized&&!pending);
  text('basic-objects-summary',locked||(!known?'DB 준비 상태를 확인하지 못했습니다. 새로고침으로 재확인하거나 준비 버튼으로 SQL 정의를 적용하세요.':initialized?'준비 완료 · 바로 실습을 진행할 수 있습니다. 수정한 SQL은 프로시저 다시 등록으로 적용하세요.':'DB 접속 성공 · '+missing.join(', ')+' · 준비 버튼으로 배포 SQL을 적용하세요. 기존 컬럼 변경은 SQL Developer에서 ALTER가 필요합니다.'));
  const tablesReady=['OML_BASIC_DATA','OML_BASIC_PREPARED','OML_BASIC_PREDICT'].every(name=>basicObjects.some(o=>o.object_name===name&&o.object_type==='TABLE'));
  controlState('initialize-basic',locked||!known?'상태 확인 후 실행하세요.':tablesReady?'테이블 3개가 있습니다.':'','없는 테이블만 생성합니다.','basic-objects-summary');
  const procedureExists=basicObjects.some(o=>o.object_name==='OML_BASIC_RUN'&&o.object_type==='PROCEDURE');
  controlState('register-basic',locked||(!known?'상태 확인 후 실행하세요.':!tablesReady?'테이블 3개를 먼저 생성하세요.':procedureExists?'프로시저가 있습니다. 다시 등록을 사용하세요.':''),'프로시저를 처음 등록합니다.','basic-objects-summary');
  controlState('reregister-basic',locked||(!known?'상태 확인 후 실행하세요.':!tablesReady?'테이블 3개를 먼저 생성하세요.':!procedureExists?'프로시저 최초 등록을 사용하세요.':''),'수정한 SQL로 프로시저를 다시 등록합니다.','basic-objects-summary');
  controlState('drop-basic-objects',locked||(!known?'상태 확인 후 실행하세요.':!basicObjects.length&&!models.some(m=>m.exists)?'삭제할 기본과제 객체가 없습니다.':''),'기본과제의 모든 실습 객체를 삭제합니다.');
  renderPreparation();renderStorage();renderModelLifecycle();renderPredictionStorage();
}
// 일시적인 메시지는 문서 흐름에 삽입하지 않습니다. 고정 알림 → 상세 팝업으로 표시합니다.
function notice(message='',error=false){if(message)presentMessage(message,error?'error':'info');}
function presentMessage(message,state='info',markup=null){
  ++messageRevision;
  if(!document.activeElement?.closest?.('#operation-status,#message-dialog'))messageAnchor=document.activeElement;
  const content=$('notice');content.hidden=false;content.className='message-content';content.dataset.state=state;
  text('message-title',state==='error'?'실행 오류':state==='pending'?'작업 진행':'작업 안내');
  if(markup!==null)content.innerHTML=markup;else content.textContent=message;
  content.setAttribute('role',state==='error'?'alert':'status');
  const title=String(message).split('\n')[0];
  const normalized=value=>String(value??'').replace(/\s+/g,' ').trim();
  // 한 줄 안내와 같은 본문을 별도 창에서 반복하지 않습니다.
  const additional=normalized(content.textContent)!==normalized(title);
  actionStatus(title,state,additional?content:null);
}
async function api(path,body){
  const options={credentials:'same-origin',headers:{}};
  if(body!==undefined){options.method='POST';options.headers['X-CSRF-Token']=csrf;if(body instanceof FormData)options.body=body;else{options.headers['Content-Type']='application/json';options.body=JSON.stringify(body);}}
  if((body!==undefined&&/^\/api\/(?:data|models|predictions|basic|assignments)/.test(path)||path==='/api/models')&&!/\/(?:preview|data|prepared-data|prediction-data)(?:\?|$)/.test(path)&&typeof clearPracticeEvidence==='function')clearPracticeEvidence('작업 후 최종 현황을 다시 확인하세요.');
  const generation=sessionGeneration,queryContext=typeof captureCodingQuery==='function'?captureCodingQuery(path,body):null;
  const progress=window.RequestProgress?.request(path,body);
  try{
  const response=await fetch(path,options);let data;
  try{data=await response.json();}catch{throw new Error('서버 응답을 확인할 수 없습니다.');}
  if(!response.ok){if(response.status===401&&generation===sessionGeneration&&!signingOut){endSession(data.code==='SESSION_TIMEOUT');}const error=new Error(typeof data.error==='string'?data.error:'입력값 또는 실행 상태를 확인하세요.');error.diagnostic=data.diagnostic;error.status=response.status;throw error;}
  if(generation!==sessionGeneration)return data;
  if(typeof rememberCodingQuery==='function')rememberCodingQuery(queryContext,data);
  if(path==='/api/identity'||path==='/api/logout'){++sessionGeneration;sessionDeadline=0;sessionObservedAt=0;}
  observeSession(data,response);
  if(data.csrf)csrf=data.csrf;
  if(Object.hasOwn(data,'instructor_lecture_url'))instructorLectureUrl=data.instructor_lecture_url;
  return data;
  }finally{window.RequestProgress?.end(progress);}
}

function loginPayload(studentId,name,password){
  return {student_id:studentId.trim(),name:name.trim(),db_password:password};
}
async function confirmIdentity(studentId,name,password){
  // 오래 열린 화면이나 서버 재시작 뒤에도 현재 세션의 확인 토큰을 먼저 받습니다.
  const session=await api('/api/session');csrf=session.csrf;
  return api('/api/identity',loginPayload(studentId,name,password));
}
const rememberedKey='com22417-login-v1';
function rememberLoginPassword(){return $('login-password')?.dataset.rememberPassword!=='false';}
function rememberedIdentity(){
  try{
    const saved=JSON.parse(localStorage.getItem(rememberedKey)||'null');
    if(saved&&!rememberLoginPassword()&&Object.hasOwn(saved,'db_password')){
      delete saved.db_password;localStorage.setItem(rememberedKey,JSON.stringify(saved));
    }
    return saved;
  }catch{return null;}
}
function saveRememberedIdentity(studentId,name,password,remember){
  try{
    if(remember){
      const saved=loginPayload(studentId,name,password);
      if(!rememberLoginPassword())delete saved.db_password;
      localStorage.setItem(rememberedKey,JSON.stringify(saved));
    }else localStorage.removeItem(rememberedKey);
  }
  catch{notice('로그인했습니다. 브라우저에서 입력값 저장을 허용하지 않아 다음 접속에는 다시 입력해야 합니다.');}
}
let lookupVersion=0,signingIn=false;
async function lookupIdentity(){
  const version=++lookupVersion,id=$('login-id').value.trim(),name=$('login-name').value.trim();
  $('login-db-user').value='';if(!id||!name)return;
  try{const session=await api('/api/session');csrf=session.csrf;const result=await api('/api/identity/lookup',{student_id:id,name});if(version!==lookupVersion)return;$('login-db-user').value=result.identity.db_user;$('identity-error').hidden=true;}
  catch(error){if(version!==lookupVersion)return;text('identity-error',error.message);$('identity-error').hidden=false;}
}
let activeTasks=0,activeMutations=0;
let latestFeedback=null;
function actionFeedback(button){
  if(!button||button.closest?.('dialog')||button.closest?.('.page-heading')||button.dataset?.source)return null;
  return $('notice');
}
let messageDismissTimer=0;
function scheduleMessageDismiss(){
  clearTimeout(messageDismissTimer);
  const bar=$('operation-status');
  if(!bar||bar.hidden||!['success','info'].includes(bar.dataset.state))return;
  const revision=messageRevision;
  messageDismissTimer=setTimeout(()=>{
    if(revision!==messageRevision||bar.hidden||bar.matches(':hover')||bar.contains(document.activeElement))return;
    dismissMessage();
  },4500);
}
function actionStatus(title,state,feedback){
  const bar=$('operation-status');if(!bar)return;
  latestFeedback=feedback;
  // 다른 팝업 안에서 발생한 알림도 그 팝업의 조작 가능한 레이어에 표시합니다.
  const host=document.activeElement?.closest?.('dialog[open]')||document.body;
  if(host?.id!=='message-dialog'&&bar.parentElement!==host){
    if(bar.matches?.(':popover-open'))bar.hidePopover();
    host?.append?.(bar);
  }
  bar.hidden=false;bar.dataset.state=state;text('operation-status-text',title);
  if($('operation-status-detail'))$('operation-status-detail').hidden=!feedback;
  if(bar.showPopover&&!bar.matches(':popover-open'))bar.showPopover();
  scheduleMessageDismiss();
}
function dismissMessage(){
  clearTimeout(messageDismissTimer);
  const bar=$('operation-status');if(bar.matches?.(':popover-open'))bar.hidePopover();bar.hidden=true;
}
function showMessageDetails(){
  if(!latestFeedback)return;
  messageOrigin=document.activeElement?.closest?.('#operation-status')?(messageAnchor||$('basic-'+page)):document.activeElement;dismissMessage();
  messageDetailsRevision=messageRevision;
  const dialog=$('message-dialog');HelpWindow.open(dialog,{reset:true});
}
async function task(button,fn,options={}){
  activeTasks++;if(options.mutation)activeMutations++;
  const title=button?.textContent?.trim(),feedback=options.feedback===false?null:actionFeedback(button);let failed=false;
  if(button){button.disabled=true;button.setAttribute('aria-busy','true');}
  const progress=window.RequestProgress?.begin((title||'화면 정보 확인')+' 처리 중입니다.');
  renderBasicControls();
  if(feedback){if(window.RequestProgress)dismissMessage();else presentMessage(title+' 처리 중입니다. 잠시 기다려 주세요.','pending');}
  const revision=messageRevision;
  try{return await fn();}catch(error){failed=true;operationNotice(error);}
  finally{
    window.RequestProgress?.end(progress);
    activeTasks--;if(options.mutation)activeMutations--;
    if(feedback&&!failed&&messageRevision===revision)presentMessage(title+' 완료','success');
    if(button){button.disabled=false;button.removeAttribute('aria-busy');}
    if(page==='models')renderModels();if(page==='data')renderStorage();if(page==='predictions')renderPredictionStorage();
    renderBasicControls();
    flushBasicNavigation();
  }
}
function diagnosticMarkup(d,message){
  return '<strong>'+esc((d.stage?d.stage+' · ':'')+(d.code||'실행 안내'))+'</strong><p>'+esc(d.title||message)+'</p>'+
    (d.procedure?'<p>호출: <code>'+esc(d.procedure)+'</code></p>':'')+
    (d.steps?.length?'<ol>'+d.steps.map(step=>'<li>'+esc(step)+'</li>').join('')+'</ol>':'')+
    (d.locations?.length?'<ul>'+d.locations.map(item=>'<li>'+esc(item.object_type)+' · DB '+esc(item.object_line)+'행 · '+esc(item.code)+(item.source?' · '+esc(item.source)+':'+esc(item.source_line):'')+'</li>').join('')+'</ul>':'')+
    (d.commands?.length?d.commands.map(command=>'<div class="feedback-command"><code>'+esc(command)+'</code><button type="button" class="secondary" data-copy-command="'+esc(command)+'">명령 복사</button></div>').join(''):'')+
    (d.examples?.length?'<h3>생성 SQL 예제</h3><p>아직 없는 객체만 표시합니다. 테이블부터 실행한 뒤 프로시저를 실행하세요.</p>'+d.examples.map(example=>'<details class="diagnostic-example"><summary>'+esc(example.title)+'</summary><p><code>'+esc(example.path)+'</code></p><button type="button" class="secondary" data-copy-command="'+esc(example.sql)+'">SQL 복사</button><pre data-diagnostic-sql>'+esc(example.sql)+'</pre></details>').join(''):'')+
    (d.message&&d.message!==d.title?'<p>'+esc(d.message)+'</p>':'')+'<div class="actions">'+
    (d.guide==='/download/assignment-template-guide.html'?'<a class="button secondary" href="'+d.guide+'" target="_blank" rel="noopener">호출 규약·구현 순서</a>':'')+
    (d.sources?.length?d.sources.map(key=>'<button type="button" class="secondary" data-source="'+esc(key)+'">'+(key.endsWith('-tables')?'테이블 SQL 전체 보기':key.endsWith('-procedure')?'프로시저 SQL 전체 보기':key==='assignment-backend'?'웹 연결 설정 보기':key==='assignment-guide'?'구현 안내 소스 보기':'관련 소스 보기')+'</button>').join(''):'')+'</div>';
}
function operationNotice(error){
  const diagnostic=error.diagnostic,state=diagnostic?.category==='objects'||['ASSIGNMENT-NOT-READY','OBJECT-NOT-READY'].includes(diagnostic?.code)?'warning':'error';
  const extra=diagnostic&&(diagnostic.steps?.length||diagnostic.locations?.length||diagnostic.commands?.length||diagnostic.examples?.length||diagnostic.sources?.length||diagnostic.procedure||diagnostic.message&&diagnostic.message!==diagnostic.title);
  presentMessage(diagnostic?.title||error.message,state,extra?diagnosticMarkup(diagnostic,error.message):null);
  $('notice').querySelectorAll('[data-diagnostic-sql]').forEach(pre=>CodeHighlight.paint(pre,pre.textContent,'example.sql'));
}
on('operation-status','pointerenter',()=>clearTimeout(messageDismissTimer));
on('operation-status','focusin',()=>clearTimeout(messageDismissTimer));
on('operation-status','pointerleave',scheduleMessageDismiss);
on('operation-status','focusout',scheduleMessageDismiss);
on('operation-status-close','click',dismissMessage);
on('operation-status-detail','click',showMessageDetails);
on('close-message','click',()=>HelpWindow.close($('message-dialog')));
on('message-dialog','close',()=>{if($('message-dialog').open||messageDetailsRevision!==messageRevision)return;dismissMessage();messageOrigin?.focus?.({preventScroll:true});});
document.addEventListener('close',event=>{
  const bar=$('operation-status');
  if(event.target!==$('message-dialog')&&bar.parentElement===event.target){
    const visible=!bar.hidden;document.body.append(bar);
    if(visible)actionStatus($('operation-status-text').textContent,bar.dataset.state,latestFeedback);
  }
},true);
document.addEventListener('click',async event=>{
  const button=event.target.closest('[data-copy-command]');if(!button)return;
  try{await navigator.clipboard.writeText(button.dataset.copyCommand);notice('명령을 복사했습니다.');}
  catch{notice('옆의 명령을 선택해 Ctrl+C로 복사하세요.');}
});
function renderStorage(){
  if(page!=='data')return;
  renderPreparation();
  const reason=basicUnavailable(),busy=importing||preparing||activeMutations?'DB 변경 작업 중입니다.':refreshing?'DB 상태 확인 중입니다.':'';
  text('data-action-status',busy||reason||(storage?.exists?`원본 ${number(state.total_rows)}행 저장됨 · CSV 교체 적재 또는 전처리 저장을 실행할 수 있습니다.`:'원본 테이블 미생성 · 현황에서 테이블 생성과 프로시저 등록을 진행하세요.'));
  const ready=busy||reason;
  controlState('import-submit',ready||(state.total_rows?'원본 데이터가 있습니다. 교체 적재를 사용하세요.':''),'빈 원본에 CSV를 처음 적재합니다.','data-action-status');
  controlState('replace-training',ready||(!state.total_rows?'원본이 비어 있습니다. 최초 적재를 사용하세요.':''),'기존 원본을 선택 CSV로 교체합니다.','data-action-status');
  controlState('clear-training',busy||(!storage?.exists?'원본 테이블 없음':!state.total_rows?'비울 원본 데이터가 없습니다.':''),'원본과 전처리값을 삭제합니다.');
  controlState('recreate-training',busy||(!person?'로그인이 필요합니다.':''),'원본 테이블 재생성 후 CSV 적재','data-action-status');
  controlState('query-data',busy||reason,'원본 조회 가능','data-action-status');
  text('storage-state',statusPhase!=='ready'?(statusPhase==='loading'?'확인 중':'확인 미완료'):storage?.exists?(initialized?'사용 가능':'SQL 준비 필요'):'미생성');
  if(!storage)return;
  text('storage-name',storage.qualified_name);text('storage-object',storage.object_id);text('storage-created',date(storage.created_at));
  text('storage-rows',statusPhase==='ready'&&initialized?number(state.total_rows)+'행':'—');
  $('storage-state').className='pill'+(initialized?' good':'');
  text('storage-views','사용 여부: Y만 사용 · TRAIN: 학습 · TEST: 평가 · N은 저장만 하고 학습·평가에서 제외');
  $('recreate-tools').hidden=false;

}
function renderPreparation(){
  if(!$('preparation-mode'))return;
  const mode=selectedMode('preparation-mode'),p=preparation[mode];
  text('prepared-target',preparedStorage?.name||'OML_BASIC_PREPARED');
  const reason=basicUnavailable()||(preparing?'전처리 저장 중입니다.':importing?'CSV 적재 중입니다.':'');
  for(const id of ['preparation-mode','prepared-source-kind','prepare-data','query-prepared-data'])controlState(id,reason,'실행 가능','prepared-status');
  text('prepared-status',reason||!state.total_rows?reason||'원본 데이터 없음 · 학습 CSV를 먼저 적재하세요.':!p?.ready?`${mode} · ${p?.rows?'저장값 있음 · 원본·프로시저 변경 또는 웹 준비 기록 없음':'전처리 미저장'} · 전처리를 실행·저장하세요.`:`${mode} · 전처리 저장 완료 · ${number(p.rows)}행 · FIT_YN=Y TRAIN ${number(p.fit_rows)}행 · TEST ${number(p.test_rows)}행${!p.fit_rows?' · 학습 제공 행이 없어 학습할 수 없습니다.':''}`);
  controlState('prepare-data',reason||(!state.total_rows?'원본 데이터 없음 · 학습 CSV를 먼저 적재하세요.':''),'전처리 실행 가능','prepared-status');
  controlState('clear-prepared',reason||(!p?.rows?'선택 방식의 저장값이 없습니다.':''),'선택 전처리값 삭제','prepared-status');
}
async function loadPreparedRows(){
  const mode=selectedMode('preparation-mode'),kind=$('prepared-source-kind').value,ticket=++preparedRequest;
  table('prepared-data',[]);
  if(!preparedStorage?.exists)return;
  const result=await api('/api/data/prepared?'+new URLSearchParams({variant:mode,source_kind:kind}));
  if(ticket!==preparedRequest||!person||mode!==selectedMode('preparation-mode')||kind!==$('prepared-source-kind').value)return;
  table('prepared-data',result.rows||[],preparedColumns(result.rows||[]),{database:true,columnRoles:learningColumnRoles()});
}
function preparedColumns(data,layout=[]){
  if(!data.length)return null;
  const titles={case_id:'사례번호',fit_yn:'학습 제공 여부',exclude_reason:'제외 사유',return_pct:'등락률(%)',range_pct:'고저폭(%)',volume_change_pct:'거래량증감(%)',close_price:'종가(USD)',stock:'종목',signal:'정답',prep_mode:'저장 방식',source_kind:'저장 구분',use_yn:'원본 사용 여부',prepared_at:'전처리 저장 시각'};
  const first=['case_id','fit_yn','exclude_reason'],last=['week_ending','source_kind','prep_mode','use_yn','prepared_at'],keys=Object.keys(data[0]);
  return [...first.filter(k=>keys.includes(k)),...keys.filter(k=>!first.includes(k)&&!last.includes(k)),...last.filter(k=>keys.includes(k))].map(k=>[k,layout.find(field=>field.name.toLowerCase()===k.toLowerCase())?.korean_name||titles[k]||labels[fields.indexOf(k)]||k]);
}
async function prepareTraining(button){
  if(preparing||importing||refreshing)return;
  const variant=selectedMode('preparation-mode');
  if(!await askConfirmation(`OML_BASIC_DATA에서 ${variant} 전처리값을 OML_BASIC_PREPARED에 저장할까요?\n선택 방식의 기존 TRAIN·TEST 저장값과 직접 수정한 FIT_YN·EXCLUDE_REASON은 원본 기준으로 교체됩니다. 저장값이 달라지면 해당 모델을 다시 학습해야 합니다.`,{title:'전처리 실행·저장',accept:'전처리 저장',opener:button}))return;
  preparing=true;renderPreparation();
  try{await task(button,async()=>{await api('/api/data/prepare',{variant});resetPredictionResults();await loadStatus();await loadPreparedRows();notice(`${variant} 전처리 저장 완료 · FIT_YN·저장값·모델 최신 상태를 확인하세요.`);},{mutation:true});}
  finally{preparing=false;renderPreparation();}
}
on('prepare-data','click',event=>prepareTraining(event.currentTarget));
on('query-prepared-data','click',event=>task(event.currentTarget,loadPreparedRows,{feedback:false}));
for(const id of ['preparation-mode','prepared-source-kind'])on(id,'change',()=>{++preparedRequest;table('prepared-data',[]);renderPreparation();task(null,loadPreparedRows,{feedback:false});});
let importing=false;
async function importTraining(mode,button){
  if(importing||preparing||refreshing)return;
  const file=$('data-file').files[0]||selectedFile;if(!file){notice('CSV 파일을 먼저 선택하세요.',true);return;}
  const target=storage?.qualified_name||'현재 계정의 OML_BASIC_DATA';
  const message=mode==='recreate'?`${file.name} 전체를 읽어 검사한 뒤 ${target}을 DROP → CREATE합니다.\n기존 원본 행은 삭제되고 OBJECT_ID가 바뀝니다. DROP은 롤백되지 않습니다.\n읽어 둔 CSV 각 행을 INSERT VALUES로 다시 적재·COMMIT합니다. 원본 테이블에서 SELECT하여 복사하지 않습니다.\n준비·예측 테이블의 기존 행은 보존하지만 이전 준비·학습·확정 기록은 해제합니다. 적재 후 전처리 저장 → 재학습 → 확정이 필요합니다. 계속하시겠습니까?`:
    `${target}에 ${file.name}을 적재합니다.\n${storage?.exists?'기존 행은 선택한 CSV로 교체하고 테이블 구조와 OBJECT_ID는 유지합니다.':'테이블을 먼저 생성합니다.'}\n이전 모델은 다시 학습·확정해야 합니다. 계속하시겠습니까?`;
  if(!await askConfirmation(message,{title:mode==='recreate'?'학습 테이블 재생성 확인':'학습데이터 적재 확인',accept:mode==='recreate'?'재생성 및 적재':'적재',danger:mode==='recreate',opener:button}))return;
  importing=true;const buttons=['import-submit','replace-training','recreate-training','choose-sample','preview'];buttons.forEach(id=>$(id).disabled=true);
  try{await task(button,async()=>{const data=upload(file);data.append('mode',mode);let result;
    try{result=await api('/api/data/import',data);}catch(error){
      if(mode==='recreate'){
        rows=[];table('data-table',[]);table('prepared-data',[]);resetPredictionResults();clearModelDictionary();
        try{await loadStatus();}catch{}
      }
      throw error;
    }
    await loadStatus();await loadRows();
    const label={created:'테이블 생성',replaced:'데이터 교체',recreated:'테이블 재생성'}[result.operation]||'적재';
    table('prepared-data',[]);notice(`${label} 완료 · ${result.storage.qualified_name}\n${number(result.loaded_rows)}행 · OBJECT_ID ${result.storage.object_id}\n전처리 실행·저장 후 모델을 다시 학습·확정하세요.`);
  });}finally{importing=false;buttons.forEach(id=>$(id).disabled=false);renderStorage();}
}
// 오류 진단에서 요청한 파일만 표시합니다. 공통 실습가이드 목록은 제공하지 않습니다.
let sourceOrigin=null,sourceRequest=0;
function clearRelatedSource(){
  ++sourceRequest;sourceOrigin=null;
  for(const id of ['source-code','source-path','source-location'])$(id).textContent='';
}
async function openSource(key,opener=document.activeElement){
  if(!person){openIdentity();return;}
  const ticket=++sourceRequest,dialog=$('help-dialog');sourceOrigin=opener;
  text('help-title','관련 소스');text('source-path','파일을 불러오는 중…');text('source-location','');text('source-code','');
  HelpWindow.open(dialog,{reset:true});dialog.scrollTop=0;
  const result=await api('/api/sources/'+encodeURIComponent(key));
  if(ticket!==sourceRequest||!person||(!dialog.open&&!HelpWindow.isMinimized(dialog)))return;
  text('source-path',result.path);text('source-location',result.line+'행 · '+result.symbol);$('copy-source-path').dataset.path=result.path;
  $('source-code').innerHTML=CodeHighlight.html(result.content,result.path).split('\n').map((line,index)=>'<span class="code-line'+(index+1===result.line?' focus-line':'')+'"><span class="line-number" aria-hidden="true">'+(index+1)+'</span>'+line+'</span>').join('');
  requestAnimationFrame(()=>{if(ticket===sourceRequest&&dialog.open)$('source-code').querySelector('.focus-line')?.scrollIntoView({block:'center'});});
}
on('close-help','click',()=>HelpWindow.close($('help-dialog')));
document.addEventListener('click',event=>{
  const source=event.target.closest('[data-source]');
  if(source)task(source,()=>openSource(source.dataset.source,source),{feedback:false});
});
on('copy-source-path','click',event=>task(event.currentTarget,async()=>{await navigator.clipboard.writeText(event.currentTarget.dataset.path);text('source-location','경로를 복사했습니다. VS Code에서 Ctrl+P로 열어 주세요.');}));
function cellValue(key,value){
  // 조회 셀은 값 그대로 표시합니다. NULL은 빈 셀이고 라벨·단위·확률 %를 덧붙이지 않습니다.
  return value==null?'':esc(['model','model_name','object_name','procedure_name'].includes(key)?objectDisplay(value):value);
}
const columnRoleLabels={identifier:'식별자',feature:'설명변수',target:'타깃변수',metadata:'기타'};
function learningColumnRoles(layout=null){
  const roles={case_id:'identifier'};
  if(basicWorkspace){
    for(const key of ['return_pct','range_pct','volume_change_pct','close_price','stock'])roles[key]='feature';
    roles.signal='target';
  }
  for(const field of layout||[]){
    const role=field.role||'';
    roles[field.name.toLowerCase()]=Object.hasOwn(columnRoleLabels,role)?role:role.includes('식별')?'identifier':role.includes('설명변수')?'feature':/타깃|타겟/.test(role)?'target':'metadata';
  }
  return roles;
}
function table(id,data,columns=null,{database=false,columnRoles=null}={}){
  const element=$(id);if(!element)return;
  if(!data?.length){element.classList.add('empty');element.textContent='표시할 데이터가 없습니다.';return;}
  element.classList.remove('empty');columns=columns||Object.keys(data[0]).map(key=>[key,key]);
  const numericKey=key=>['case_id','return_pct','range_pct','volume_change_pct','close_price','probability','column_id','n'].includes(key);
  const heading=(key,title)=>database?'<span class="column-name">'+esc(key.toUpperCase())+'</span>'+(String(title).toUpperCase()!==key.toUpperCase()?'\n<span class="column-description">'+esc(title)+'</span>':''):esc(title);
  const roleFor=key=>Object.hasOwn(columnRoleLabels,columnRoles?.[key.toLowerCase()])?columnRoles[key.toLowerCase()]:'metadata';
  const roleAttribute=key=>columnRoles?' data-column-role="'+roleFor(key)+'"':'';
  const legend=columnRoles?'<ul class="mission-column-legend" aria-label="컬럼 역할">'+Object.entries(columnRoleLabels).map(([role,title])=>'<li data-column-role="'+role+'">'+title+'</li>').join('')+'</ul>':'';
  element.innerHTML=legend+'<table'+(database||columnRoles?' class="'+[database?'database-result':'',columnRoles?'learning-data':''].filter(Boolean).join(' ')+'"':'')+'><thead><tr>'+columns.map(([key,title])=>'<th scope="col"'+(numericKey(key)?' class="numeric"':'')+roleAttribute(key)+'>'+heading(key,title)+(columnRoles?'<span class="mission-column-role">'+columnRoleLabels[roleFor(key)]+'</span>':'')+'</th>').join('')+'</tr></thead><tbody>'+data.map(row=>'<tr>'+columns.map(([key])=>'<td'+(numericKey(key)?' class="numeric"':'')+roleAttribute(key)+'>'+cellValue(key,row[key])+'</td>').join('')+'</tr>').join('')+'</tbody></table>';
}
// 스키마는 한 행이 한 컬럼입니다. 데이터 조회와 같은 역할 색상/이름을 사용합니다.
function schemaTable(id,columns,{korean=false}={}){
  const headings=[['name','컬럼명']];
  if(korean)headings.push(['korean_name','한글 라벨']);
  headings.push(['type','Oracle 타입'],['nullable','필수 여부'],['description','역할·설명'],['rules','기본값·제약']);
  table(id,columns,headings);
  const element=$(id);if(!element||!columns?.length)return;
  const labels={...columnRoleLabels,identifier:'식별키'},legend=document.createElement('ul');
  legend.className='mission-column-legend';legend.setAttribute('aria-label','컬럼 역할 색상');
  for(const [role,label] of Object.entries(labels)){
    const item=document.createElement('li');item.dataset.columnRole=role;item.textContent=label;legend.append(item);
  }
  element.prepend(legend);
  element.querySelectorAll('tbody tr').forEach((row,index)=>{
    const role=Object.hasOwn(labels,columns[index].role)?columns[index].role:'metadata';
    row.dataset.columnRole=role;
    const badge=document.createElement('span');badge.className='mission-column-role';badge.textContent=labels[role];
    row.cells[0].append(document.createElement('br'),badge);
  });
}
// 기존 status 응답으로 화면의 다음 작업만 결정합니다. DB 작업을 실행하지 않습니다.
function overviewState(data,authenticated,phase){
  if(!authenticated)return {key:'auth',title:'로그인하고 실습을 시작하세요',reason:'로그인 후 현재 데이터와 모델 상태를 확인합니다.',label:'로그인',action:'identity'};
  if(phase==='loading')return {key:'loading',title:'실습 상태를 조회하고 있습니다',reason:'Oracle 응답을 확인한 뒤 현재 지표와 다음 작업을 표시합니다.',label:'조회 중',action:'wait'};
  if(phase!=='ready')return {key:'error',title:'현재 상태를 확인하지 못했습니다',reason:'이전 조회값을 현재 상태로 표시하지 않습니다. 연결을 확인하고 다시 조회하세요.',label:'상태 다시 조회',action:'refresh'};
  const s=data.state||{},ms=data.models||[],current=ms.filter(m=>m.is_current===1);
  if(!data.initialized||!(Number(s.total_rows)>0))return {key:'data',title:'학습데이터부터 준비하세요',reason:'CSV를 미리 보고 적재한 다음 학습·평가 분할과 데이터 품질을 확인하세요.',label:'학습데이터 준비',screen:'data'};
  if(data.preparation&&!['RAW','CLEAN'].some(mode=>data.preparation[mode]?.ready))return {key:'prepare',title:'전처리값을 별도 테이블에 저장하세요',reason:'학습데이터에서 RAW 또는 CLEAN 선택 → 전처리 실행·저장 → FIT_YN을 확인하세요.',label:'전처리 실행·저장',screen:'data'};
  if(current.length<2)return {key:'models',title:ms.some(m=>m.model_name)?'저장된 준비값으로 다시 학습하세요':'두 모델을 생성하고 비교하세요',reason:'각 방식의 PREPARED에서 FIT_YN=Y TRAIN만 학습하고 고정 TEST로 평가합니다.',label:'모델 생성·비교',screen:'models'};
  if(s.confirmed_current!==1||!current.some(m=>m.is_confirmed===1))return {key:'confirm',title:'예측에 사용할 모델을 확정하세요',reason:'4단계에서 RAW/CLEAN을 선택해 바로 예측할 수 있습니다. 실행 성공 시 사용 모델로 저장합니다.',label:'4단계 · 모델 선택·예측',screen:'predictions'};
  if(!(Number(data.prediction_storage?.rows)>0))return {key:'prediction-data',title:'새로운 예측 데이터를 준비하세요',reason:'확정한 모델로 분류할 별도의 예측 CSV를 미리 보고 적재하세요.',label:'예측 데이터 준비',screen:'predictions'};
  return {key:'ready',title:'새 데이터의 신호를 예측할 수 있습니다',reason:'모델 확정과 예측 데이터 적재가 완료되었습니다. 입력 구성을 확인하고 실행하세요.',label:'예측 실행 화면',screen:'predictions'};
}
function renderOverview(phase=statusPhase){
  statusPhase=phase;
  const next=overviewState({state,models,initialized,preparation,prediction_storage:predictionStorage},Boolean(person),phase);
  // 한 번 성공했던 숫자도 인증/조회가 불확실하면 지웁니다. 미확인은 0이 아닙니다.
  const known=Boolean(person)&&phase==='ready';
  const current=known?models.filter(m=>m.is_current===1):[];
  const confirmed=known&&state.confirmed_current===1?current.find(m=>m.is_confirmed===1):null;
  text('total-rows',known?number(state.total_rows):'—');
  text('split-counts',known?number(state.train_rows)+' / '+number(state.test_rows):'—');
  text('model-count',known?current.length:'—');text('confirmed',known?(confirmed?(confirmed.variant==='CLEAN'?'정제 적용':'정제 미적용'):'미확정'):'확인 대기');
  text('data-revision','데이터 버전 '+(known?(state.data_rev??'—'):'—'));
  text('flow-train',known?number(state.train_rows):'—');text('flow-test',known?number(state.test_rows):'—');
  text('overview-data-note',known?'전체 데이터 · 미사용 '+number(state.disabled_rows)+'행 포함':'조회 후 확인');
  text('status-freshness',!person?'로그인 필요':phase==='loading'?'현재 상태 조회 중':phase==='ready'?'최근 조회 '+new Intl.DateTimeFormat('ko-KR',{hour:'2-digit',minute:'2-digit',hour12:false}).format(statusCheckedAt||new Date()):'조회 실패 · 재확인 필요');
  text('next-title',next.title);text('next-reason',next.reason);
  for(const link of document.querySelectorAll('[data-next-link],.oml-next>a')){
    link.textContent='학습데이터로 이동 →';
    link.href='/basic#data';link.dataset.basicTab='data';delete link.dataset.overviewAction;link.removeAttribute('aria-disabled');
  }
  const dataReady=known&&initialized&&Number(state.total_rows)>0;
  const stages={
    data:[dataReady?(['RAW','CLEAN'].some(mode=>preparation[mode]?.ready)?'전처리 저장됨':'전처리 필요'):known?'데이터 필요':'확인 대기',dataReady&&['RAW','CLEAN'].some(mode=>preparation[mode]?.ready)?'success':'neutral',known?'원본 '+number(state.total_rows)+'행 · 학습 제공 RAW '+number(preparation.RAW?.fit_rows)+' / CLEAN '+number(preparation.CLEAN?.fit_rows):'현재 데이터의 준비 상태를 확인하세요.'],
    models:[known?(current.length===2?(confirmed?'확정 완료':'모델 선택 필요'):models.length?'재학습 필요':'생성 필요'):'확인 대기',known&&confirmed&&current.length===2?'success':known?'warning':'neutral',known?'최신 '+current.length+'개 / 정제 전후 2개 · '+(confirmed?'예측 모델 확정':'생성·비교 후 사용할 모델을 확정하세요.'):'현재 데이터 버전에 맞는 모델을 확인하세요.'],
    predictions:[known?(confirmed&&Number(predictionStorage?.rows)>0?'실행 가능':'준비 필요'):'확인 대기',known&&confirmed&&Number(predictionStorage?.rows)>0?'success':'neutral',known?'예측 입력 '+number(predictionStorage?.rows)+'행 · '+(confirmed?'입력 구성 확인 후 실행':'모델 확정이 필요합니다.'):'모델 확정과 예측 입력 적재 상태를 확인하세요.']
  };
  for(const [stage,[label,status,detail]] of Object.entries(stages)){
    text('overview-'+stage+'-state',label);text('overview-'+stage+'-detail',detail);
    if($('overview-'+stage+'-state'))$('overview-'+stage+'-state').dataset.state=phase==='error'?'error':status;
    text('progress-'+stage,status==='success'?'✓':{data:'01',models:'02',predictions:'03'}[stage]);
    if($('progress-'+stage))$('progress-'+stage).dataset.state=status;
  }
}
function resetRemoteState(){
  predictionChoice=null;
  if(typeof clearPracticeEvidence==='function')clearPracticeEvidence('로그인 후 최종 상태를 확인하세요.');
  labHistory=[];labSeen.clear();previousPrediction=null;history=[];table('history',[]);table('model-lab-history',[]);
  clearModelDictionary();
  if($('model-add-file')){$('model-add-file').value='';text('model-add-file-name','새 CASE_ID · Y/TRAIN만 · 최대 5,000행 / 2 MiB');}
  state={};models=[];storage=null;predictionStorage=null;preparation={};preparedStorage=null;basicObjects=[];initialized=false;++preparedRequest;table('prepared-data',[]);renderPreparation();predictionContext='';rows=[];
  for(const id of ['run','prediction-model-select','train-both','add-row'])if($(id))$(id).disabled=true;
  document.querySelectorAll('[data-train],[data-confirm]').forEach(button=>button.disabled=true);
  for(const id of ['storage-rows','storage-object','storage-created','prediction-storage-rows','prediction-storage-object','prediction-storage-loaded','prediction-model'])text(id,'—');
  text('storage-name','현재 상태 확인 필요');text('storage-state','확인 필요');text('prediction-storage-name','현재 상태 확인 필요');text('prediction-storage-state','확인 필요');
  for(const id of ['storage-state','prediction-storage-state'])if($(id))$(id).className='pill';
  if($('data-table'))table('data-table',[]);
  if($('results'))resetPredictionResults();
  if(typeof modelResults!=='undefined'){modelResults={models:[],metrics:[],settings:[],attributes:[]};if(page==='models')renderModels();}
  if(typeof resetAssignmentWorkspace==='function')resetAssignmentWorkspace();
}
function renderPerson(){
  document.body.dataset.auth=authenticationPending?'checking':person?'ready':'locked';
  if($('auth-check'))$('auth-check').hidden=!authenticationPending;
  const gate=document.querySelector('.login-gate');if(gate)gate.hidden=authenticationPending||Boolean(person)||(mainWorkspace&&loginView);
  renderObjectOwners();
  if(!person&&typeof resetBasicDatasetViewers==='function')resetBasicDatasetViewers();
  if(!person&&typeof resetMissionSchema==='function')resetMissionSchema();
  if(!person){instructorLectureUrl=null;clearModelDictionary();clearRelatedSource();if(typeof clearCodingHelp==='function')clearCodingHelp();}
  document.querySelectorAll('[data-instructor-lecture]').forEach(link=>{
    const allowed=person&&instructorLectureUrl==='/instructor/python-web-lecture.html';
    link.hidden=!allowed;
    if(allowed)link.setAttribute('href',instructorLectureUrl);else link.removeAttribute('href');
  });
  for(const element of document.querySelectorAll('.sidebar,.workspace')){const accessible=!authenticationPending&&(Boolean(person)||(element.classList.contains('workspace')&&mainWorkspace&&loginView));element.hidden=!accessible;element.inert=!accessible;element.setAttribute('aria-hidden',accessible?'false':'true');}
  document.body.dataset.entry=mainWorkspace&&loginView?'login':'intro';
  if(typeof renderMainPage==='function')renderMainPage();
  text('account-name',person?.name||'로그인 전');text('account-id',person?.student_id||'작업 계정');
  for(const [id,key] of [['department','department'],['student-id','student_id'],['name','name'],['db-user','db_user']])text(id,person?.[key]);
  text('grade',person?.grade?person.grade+'학년':'—');text('identity-state',person?'로그인됨':'로그인 필요');
  if($('identity-state'))$('identity-state').className='pill'+(person?' good':'');
  $('logout').hidden=!person;$('top-login').hidden=Boolean(person);
  if(!person){sessionDeadline=0;sessionObservedAt=0;}
  renderSessionTime();
  const accountAction='로그인 정보';
  text('mobile-account',accountAction);$('account-button').setAttribute('aria-label',accountAction);$('account-button').setAttribute('title',accountAction);
  if(!person){resetRemoteState();text('connection','로그인 필요');$('connection').className='pill';renderOverview('auth');}
}
function openIdentity(){
  if(signingOut)return;
  if(!mainWorkspace){location.assign('/?login=1');return;}
  dismissMessage();loginView=true;identityOrigin=document.activeElement;
  window.history.replaceState(null,'','/?login=1');
  const saved=rememberedIdentity();text('identity-title',person?'계정 전환':'로그인');text('identity-error',identityConfigured?'':'명단 등록 후 사용할 수 있습니다. security/students.json을 확인하세요.');$('identity-error').hidden=identityConfigured;$('connection-check').hidden=true;
  $('login-id').value=person?.student_id||saved?.student_id||'';$('login-name').value=person?.name||saved?.name||'';
  const same=saved&&saved.student_id===$('login-id').value&&saved.name===$('login-name').value;
  $('login-password').value=same&&rememberLoginPassword()?saved.db_password||'':'';$('remember-identity').checked=Boolean(same);
  $('login-db-user').value='';renderPerson();lookupIdentity();
  $('login-id').focus({preventScroll:true});window.scrollTo(0,0);
}
function closeIdentity(){
  if(signingIn)return;
  ++lookupVersion;loginView=false;$('login-password').value='';window.history.replaceState(null,'','/');renderPerson();
  if(!person)$('gate-login').focus({preventScroll:true});else $('account-button').focus({preventScroll:true});
}
function renderConnectionCheck(result){
  const panel=$('connection-check');panel.hidden=false;panel.className='connection-check '+(result.success?'success':result.success===false?'failure':'pending');
  panel.innerHTML='<h3>'+esc(result.title)+'</h3>'+(result.code?'<p class="connection-code">'+esc(result.code)+(result.db_user?' · '+esc(result.db_user):'')+'</p>':'')+
    (result.connection?'<dl class="login-connection-facts">'+[['session_user','실제 접속 계정'],['current_schema','현재 스키마'],['connection_alias','서비스 별칭'],['database_name','DB 이름'],['service_name','실제 서비스명'],['checked_at','확인 시각']].map(([key,label])=>'<div><dt>'+esc(label)+'</dt><dd>'+esc(key==='checked_at'?date(result.connection[key]):result.connection[key])+'</dd></div>').join('')+'</dl>':'')+
    (result.steps?.length?'<ol>'+result.steps.map(step=>'<li>'+esc(step)+'</li>').join('')+'</ol>':'')+(result.message?'<p>'+esc(result.message)+'</p>':'');
}
function accountBusy(busy){signingIn=busy;for(const id of ['cancel-identity','test-connection','login-submit','login-id','login-name','login-password','remember-identity'])if($(id))$(id).disabled=busy;}
async function loadStatus(){
  if(typeof clearPracticeEvidence==='function')clearPracticeEvidence('현재 상태를 확인하고 있습니다.');
  renderOverview('loading');renderBasicControls();
  try{const data=await api('/api/status?include_evidence=1');if(data.practice&&typeof renderPracticeEvidence==='function')renderPracticeEvidence(data.practice);state=data.state;models=data.models;initialized=data.initialized!==false;basicObjects=data.objects||[];storage=data.storage||null;predictionStorage=data.prediction_storage||null;preparation=data.preparation||state.preparation||{};preparedStorage=data.prepared_storage||null;
    text('connection','Oracle 연결됨');$('connection').className='pill good';
    text('total-rows',number(state.total_rows));text('split-counts',number(state.train_rows)+' / '+number(state.test_rows));
    statusCheckedAt=new Date();renderOverview('ready');
    const current=models.find(m=>m.is_confirmed===1);text('prediction-model',current?.model_name||'미확정');
    if(page==='predictions'){
      const context=JSON.stringify([current?.model_name,current?.trained_at,state.data_rev,predictionStorage?.loaded_at,predictionStorage?.rows]);
      if(predictionContext&&context!==predictionContext)resetPredictionResults();predictionContext=context;
    }
    text('data-quality',`TRAIN ${number(state.train_rows)}행 · TEST ${number(state.test_rows)}행 · 미사용 ${number(state.disabled_rows)}행. 원본 오류는 CSV 미리보기에서 확인하세요.`);
  }catch(error){resetRemoteState();text('connection',person?'DB 조회 실패':'로그인 필요');$('connection').className='pill'+(person?' bad':'');renderOverview(person?'error':'auth');throw error;}
  finally{renderBasicControls();}
}
async function loadRows(){
  const filters=[$('filter-use'),$('filter-split')],query=new URLSearchParams({use_yn:filters[0].value,split:filters[1].value});
  filters.forEach(filter=>filter.disabled=true);
  try{const result=await api('/api/data?'+query);rows=result.rows;table('data-table',rows,fields.map((key,i)=>[key,labels[i]]),{database:true,columnRoles:learningColumnRoles()});text('row-count',number(rows.length)+'행');}
  finally{filters.forEach(filter=>filter.disabled=false);}
}
function upload(file){if(!file)throw new Error('CSV 파일을 먼저 선택하세요.');const data=new FormData();data.append('file',file);return data;}
async function preview(){const result=await api('/api/data/preview',upload($('data-file').files[0]||selectedFile));const q=result.summary;$('preview-box').hidden=false;text('quality-summary',`${q.rows}행 · 사용 ${q.used}행 / 미사용 ${q.disabled}행 · 결측값 ${q.missing}개 · 유효하지 않은 값 ${q.invalid}개 · 이상치 ${q.outliers}개 · 라벨 제외 ${q.invalid_target}행`);table('preview-table',result.rows,fields.map((key,i)=>[key,labels[i]]),{database:true,columnRoles:learningColumnRoles()});}
function renderPredictionStorage(){
  if(page!=='predictions')return;
  renderPredictionModel();
  const s=predictionStorage;
  text('prediction-storage-name',s?.qualified_name||'로그인 후 확인');text('prediction-storage-object',s?.object_id);
  text('prediction-storage-rows',s?number(s.rows)+'행':'—');text('prediction-storage-loaded',date(s?.loaded_at));
  text('prediction-storage-state',statusPhase!=='ready'?(statusPhase==='loading'?'확인 중':'확인 미완료'):s?.rows?'적재 완료':s?.exists?'적재 대기':'미생성');
  $('prediction-storage-state').className='pill'+(s?.rows?' good':'');

  const busy=predictionImporting?'예측 CSV 적재 중입니다.':predictionRunning?'예측 실행 중입니다.':modelBusy?'모델 작업 중입니다.':'';
  controlState('prediction-import-submit',busy||basicUnavailable()||(s?.rows?'입력이 있습니다. 교체 적재를 사용하세요.':''),'빈 예측 테이블에 CSV를 적재합니다.','prediction-import-status');
  controlState('replace-prediction',busy||basicUnavailable()||(!s?.rows?'입력이 없습니다. 최초 적재를 사용하세요.':''),'예측 CSV 교체 적재','prediction-import-status');
  controlState('clear-prediction',busy||basicUnavailable()||(!s?.rows?'비울 예측 입력이 없습니다.':''),'예측 입력을 비웁니다.');
  text('prediction-import-status',busy||basicUnavailable()||(s?.rows?`예측 원본 ${number(s.rows)}행 적재 완료 · CSV를 교체하거나 선택 모델로 예측할 수 있습니다.`:'예측 원본 없음 · 예측 CSV를 선택하고 적재하세요.'));
  const current=selectedPredictionModel();
  const modelReady=Boolean(current);
  const reason=basicUnavailable()||busy||(!modelReady?'최신 RAW 또는 CLEAN 모델을 선택하세요. 모델이 없으면 3단계에서 생성하세요.':!s?.rows?'예측 입력 없음 · 예측 CSV를 적재하세요.':'');
  controlState('run',reason,'예측 실행 가능','prediction-ready');
  text('prediction-ready',reason||`${number(s.rows)}행 준비 완료 · 예측 실행을 누르세요.`);
  text('loaded-predictions-count',`적재된 데이터 확인 · ${number(s?.rows||0)}행`);
}
function confirmedPredictionModel(){
  if(state.confirmed_current!==1)return null;
  return models.find(m=>m.exists===1&&m.is_confirmed===1&&m.is_current===1)||null;
}
function selectedPredictionModel(){
  return models.find(m=>m.variant===selectedMode('prediction-model-select')&&m.exists===1&&m.is_current===1)||null;
}
function renderPredictionModel(){
  const group=$('prediction-model-select');if(!group)return;
  const reason=basicUnavailable()||(modelBusy||predictionImporting||predictionRunning?'DB 작업 중입니다. 완료 후 사용할 수 있습니다.':'');
  if(predictionChoice===null&&statusPhase==='ready')predictionChoice=state.confirmed_variant||models.find(m=>m.is_current===1)?.variant||'RAW';
  group.disabled=Boolean(reason);
  setWorkMode(group.id,predictionChoice);
  for(const button of group.querySelectorAll('.mode-option')){
    const m=models.find(m=>m.variant===button.value);
    button.disabled=Boolean(reason)||m?.is_current!==1;
    text('prediction-choice-name-'+button.value,objectDisplay(m?.model_name||'OML_BASIC_'+button.value+'_MODEL'));
    text('prediction-choice-state-'+button.value,!m?.exists?'모델 없음':m.is_current!==1?'재학습 필요':m.is_confirmed?'사용 모델 · 실행 가능':'최신 모델 · 실행 가능');
  }
  const current=selectedPredictionModel(),mode=selectedMode('prediction-model-select');
  text('prediction-model',current?objectDisplay(current.model_name):'선택 모델 확인 필요');
  if($('result-state')?.textContent==='실행 대기')text('result-caption',current?mode+' 모델로 예측할 수 있습니다.':'최신 모델을 선택하세요.');
  text('prediction-mode-rule',mode+': 예측 원본 → 학습과 같은 규칙으로 PREPARED의 PREDICT 행 저장 → PREDICTION. TRAIN·TEST 저장값은 유지합니다.');
  text('prediction-model-help',reason||(current?'선택한 '+mode+' 모델로 바로 실행합니다. 실행 성공 시 사용 모델로 저장됩니다.':'선택 모델이 없거나 최신이 아닙니다. 다른 모델을 선택하거나 3단계에서 생성·재학습하세요.'));
}
function resetPredictionResults(){
  if($('prediction-proof-return'))$('prediction-proof-return').hidden=true;
  table('results',[]);if($('prediction-error'))$('prediction-error').hidden=true;
  text('result-state','실행 대기');text('result-caption','RAW 또는 CLEAN 모델을 선택하고 예측을 실행하세요.');
}
async function previewPrediction(){
  const file=$('prediction-file').files[0]||selectedPrediction;
  const result=await api('/api/predictions/preview',upload(file)),q=result.summary;
  $('prediction-preview-box').hidden=false;
  text('prediction-quality',`${number(q.rows)}행 · 결측값 ${q.missing}개 · 유효하지 않은 값 ${q.invalid}개 · 이상치 ${q.outliers}개 · 비교용 라벨 ${q.labeled}행 · 최대 100행 표시`);
  table('prediction-preview',result.rows,predictionColumns,{database:true});
}
async function loadPredictionRows(){
  if(!predictionStorage?.exists){table('prediction-data',[]);return;}
  const result=await api('/api/predictions/data');table('prediction-data',result.rows,predictionColumns,{database:true});
  if(predictionStorage.rows>100)text('loaded-predictions-count',`적재된 데이터 확인 · 전체 ${number(predictionStorage.rows)}행 중 100행 표시`);
}
async function importPrediction(button,mode='initial'){
  if(predictionImporting)return;
  const file=$('prediction-file').files[0]||selectedPrediction;
  if(!file){notice('예측 CSV 파일을 먼저 선택하세요.',true);return;}
  if(!await askConfirmation(`${predictionStorage?.qualified_name||person.db_user+".OML_BASIC_PREDICT"}에 ${file.name}을 적재합니다.\n${mode==='initial'?'빈 예측 테이블에 처음 적재합니다.':'기존 예측 행을 선택 CSV로 교체합니다.'} 테이블 ID와 학습 모델은 유지됩니다. 계속하시겠습니까?`,{title:mode==='initial'?'예측 CSV 최초 적재':'예측 CSV 교체 적재',accept:'적재',opener:button}))return;
  predictionImporting=true;
  const controls=['prediction-file','choose-prediction','preview-prediction','prediction-import-submit','replace-prediction'];controls.forEach(id=>$(id).disabled=true);renderPredictionStorage();
  try{await task(button,async()=>{
    const data=upload(file);data.append('mode',mode);const result=await api('/api/predictions/import',data);resetPredictionResults();
    await loadStatus();await loadPredictionRows();await loadColumns();
    $('prediction-preview-box').hidden=true;$('loaded-predictions').open=true;
    notice(`예측 데이터 적재 완료 · ${result.prediction_storage.qualified_name}\n${number(result.loaded_rows)}행 · OBJECT_ID ${result.prediction_storage.object_id}`);
  });}finally{predictionImporting=false;controls.forEach(id=>$(id).disabled=false);renderPredictionStorage();}
}
let modelResults={metrics:[],details:{}};
const percent=value=>value==null?'—':value.toFixed(1)+'%';
function comparisonTable(id,items,highlight=true){
  const element=$(id);element.classList.remove('empty');
  element.innerHTML='<table class="compare-table"><thead><tr><th scope="col">항목</th><th scope="col">정제 미적용</th><th scope="col">정제 적용</th></tr></thead><tbody>'+items.map(([label,raw,clean])=>
    '<tr'+(highlight&&raw!==clean?' class="different"':'')+'><th scope="row">'+esc(label)+'</th><td>'+esc(raw??'—')+'</td><td>'+esc(clean??'—')+'</td></tr>').join('')+'</tbody></table>';
}
// SQL이 반환한 TEST 혼동행렬만 집계합니다. TRAIN이나 예측 CSV의 결과를 섞지 않습니다.
function modelScore(variant){
  const current=models.find(m=>m.variant===variant)?.is_current===1;
  const values=current?(modelResults.metrics||[]).filter(row=>row.variant===variant):[];
  const count=(actual,predicted)=>values.filter(row=>(actual==null||row.actual===actual)&&(predicted==null||row.predicted===predicted)).reduce((sum,row)=>sum+Number(row.n),0);
  const total=count(null,null),correct=values.reduce((sum,row)=>sum+(row.actual===row.predicted?Number(row.n):0),0);
  const cell=(actual,predicted)=>values.filter(row=>row.actual===actual&&row.predicted===predicted).reduce((sum,row)=>sum+Number(row.n),0);
  return {total,correct,errors:total-correct,cell,accuracy:total?100*correct/total:null,
    alwaysBuy:total?100*count('BUY',null)/total:null,alwaysSell:total?100*count('SELL',null)/total:null,
    precision:count(null,'BUY')?100*count('BUY','BUY')/count(null,'BUY'):null,
    recall:count('BUY',null)?100*count('BUY','BUY')/count('BUY',null):null};
}
function renderModels(){
  if(page!=='models')return;
  const scores={RAW:modelScore('RAW'),CLEAN:modelScore('CLEAN')};
  text('evaluation-scope',`USE_YN=Y · TRAIN ${number(state.train_rows)}행 학습 / TEST ${number(state.test_rows)}행 평가 · 유효한 BUY/SELL 라벨만 사용`);
  for(const v of ['RAW','CLEAN']){
    const m=models.find(item=>item.variant===v),s=scores[v];
    text('accuracy-'+v,percent(s.accuracy));text('correct-'+v,s.total?`${number(s.correct)} / ${number(s.total)}행`:'—');
    text('errors-'+v,s.total?number(s.errors)+'행':'—');text('precision-'+v,percent(s.precision));text('recall-'+v,percent(s.recall));
    const status=m?.is_confirmed===1?'기본 예측 모델':m?.is_current===1?'생성 완료':m?.exists===1?'전체 재학습 필요':'미생성';
    text('state-'+v,status);$('state-'+v).className='pill'+(m?.is_confirmed===1?' good':'');$('card-'+v).classList.toggle('selected',m?.is_confirmed===1);
    const confirmButton=document.querySelector(`[data-confirm="${v}"]`);
    confirmButton.disabled=modelBusy||refreshing||m?.is_current!==1||m?.is_confirmed===1;
    $('accuracy-'+v).classList.remove('better');
  }
  renderModelLifecycle();
  const raw=scores.RAW,clean=scores.CLEAN,comparable=raw.total>0&&raw.total===clean.total;
  if(comparable){
    const delta=clean.accuracy-raw.accuracy;
    text('comparison-summary',`정제 적용 정확도 ${Math.abs(delta).toFixed(1)}%p ${delta>0?'높음':delta<0?'낮음':'차이 없음'} · 오분류 ${raw.errors} → ${clean.errors}행`);
    if(delta!==0)$('accuracy-'+(delta>0?'CLEAN':'RAW')).classList.add('better');
  }else text('comparison-summary',!state.test_rows?'평가할 TEST 행이 없습니다. 학습데이터의 USE_YN·SPLIT·라벨을 확인하세요.':'두 모델을 현재 데이터로 학습한 뒤 같은 TEST로 비교합니다.');
  text('constant-baseline',raw.total||clean.total?`같은 TEST에서 항상 BUY로 분류: ${percent((raw.total?raw:clean).alwaysBuy)} · 항상 SELL로 분류: ${percent((raw.total?raw:clean).alwaysSell)}. 모델이 이 단순 기준보다 나은지도 비교하세요.`:'모델 생성 후 같은 TEST의 항상 BUY·항상 SELL 기준 정확도를 표시합니다.');
  const pairs=[['SELL','SELL'],['SELL','BUY'],['BUY','SELL'],['BUY','BUY']];
  for(const item of modelResults.metrics||[])if(!pairs.some(([a,p])=>a===item.actual&&p===item.predicted))pairs.push([item.actual,item.predicted]);
  table('metrics',pairs.map(([actual,predicted])=>({actual,predicted,raw:raw.total?raw.cell(actual,predicted):'—',clean:clean.total?clean.cell(actual,predicted):'—'})),[['actual','실제 값'],['predicted','예측 값'],['raw','미적용 · 건수'],['clean','적용 · 건수']]);
  const setting=(v,key)=>(modelResults.details?.[v]||[]).find(item=>item.section==='SETTING'&&item.name===key)?.value??null;
  comparisonTable('model-settings',[
    ['알고리즘',...['RAW','CLEAN'].map(v=>setting(v,'ALGO_NAME')?.replace('ALGO_DECISION_TREE','Decision Tree'))],
    ['최대 깊이',setting('RAW','TREE_TERM_MAX_DEPTH'),setting('CLEAN','TREE_TERM_MAX_DEPTH')],
    ['숫자 변환·범주 대소문자','공통 적용','공통 적용'],
    ['결측·변환 실패','NULL · 트리 자체 결측 처리','NULL · 트리 자체 결측 처리'],
    ['범위 밖 숫자','입력값 유지','NULL로 변경'],
    ['종목 코드','공백 제거·대문자화','공백 제거·대문자화']
  ]);
  comparisonTable('model-info',[
    ['모델명',...['RAW','CLEAN'].map(v=>objectDisplay(models.find(m=>m.variant===v)?.model_name))],
    ['생성 시각',...['RAW','CLEAN'].map(v=>date(models.find(m=>m.variant===v)?.trained_at))],
    ['학습 데이터 버전',...['RAW','CLEAN'].map(v=>models.find(m=>m.variant===v)?.trained_rev)]
  ],false);
  for(const [section,id] of [['SETTING','model-details'],['ATTRIBUTE','model-attributes']]){
    const items=v=>(modelResults.details?.[v]||[]).filter(item=>item.section===section);
    const names=[...new Set(['RAW','CLEAN'].flatMap(v=>items(v).map(item=>item.name)))].sort();
    if(!names.length){table(id,[]);continue;}
    comparisonTable(id,names.map(name=>[name,...['RAW','CLEAN'].map(v=>items(v).find(item=>item.name===name)?.value??(section==='ATTRIBUTE'?'등록 없음':null))]));
  }
}
on('query-models','click',event=>task(event.currentTarget,loadModels,{mutation:false}));
on('query-prediction-data','click',event=>task(event.currentTarget,loadPredictionRows,{mutation:false}));
on('query-prediction-columns','click',event=>task(event.currentTarget,loadColumns,{mutation:false}));
async function loadModels(){modelResults=await api('/api/models');models=modelResults.models;renderModels();
  if(typeof syncPracticeEvidence==='function')await syncPracticeEvidence();
  for(const model of models.filter(m=>m.is_current===1)){const score=modelScore(model.variant),key=JSON.stringify([model.model_name,model.trained_at,model.trained_rev,modelResults.metrics]);if(!score.total||labSeen.has(key))continue;labSeen.add(key);labHistory.unshift({time:date(new Date()),model:model.model_name,trained:date(model.trained_at),revision:model.trained_rev,accuracy:percent(score.accuracy),correct:`${score.correct} / ${score.total}`});}
  labHistory=labHistory.slice(0,20);table('model-lab-history',labHistory,[['time','평가 시각'],['model','모델'],['trained','모델 생성 시각'],['revision','학습 버전'],['accuracy','TEST 정확도'],['correct','정답 / TEST']]);
}
async function loadColumns(){const data=await api('/api/predictions/columns?experiment='+$('experiment').value);table('columns',data.columns,[['column_id','순서'],['column_name','이름'],['data_type','타입']],{database:true});}
async function refresh(){
  if(mainWorkspace){if(typeof loadMainConnection==='function')await loadMainConnection();return;}
  if(basicWorkspace&&basicMutationBusy()){presentMessage('DB 변경 작업이 진행 중입니다. 완료 후 상태를 새로고침하세요.','info');return;}
  if(refreshing)return;refreshing=true;
  if($('assignment-import')){try{if(typeof loadAssignmentReadiness==='function')await loadAssignmentReadiness();}finally{refreshing=false;}return;}
  try{await loadStatus();if(!initialized){if(page==='models')renderModels();return;}if(page==='data'){await loadRows();await loadPreparedRows();}if(page==='models')await loadModels();if(page==='predictions'){await loadPredictionRows();await loadColumns();}}
  finally{refreshing=false;renderBasicControls();if(page==='models')renderModels();flushBasicNavigation();}
}
const lifecycleActions={
  'create-tables':['테이블 생성','없는 기본과제 테이블 3개를 생성합니다. 기존 행은 유지합니다.'],
  'register-procedure':['프로시저 최초 등록','sql/classifier.sql을 DB에 등록합니다. 테이블·데이터는 유지하며 전처리·학습 기록은 해제합니다.'],
  'reregister-procedure':['프로시저 다시 등록','sql/classifier.sql의 수정 내용을 DB에 반영합니다. 테이블·데이터는 유지하며 전처리·학습 기록은 해제합니다.'],
  'drop-objects':['실습 오브젝트 삭제','기본과제 모델 2개·테이블 3개·프로시저를 삭제합니다. 모든 실습 데이터가 사라지며 되돌릴 수 없습니다.'],
  'clear-training':['학습 데이터 비우기','학습 원본과 모든 전처리 저장값을 삭제합니다. 테이블·모델은 유지하며 전처리와 재학습이 필요합니다.'],
  'clear-prediction':['예측 입력 비우기','예측 원본과 예측 전처리값을 삭제합니다. 학습 데이터·모델은 유지합니다.'],
  'clear-prepared':['선택 전처리값 비우기','선택한 RAW/CLEAN의 모든 전처리값을 삭제합니다. 해당 모델의 최신·확정 상태도 해제합니다.'],
  'unconfirm':['모델 확정 해제','예측에 사용할 모델 선택을 해제합니다. 생성된 모델과 데이터는 유지합니다.']
};
async function applyBasicLifecycle(button){
  const action=button.dataset.basicLifecycle,variant=action==='clear-prepared'?selectedMode('preparation-mode'):'RAW',generation=sessionGeneration;
  const [title,message]=lifecycleActions[action];
  if(!await askConfirmation((person?.db_user||'')+' · '+(action==='clear-prepared'?variant+' · ':'')+message,{title,accept:action.startsWith('clear')?'비우기':action==='drop-objects'?'삭제':action==='unconfirm'?'해제':'적용',danger:action.startsWith('clear')||action==='drop-objects',opener:button}))return;
  if(!person||generation!==sessionGeneration||basicMutationBusy()||refreshing)return;
  await task(button,async()=>{
    try{const result=await api('/api/basic/lifecycle',{action,variant});notice(result.message);}
    finally{
      rows=[];table('data-table',[]);table('prepared-data',[]);resetPredictionResults();clearModelDictionary();
      modelResults={metrics:[],details:{}};labHistory=[];labSeen.clear();history=[];previousPrediction=null;table('history',[]);table('model-lab-history',[]);
      await loadStatus();
      if(initialized){if(page==='data'){await loadRows();await loadPreparedRows();}if(page==='predictions')await loadPredictionRows();if(page==='models')await loadModels();}
    }
  },{mutation:true});
}
document.querySelectorAll('[data-basic-lifecycle]').forEach(button=>on(button.id,'click',()=>applyBasicLifecycle(button)));
on('query-data','click',event=>task(event.currentTarget,loadRows));
on('account-button','click',openIdentity);on('top-login','click',openIdentity);on('cancel-identity','click',closeIdentity);
on('gate-login','click',openIdentity);
on('help-dialog','close',()=>{const dialog=$('help-dialog');if(!dialog.open&&!HelpWindow.isMinimized(dialog)){++sourceRequest;if(sourceOrigin?.isConnected)sourceOrigin.focus({preventScroll:true});}});
on('open-menu','click',()=>{$('open-menu').setAttribute('aria-expanded','true');$('mobile-menu').showModal();});
on('close-menu','click',()=>$('mobile-menu').close());
on('mobile-menu','close',()=>{$('open-menu').setAttribute('aria-expanded','false');$('open-menu').focus();});
on('mobile-account','click',()=>{$('mobile-menu').close();openIdentity();});
document.addEventListener('click',event=>{
  if(event.target.closest('#mobile-menu a')&&$('mobile-menu')?.open)$('mobile-menu').close();
  const link=event.target.closest('[data-overview-action]');if(!link)return;
  event.preventDefault();if(link.dataset.overviewAction==='identity')openIdentity();
  if(link.dataset.overviewAction==='refresh')task(null,refresh);
});
for(const id of ['login-id','login-name']){on(id,'input',()=>{++lookupVersion;$('login-db-user').value='';$('identity-error').hidden=true;$('connection-check').hidden=true;});on(id,'change',lookupIdentity);}
on('login-password','input',()=>{$('connection-check').hidden=true;$('identity-error').hidden=true;});
on('test-connection','click',async()=>{
  if(!$('identity-form').reportValidity())return;
  const id=$('login-id').value,name=$('login-name').value,password=$('login-password').value,button=$('test-connection');
  accountBusy(true);button.setAttribute('aria-busy','true');$('identity-error').hidden=true;++lookupVersion;
  renderConnectionCheck({title:'Oracle DB에 연결하고 있습니다.',message:'네트워크와 DB 응답을 기다리고 있습니다.'});
  try{const session=await api('/api/session');csrf=session.csrf;const result=await api('/api/identity/test',loginPayload(id,name,password));$('login-db-user').value=result.db_user;renderConnectionCheck(result);}
  catch(error){if(error.diagnostic)renderConnectionCheck(error.diagnostic);else renderConnectionCheck({success:false,title:error.message,steps:[],message:'학번·이름과 DB 연결 설정을 확인한 뒤 다시 테스트하세요.'});}
  finally{accountBusy(false);button.removeAttribute('aria-busy');}
});
on('remember-identity','change',()=>{if(!$('remember-identity').checked){try{localStorage.removeItem(rememberedKey);}catch{}}});
on('identity-form','submit',async event=>{
  event.preventDefault();const button=event.submitter,id=$('login-id').value,name=$('login-name').value,password=$('login-password').value,remember=$('remember-identity').checked;
  accountBusy(true);button.setAttribute('aria-busy','true');$('identity-error').hidden=true;$('connection-check').hidden=true;++lookupVersion;
  try{const result=await confirmIdentity(id,name,password);person=result.identity;sessionEnding=false;loginView=false;window.history.replaceState(null,'','/');$('login-db-user').value=person.db_user;saveRememberedIdentity(id,name,password,remember);$('login-password').value='';if(typeof resetMainConnection==='function')resetMainConnection();renderPerson();await refresh();window.scrollTo(0,0);}
  catch(error){if(error.diagnostic)renderConnectionCheck(error.diagnostic);else{text('identity-error',error.message);$('identity-error').hidden=false;}}
  finally{accountBusy(false);button.removeAttribute('aria-busy');}
});
async function logout(button){
  if(signingOut)return;
  signingOut=true;button.disabled=true;button.setAttribute('aria-busy','true');
  try{
    await api('/api/logout',{});
    person=null;loginView=false;loginAt=null;++lookupVersion;sessionEnding=false;window.RequestProgress?.reset();
    if(typeof finishLayerConfirmation==='function')finishLayerConfirmation(false);
    for(const dialog of document.querySelectorAll('dialog[open]'))HelpWindow.close(dialog);
    if($('login-password'))$('login-password').value='';
    renderPerson();
    if(mainWorkspace){window.history.replaceState(null,'','/');window.scrollTo(0,0);$('gate-login').focus({preventScroll:true});}
    else location.replace('/');
  }catch(error){operationNotice(error);}
  finally{signingOut=false;button.disabled=false;button.removeAttribute('aria-busy');}
}
on('logout','click',event=>logout(event.currentTarget));on('refresh','click',event=>person?task(event.currentTarget,refresh,{feedback:false}):openIdentity());
on('choose-sample','click',event=>task(event.currentTarget,async()=>{const response=await fetch('/download/sample.csv');selectedFile=new File([await response.blob()],'classification.csv',{type:'text/csv'});$('data-file').value='';text('selected-filename',selectedFile.name);await preview();}));
on('data-file','change',()=>{selectedFile=null;$('preview-box').hidden=true;text('selected-filename',$('data-file').files[0]?.name||'선택한 CSV가 없습니다.');});on('preview','click',event=>task(event.currentTarget,preview));
on('import-form','submit',event=>{event.preventDefault();importTraining(event.submitter?.id==='replace-training'?'replace':'initial',event.submitter);});
on('recreate-training','click',event=>importTraining('recreate',event.currentTarget));
for(const id of ['filter-use','filter-split'])on(id,'change',()=>task(null,loadRows));
async function modelAction(button,action){
  if(modelBusy)return;modelBusy=true;renderModels();
  if($('results'))resetPredictionResults();
  try{await task(button,async()=>{try{await action();}finally{await loadStatus();await loadModels();}});}
  finally{modelBusy=false;renderModels();}
}
function renderModelLifecycle(){
  if(!$('model-lifecycle-mode'))return;
  const mode=selectedMode('model-lifecycle-mode'),m=models.find(item=>item.variant===mode),p=preparation[mode],busy=modelBusy||refreshing||!initialized;
  text('model-lifecycle-label','실행 대상');
  text('model-lifecycle-name',m?.model_name||`OML_BASIC_${mode}_MODEL`);
  text('model-training-count',p?.ready?'FIT_YN=Y '+number(p.fit_rows)+'행 · TEST '+number(p.test_rows)+'행':'전처리 저장 필요');
  text('model-training-condition',`PREP_MODE = '${mode}' AND SOURCE_KIND = 'TRAIN' AND FIT_YN = 'Y'`);
  text('model-mode-effect',`${mode} 전처리 저장값 → ${mode} 모델 · 다른 방식의 준비값·모델 유지`);
  const reason=basicUnavailable()||(modelBusy?'모델 작업 중입니다.':'');
  const training=reason||(!p?.ready?`${mode} 전처리 저장 필요`:!p.fit_rows?'FIT_YN=Y TRAIN 0행 · DB에서 확인하세요.':'');
  text('model-preparation',reason||(!p?.ready?`${mode} 전처리 저장 필요 · 학습데이터 단계에서 실행·저장하세요.`:training||`${mode} 전처리 저장 완료 · FIT_YN=Y TRAIN ${number(p.fit_rows)}행으로 학습 가능`));
  text('model-lifecycle-state',reason||(m?.exists===1?(m.is_current===1?'현재 데이터로 학습됨':'모델 있음 · 재학습 필요'):'모델 미생성 · '+(training?'전처리·학습 제공 행 확인 필요':'최초 생성 가능')));
  if(modelBusy||!person||(dictionaryStamp&&dictionaryStamp!==modelDictionaryStamp()))clearModelDictionary();
  $('query-model-dictionary').disabled=busy||dictionaryBusy;
  controlState('unconfirm-model',reason||(!models.some(m=>m.is_confirmed)?'확정된 모델이 없습니다.':''),'모델 선택 해제');
  controlState('model-initial',reason||(m?.exists===1?'이미 생성됨 · 다시 학습을 이용하세요.':training),'최초 생성 가능');
  controlState('model-retrain',reason||(m?.exists!==1?'모델 없음 · 최초 생성이 먼저입니다.':training),'저장된 TRAIN 전체로 모델을 다시 만듭니다.');
  controlState('model-delete',reason||(m?.exists!==1?'모델 없음 · 삭제할 대상이 없습니다.':''),'선택 모델 삭제 가능');
  $('model-lifecycle-mode').disabled=modelBusy||dictionaryBusy;
}
function modelDictionaryStamp(){const mode=selectedMode('model-lifecycle-mode'),m=models.find(item=>item.variant===mode);return JSON.stringify([mode,m?.exists,m?.trained_at,m?.is_current,person?.db_user]);}
function clearModelDictionary(){
  ++dictionaryRequest;dictionaryStamp='';const root=$('model-dictionary-results');if(!root)return;
  root.replaceChildren();const p=document.createElement('p');p.className='muted';p.textContent='모델 생성 후 ‘모델 정보 조회’를 누르세요. 생성 전에도 ?에서 조회 SQL과 읽는 방법을 확인할 수 있습니다.';root.append(p);
}
function renderDictionaryObject(parent,detail,index){
  const box=document.createElement('details'),summary=document.createElement('summary'),note=document.createElement('p'),body=document.createElement('div'),sql=document.createElement('pre'),copy=document.createElement('button');
  box.className='dictionary-view-code';summary.textContent=detail.object_name+' · '+detail.code+' · '+detail.meaning;
  note.className='compact-note muted';note.textContent=detail.error||(!detail.sql?'일반 조회 가능한 컬럼이 없어 컬럼 정의만 제공합니다.':detail.rows.length+'행 조회 · 최대 '+detail.row_limit+'행 · 실제 DB 값');
  body.id='dictionary-object-data-'+index;body.className='table-wrap';box.append(summary,note,body);
  if(detail.explanation){const explanation=document.createElement('p');explanation.className='compact-note';explanation.textContent=detail.explanation;box.append(explanation);}
  if(detail.omitted_columns.length){const omitted=document.createElement('p');omitted.className='compact-note muted';omitted.textContent='컬럼 정의만 표시: '+detail.omitted_columns.join(', ');box.append(omitted);}
  parent.append(box);
  if(detail.error||!detail.sql)body.hidden=true;else table(body.id,detail.rows,null,{database:true});
  if(detail.sql){copy.type='button';copy.className='secondary';copy.textContent='조회 SQL 복사';copy.addEventListener('click',()=>task(copy,async()=>{await navigator.clipboard.writeText(detail.sql);notice('실제 조회에 사용한 SQL을 복사했습니다.');}));CodeHighlight.paint(sql,detail.sql,'dictionary_detail_rows.sql');sql.tabIndex=0;box.append(copy,sql);}
}
async function loadModelDictionary(){
  clearModelDictionary();const ticket=dictionaryRequest,stamp=modelDictionaryStamp(),variant=selectedMode('model-lifecycle-mode');dictionaryBusy=true;renderModelLifecycle();
  try{
    const result=await api('/api/models/dictionary?'+new URLSearchParams({variant}));
    if(ticket!==dictionaryRequest||stamp!==modelDictionaryStamp()||!person)return;
    dictionaryStamp=stamp;const root=$('model-dictionary-results');root.replaceChildren();
    const heading=document.createElement('h3');heading.textContent=objectDisplay(result.model_name);root.append(heading);
    if(result.naming){
      const info=document.createElement('div'),title=document.createElement('h4'),description=document.createElement('p'),example=document.createElement('code'),link=document.createElement('a');
      info.className='dictionary-naming';title.textContent='자동 생성 객체명 읽는 방법';description.textContent=result.naming.description;
      const actual=(result.object_details||[]).find(d=>d.code==='VC')||result.object_details?.[0];
      example.textContent=actual?result.naming.prefix+' + '+actual.code+' + '+result.model_name+' = '+actual.object_name:'DM$ + 객체 구분 코드 2자 + 지정 모델명';
      link.href=result.naming.documentation_url;link.target='_blank';link.rel='noopener noreferrer';link.textContent='Oracle 공식 모델 상세 뷰 설명';info.append(title,example,description,link);root.append(info);
    }
    for(const [index,section] of result.sections.entries()){
      const detail=document.createElement('details'),summary=document.createElement('summary'),description=document.createElement('p'),body=document.createElement('div');detail.open=index===0;
      summary.textContent=`${section.title} · ${section.view} · ${section.rows.length}행`;description.textContent=section.description;body.className='table-wrap';body.id='dictionary-result-'+section.key;
      const content=document.createElement('div');content.className='dictionary-section-body';
      content.append(description,body);detail.append(summary,content);root.append(detail);
      if(section.rows.length)table(body.id,section.rows,section.columns,{database:true});else{body.classList.add('empty');body.textContent=result.exists?section.empty:'모델이 없습니다. 최초 학습 후 다시 조회하세요.';}
      if(section.key==='views'||section.key==='generated_objects'){
        for(const [i,detail] of (result.object_details||[]).entries()){
          if((section.key==='views')===(detail.object_type==='VIEW'))renderDictionaryObject(content,detail,i);
        }
      }
    }
  }catch(error){clearModelDictionary();throw error;}
  finally{dictionaryBusy=false;renderModelLifecycle();}
}
on('query-model-dictionary','click',event=>task(event.currentTarget,loadModelDictionary));
on('model-lifecycle-mode','change',renderModelLifecycle);
on('model-add-file','change',()=>text('model-add-file-name',$('model-add-file').files[0]?.name||'새 CASE_ID · Y/TRAIN만 · 최대 5,000행 / 2 MiB'));
for(const [id,action,label] of [['model-initial','INIT','최초 학습'],['model-retrain','RETRAIN','전체 재학습']])on(id,'click',async event=>{const button=event.currentTarget,variant=selectedMode('model-lifecycle-mode');if(!await askConfirmation(action==='INIT'?`OML_BASIC_${variant}_MODEL을 PREPARED의 선택 방식·FIT_YN=Y TRAIN으로 처음 생성할까요? 모델 생성은 자동 커밋됩니다.`:`OML_BASIC_${variant}_MODEL을 현재 저장된 ${variant} · FIT_YN=Y TRAIN 전체로 다시 만듭니다.\n기존 모델은 삭제·재생성됩니다. 새 TRAIN은 먼저 적재하고 전처리 저장을 완료하세요.\n이 버튼은 데이터를 추가하거나 전처리를 다시 실행하지 않습니다. 진행할까요?`,{title:label,accept:'학습 실행',opener:button}))return;modelAction(button,async()=>{await api('/api/models/train',{variant,action});notice(label+' 완료 · TEST 평가와 같은 입력 예측을 비교하세요.');});});
on('model-delete','click',async event=>{const button=event.currentTarget,variant=selectedMode('model-lifecycle-mode');if(!await askConfirmation(`OML_BASIC_${variant}_MODEL 모델을 삭제할까요?\n학습·TEST·예측 테이블과 다른 모델은 유지됩니다. 모델 삭제는 롤백되지 않습니다.`,{title:'선택 모델 삭제 확인',accept:'모델 삭제',danger:true,opener:button}))return;modelAction(button,async()=>{const result=await api('/api/models/delete',{variant});notice(result.message);});});
document.querySelectorAll('[data-confirm]').forEach(button=>button.addEventListener('click',async()=>{const variant=button.dataset.confirm;if(!await askConfirmation(`${variant} 모델을 기본 예측 모델로 저장할까요? 4단계에서 다른 모델도 바로 선택할 수 있습니다.`,{title:'사용 모델 확정',accept:'확정 저장',opener:button}))return;modelAction(button,async()=>{await api('/api/models/confirm',{variant});predictionChoice=variant;notice('기본 예측 모델을 저장했습니다.');});}));
on('prediction-model-select','change',()=>{predictionChoice=selectedMode('prediction-model-select');resetPredictionResults();renderPredictionStorage();});
on('choose-prediction','click',event=>task(event.currentTarget,async()=>{
  const response=await fetch('/download/prediction.csv');selectedPrediction=new File([await response.blob()],'prediction.csv',{type:'text/csv'});
  const transfer=new DataTransfer();transfer.items.add(selectedPrediction);$('prediction-file').files=transfer.files;
  text('prediction-filename','기본 데이터 · '+selectedPrediction.name);await previewPrediction();
}));
on('prediction-file','change',()=>{selectedPrediction=null;$('prediction-preview-box').hidden=true;text('prediction-filename',$('prediction-file').files[0]?.name||'선택한 CSV가 없습니다.');});
on('preview-prediction','click',event=>task(event.currentTarget,previewPrediction));
on('close-prediction-preview','click',()=>$('prediction-preview-box').hidden=true);
on('prediction-import','submit',event=>{event.preventDefault();importPrediction(event.submitter,event.submitter?.id==='replace-prediction'?'replace':'initial');});
on('experiment','change',()=>task(null,async()=>{table('results',[]);if($('prediction-error'))$('prediction-error').hidden=true;text('result-state','실행 대기');await loadColumns();}));
on('run','click',async event=>{
  if(predictionRunning||modelBusy||predictionImporting||refreshing)return;
  const button=event.currentTarget,variant=selectedMode('prediction-model-select'),generation=sessionGeneration;
  if(!selectedPredictionModel())return;
  if(!await askConfirmation(variant+' 모델로 '+number(predictionStorage?.rows)+'행을 예측할까요? 성공하면 사용 모델도 '+variant+'로 저장합니다.',{title:'선택 모델로 예측 실행',accept:'예측 실행',opener:button}))return;
  if(generation!==sessionGeneration||!person)return;
  predictionChoice=variant;
  $('prediction-proof-return').hidden=true;
  predictionRunning=true;renderPredictionStorage();
  try{await task(button,async()=>{
  const experiment=$('experiment').value;let entry={time:date(new Date()),experiment:experimentLabels[experiment]},executionError=null;$('prediction-error').hidden=true;text('result-state','실행 중');
  try{const data=await api('/api/predictions/run',{experiment,variant});table('results',data.rows,[['case_id','CASE_ID'],['stock','종목'],['week_ending','기준 주 마감일'],['predicted','다음 주 매수·매도 신호'],['probability','예측 클래스 확률'],['actual','비교용 실제 신호']],{database:true});
    const same=previousPrediction&&previousPrediction.input===data.input_fingerprint,old=new Map((previousPrediction?.rows||[]).map(r=>[r.case_id,r]));
    const changed=same?data.rows.filter(r=>old.get(r.case_id)?.prediction!==r.prediction).length:null;
    const probabilityChanged=same?data.rows.filter(r=>Math.abs((old.get(r.case_id)?.probability??-1)-r.probability)>1e-9).length:null;
    entry={...entry,model:data.model_name,status:'완료',rows:data.rows.length,comparison:!previousPrediction?'첫 예측':!same?'입력이 달라 직접 비교하지 않음':`같은 입력 · 이전 대비 분류 ${changed}행 / 확률 ${probabilityChanged}행 변경`};
    if(data.verified){state.confirmed_variant=variant;state.confirmed_current=1;models.forEach(m=>m.is_confirmed=Number(m.variant===variant));}
    previousPrediction={input:data.input_fingerprint,rows:data.rows};text('result-state','완료');text('result-caption',data.model_name+' · '+data.rows.length+'행 · '+entry.comparison);$('prediction-proof-return').hidden=!data.verified;if(data.verified)notice('예측 실행 성공 · 단계별 작업 상태와 최종 현황을 확인하세요.');else text('result-state','결과 확인 필요');
  }catch(error){executionError=error;entry={...entry,status:'오류',rows:'—',comparison:error.message};text('prediction-error',error.message);table('results',[]);text('result-state','실행 오류');}
  history.unshift(entry);history=history.slice(0,20);table('history',history,[['time','시각'],['model','실행 모델'],['status','상태'],['rows','결과 행'],['comparison','이전 성공 실행과 비교']]);
  if(typeof syncPracticeEvidence==='function')await syncPracticeEvidence();
  if(executionError)throw executionError;
  });}finally{predictionRunning=false;renderPredictionStorage();}
});
function fontSize(value){const size=Math.max(14,Math.min(22,Number(value)||16));document.documentElement.style.setProperty('--size',size+'px');text('font-size',size);$('font-minus').disabled=size<=14;$('font-plus').disabled=size>=22;try{localStorage.setItem('oml-font-size-v2',size);}catch{}}
on('font-minus','click',()=>fontSize(Number($('font-size').value)-2));on('font-plus','click',()=>fontSize(Number($('font-size').value)+2));
async function start(){
  try{fontSize(localStorage.getItem('oml-font-size-v2')||16);}catch{fontSize(16);}
  authenticationPending=true;document.body.dataset.auth='checking';
  if($('auth-check'))$('auth-check').hidden=false;
  text('auth-check-message','로그인 상태를 확인하고 있습니다.');
  if($('auth-check-retry'))$('auth-check-retry').hidden=true;
  const track=$('auth-check')?.querySelector('.loading-track');if(track)track.hidden=false;
  const generation=sessionGeneration;
  try{
    const session=await api('/api/session');if(generation!==sessionGeneration)return;
    csrf=session.csrf;person=session.identity;identityConfigured=session.configured!==false;
    authenticationPending=false;renderPerson();
    if(mainWorkspace&&loginView)openIdentity();
    if(!person){if(session.session?.expired)endSession(true);return;}
    await refresh();
  }catch(error){
    if(authenticationPending){
      text('auth-check-message','로그인 상태를 확인하지 못했습니다. 연결을 확인한 뒤 다시 시도하세요.');
      if(track)track.hidden=true;
      if($('auth-check-retry'))$('auth-check-retry').hidden=false;
    }else{renderPerson();notice(error.message,true);}
  }
}
on('auth-check-retry','click',()=>start());
function revealCurrentStep(nav){
  const selected=nav?.querySelector('.workflow-tab[aria-current="step"]');if(!selected)return;
  const area=nav.getBoundingClientRect(),item=selected.getBoundingClientRect();
  if(item.left<area.left)nav.scrollLeft-=area.left-item.left;
  else if(item.right>area.right)nav.scrollLeft+=item.right-area.right;
}
function renderBasicWorkspace(){
  if(!basicWorkspace)return;
  document.body.dataset.page=page;
  document.querySelectorAll('[data-basic-panel]').forEach(panel=>panel.hidden=panel.dataset.basicPanel!==page);
  document.querySelectorAll('.basic-tabs [data-basic-tab]').forEach(link=>{
    if(link.dataset.basicTab===page)link.setAttribute('aria-current','step');else link.removeAttribute('aria-current');
  });
  revealCurrentStep(document.querySelector('.basic-tabs'));
}
let pendingBasicNavigation=null,basicSwitching=false;
function basicMutationBusy(){return activeMutations||modelBusy||predictionRunning||predictionImporting||importing||preparing;}
function flushBasicNavigation(){
  if(!basicWorkspace||!pendingBasicNavigation||refreshing||basicSwitching||basicMutationBusy())return;
  const next=pendingBasicNavigation;pendingBasicNavigation=null;return activateBasic(next.screen,next.push);
}
async function activateBasic(screen,push=true){
  if(!basicWorkspace||!basicScreens.includes(screen))return;
  if(basicMutationBusy()){
    pendingBasicNavigation=null;
    presentMessage('데이터 적재·수정 또는 모델 작업이 진행 중입니다. 완료 후 단계를 선택하세요.','info');
    if(!push)window.history.replaceState({basicScreen:page},'', '/basic#'+page);
    return;
  }
  if(refreshing||basicSwitching){pendingBasicNavigation={screen,push};return;}
  if(screen===page)return;
  basicSwitching=true;
  try{
    // 사용자가 단계를 바꿀 때만 한 번 이동합니다. 메시지·조회 완료로 다시 스크롤하지 않습니다.
    window.scrollTo?.({top:0,left:0,behavior:'instant'});
    page=screen;renderBasicWorkspace();
    if(push)window.history.pushState({basicScreen:screen},'', '/basic#'+screen);
    $('basic-'+screen)?.focus({preventScroll:true});
    if(person)await task(null,refresh,{feedback:false});
  }finally{basicSwitching=false;flushBasicNavigation();}
}
document.addEventListener('click',event=>{
  const link=event.target.closest('[data-basic-tab],[data-step-next]');
  if(!basicWorkspace||!link||event.ctrlKey||event.metaKey||event.shiftKey||event.altKey)return;
  event.preventDefault();activateBasic(link.dataset.basicTab||link.dataset.stepNext);
});
if(basicWorkspace){
  window.history.scrollRestoration='manual';
  renderBasicWorkspace();
  window.history.replaceState({basicScreen:page},'',location.href);
  window.addEventListener('popstate',event=>activateBasic(event.state?.basicScreen||location.hash.slice(1)||initialBasicScreen,false));
}
start();

window.addEventListener('resize',()=>{revealCurrentStep(document.querySelector('.basic-tabs'));});
