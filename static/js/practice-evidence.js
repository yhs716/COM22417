"use strict";
// 서버의 현재 DB 검증 결과만 표시합니다. 클릭 이력으로 성공을 만들지 않습니다.
let practiceEvidenceVersion=0,practiceEvidenceBusy=false,practiceEvidenceResult=null,practiceDetailOpener=null;
let practiceWorkInitialized=false;
const practiceSuccessBadges={home:'오브젝트 생성 성공',data:'학습자료 적재 성공',models:'모델생성 평가 성공',predictions:'모델예측 실행 성공'};
function proofNode(tag,className,value){
 const node=document.createElement(tag);if(className)node.className=className;
 if(value!==undefined)node.textContent=value;return node;
}
const practiceAssignmentTitles={basic:'기본과제',mission:'미션과제',creative:'창의과제'};
function practiceProgress(step){
 const checks=step.checks||[],completed=checks.filter(check=>check.success).length,total=checks.length;
 return {completed,total,remaining:total-completed,label:'성공 '+completed+'개 · 대기 '+(total-completed)+'개'};
}
function practiceStageBadge(step){return (step.success?'✓ ':'○ ')+(step.success?(practiceSuccessBadges[step.id]||step.badge):practiceProgress(step).label);}
function practicePanel(id){return $(basicWorkspace?'basic-'+id:'assignment-panel-'+id);}
function initializePracticeWork(){
 if(practiceWorkInitialized)return;practiceWorkInitialized=true;
 for(const id of ['home','data','models','predictions']){
  const panel=practicePanel(id);if(!panel)continue;
  const heading=panel.querySelector(id==='home'?(basicWorkspace?'.basic-object-panel>.section-heading':'.assignment-connection-panel>.assignment-section-heading'):'.section-heading');
  if(!heading)continue;
  heading.classList.add('practice-stage-heading');
  const box=proofNode('div','practice-stage-status'),button=proofNode('button','practice-step-stamp','확인 대기'),count=proofNode('small','practice-work-count','현황과 같은 기준으로 확인합니다.');
  box.dataset.practiceStage=id;button.type='button';button.disabled=true;button.dataset.proofStep=id;
  button.setAttribute('aria-haspopup','dialog');button.setAttribute('aria-controls','practice-detail-dialog');
  box.append(button,count);heading.append(box);
 }
}
function practiceDependency(stage,destination,label){
 const panel=practicePanel(stage);let link=panel?.querySelector('[data-practice-dependency="'+destination+'"]');
 if(!panel)return null;if(link)return link;
 link=proofNode('a','button secondary practice-dependency',label+' →');link.dataset.practiceDependency=destination;
 link.href=basicWorkspace?'/basic#'+destination:'#';link.dataset[basicWorkspace?'basicTab':'assignmentTab']=destination;
 const heading=panel.querySelector('.section-heading');heading?.after(link);return link;
}
function practiceTaskTarget(step,check){
 const custom=!basicWorkspace,button=(basic,other)=>$(custom?other:basic);
 if(step.id==='home'){
  if(custom&&assignmentKey==='mission')return {node:document.querySelector('[data-mission-schema="'+missionSelectionCurrent+'"]'),hint:'스키마 조회 → DATA·PREPARED·PREDICT·RUN 각 탭의 생성 SQL 전체 복사 → SQL Developer에서 F5 직접 실행 → 웹 새로고침으로 준비 자동 확인'};
  return custom?{node:$('assignment-check'),hint:'직접 SQL 생성·수정 후 SQL 실행 결과 연계'}:check.label.includes('테이블')?{node:$('initialize-basic'),hint:'테이블 생성으로 확인'}:{node:$('register-basic')?.closest('.actions'),group:true,hint:'프로시저 최초 등록 또는 다시 등록으로 확인'};
 }
 if(step.id==='data'){
  if(check.label==='학습 CSV 원본 적재')return {node:button('import-submit','assignment-import'),hint:'CSV 최초/교체 적재 후 원본 행 확인'};
  if(check.label==='객체·연결 준비')return {node:practiceDependency('data','home','객체·연결 준비 확인'),hint:'현황에서 테이블 3개와 RUN 준비'};
  return {node:button('prepare-data','assignment-prepare'),hint:check.label.startsWith('RAW')?'RAW를 선택해 전처리·학습/TEST 준비':'CLEAN을 선택해 전처리·학습/TEST 준비'};
 }
 if(step.id==='models'){
  if(check.label.includes('최신 모델 생성'))return {node:practicePanel('models')?.querySelector('.model-action-bar'),group:true,hint:check.label.split(' ')[0]+' 선택 → 최초 생성 또는 전체 다시 학습'+(custom?' → SQL 실행 결과 연계':'')};
  if(check.label==='기본 예측 모델 지정')return {node:$('model-comparison')?.querySelector('.model-actions th'),inside:true,hint:'RAW/CLEAN 중 하나를 기본 예측 모델로 지정'};
  return {node:button('query-models','assignment-evaluate'),hint:check.label==='같은 전체 TEST 비교'?'RAW/CLEAN의 TEST 전체 행을 같게 준비하고 비교':check.label.split(' ')[0]+' 모델의 TEST 평가 성공 확인'};
 }
 if(step.id==='predictions'){
  if(check.label==='모델 생성·평가 완료')return {node:practiceDependency('predictions','models','모델 생성·TEST 평가 확인'),hint:'모델 단계의 모든 성공 기준 완료'};
  if(check.label==='예측 CSV 입력 적재')return {node:button('prediction-import-submit','assignment-prediction-import'),hint:'예측 CSV 최초/교체 적재 후 입력 행 확인'};
  return {node:button('run','assignment-predict'),hint:'현재 입력·현재 모델로 예측을 실행한 실제 결과로 확인'};
 }
 return {};
}
function practiceTaskHost(target){
 const node=target.node;if(!node)return null;
 let anchor=target.group||target.inside?node:node.closest('.action-with-help');
 if(target.inside){
  anchor=node.querySelector(':scope>.practice-task-anchor');
  if(!anchor){anchor=proofNode('span','practice-task-anchor');anchor.append(...node.childNodes);node.append(anchor);}
 }
 if(!anchor){
  anchor=node.closest('.practice-action-slot');
  if(!anchor){anchor=proofNode('span','practice-action-slot');node.before(anchor);anchor.append(node);}
 }
 anchor.classList.add('practice-task-anchor');
 let host=anchor.querySelector(':scope>.practice-task-markers');
 if(!host){host=proofNode('span','practice-task-markers');host.setAttribute('aria-label','작업 상태');anchor.append(host);}
 return host;
}
function renderModeProgress(result){
 for(const group of document.querySelectorAll('.mode-choice[data-mode-stage]')){
  if(group.dataset.modeStage==='predictions')continue;
  const step=result?.steps.find(item=>item.id===group.dataset.modeStage);
  for(const button of group.querySelectorAll('.mode-option')){
   const checks=step?.checks.filter(check=>check.label.startsWith(button.value+' ')),done=checks?.filter(check=>check.success).length;
   button.dataset.state=checks?.length?(done===checks.length?'success':'pending'):'unchecked';
   button.querySelector('.mode-progress').textContent=checks?.length?(done===checks.length?'✓ 작업 완료':'성공 '+done+' · 대기 '+(checks.length-done)):'완료 상태 확인 전';
  }
 }
}
function renderPracticeWork(result=null){
 initializePracticeWork();
 if(typeof hideHelpTooltip==='function')hideHelpTooltip();renderModeProgress(result);
 document.querySelectorAll('.practice-task-markers').forEach(host=>{host.replaceChildren();host.hidden=true;});
 for(const box of document.querySelectorAll('[data-practice-stage]')){
  const step=result?.steps.find(item=>item.id===box.dataset.practiceStage),button=box.querySelector('button'),count=box.querySelector('small');
  box.dataset.state=step?(step.success?'success':'pending'):'unchecked';button.disabled=!step;button.textContent=step?practiceStageBadge(step):'확인 대기';
  button.setAttribute('aria-label',step?step.label+' · '+practiceStageBadge(step)+' · 세부 작업 보기':'현재 상태 확인 대기');
  count.textContent=step?practiceProgress(step).label+' · 전체 '+practiceProgress(step).total+'개':'현황과 같은 기준으로 확인합니다.';
  if(!step)continue;
  for(const [index,check] of (step.checks||[]).entries()){
   const target=practiceTaskTarget(step,check),host=practiceTaskHost(target);if(!host)continue;
   const status='작업 '+(index+1)+' · '+(check.success?'✓ 성공':'○ 대기');
   const marker=proofNode('button','practice-task-marker'),label=proofNode('strong','',(index+1)+' '+(check.success?'✓':'○'));
   marker.type='button';marker.dataset.proofStep=step.id;marker.dataset.proofCheck=String(index);marker.dataset.state=check.success?'success':'pending';
   marker.setAttribute('aria-haspopup','dialog');marker.setAttribute('aria-controls','practice-detail-dialog');
   marker.setAttribute('aria-label',step.label+' · '+status+' · '+check.label+' · 성공 기준 보기');
   const tip=proofNode('span','code-help-tooltip practice-task-tooltip',status+' · '+check.label+'\n'+target.hint+(check.detail?' · '+check.detail:''));
   tip.id='practice-tip-'+step.id+'-'+index;tip.setAttribute('role','tooltip');marker.setAttribute('aria-describedby',tip.id);
   marker.append(label,proofNode('span','',check.label));host.append(marker,tip);host.hidden=false;
  }
 }
}
async function syncPracticeEvidence(){
 if(!person||!$('practice-proof'))return;
 const version=practiceEvidenceVersion,generation=sessionGeneration,key=basicWorkspace?'basic':document.querySelector('.assignment-workspace')?.dataset.assignment;
 try{
  const result=await api('/api/practice/'+key+'/evidence');
  if(version!==practiceEvidenceVersion||generation!==sessionGeneration||!person)return;
  renderPracticeEvidence(result);
 }catch(error){if(version===practiceEvidenceVersion&&generation===sessionGeneration)clearPracticeEvidence('실행 후 상태 확인 실패 · 최종 현황을 다시 확인하세요.');}
}
function renderPracticeSeal(result=null){
 const seal=$('practice-seal'),complete=result?.complete===true;
 const label=complete?(practiceAssignmentTitles[result.assignment]||'실습')+' 성공':result?result.passed+' / 4 완료':'확인 필요';
 seal.replaceChildren();seal.setAttribute('aria-label',label+' · 세부 작업 보기');
 if(!complete){seal.textContent=label;return;}
 const top=proofNode('span','practice-seal-meta','OML · VERIFIED'),mark=proofNode('span','practice-seal-mark','✓'),caption=proofNode('span','practice-seal-caption','전 단계 검증 완료');
 for(const node of [top,mark,caption])node.setAttribute('aria-hidden','true');
 seal.append(top,mark,proofNode('strong','practice-seal-label',label),caption);
}
function clearPracticeEvidence(message='현재 상태를 다시 확인하세요.'){
 ++practiceEvidenceVersion;practiceEvidenceResult=null;closePracticeDetail(false);const root=$('practice-proof');if(!root)return;
 renderPracticeWork();
 $('practice-seal').disabled=true;$('practice-detail-groups')?.replaceChildren();text('practice-detail-summary','');
 text('practice-proof-topic','현재 과제의 기능 실행 결과를 확인합니다.');
 root.dataset.state='pending';renderPracticeSeal();text('practice-proof-status',message);
 text('practice-proof-student',person?person.name+' · '+person.student_id:'로그인 후 확인');
 text('practice-proof-owner',person?.db_user||'—');text('practice-proof-time','확인 전');
 $('practice-capture-guide').hidden=true;
 const row=proofNode('tr'),cell=proofNode('td','',message);cell.colSpan=3;row.append(cell);$('practice-proof-steps').replaceChildren(row);
 $('practice-verify').disabled=!person||practiceEvidenceBusy;
}
function renderPracticeEvidence(result){
 const root=$('practice-proof');if(!root||!person||!result)return;
 if(result.student?.student_id!==person.student_id||result.student?.db_user!==person.db_user)return;
 ++practiceEvidenceVersion;closePracticeDetail(false);practiceEvidenceResult=result;root.dataset.state=result.complete?'success':'pending';
 $('practice-seal').disabled=false;
 text('practice-proof-topic',result.title+(result.mission_title?' · '+result.mission_title:''));
 text('practice-proof-student',result.student.name+' · '+result.student.student_id);text('practice-proof-owner',result.student.db_user);
 text('practice-proof-time',new Date(result.checked_at).toLocaleString('ko-KR'));
 renderPracticeSeal(result);
 const checks=result.steps.flatMap(step=>step.checks||[]),completed=checks.filter(check=>check.success).length;
 text('practice-proof-status',result.complete?'모든 단계 검증 완료':result.passed+'/4 단계 완료'+(checks.length?' · 세부 작업 '+completed+'/'+checks.length+' 완료 · '+(checks.length-completed)+'개 남음':' · 단계를 선택해 남은 작업을 확인하세요.'));
 const rows=$('practice-proof-steps');rows.replaceChildren();
 for(const [index,step] of result.steps.entries()){
  const row=proofNode('tr'),heading=proofNode('th'),link=proofNode('a','',String(index+1).padStart(2,'0')+' '+step.label);
  heading.scope='row';link.href=result.assignment==='basic'?'/basic#'+step.id:'#';link.dataset[result.assignment==='basic'?'basicTab':'assignmentTab']=step.id;
  heading.append(link);const detail=proofNode('td','practice-proof-detail'),status=proofNode('td'),checks=step.checks||[],remaining=checks.filter(check=>!check.success);
  if(!step.success&&checks.length){
   detail.append(proofNode('strong','','남은 작업 '+remaining.length+'개'),proofNode('span','',remaining.slice(0,2).map(check=>check.label).join(' · ')+(remaining.length>2?' 외 '+(remaining.length-2)+'개':'')));
  }else detail.textContent=step.detail;
  const badge=practiceStageBadge(step);
  const button=proofNode('button','practice-step-stamp',badge);button.type='button';button.dataset.proofStep=step.id;
  button.setAttribute('aria-haspopup','dialog');button.setAttribute('aria-controls','practice-detail-dialog');button.setAttribute('aria-label',step.label+' · '+badge+' · 세부 작업 보기');
  row.dataset.state=step.success?'success':'pending';status.append(button);
  if(checks.length&&!step.success)status.append(proofNode('small','practice-work-count','전체 '+checks.length+'개 · 클릭해 상세 확인'));
  row.append(heading,detail,status);rows.append(row);
 }
 $('practice-capture-guide').hidden=!result.complete;$('practice-verify').disabled=practiceEvidenceBusy;
 renderPracticeWork(result);
}
async function verifyPracticeEvidence(){
 if(!person||practiceEvidenceBusy)return;
 if(basicWorkspace?basicMutationBusy()||refreshing:typeof assignmentBusy!=='undefined'&&(assignmentBusy||assignmentPhase==='loading'))return;
 practiceEvidenceBusy=true;clearPracticeEvidence('현재 DB 상태와 성공 결과를 확인하고 있습니다.');
 const version=practiceEvidenceVersion,generation=sessionGeneration,key=basicWorkspace?'basic':document.querySelector('.assignment-workspace')?.dataset.assignment;
 try{
  const result=await api('/api/practice/'+key+'/evidence');
  if(version!==practiceEvidenceVersion||generation!==sessionGeneration||!person)return;
  renderPracticeEvidence(result);
 }catch(error){
  if(generation!==sessionGeneration)return;
  clearPracticeEvidence('최종 확인 실패 · 다시 확인하세요.');operationNotice(error);
 }finally{practiceEvidenceBusy=false;if($('practice-verify'))$('practice-verify').disabled=!person;}
}
on('practice-verify','click',verifyPracticeEvidence);

function closePracticeDetail(restore=true){
 const opener=practiceDetailOpener;practiceDetailOpener=null;
 const dialog=$('practice-detail-dialog');if(dialog?.open)HelpWindow.close(dialog);
 if(restore&&person&&opener?.isConnected)opener.focus({preventScroll:true});
}
function openPracticeDetail(id='',focusCheck=null){
 const result=practiceEvidenceResult;
 if(!result||!person||result.student.student_id!==person.student_id||result.student.db_user!==person.db_user)return;
 const steps=id?result.steps.filter(step=>step.id===id):result.steps;if(!steps.length)return;hideHelpTooltip();
 const checks=steps.flatMap(step=>step.checks||[]),completed=checks.filter(check=>check.success).length;
 text('practice-detail-title',id?steps[0].label+' · 세부 작업':'전체 실습 · 세부 작업');
 text('practice-detail-summary',checks.length?completed+'/'+checks.length+' 완료 · '+(checks.length-completed)+'개 남음':'현재 확인 결과');
 const groups=$('practice-detail-groups');groups.replaceChildren();
 for(const step of steps){
  const section=proofNode('section','practice-check-group');
  if(!id)section.append(proofNode('h3','',step.label));
  const list=proofNode('ul','practice-check-list');
  for(const [index,check] of (step.checks||[]).entries()){
   const item=proofNode('li'),state=proofNode('span','practice-check-state','작업 '+(index+1)+' · '+(check.success?'✓ 성공':'○ 대기')),body=proofNode('div');
   if(step.id===id&&index===focusCheck)item.dataset.focused='true';
   item.dataset.state=check.success?'success':'pending';body.append(proofNode('strong','',check.label));
   if(check.detail)body.append(proofNode('p','',check.detail));
   item.append(state,body);list.append(item);
  }
  section.append(list);if(!step.checks?.length)section.append(proofNode('p','',step.detail));groups.append(section);
 }
 const go=$('practice-detail-go');go.hidden=!id;delete go.dataset.basicTab;delete go.dataset.assignmentTab;
 if(id){go.href=result.assignment==='basic'?'/basic#'+id:'#';go.dataset[result.assignment==='basic'?'basicTab':'assignmentTab']=id;}
 practiceDetailOpener=document.activeElement;HelpWindow.open($('practice-detail-dialog'),{reset:true});$('close-practice-detail').focus({preventScroll:true});
}
on('practice-seal','click',()=>openPracticeDetail());
document.addEventListener('click',event=>{const button=event.target.closest('[data-proof-step]');if(button&&!button.disabled)openPracticeDetail(button.dataset.proofStep,button.dataset.proofCheck===undefined?null:Number(button.dataset.proofCheck));});
on('close-practice-detail','click',()=>closePracticeDetail());
on('practice-detail-go','click',event=>{
 const id=event.currentTarget.dataset.basicTab||event.currentTarget.dataset.assignmentTab,assignment=practiceEvidenceResult?.assignment;
 closePracticeDetail(false);
 requestAnimationFrame(()=>document.querySelector(assignment==='basic'?'#basic-workflow [data-basic-tab="'+id+'"]':'.assignment-tabs [data-assignment-tab="'+id+'"]')?.focus({preventScroll:true}));
});
on('practice-detail-dialog','close',()=>{const opener=practiceDetailOpener;practiceDetailOpener=null;if(person&&opener?.isConnected)opener.focus({preventScroll:true});});

document.addEventListener('click',event=>{if(event.target.closest('[data-basic-tab],[data-assignment-tab],[data-step-next]')&&$('practice-detail-dialog')?.open)closePracticeDetail(false);});
renderPracticeWork();
