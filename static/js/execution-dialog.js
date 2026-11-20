// [CODING-FLOW] 같은 구조의 호출 흐름에서 실제 파일과 연속된 원본 구간을 탐색합니다.
let executionOpener=null,executionRequest=0,executionFlow=null,executionStage=null,executionItem=null,executionFile=null;
const executionLineOffsets=new Map();
// [RUNTIME-SQL] Only bounded successful query traces, in memory for this account/session.
const codingQueryTraces=new Map();let codingTraceVersion=0,codingTraceTicket=0;
function codingTraceKey(values){
  if(!person?.db_user||!['basic','mission'].includes(values.assignment)||!['data','prepared-data','prediction-data'].includes(values.operation))return '';
  const key=[sessionGeneration,person.db_user,values.assignment,values.assignment==='mission'&&typeof missionSelectionCurrent!=='undefined'?missionSelectionCurrent:'',values.operation];
  if(values.operation==='prepared-data')key.push(values.variant||'RAW',values.source_kind||'ALL');
  if(values.assignment==='basic'&&values.operation==='data')key.push(values.use_yn||'ALL',values.split||'ALL');
  return JSON.stringify(key);
}
function captureCodingQuery(path,body){
  const url=new URL(path,location.origin),route=url.pathname,mission=route.match(/^\/api\/assignments\/(mission|creative)\/([^/]+)$/);
  const operation=({'/api/data':'data','/api/data/prepared':'prepared-data','/api/predictions/data':'prediction-data'})[route]||mission?.[2];
  const assignment=mission?.[1]||'basic',values={operation,assignment};
  for(const name of ['variant','source_kind','use_yn','split'])values[name]=body&&!(body instanceof FormData)?body[name]:url.searchParams.get(name);
  const key=codingTraceKey(values);
  if(!key){
    if(body!==undefined&&!route.startsWith('/api/identity')&&!route.startsWith('/api/session')){codingQueryTraces.clear();++codingTraceVersion;}
    return null;
  }
  const context={key,version:codingTraceVersion,ticket:++codingTraceTicket,owner:person.db_user};
  codingQueryTraces.delete(key);codingQueryTraces.set(key,{ticket:context.ticket,records:[]});
  while(codingQueryTraces.size>8)codingQueryTraces.delete(codingQueryTraces.keys().next().value);
  return context;
}
function rememberCodingQuery(context,data){
  if(!context||context.version!==codingTraceVersion||context.owner!==person?.db_user||codingQueryTraces.get(context.key)?.ticket!==context.ticket)return;
  const records=[];let size=0;
  for(const entry of data.trace||[]){
    // Keep the executed statement intact. Never collect CSV batch values or procedural OUT values.
    const sql=entry.rendered_sql,plain=typeof sql==='string'?sql.replace(/--[^\n]*|\/\*[\s\S]*?\*\//g,'').trim():'';
    if(entry.status!=='success'||entry.batch_count!==undefined||!/^sql\/queries\/[a-z_]+\.sql$/.test(entry.path||'')||!/^SELECT\b/i.test(plain)||sql.length>32000)continue;
    const tokens=sql.match(/'(?:''|[^'])*'|"(?:""|[^"])*"|--[^\n]*|\/\*[\s\S]*?\*\/|:[A-Za-z][A-Za-z0-9_]*/g)||[];
    if(tokens.some(token=>token.startsWith(':'))||sql.includes('{{'))continue;
    if(size+sql.length>64000||records.length>=16)break;
    records.push({path:entry.path,sql,at:entry.at||''});size+=sql.length;
  }
  codingQueryTraces.set(context.key,{ticket:context.ticket,records,owner:context.owner});
}
function addExecutedCodingQueries(flow,values){
  const history=codingQueryTraces.get(codingTraceKey(values)),stage=flow?.stages.find(entry=>entry.id==='sql');
  if(!history?.records.length||!stage||!/^[A-Z][A-Z0-9_$#]{0,29}$/.test(history.owner))return flow;
  const allowed=new Set(stage.items.filter(item=>item.origin==='source').map(item=>item.path)),owner=history.owner;
  for(const [index,record] of history.records.entries()){
    if(!allowed.has(record.path))continue;
    const id='sql-executed-'+index,path='마지막 실제 조회 · '+record.path;
    // Account guard is added for F5 reuse. The recorded SQL itself is not rewritten.
    const content='-- 마지막 실제 조회 기록 · '+record.at+'\n-- 실행 당시 원문 · 다시 실행하면 현재 DB를 조회합니다.\n'+
      'WHENEVER SQLERROR EXIT SQL.SQLCODE ROLLBACK\nBEGIN\n'+
      "  IF SYS_CONTEXT('USERENV', 'SESSION_USER') <> '"+owner+"'\n"+
      "     OR SYS_CONTEXT('USERENV', 'CURRENT_SCHEMA') <> '"+owner+"' THEN\n"+
      "    RAISE_APPLICATION_ERROR(-20030, '발급 계정 "+owner+"으로 접속하세요.');\n  END IF;\nEND;\n/\n"+
      record.sql.trim().replace(/;$/,'')+'\n;\n';
    flow.files[id]={id,path,origin:'generated',kind:'sql-generated',content,line_count:content.split('\n').length};
    stage.items.push({id,file_id:id,title:'마지막 실제 조회 · '+record.path.split('/').at(-1),path,origin:'generated',kind:'sql-generated',line:null,end_line:null,runtime_kind:'executed',source_path:record.path,role:'같은 계정·미션·조회 조건의 성공 기록 · '+record.at});
  }
  return flow;
}
function codingSourceKind(item){
  return item.runtime_kind==='selected'?'현재 선택값 · 실행용 SQL · 미실행':item.runtime_kind==='executed'?'마지막 실제 조회 기록':item.origin==='generated'?'생성 예제 · 실제 파일과 구분':'실제 파일 전체';
}
// [HELP-TOOLTIP] popover는 브라우저 top layer에서 표시되어 조상 overflow/stacking에 잘리지 않습니다.
let helpTooltip=null,helpTooltipButton=null;
function hideHelpTooltip(){
  if(helpTooltip?.matches(':popover-open'))helpTooltip.hidePopover();
  helpTooltip=null;helpTooltipButton=null;
}
function showHelpTooltip(button){
  const tooltip=button.nextElementSibling;
  if(!tooltip?.classList.contains('code-help-tooltip')||!tooltip.showPopover)return;
  if(helpTooltipButton===button)return;
  hideHelpTooltip();tooltip.setAttribute('popover','manual');tooltip.showPopover();
  helpTooltip=tooltip;helpTooltipButton=button;
  positionHelpTooltip();
}
function positionHelpTooltip(){
  if(!helpTooltipButton)return;
  const anchor=helpTooltipButton.getBoundingClientRect(),box=helpTooltip.getBoundingClientRect(),gap=8;
  if(anchor.bottom<0||anchor.top>innerHeight||anchor.right<0||anchor.left>innerWidth){hideHelpTooltip();return;}
  helpTooltip.style.left=Math.max(gap,Math.min(helpTooltipButton.matches('.practice-task-marker')?anchor.left:anchor.right-box.width,innerWidth-box.width-gap))+'px';
  const below=anchor.bottom+gap,above=anchor.top-box.height-gap;
  helpTooltip.style.top=Math.max(gap,Math.min(below+box.height<=innerHeight-gap?below:above,innerHeight-box.height-gap))+'px';
}
document.addEventListener('pointerover',event=>{const button=event.target.closest('.code-help,.practice-task-marker');if(button)showHelpTooltip(button);});
document.addEventListener('pointerout',event=>{if(helpTooltipButton?.contains(event.target)&&!helpTooltipButton.contains(event.relatedTarget)&&!helpTooltipButton.matches(':focus-visible'))hideHelpTooltip();});
document.addEventListener('focusin',event=>{if(event.target.matches('.code-help,.practice-task-marker'))showHelpTooltip(event.target);});
document.addEventListener('focusout',event=>{if(event.target===helpTooltipButton&&!helpTooltipButton.matches(':hover'))hideHelpTooltip();});
document.addEventListener('keydown',event=>{if(event.key==='Escape')hideHelpTooltip();});
document.addEventListener('click',event=>{if(event.target.closest('[data-basic-tab],[data-assignment-tab],.mode-option'))hideHelpTooltip();});
document.addEventListener('scroll',positionHelpTooltip,true);
window.addEventListener('resize',hideHelpTooltip);
function resetCodingFlow(){
  executionFlow=null;executionStage=null;executionItem=null;executionFile=null;executionLineOffsets.clear();
  for(const id of ['execution-flow','execution-items','execution-code','execution-code-source','execution-code-role','execution-apply-steps','execution-apply-details','execution-verify-code'])$(id)?.replaceChildren();
  $('execution-stage-detail').hidden=true;$('execution-source-panel').hidden=true;
  $('execution-apply').hidden=true;$('execution-apply').open=false;$('execution-apply-command').hidden=true;$('execution-apply-command').open=false;
  $('execution-manual-note').hidden=true;text('execution-manual-note','');
  for(const id of ['execution-copy-state','execution-flow-status','execution-warning','execution-apply-summary','execution-apply-owner','execution-mode'])text(id,'');
}
function clearCodingHelp(){codingQueryTraces.clear();++codingTraceVersion;hideHelpTooltip();++executionRequest;HelpWindow.closeAll();resetCodingFlow();}
function codingNode(tag,className,value){
  const element=document.createElement(tag);if(className)element.className=className;
  if(value!==undefined&&value!==null)element.textContent=String(value);return element;
}
function codeBlock(parent,title,value,open=false,path=''){
  if(!value)return;
  const detail=codingNode('details'),summary=codingNode('summary','',title),pre=codingNode('pre'),copy=codingNode('button','secondary','이 구간 복사');
  detail.open=open;CodeHighlight.paint(pre,value,path);pre.tabIndex=0;copy.type='button';
  copy.addEventListener('click',async()=>{
    try{await navigator.clipboard.writeText(value);text('execution-copy-state','복사했습니다.');}
    catch{text('execution-copy-state','코드를 선택해 Ctrl+C로 복사하세요.');}
  });
  detail.append(summary,copy,pre);parent.append(detail);
}
function flowSourceLocation(item){
  const path=item.path||'생성된 실행 예제',line=Number(item.line),end=Number(item.end_line);
  return path+(line>0?':'+line+(end>line?'–'+end:''):'');
}
function keepFlowButtonVisible(button){
  const track=$('execution-flow'),item=button.getBoundingClientRect(),box=track.getBoundingClientRect();
  if(item.left<box.left)track.scrollLeft-=box.left-item.left+4;
  else if(item.right>box.right)track.scrollLeft+=item.right-box.right+4;
}
function flowFile(item){return executionFlow?.files?.[item.file_id];}
function flowItemRange(item){
  const file=flowFile(item);if(!file)return {start:0,end:0};
  if(item.origin!=='source')return {start:0,end:file.content.length};
  let offsets=executionLineOffsets.get(file.id);
  if(!offsets){
    offsets=[0];let index=-1;
    while((index=file.content.indexOf('\n',index+1))!==-1)offsets.push(index+1);
    executionLineOffsets.set(file.id,offsets);
  }
  return {start:offsets[item.line-1]??0,end:offsets[item.end_line]===undefined?file.content.length:offsets[item.end_line]-1};
}
function flowItemContent(item){
  const file=flowFile(item),range=flowItemRange(item);return file?.content.slice(range.start,range.end)||'';
}
function codingTextRange(start,end){
  const pre=$('execution-code'),walker=document.createTreeWalker(pre,NodeFilter.SHOW_TEXT);
  let node,offset=0,first,last;
  while((node=walker.nextNode())){
    const next=offset+node.length;
    if(!first&&start<next)first={node,offset:start-offset};
    if(end<=next){last={node,offset:end-offset};break;}
    offset=next;
  }
  if(!first||!last)return null;
  const range=document.createRange();range.setStart(first.node,first.offset);range.setEnd(last.node,last.offset);return range;
}
function focusCodingSource(item){
  const pre=$('execution-code'),file=flowFile(item);
  // 같은 파일에서는 구문 DOM을 다시 만들지 않습니다. 이전 강조만 해제합니다.
  pre.querySelectorAll('.code-source-focus').forEach(mark=>mark.replaceWith(...mark.childNodes));pre.normalize();
  let {start,end}=flowItemRange(item);
  if(item.focus_text){
    const found=file.content.indexOf(item.focus_text,start);
    if(found>=start&&found+item.focus_text.length<=end){start=found;end=found+item.focus_text.length;}
  }
  const range=codingTextRange(start,end);
  let mark=null;
  if(range&&item.origin==='source'){
    mark=document.createElement('span');mark.className='code-source-focus';
    if(item.focus_text)mark.classList.add('code-button-focus');
    mark.dataset.sourceLine=String(item.line);mark.append(range.extractContents());range.insertNode(mark);
  }
  requestAnimationFrame(()=>{
    if(executionItem!==item||executionFile!==file.id)return;
    pre.scrollLeft=0;
    if(mark){const box=pre.getBoundingClientRect(),r=mark.getBoundingClientRect();pre.scrollTop+=r.top-box.top-24;}
    else pre.scrollTop=0;
  });
}
function selectFlowItem(id){
  const item=executionStage?.items.find(entry=>entry.id===id);if(!item)return;
  const file=flowFile(item);if(!file)return;
  executionItem=item;
  $('execution-items').querySelectorAll('[data-flow-item]').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.flowItem===id)));
  $('execution-source-panel').hidden=false;$('execution-source-panel').dataset.sourceKind=executionStage.id==='sql'?'sql':'source';
  text('execution-code-title',file.origin==='source'?file.path.split('/').at(-1):item.title);
  const language=({'html':'HTML · Jinja','javascript':'JavaScript','python':'Python','sql':'SQL · PL/SQL','sql-generated':'SQL · PL/SQL','powershell':'PowerShell'})[file.kind]||'';
  text('execution-source-kind',codingSourceKind(item)+(language?' · '+language:''));
  text('execution-code-source',flowSourceLocation(item)+(file.origin==='source'?' · 전체 '+file.line_count+'행':''));
  text('execution-code-role',item.runtime_kind?item.role:item.title+(item.role?' · '+item.role:''));$('execution-code-role').hidden=false;
  const pre=$('execution-code');
  if(executionFile!==file.id){
    CodeHighlight.paint(pre,file.content,file.path);
    executionFile=file.id;pre.dataset.fileId=file.id;pre.dataset.sourceKind=file.kind;
  }
  pre.setAttribute('aria-label',file.path+' 파일 전체 · '+item.title);
  pre.dataset.sourcePath=file.path;pre.dataset.sourceLine=String(item.line||'');pre.dataset.sourceEndLine=String(item.end_line||'');
  focusCodingSource(item);text('execution-copy-state','');
}
function selectFlowStage(id,itemId){
  const stage=executionFlow?.stages.find(entry=>entry.id===id);if(!stage)return;
  executionStage=stage;executionItem=null;
  $('execution-flow').querySelectorAll('[data-flow-stage]').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.flowStage===id)));
  const active=[...$('execution-flow').querySelectorAll('[data-flow-stage]')].find(button=>button.dataset.flowStage===id);
  if(active)keepFlowButtonVisible(active);
  $('execution-stage-detail').hidden=false;$('execution-stage-detail').dataset.flowKind=id==='sql'?'sql':'source';
  text('execution-stage-title',stage.label+' · '+stage.technology);
  const groups=new Map();
  for(const item of stage.items){if(!groups.has(item.file_id))groups.set(item.file_id,[]);groups.get(item.file_id).push(item);}
  text('execution-stage-count',stage.items.length?groups.size+'개 파일·예제 / '+stage.items.length+'개 구간':'참여 없음');
  text('execution-stage-summary',stage.summary||'');$('execution-stage-summary').hidden=!stage.items.length||stage.summary===stage.items[0].title;
  $('execution-items').replaceChildren();$('execution-items').scrollTop=0;$('execution-source-panel').hidden=true;
  $('execution-stage-empty').hidden=stage.items.length>0;
  text('execution-stage-empty',stage.items.length?'':(stage.summary||'이 작업에서는 이 단계를 거치지 않습니다.'));
  for(const [fileId,items] of groups){
    const file=flowFile(items[0]),group=codingNode('details','coding-file-group'),summary=codingNode('summary','coding-file-heading');
    group.open=true;group.dataset.fileId=fileId;summary.dataset.flowFile=fileId;
    const heading=codingNode('span','coding-file-label');
    heading.append(codingNode('strong','',file.origin==='source'?file.path.split('/').at(-1):items[0].runtime_kind?(items[0].runtime_kind==='selected'?'런타임 · ':'실제 조회 · ')+items[0].source_path.split('/').at(-1):'생성 예제 · '+items[0].title),
                   codingNode('small','',file.path+' · '+items.length+'개 구간'));
    summary.append(heading);group.append(summary);
    const children=codingNode('div','coding-file-items');
    for(const item of items){
      const button=codingNode('button','secondary coding-flow-item');button.type='button';
      button.dataset.flowItem=item.id;button.setAttribute('aria-pressed','false');button.setAttribute('aria-controls','execution-source-panel');
      const label=codingNode('span','coding-item-label');
      label.append(codingNode('strong','',item.runtime_kind?codingSourceKind(item):item.title),codingNode('small','',item.origin==='source'?item.line+(item.end_line>item.line?'–'+item.end_line:'')+'행':item.runtime_kind?'SQL Developer F5':'파일 원문과 별도 생성'));
      button.append(label);children.append(button);
    }
    group.append(children);$('execution-items').append(group);
  }
  if(stage.items.length)selectFlowItem(stage.items.some(item=>item.id===itemId)?itemId:stage.items[0].id);
}

function renderCodingFlow(flow){
  if(!flow||!Array.isArray(flow.stages)||!flow.stages.length)throw new Error('호출 흐름을 불러오지 못했습니다. 화면을 새로고침한 뒤 다시 열어 주세요.');
  executionFlow=flow;
  $('execution-dialog').dataset.flowMode=flow.mode||'web-execution';
  text('execution-mode',flow.mode_label||({'web-execution':'화면 실행 흐름','local-preview':'파일 미리보기 흐름','manual-guide':'직접 실행 SQL 가이드'})[flow.mode]||'호출 흐름');
  text('execution-flow-status',flow.summary||'각 단계를 선택하면 호출 순서에 따른 파일과 소스를 확인할 수 있습니다.');
  for(const [index,stage] of flow.stages.entries()){
    const cell=codingNode('div','coding-flow-step'),button=codingNode('button','secondary coding-flow-stage');button.type='button';
    button.dataset.flowStage=stage.id;button.dataset.flowKind=stage.id==='sql'?'sql':'source';
    button.dataset.flowEmpty=String(!stage.items.length);button.setAttribute('aria-pressed','false');button.setAttribute('aria-controls','execution-stage-detail');
    button.append(codingNode('span','coding-stage-number',String(index+1).padStart(2,'0')),codingNode('strong','',stage.label),codingNode('span','coding-stage-technology',stage.technology),codingNode('span','coding-stage-size',stage.items.length?stage.items.length+'개 소스':'참여 없음'));
    cell.append(button);
    if(index<flow.stages.length-1){const arrow=codingNode('span','coding-flow-arrow','→');arrow.setAttribute('aria-hidden','true');cell.append(arrow);}
    $('execution-flow').append(cell);
  }
  const first=flow.stages.find(stage=>stage.items.some(item=>item.id===flow.initial_item))||flow.stages.find(stage=>stage.items.length)||flow.stages[0];
  selectFlowStage(first.id,flow.initial_item);
}
function renderCodingApplication(result){
  const application=result.application||{},steps=application.steps||[];
  text('execution-apply-title',application.title||'수정 후 적용 방법');
  text('execution-apply-summary',application.summary||'');
  text('execution-apply-owner',application.owner?'DB 계정 · '+application.owner:'');
  $('execution-apply-owner').hidden=!application.owner;
  for(const [index,step] of steps.entries()){
    const item=codingNode('li'),body=codingNode('div');
    body.append(codingNode('strong','',application.step_titles?.[index]||'단계 '+(index+1)),codingNode('p','',step));
    item.append(codingNode('span','coding-apply-number',index+1),body);
    $('execution-apply-steps').append(item);
  }
  $('execution-apply-steps').hidden=!steps.length;
  text('execution-warning',application.caution||'');$('execution-warning').hidden=!application.caution;
  for(const note of application.details||[]){
    const detail=codingNode('details','coding-apply-detail');
    detail.append(codingNode('summary','',note.title),codingNode('p','',note.text));
    $('execution-apply-details').append(detail);
  }
  $('execution-apply-command').hidden=!application.command;
  $('execution-apply-command').querySelector('code').textContent=application.command||'';
  text('execution-command-title',application.command_title||'터미널로 적용하기');
  text('execution-command-note',application.command_note||'');
  codeBlock($('execution-verify-code'),application.verification_title||'DB 반영 확인 SQL',application.verification,false,'example.sql');
  $('execution-apply').hidden=!steps.length;
}
function codingTrigger(button){
  if(!button.classList.contains('code-help'))return button;
  return button.closest('.action-with-help')?.querySelector('button:not(.code-help),input[type="submit"],a')||button;
}
async function openExecution(button){
  hideHelpTooltip();
  if(!person){openIdentity();return;}
  const assignment=document.querySelector('[data-assignment]')?.dataset.assignment||'basic';
  const manual=button.hasAttribute('data-manual-action');
  if(manual&&button.disabled)return;
  executionOpener=button;const ticket=++executionRequest,dialog=$('execution-dialog'),trigger=codingTrigger(button);
  const operation=button.dataset.manualAction||button.dataset.code||button.dataset.execution;
  const preparing=['prepare','prepared-data','clear-prepared'].includes(operation);
  const variant=button.dataset.variant||(assignment==='basic'?(preparing?selectedMode('preparation-mode'):['initial-train','retrain','append-train','delete-model','model-dictionary'].includes(operation)?selectedMode('model-lifecycle-mode'):operation==='predict'?selectedMode('prediction-model-select'):operation==='confirm'?selectedMode('model-lifecycle-mode'):'RAW'):(preparing?selectedMode('assignment-preparation-mode'):operation==='predict'?selectedMode('assignment-predict-mode'):selectedMode('assignment-mode')))||'RAW';
  const triggerLabel=(trigger.textContent||trigger.getAttribute('aria-label')||'').trim().replace(/\s+/g,' ');
  const values={operation,assignment,variant,use_yn:$('filter-use')?.value||'ALL',split:$('filter-split')?.value||'ALL',source_kind:$(assignment==='basic'?'prepared-source-kind':'assignment-prepared-source-kind')?.value||'TRAIN',trigger_id:trigger.id||'',trigger_label:triggerLabel,page:basicWorkspace?page:(document.body.dataset.page||'')};
  if(assignment==='mission'&&typeof missionSelectionCurrent!=='undefined')values.mission=missionSelectionCurrent;
  resetCodingFlow();text('execution-title',(triggerLabel&&triggerLabel!=='?'?triggerLabel:'코드')+' · 코딩도움말');
  text('execution-context',({'basic':'기본과제','mission':'미션과제','creative':'창의과제'})[assignment]+' · '+variant);
  if(manual){$('execution-manual-note').hidden=false;text('execution-manual-note','아래 구문을 복사하여 발급 계정 '+person.db_user+'의 실제 DB에 접속한 SQL Developer에서 전체 F5로 실행하세요. 완료 후 SQL 실행 결과 연계를 누르세요.');}
  text('execution-flow-status','버튼의 호출 흐름과 소스를 불러오는 중…');
  document.querySelector('.coding-flow-workspace').setAttribute('aria-busy','true');HelpWindow.open(dialog,{reset:true});dialog.scrollTop=0;
  try{
    const result=await api('/api/coding-help?'+new URLSearchParams(values));
    if(ticket!==executionRequest||(!dialog.open&&!HelpWindow.isMinimized(dialog)))return;
    const actionLabel=result.flow?.trigger?.label||(triggerLabel&&triggerLabel!=='?'?triggerLabel:result.title);
    text('execution-title',actionLabel+' · 코딩도움말');
    const context=result.flow?.context;
    if(context)text('execution-context',context);
    renderCodingFlow(addExecutedCodingQueries(result.flow,values));renderCodingApplication(result);
    if(manual)selectFlowStage('sql');
    $('execution-flow').scrollLeft=0;dialog.scrollTop=0;
  }catch(error){
    if(ticket!==executionRequest)return;
    text('execution-flow-status',error.message);
  }finally{
    if(ticket===executionRequest)document.querySelector('.coding-flow-workspace').setAttribute('aria-busy','false');
  }
}
function codingFlowKeys(event,selector,select){
  if(!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','Home','End'].includes(event.key))return;
  const current=event.target.closest(selector);if(!current)return;
  const buttons=[...current.parentElement.closest('[role="group"]').querySelectorAll(selector)].filter(button=>button.getClientRects().length),index=buttons.indexOf(current);
  const next=event.key==='Home'?0:event.key==='End'?buttons.length-1:(index+(['ArrowLeft','ArrowUp'].includes(event.key)?-1:1)+buttons.length)%buttons.length;
  event.preventDefault();buttons[next].focus({preventScroll:true});select(buttons[next]);
  if(selector==='[data-flow-item]'){
    const box=$('execution-items').getBoundingClientRect(),item=buttons[next].getBoundingClientRect();
    if(item.top<box.top)$('execution-items').scrollTop-=box.top-item.top+3;
    else if(item.bottom>box.bottom)$('execution-items').scrollTop+=item.bottom-box.bottom+3;
  }
}
document.addEventListener('click',event=>{
  const button=event.target.closest('[data-code],[data-execution],[data-manual-action]');if(button&&!button.disabled)openExecution(button);
  const stage=event.target.closest('[data-flow-stage]');if(stage)selectFlowStage(stage.dataset.flowStage);
  const item=event.target.closest('[data-flow-item]');if(item)selectFlowItem(item.dataset.flowItem);
  const heading=event.target.closest('[data-flow-file]');
  if(heading&&heading.dataset.flowFile!==executionFile){
    const first=executionStage?.items.find(item=>item.file_id===heading.dataset.flowFile);
    if(first)selectFlowItem(first.id);
  }
});
on('execution-flow','keydown',event=>codingFlowKeys(event,'[data-flow-stage]',button=>selectFlowStage(button.dataset.flowStage)));
on('execution-items','keydown',event=>codingFlowKeys(event,'[data-flow-item]',button=>selectFlowItem(button.dataset.flowItem)));
on('close-execution','click',()=>HelpWindow.close($('execution-dialog')));
on('execution-dialog','close',()=>{const dialog=$('execution-dialog');if(dialog.open||HelpWindow.isMinimized(dialog))return;++executionRequest;executionOpener?.focus({preventScroll:true});});
async function copyCodingSource(whole=false){
  if(!executionItem)return;const item=executionItem,file=flowFile(item),ticket=executionRequest;
  try{
    await navigator.clipboard.writeText(whole?file.content:flowItemContent(item));
    if(ticket===executionRequest&&item===executionItem)text('execution-copy-state',whole?'파일 전체를 복사했습니다.':'선택한 소스 구간을 복사했습니다.');
  }catch{
    if(ticket!==executionRequest||item!==executionItem)return;
    const pre=$('execution-code'),bounds=whole?{start:0,end:file.content.length}:flowItemRange(item),range=codingTextRange(bounds.start,bounds.end);
    pre.focus({preventScroll:true});
    if(range){const selection=window.getSelection();selection.removeAllRanges();selection.addRange(range);}
    text('execution-copy-state','Ctrl+C로 복사하세요.');
  }
}
on('copy-execution','click',()=>copyCodingSource());
on('copy-execution-file','click',()=>copyCodingSource(true));
