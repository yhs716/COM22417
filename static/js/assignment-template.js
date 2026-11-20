// [ASSIGNMENT-EVENT] DB 작성은 SQL에서, 이 파일은 연결·적재·프로시저 호출 결과 표시만 담당합니다.
let assignmentState=null,assignmentBusy=false,assignmentReadinessVersion=0,assignmentReadinessDiagnostic=null;
let assignmentSchemaRequest=0;
let assignmentPhase='unchecked';
const assignmentKey=document.querySelector('[data-assignment]')?.dataset.assignment;
const missionDatasets=JSON.parse($('mission-dataset-catalog')?.textContent||'[]');
let missionSelectionCurrent='',missionSelectionOwner='',missionSelectionVersion=0,missionSelectionSaving=false;
let missionCsvKey='',missionCsvKind='training',missionCsvPage=1,missionCsvPages=1,missionCsvRequest=0;
const assignmentActions=['assignment-import','assignment-data-refresh','assignment-prepare','assignment-prepared-data','assignment-train','assignment-evaluate','assignment-predict','assignment-initial','assignment-retrain','assignment-delete-model','assignment-prediction-import','assignment-prediction-data'];
const assignmentResultDefaults={
  'assignment-input-rows':['예측 입력 조회를 누르세요.','조회 전'],
  'assignment-data':['원본 데이터 조회를 누르면 본인 테이블의 실제 행을 표시합니다.','조회 전'],
  'assignment-prepared-rows':['전처리 실행·저장 후 FIT_YN과 저장값을 확인하세요.','조회 전'],
  'assignment-evaluation':['직접 생성한 모델을 연계한 뒤 TEST 평가를 실행하면 결과를 표시합니다.','실행 전'],
  'assignment-predictions':['입력 테이블을 준비한 뒤 선택 모델로 예측하세요.','실행 전']
};
function assignmentEmpty(id,message,count){
  const element=$(id);if(!element)return;element.classList.add('empty');element.textContent=message;
  if(count!==undefined)text(id+'-count',count);
}
function clearAssignmentResults(ids=Object.keys(assignmentResultDefaults)){
  if(ids.includes('assignment-predictions')){text('assignment-prediction-comparison','');if($('assignment-proof-return'))$('assignment-proof-return').hidden=true;}
  for(const id of ids){const [message,count]=assignmentResultDefaults[id];assignmentEmpty(id,message,count);}
}
function renderAssignmentControls(){
  const reason=assignmentUnavailable();
  for(const id of assignmentActions)controlState(id,reason,'실행 가능');
  for(const id of ['assignment-check','assignment-model-link','assignment-prediction-link','assignment-save'])controlState(id,!person?'로그인이 필요합니다.':assignmentBusy||assignmentPhase==='loading'?'DB 작업 중입니다. 완료 후 다시 확인할 수 있습니다.':'','SQL Developer에서 실행·COMMIT → SQL 실행 결과 연계 → 현황 확인','assignment-readiness-summary');
  $('assignment-connection')?.querySelectorAll('input').forEach(input=>input.disabled=assignmentBusy);
  for(const id of ['assignment-mode','assignment-predict-mode','assignment-preparation-mode','assignment-prepared-source-kind','mission-dataset'])if($(id))$(id).disabled=assignmentBusy;
  document.querySelectorAll('[data-mission-choice]').forEach(button=>button.disabled=assignmentBusy||missionSelectionSaving);
  if($('mission-dataset'))$('mission-dataset').disabled=assignmentBusy||missionSelectionSaving;
  controlState('clear-mission-selection',assignmentBusy||missionSelectionSaving||!missionSelectionCurrent?'선택한 미션이 없거나 저장 중입니다.':'','선택 해제 · DB는 유지');
  const prepMode=selectedMode('assignment-preparation-mode'),prep=assignmentState?.preparation?.[prepMode];
  const prepCounts=prep?.rows?number(prep.rows)+'행 · 학습 제공 '+number(prep.fit_rows)+'행 · TEST '+number(prep.test_rows)+'행':'전처리 데이터 없음';
  text('assignment-prepared-status',reason||prepMode+' · '+prepCounts+(prep?.rows?(prep.ready?' · 웹 연계 확인 완료':' · DB 데이터 있음 · 웹 연계 확인 필요'):' · 직접 SQL로 전처리한 뒤 조회·연계하세요.')+(prep?.rows&&!prep.fit_rows?' · 학습 제공 행이 없습니다.':'')+(prep?.rows&&!prep.test_rows?' · TEST 평가 행이 없습니다.':''));
  const unlinked=['RAW','CLEAN'].filter(mode=>assignmentState?.preparation?.[mode]?.rows&&!assignmentState.preparation[mode].ready);
  const linked=['RAW','CLEAN'].filter(mode=>assignmentState?.preparation?.[mode]?.ready);
  controlState('assignment-prepared-link',reason,'DB 결과를 검증하고 웹 연계 정보만 저장합니다.','assignment-prepared-link-status');
  text('assignment-prepared-link-status',reason||(unlinked.length?unlinked.join(' · ')+' 데이터는 DB에 있습니다. 직접 SQL 실행을 마쳤으면 SQL 실행 결과 연계를 누르세요.':linked.length===2?'RAW · CLEAN 웹 연계 완료. 현재 원본·프로시저 기준으로 확인했습니다.':'직접 SQL로 전처리한 뒤 DB 결과를 웹에 연계하세요.'));
  for(const id of ['assignment-prepare','assignment-prepared-data'])controlState(id,reason,'실행 가능','assignment-prepared-status');
  const trainingReason=assignmentTableUnavailable(false),predictionTableReason=assignmentTableUnavailable(true);
  text('assignment-data-status',trainingReason||'CSV 적재 가능 · 파일 선택 → 교체 적재 → 전처리·학습은 직접 SQL로 실행하세요.');
  text('assignment-prediction-input-status',predictionTableReason||'예측 CSV 적재 가능 · 입력을 적재한 뒤 준비된 모델로 예측하세요.');
  controlState('assignment-data-refresh',trainingReason,'원본 데이터 조회 가능','assignment-data-status');
  controlState('assignment-prediction-data',predictionTableReason,'예측 입력 조회 가능','assignment-prediction-input-status');
  renderAssignmentModel();
  const predictionMode=selectedMode('assignment-predict-mode'),predictionModel=assignmentState?.models?.find(m=>m.variant===predictionMode);
  const predictionReason=reason||(!predictionModel?.exists?`${predictionMode} 모델 없음 · SQL Developer에서 최초 생성 후 현황에서 연계 확인하세요.`:!predictionModel.is_current?`${predictionMode} 모델이 최신이 아닙니다. 전처리 상태 확인 후 재학습하세요.`:'');
  controlState('assignment-predict',predictionReason,'모델 준비 완료 · 적재한 입력으로 예측 가능','assignment-predict-status');
  text('assignment-predict-status',predictionReason||`${predictionMode} 최신 모델 준비 완료 · 입력 조회로 적재 행을 확인한 뒤 예측하세요. 실행 성공과 예측 품질은 별도로 확인합니다.`);
  text('assignment-predict-call','OML_'+(assignmentKey||'').toUpperCase()+"_RUN('PREDICT', '"+predictionMode+"', :p_result, :p_sql)");
  document.querySelector('[data-assignment]')?.setAttribute('aria-busy',String(assignmentBusy||assignmentPhase==='loading'));
  // Local file selection does not depend on DB object readiness and never uploads data.
  for(const id of ['assignment-file','assignment-prediction-file','assignment-add-file'])if($(id))$(id).disabled=!person||assignmentBusy||missionSelectionSaving;
  controlState('assignment-prepare',reason||(!assignmentState?.state?.total_rows?'원본 데이터 없음 · 학습 CSV를 먼저 적재하세요.':''),'직접 실행 SQL 보기','assignment-prepared-status');
  controlState('assignment-clear-prepared',reason||(!prep?.rows?'선택 방식의 저장값이 없습니다.':''),'선택 전처리값 삭제 SQL 보기');
  controlState('assignment-clear-training',trainingReason||(!assignmentState?.state?.total_rows?'비울 원본 데이터가 없습니다.':''),'원본·전처리값 삭제 SQL 보기');
  controlState('assignment-clear-prediction',predictionTableReason||(!assignmentState?.prediction_storage?.rows?'비울 예측 입력이 없습니다.':''),'예측 입력 삭제 SQL 보기');
  const objectReason=!person?'로그인이 필요합니다.':assignmentBusy||assignmentPhase==='loading'?'DB 상태 확인 중입니다.':assignmentPhase!=='ready'?'현황에서 상태를 확인하세요.':'';
  controlState('assignment-drop-objects',objectReason||(!assignmentState?.objects?.length&&!assignmentState?.models?.some(m=>m.exists)?'삭제할 실습 객체가 없습니다.':''),'실습 객체 삭제 SQL 보기');
  for(const button of document.querySelectorAll('[data-manual-action]')){
    if(assignmentKey==='mission'&&(missionSelectionSaving||!missionSelectionCurrent))controlState(button.id,'미션을 선택하고 저장을 마친 뒤 SQL을 확인하세요.');
    else if(!button.disabled){
      button.title='직접 실행 SQL 보기 · SQL Developer에서 실행 후 결과를 연계하세요.';
      text(button.id+'-status','직접 실행 SQL 보기 · 실행 후 SQL 실행 결과 연계');
    }
  }
  controlState('assignment-import',assignmentImportUnavailable(false),'선택 CSV로 학습·TEST 데이터를 교체합니다.','assignment-file-state');
  controlState('assignment-prediction-import',assignmentImportUnavailable(true),'선택 CSV로 예측 입력을 교체합니다.','assignment-prediction-file-state');
  renderMissionBinding();
}
function missionObjectsEmpty(){
  return assignmentKey==='mission'&&Array.isArray(assignmentState?.objects)&&assignmentState.objects.length===0;
}
function renderMissionBinding(){
  if(assignmentKey!=='mission')return;
  const binding=assignmentState?.mission,panel=$('mission-binding-status');panel.hidden=!person||!binding||missionObjectsEmpty();
  if(!binding)return;
  panel.dataset.state=binding.ready?'matched':binding.can_link?'unlinked':'mismatch';
  text('mission-binding-summary','선택: '+binding.selected_title+' / DB 규약 확인: '+binding.detected_title+' / 마지막 전처리·모델 연계: '+binding.applied_title);
  text('mission-binding-next',binding.ready?'선택 미션과 DB 객체가 일치합니다. 객체 준비는 조회로 자동 확인하며 별도 연계가 필요 없습니다. 전처리·모델 결과 연계는 각 단계에서 진행하세요.':binding.reason+' 기존 DB 미션으로 돌아가거나 선택 미션의 세 테이블·RUN을 직접 적용한 뒤 웹을 새로고침하세요.'+(binding.problems?.length?' '+binding.problems.join(' · '):''));
  $('mission-binding-return').hidden=!binding.detected||binding.detected===missionSelectionCurrent;
  $('mission-binding-return').disabled=assignmentBusy||missionSelectionSaving;
  const reason=!person?'로그인하세요.':assignmentBusy||missionSelectionSaving||assignmentPhase==='loading'?'상태 확인 중입니다.':missionObjectsEmpty()?assignmentUnavailable():!binding.can_link?binding.reason:'';
  for(const id of ['assignment-check','assignment-prepared-link','assignment-model-link','assignment-prediction-link'])controlState(id,reason,'선택 미션과 실제 DB를 검증한 뒤 연계합니다.');
}
function assignmentTableUnavailable(prediction=false){
  if(!person)return '로그인 후 실행하세요.';
  if(assignmentBusy||missionSelectionSaving)return '작업 완료 후 실행하세요.';
  if(assignmentPhase==='loading'||!assignmentState)return '현황에서 테이블 상태를 먼저 확인하세요.';
  if(assignmentPhase==='error')return '현황에서 DB 상태를 다시 확인하세요.';
  const table=assignmentState.config?.[prediction?'prediction_table':'training_table']||'OML_'+assignmentKey.toUpperCase()+(prediction?'_PREDICT':'_DATA');
  if(!assignmentState.objects?.some(row=>row.object_name===table&&row.object_type==='TABLE'&&row.status==='VALID'))return table+' 테이블을 먼저 생성하세요. '+(assignmentKey==='mission'?'현황의 스키마 조회에서 생성 SQL을 확인하세요.':'직접 작성한 CREATE TABLE을 실행하세요.');
  return '';
}
function assignmentImportUnavailable(prediction=false){
  const reason=assignmentTableUnavailable(prediction);if(reason)return reason;
  if(assignmentKey==='mission'&&!missionSelectionCurrent)return '미션을 먼저 선택하세요.';
  if(assignmentKey==='mission'&&assignmentState?.mission&&!assignmentState.mission.tables[prediction?'prediction':'training'])return '선택 미션에 맞는 적재 대상 테이블을 먼저 적용하세요.';
  const file=$(prediction?'assignment-prediction-file':'assignment-file')?.files[0];
  if(!file)return 'CSV 파일을 먼저 선택하세요.';
  if(!file.name.toLowerCase().endsWith('.csv'))return 'CSV 확장자 파일을 선택하세요.';
  if(!file.size||file.size>2*1024*1024)return 'CSV는 0바이트 초과, 2 MiB 이하로 선택하세요.';
  return '';
}
async function importAssignmentCsv(button,prediction=false){
  const reason=assignmentImportUnavailable(prediction);
  if(reason){notice(reason,true);return;}
  const file=$(prediction?'assignment-prediction-file':'assignment-file').files[0],owner=person.db_user,generation=sessionGeneration,mission=missionSelectionCurrent;
  const target=owner+'.'+assignmentState.config[prediction?'prediction_table':'training_table'];
  assignmentBusy=true;renderAssignmentControls();
  try{
    if(!await askConfirmation(target+'의 기존 행을 '+file.name+' 파일로 교체할까요?\n파일 전체 검사 후 500행씩 적재합니다. 오류가 나면 기존 데이터를 복구합니다.'+(prediction?'':'\n적재 후 전처리·학습을 다시 실행하세요.'),{title:prediction?'예측 CSV 교체 적재':'학습 CSV 교체 적재',accept:'교체 적재',opener:button}))return;
    if(generation!==sessionGeneration||owner!==person?.db_user||(assignmentKey==='mission'&&mission!==missionSelectionCurrent))return;
    await task(button,async()=>{
      const body=upload(file);if(assignmentKey==='mission')body.append('mission',mission);
      const result=await api('/api/assignments/'+assignmentKey+'/'+(prediction?'prediction-import':'import')+'/csv',body);
      if(generation!==sessionGeneration||owner!==person?.db_user)return;
      if(prediction){assignmentPreviousPrediction=null;clearAssignmentResults(['assignment-input-rows','assignment-predictions']);}
      else{assignmentScores={};assignmentPreviousPrediction=null;clearAssignmentResults();renderAssignmentComparison();}
      try{await loadAssignmentReadiness();}catch{notice(result.message+' · 적재는 완료됐습니다. 현황에서 DB 상태를 다시 확인하세요.');return;}
      text(prediction?'assignment-prediction-file-state':'assignment-file-state',file.name+' · '+number(result.loaded_rows)+'행 적재 완료');
      notice(result.message+'\n'+result.table+(prediction?'':'\n전처리·학습을 직접 실행한 뒤 현황에서 연계 확인하세요.'));
    },{mutation:true});
  }finally{assignmentBusy=false;renderAssignmentControls();}
}
function assignmentUnavailable(){
  if(!person)return '로그인 후 상태를 확인하세요.';
  if(assignmentPhase==='loading')return '테이블·프로시저 확인 중입니다. 완료 후 사용할 수 있습니다.';
  if(assignmentBusy)return 'DB 작업 중입니다. 완료 후 사용할 수 있습니다.';
  if(assignmentPhase==='error')return '준비 상태 조회 실패 · 현황에서 다시 확인하세요.';
  if(!assignmentState)return '준비 상태 확인 전 · 현황에서 테이블·프로시저를 확인하세요.';
  if(missionObjectsEmpty())return '미션 실습 객체 생성 전 · 선택 미션의 DATA → PREPARED → PREDICT → RUN을 먼저 생성하세요.';
  if(assignmentKey==='mission'&&assignmentState.mission&&!assignmentState.mission.ready)return assignmentState.mission.reason;
  if(!assignmentState.ready)return '객체 생성·수정 필요 · 현황의 객체별 안내를 확인하세요.';
  return '';
}
function assignmentNext(title,description,tab,label){
  text('assignment-next-title',title);text('assignment-next-description',description);
  
}
function setAssignmentBadge(label,state='pending'){
  text('assignment-ready-badge',label);if($('assignment-ready-badge'))$('assignment-ready-badge').dataset.state=state;
}
function setAssignmentConnection(label,state=''){
  const connection=$('connection');if(!connection)return;
  text('connection',person?label:'로그인 필요');connection.className='pill'+(person&&state?' '+state:'');
  connection.title=person&&state==='good'?'실제 DB 메타데이터 조회에 성공했습니다. 과제 테이블·프로시저의 준비 상태는 현황에서 별도로 확인하세요.':'';
}
function clearAssignmentFiles(){
  for(const [id,stateId] of [['assignment-file','assignment-file-state'],['assignment-prediction-file','assignment-prediction-file-state'],['assignment-add-file','assignment-add-file-state']]){if($(id))$(id).value='';text(stateId,assignmentKey==='mission'?'CSV 파일을 선택하고 교체 적재를 누르세요. 첫 줄은 영문 헤더, 구분자는 쉼표입니다.':'직접 만든 테이블에 맞는 CSV를 선택하고 교체 적재를 누르세요.');}
}
function resetAssignmentWorkspace(){
  if(typeof clearPracticeEvidence==='function')clearPracticeEvidence('로그인 후 과제의 최종 상태를 확인하세요.');
  if($('assignment-schema-dialog')){++assignmentSchemaRequest;if($('assignment-schema-dialog').open)HelpWindow.close($('assignment-schema-dialog'));$('assignment-schema-columns').replaceChildren();}
  ++assignmentReadinessVersion;assignmentState=null;assignmentPhase='unchecked';assignmentReadinessDiagnostic=null;
  assignmentScores={};assignmentHistory=[];assignmentPreviousPrediction=null;table('assignment-lab-history',[]);renderAssignmentComparison();
  clearAssignmentResults();assignmentEmpty('assignment-readiness-table','연결 확인 후 테이블·프로시저별 상태를 표시합니다.');
  text('assignment-readiness-summary','로그인 후 본인 계정의 테이블·프로시저를 확인합니다.');
  setAssignmentBadge('확인 전');if($('assignment-diagnostic'))$('assignment-diagnostic').hidden=true;
  setAssignmentConnection('DB 연결 확인 필요');
  clearAssignmentFiles();
  if(assignmentKey==='mission'){++missionSelectionVersion;missionSelectionOwner='';missionSelectionSaving=false;selectMissionDataset('');++missionCsvRequest;if($('mission-csv-dialog').open)HelpWindow.close($('mission-csv-dialog'));$('mission-csv-rows').replaceChildren();}
  assignmentNext('과제 준비 상태를 확인하세요','로그인 후 본인 계정의 테이블과 프로시저를 조회합니다.','home','테이블·프로시저 확인');
  renderAssignmentControls();
}
function renderAssignmentReadiness(result){
  const roles=[['training_table','원본 TRAIN·TEST','TABLE'],['prepared_table','전처리 저장·모델 입력','TABLE'],['prediction_table','예측 입력','TABLE'],['procedure_name','실행 프로시저','PROCEDURE']];
  const records=roles.map(([field,role,kind])=>{
    const name=result.config[field],object=result.objects.find(row=>row.object_name===name&&row.object_type===kind);
    let status=!object?'미생성':object.status==='VALID'?'확인 완료':'컴파일 오류';
    if(field==='procedure_name'&&object&&result.missing.some(value=>value.includes('인자 불일치')))status='인자 규약 불일치';
    if(field==='prepared_table'&&object&&result.missing.some(value=>value.startsWith(name)&&value.includes('컬럼 누락')))status='운영 컬럼 누락';
    return {role,object_name:objectDisplay(name),status,object_id:object?.object_id??'—',next_step:!object?(kind==='TABLE'?'01_tables.sql 작성·F5 실행':'02_procedure.sql 작성·F5 실행'):status==='확인 완료'?'연결됨':kind==='TABLE'?'01_tables.sql 확인·기존 테이블 ALTER':'02_procedure.sql 수정·F5 재실행'};
  });
  table('assignment-readiness-table',records,[['role','용도'],['object_name','현재 연결 이름'],['status','DB 확인 결과'],['object_id','OBJECT_ID'],['next_step','다음 행동']]);
  for(const [field,id] of [['training_table','assignment-training-target'],['prepared_table','assignment-prepared-target'],['prediction_table','assignment-prediction-target']])text(id,result.config[field]);
  const absent=(result.issues||[]).filter(item=>item.kind==='missing');
  setAssignmentBadge(result.ready?'사용 가능':absent.length?'객체 생성 필요':'객체 수정 필요',result.ready?'ready':'pending');
  text('assignment-readiness-summary',result.ready?'DB 접속 완료 · 테이블 3개와 프로시저 확인 완료. 학습데이터 단계로 이동하세요.':absent.length?`DB 접속 완료 · 아래 미생성 객체 ${absent.length}개를 표시된 이름으로 생성하세요.`:'DB 접속 완료 · 아래 객체의 수정할 내용을 확인하세요.');
  if($('assignment-diagnostic'))$('assignment-diagnostic').hidden=result.ready||!result.diagnostic;
  text('assignment-diagnostic','연결 상태·오류 상세');
  const prepared=result.ready&&['RAW','CLEAN'].some(mode=>result.preparation?.[mode]?.ready);
  assignmentNext(!result.ready?'객체를 준비하면 연결됩니다':prepared?'모델 최신 상태와 TEST 결과를 확인하세요':'전처리값을 준비하세요',!result.ready?'생성 SQL을 본인 데이터에 맞게 수정 → 같은 계정에서 F5 실행 → 위의 테이블·프로시저 확인':prepared?'SQL Developer에서 FIT_YN=Y TRAIN으로 모델을 생성·재학습한 뒤 현황에서 연계 확인하고 같은 TEST로 평가합니다.':'SQL Developer에서 RAW 또는 CLEAN 전처리·학습을 실행하고 FIT_YN을 확인한 뒤 현황에서 연계 확인을 누르세요.',!result.ready?'home':prepared?'models':'data',!result.ready?('연결 상태·오류 상세'):prepared?'모델 생성·비교로 이동':'학습데이터로 이동');
}
async function loadAssignmentReadiness(includeEvidence=false){
  if(!assignmentKey||!person)return;
  await restoreMissionSelection();
  if(!person)return;
  if(typeof clearPracticeEvidence==='function')clearPracticeEvidence('현재 과제 상태를 확인하고 있습니다.');
  const version=++assignmentReadinessVersion;
  assignmentState=null;assignmentPhase='loading';assignmentReadinessDiagnostic=null;renderAssignmentControls();setAssignmentBadge('확인 중','loading');
  setAssignmentConnection('DB 조회 중');
  text('assignment-readiness-summary','본인 계정의 테이블·프로시저·인자 규약을 조회하고 있습니다.');
  assignmentEmpty('assignment-readiness-table','실제 DB 메타데이터를 조회하고 있습니다.');
  if($('assignment-diagnostic'))$('assignment-diagnostic').hidden=true;
  try{
    const result=await api(`/api/assignments/${assignmentKey}/status?include_evidence=1`);
    if(version!==assignmentReadinessVersion||!person)return;
    assignmentState=result;assignmentPhase='ready';
    if(result.practice&&typeof renderPracticeEvidence==='function')renderPracticeEvidence(result.practice);
    assignmentReadinessDiagnostic=result.diagnostic;
    // DB 접속 성공과 학생이 작성할 객체의 준비 완료는 서로 다른 상태입니다.
    setAssignmentConnection('DB 연결됨','good');
    for(const field of ['training_table','prepared_table','prediction_table','procedure_name'])$('assignment-connection').elements[field].value=result.config[field];
    for(const mode of ['RAW','CLEAN'])if(!result.models?.find(m=>m.variant===mode&&m.is_current))delete assignmentScores[mode];
    renderAssignmentComparison();
    renderAssignmentReadiness(result);
  }catch(error){
    if(version!==assignmentReadinessVersion||!person)return;
    const disconnected=error.diagnostic?.category==='connection';
    const connected=error.diagnostic?.db_connected===true||assignmentState?.connected===true;
    assignmentState=null;assignmentPhase='error';assignmentReadinessDiagnostic=error.diagnostic;
    assignmentScores={};renderAssignmentComparison();
    clearAssignmentResults();clearAssignmentFiles();setAssignmentBadge(disconnected?'DB 접속 실패':'확인 미완료','error');
    setAssignmentConnection(disconnected?'DB 접속 실패':connected?'DB 연결됨':'서버 응답 확인 필요',disconnected?'bad':connected?'good':'');
    text('assignment-readiness-summary',disconnected?'DB에 접속하지 못했습니다. 접속 안내를 확인한 뒤 다시 시도하세요.':connected?'DB에는 접속했습니다. 객체 조회 중 문제가 발생해 준비 상태를 확인하지 못했습니다.':'요청을 완료하지 못했습니다. 잠시 후 다시 확인하세요.');
    assignmentEmpty('assignment-readiness-table','현재 상태를 확인하지 못해 이전 조회 결과를 지웠습니다.');
    if($('assignment-diagnostic'))$('assignment-diagnostic').hidden=!assignmentReadinessDiagnostic;
    text('assignment-diagnostic','연결 상태·오류 상세');
    assignmentNext(disconnected?'DB 접속을 확인하세요':'테이블·프로시저 확인을 다시 실행하세요',error.diagnostic?.title||error.message,'home','다시 확인');
    throw error;
  }finally{renderAssignmentControls();}
}
async function assignmentTask(button,action,file,variant=selectedMode(action==='predict'?'assignment-predict-mode':['prepare','prepared-data'].includes(action)?'assignment-preparation-mode':'assignment-mode')){
  if(assignmentBusy||(['data','prediction-data'].includes(action)?assignmentTableUnavailable(action==='prediction-data'):!assignmentState?.ready))return;
  if(action==='predict'&&!await askConfirmation(`${variant} 모델과 적재된 예측 입력으로 예측을 실행할까요?`,{title:'예측 실행',accept:'실행',opener:button}))return;
  const version=assignmentReadinessVersion;
  if(action==='predict')$('assignment-proof-return').hidden=true;
  assignmentBusy=true;renderAssignmentControls();
  const target={data:'assignment-data',prepare:'assignment-prepared-rows','prepared-data':'assignment-prepared-rows','prediction-data':'assignment-input-rows',evaluate:'assignment-evaluation',train:'assignment-evaluation','initial-train':'assignment-evaluation',retrain:'assignment-evaluation','delete-model':'assignment-evaluation',predict:'assignment-predictions'}[action];
  // 새 요청의 실패 뒤 이전 결과가 현재 결과로 남지 않게 실행 전에 비웁니다.
  if(action==='import'){assignmentScores={};clearAssignmentResults();renderAssignmentComparison();}
  else if(target)assignmentEmpty(target,'요청한 작업을 처리하고 있습니다.','처리 중');
  if(['prepare','train','initial-train','retrain','delete-model'].includes(action))clearAssignmentResults(['assignment-predictions']);
  try{await task(button,async()=>{
    let body={variant,...(assignmentKey==='mission'?{mission:missionSelectionCurrent}:{})},url=`/api/assignments/${assignmentKey}/${action}`;
    const sourceKind=$('assignment-prepared-source-kind')?.value||'TRAIN';if(action==='prepared-data')body.source_kind=sourceKind;
    if(file){body=upload(file);body.append('variant',variant);url+='/csv';}
    try{
      let result=await api(url,body);if(!person||version!==assignmentReadinessVersion)return;
      if(action==='evaluate'){assignmentScores[variant]=result.rows||[];renderAssignmentComparison();recordAssignmentLab(action,variant,result.rows||[],result.input_fingerprint);}
      if(action==='predict'){recordAssignmentLab(action,variant,result.rows||[],result.input_fingerprint);$('assignment-proof-return').hidden=!result.verified;}
      if(['import','prepare','train','initial-train','retrain','delete-model'].includes(action)){delete assignmentScores[variant];await loadAssignmentReadiness();renderAssignmentComparison();}
      if(action==='prepare'){const stored=await api(`/api/assignments/${assignmentKey}/prepared-data`,{variant,source_kind:sourceKind});result={...result,rows:stored.rows};}
      const learningData=['assignment-data','assignment-prepared-rows'].includes(target),layout=missionDatasets.find(item=>item.key===missionSelectionCurrent)?.layout||[];
      if(target){table(target,result.rows||[],learningData?preparedColumns(result.rows||[],layout):null,{database:true,columnRoles:learningData?learningColumnRoles(layout):null});text(target+'-count',action==='data'?`이번 조회 ${number(result.rows?.length||0)}행 · 최대 5,000행`:`${variant} · ${number(result.rows?.length||0)}개 결과`);}
      if(action==='import')assignmentNext('전처리값을 저장하세요','RAW 또는 CLEAN을 선택하고 전처리 실행·저장 → FIT_YN과 실제 저장값을 확인합니다.','data','전처리 저장·확인');
      if(action==='prepare')assignmentNext('모델 최신 상태를 확인하세요',`${variant} 전처리 저장 완료 · FIT_YN=Y TRAIN으로 학습하며, 저장값이 달라졌으면 다시 학습합니다.`,'models','모델 생성·비교로 이동');
      if(action==='train')assignmentNext('같은 TEST로 평가하세요',`${variant} 모델 생성 결과를 확인하고 TEST 평가를 실행합니다.`,'models','모델 생성·비교로 이동');
      if(action==='evaluate')assignmentNext('새 입력으로 예측하세요','평가 결과를 확인하고 본인 모델의 새 입력 예측을 실행합니다.','predictions','예측 실행으로 이동');
      if(action==='predict')assignmentNext('현황에서 최종 성공 여부를 확인하세요','각 단계의 작업 상태와 최종 실습 현황에서 모든 성공 기준을 확인하세요.','home','최종 현황 확인');
      if(result.message&&!['data','prepared-data','prediction-data'].includes(action))notice(result.message);
    }catch(error){if(!person||version!==assignmentReadinessVersion)return;if(target)assignmentEmpty(target,'작업에 실패했습니다. 알림의 안내를 확인하세요.','실행 실패');throw error;}
  },{mutation:!['data','prepared-data','prediction-data','evaluate'].includes(action),feedback:!['data','prepared-data','prediction-data'].includes(action)});}finally{if(['evaluate','predict'].includes(action)&&typeof syncPracticeEvidence==='function')await syncPracticeEvidence();assignmentBusy=false;renderAssignmentControls();}
}
async function confirmAssignmentLink(button){
  if(assignmentBusy||!person)return;
  const mission=missionSelectionCurrent,owner=missionSelectionIdentity();
  if(!await askConfirmation('DB에 저장된 테이블·전처리·모델 상태를 검증하여 웹 연계 정보를 저장할까요? RAW/CLEAN 전처리 데이터와 현재 원본·프로시저를 대조합니다. 데이터 적재·전처리·학습을 다시 실행하지 않습니다.',{title:'SQL 실행 결과 연계',accept:'확인·연계 저장',opener:button}))return;
  if(owner!==missionSelectionIdentity()||mission!==missionSelectionCurrent)return;
  assignmentBusy=true;renderAssignmentControls();
  try{
    await task(button,async()=>{await api('/api/assignments/'+assignmentKey+'/link',assignmentKey==='mission'?{mission}:{});await loadAssignmentReadiness(true);notice('SQL 실행 결과를 웹에 연계했습니다. 최종 현황도 갱신했습니다.');},{feedback:false});
  }finally{assignmentBusy=false;renderAssignmentControls();}
}
on('assignment-check','click',event=>confirmAssignmentLink(event.currentTarget));
on('assignment-prepared-link','click',event=>confirmAssignmentLink(event.currentTarget));
on('assignment-model-link','click',event=>confirmAssignmentLink(event.currentTarget));
on('assignment-prediction-link','click',event=>confirmAssignmentLink(event.currentTarget));
function showAssignmentDiagnostic(){if(assignmentReadinessDiagnostic){operationNotice({message:assignmentReadinessDiagnostic.title,diagnostic:assignmentReadinessDiagnostic});showMessageDetails();}}
on('assignment-diagnostic','click',showAssignmentDiagnostic);
on('assignment-import','click',event=>importAssignmentCsv(event.currentTarget,false));
on('assignment-prediction-import','click',event=>importAssignmentCsv(event.currentTarget,true));
on('assignment-data-refresh','click',event=>{$('assignment-original-detail').open=true;assignmentTask(event.currentTarget,'data');});
on('assignment-prepared-data','click',event=>assignmentTask(event.currentTarget,'prepared-data'));
for(const id of ['assignment-preparation-mode','assignment-prepared-source-kind'])on(id,'change',()=>{clearAssignmentResults(['assignment-prepared-rows']);renderAssignmentControls();assignmentTask(null,'prepared-data');});
on('assignment-evaluate','click',event=>assignmentTask(event.currentTarget,'evaluate'));
on('assignment-predict','click',event=>assignmentTask(event.currentTarget,'predict'));
on('assignment-prediction-data','click',event=>{$('assignment-input-detail').open=true;assignmentTask(event.currentTarget,'prediction-data');});
for(const [id,stateId] of [['assignment-file','assignment-file-state'],['assignment-prediction-file','assignment-prediction-file-state']])on(id,'change',()=>{
  const file=$(id).files[0];
  text(stateId,file?file.name+' · 파일 선택 완료 · CSV 교체 적재를 눌러 업로드하세요.':'선택한 파일이 없습니다.');renderAssignmentControls();
});
on('assignment-mode','change',renderAssignmentControls);
on('assignment-predict-mode','change',()=>{clearAssignmentResults(['assignment-predictions']);text('assignment-prediction-comparison','');renderAssignmentControls();});
document.addEventListener('click',event=>{
  const button=event.target.closest('[data-assignment-tab],[data-step-next]');if(!button)return;
  if(assignmentBusy){notice('DB 작업 완료 후 단계를 바꾸세요.');return;}
  const tab=button.dataset.assignmentTab||button.dataset.stepNext,active=document.querySelector('.assignment-tabs [aria-current="step"]')?.dataset.assignmentTab;
  document.querySelectorAll('[data-assignment-panel]').forEach(panel=>panel.hidden=panel.dataset.assignmentPanel!==tab);
  document.querySelectorAll('.assignment-tabs [data-assignment-tab]').forEach(item=>item.setAttribute('aria-current',item.dataset.assignmentTab===tab?'step':'false'));
  revealCurrentStep(document.querySelector('.assignment-tabs'));
  if(active!==tab)window.scrollTo({top:0,behavior:'instant'});
  if(tab==='home'&&person)task(null,loadAssignmentReadiness,{feedback:false});
});
function missionFieldRoles(item){
  const layout=item?.layout||[],describe=field=>field.name+' ('+field.korean_name+')';
  return {key:layout.filter(field=>field.name==='case_id').map(describe).join(', '),
    features:layout.filter(field=>field.role.includes('설명변수')).map(describe).join(', '),
    target:layout.filter(field=>field.name==='label').map(field=>describe(field)+' · '+field.valid).join(', ')};
}
function selectMissionDataset(key){
    const previous=missionSelectionCurrent,item=missionDatasets.find(entry=>entry.key===key);missionSelectionCurrent=item?.key||'';
    if(previous!==missionSelectionCurrent){clearAssignmentFiles();if(typeof clearPracticeEvidence==='function')clearPracticeEvidence('선택 미션과 DB 적용 상태를 다시 확인하세요.');}
    if($('mission-dataset'))$('mission-dataset').value=item?.key||'';
    $('mission-preview-selected').hidden=!item;$('mission-variable-summary').hidden=!item;
    const roles=missionFieldRoles(item);text('mission-key-fields',roles.key);text('mission-feature-fields',roles.features);text('mission-target-fields',roles.target);
    document.querySelectorAll('[data-mission-card]').forEach(card=>card.classList.toggle('selected',card.dataset.missionCard===item?.key));
    document.querySelectorAll('[data-mission-choice]').forEach(button=>{const selected=button.dataset.missionChoice===item?.key;button.setAttribute('aria-pressed',String(selected));button.title=selected?'현재 선택한 미션':'이 미션 선택';});
    text('mission-selection-note',item?`선택: ${item.title} · 학습·TEST CSV와 별도 예측 CSV를 내려받으세요. 주제 선택과 DB 적재는 별도 작업입니다.`:`선택 전 · 위 ${missionDatasets.length}개 중 하나를 선택하고 CSV를 내려받으세요.`);
    text('mission-data-selection',item?`선택: ${item.title} · 다운로드한 ${item.filename}을 선택하고 CSV 교체 적재를 누르세요. 주제 선택만으로 DB 데이터는 바뀌지 않습니다.`:`선택 전 · 현황의 예시 ${missionDatasets.length}종 또는 위 목록에서 미션을 선택하세요.`);
    text('mission-model-selection',item?'선택: '+item.title+' · 이 미션의 컬럼과 라벨을 반영한 SQL 가이드를 사용합니다.':'현황에서 미션을 선택하세요.');
    text('mission-prediction-selection',item?`선택: ${item.title} · 별도 예측 ${item.prediction_filename} 30행을 내려받아 적재하세요.`:'선택한 미션의 별도 예측 CSV 30행을 내려받아 적재하세요.');
    for(const [id,kind] of [['mission-download','training'],['mission-prediction-download','prediction']]){$(id).hidden=!item;if(item)$(id).href=`/download/datasets/${item.key}?kind=${kind}`;else $(id).removeAttribute('href');}
    for(const [id,file] of [['mission-tables-download','tables'],['mission-procedure-download','procedure']])if($(id)){$(id).hidden=!item;if(item)$(id).href='/api/assignments/mission/guide/download?'+new URLSearchParams({file,mission:item.key});}
    $('mission-dataset-empty').hidden=Boolean(item);$('mission-fields').hidden=!item;$('mission-baseline').hidden=!item;
    table('mission-fields',item?.layout||[],[['name','영문 컬럼명'],['korean_name','한글 명칭'],['role','역할·설명'],['valid','유효값·범위']]);
    text('mission-baseline',item?.baseline?`배포 전 실제 검증 RAW 정확도 ${item.baseline.raw_accuracy}% · TEST ${item.baseline.test_rows}행 · Decision Tree / PREP_AUTO ON / 깊이 ${item.baseline.max_depth} / 최소 잎 ${item.baseline.min_percent_node}%. 본인 설정의 성능이나 정제 후 향상은 보장하지 않습니다.`:item?'이 미션의 배포 전 Oracle 학습·성능 검증은 아직 실행하지 않았습니다. 본인 프로시저로 학습하고 고정 TEST로 평가하세요.':'');
}
function missionSelectionIdentity(){return person?JSON.stringify([person.student_id,person.db_user]):'';}
async function restoreMissionSelection(){
  if(assignmentKey!=='mission'||!person)return;
  const owner=missionSelectionIdentity();if(missionSelectionOwner===owner)return;
  const version=++missionSelectionVersion;selectMissionDataset('');
  try{
    const result=await api('/api/assignments/mission/selection');
    if(version!==missionSelectionVersion||owner!==missionSelectionIdentity())return;
    missionSelectionOwner=owner;selectMissionDataset(result.key);
  }catch(error){if(version===missionSelectionVersion&&person)notice('저장된 미션 선택을 불러오지 못했습니다. '+error.message,true);}
}
async function saveMissionSelection(key){
  if(!person||assignmentBusy||missionSelectionSaving||key===missionSelectionCurrent)return;
  const owner=missionSelectionIdentity(),previous=missionSelectionCurrent,version=++missionSelectionVersion;let saved=false;
  missionSelectionSaving=true;selectMissionDataset(key);renderAssignmentControls();
  $('mission-dataset').disabled=true;
  try{
    const item=missionDatasets.find(entry=>entry.key===key);
    const approved=await askConfirmation((item?.title||'미션 선택 해제')+' 상태를 저장할까요? 선택만 저장하며 DB 객체와 데이터는 변경하지 않습니다.',{title:'미션 선택 저장',accept:'선택 저장'});
    if(version!==missionSelectionVersion||owner!==missionSelectionIdentity())return;
    if(!approved){selectMissionDataset(previous);return;}
    const result=await api('/api/assignments/mission/selection',{key});
    if(version!==missionSelectionVersion||owner!==missionSelectionIdentity())return;
    saved=true;missionSelectionOwner=owner;selectMissionDataset(result.key);
    assignmentScores={};assignmentPreviousPrediction=null;clearAssignmentResults();renderAssignmentComparison();
    await loadAssignmentReadiness(true);
  }catch(error){
    if(version===missionSelectionVersion&&owner===missionSelectionIdentity()){if(!saved)selectMissionDataset(previous);notice((saved?'선택은 저장됐습니다. 현황을 다시 확인하세요. ':'미션 선택을 저장하지 못했습니다. ')+error.message,true);}
  }finally{
    if(version===missionSelectionVersion){missionSelectionSaving=false;renderAssignmentControls();}
  }
}
on('clear-mission-selection','click',()=>saveMissionSelection(''));
on('mission-binding-return','click',()=>saveMissionSelection(assignmentState?.mission?.detected||''));
on('mission-dataset','change',()=>saveMissionSelection($('mission-dataset').value));
document.addEventListener('click',event=>{const button=event.target.closest('[data-mission-choice]');if(button)saveMissionSelection(button.dataset.missionChoice);});
let assignmentScores={},assignmentHistory=[],assignmentPreviousPrediction=null;
function renderAssignmentModel(){
  if(!assignmentKey||!$('assignment-mode'))return;
  const mode=selectedMode('assignment-mode'),m=assignmentState?.models?.find(x=>x.variant===mode),p=assignmentState?.preparation?.[mode],reason=assignmentUnavailable();
  text('assignment-model-name',m?.model_name||`OML_${assignmentKey.toUpperCase()}_${mode}_MODEL`);
  text('assignment-model-label',`${mode} · 현재 작업`);
  text('assignment-mode-effect',`제공 예제: ${mode} 전처리 저장값 → ${mode} 모델 · 실제 조건은 본인 프로시저`);
  text('assignment-training-condition',`PREP_MODE = '${mode}' AND SOURCE_KIND = 'TRAIN' AND FIT_YN = 'Y'`);
  text('assignment-model-training-count',p?.ready?'FIT_YN=Y '+number(p.fit_rows)+'행 · TEST '+number(p.test_rows)+'행':'직접 전처리 후 연계 확인 필요');
  const training=reason||(!p?.ready?`${mode} 전처리 저장 필요`:!p.fit_rows?'FIT_YN=Y TRAIN 0행 · DB에서 확인하세요.':'');
  text('assignment-model-preparation',reason||(!p?.ready?(p?.rows?mode+' 전처리 데이터 '+number(p.rows)+'행 있음 · SQL 실행 결과 연계 필요':mode+' 전처리 미저장 · 직접 SQL 실행 후 SQL 실행 결과 연계를 누르세요.'):training||mode+' 전처리 웹 연계 완료 · FIT_YN=Y TRAIN '+number(p.fit_rows)+'행으로 학습 가능'));
  text('assignment-model-state',reason||(m?.exists?(m.is_current?'직접 생성한 모델 연계 확인됨':'모델 있음 · 직접 학습 후 SQL 실행 결과 연계 필요'):'모델 미생성 · '+(training?'전처리·학습 제공 행 확인 필요':'최초 생성 가능')));
  controlState('assignment-initial',reason||(m?.exists?'이미 생성됨 · 다시 학습을 이용하세요.':training),'최초 생성 가능');
  for(const id of ['assignment-retrain'])controlState(id,reason||(!m?.exists?'모델 없음 · 최초 생성이 먼저입니다.':training),'저장된 TRAIN 전체로 재생성 가능');
  controlState('assignment-delete-model',reason||(!m?.exists?'모델 없음 · 삭제할 대상이 없습니다.':''),'선택 모델 삭제 가능');
  const evaluation=reason||(!m?.exists?'모델 없음 · 최초 생성이 먼저입니다.':!m.is_current?'모델이 최신이 아닙니다. 전처리 상태 확인 후 재학습하세요.':'');
  controlState('assignment-evaluate',evaluation,'선택 모델 TEST 평가 가능','assignment-evaluate-status');
  text('assignment-evaluate-status',evaluation||`${mode} 최신 모델 · 같은 TEST 전체로 평가할 수 있습니다.`);
}
function renderAssignmentComparison(){
  if(!$('assignment-comparison'))return;
  for(const mode of ['RAW','CLEAN']){
    const model=assignmentState?.models?.find(item=>item.variant===mode);
    const rows=model?.exists&&model.is_current?assignmentScores[mode]:null;
    const total=rows?.reduce((sum,row)=>sum+Number(row.n),0)||0;
    const correct=rows?.reduce((sum,row)=>sum+(row.actual===row.predicted?Number(row.n):0),0)||0;
    text('assignment-compare-name-'+mode,model?.model_name||'OML_'+assignmentKey.toUpperCase()+'_'+mode+'_MODEL');
    text('assignment-compare-state-'+mode,!assignmentState?'확인 전':!model?.exists?'미생성':model.is_current?'생성 완료':'연계·재학습 확인 필요');
    text('assignment-compare-accuracy-'+mode,total?percent(100*correct/total):rows?'평가 행 없음':'평가 전');
    text('assignment-compare-correct-'+mode,total?number(correct)+' / '+number(total)+'행':'—');
    text('assignment-compare-errors-'+mode,total?number(total-correct)+'행':'—');
  }
}
function recordAssignmentLab(action,mode,rows,input){
  let comparison='첫 실행';
  if(action==='evaluate'){const total=rows.reduce((n,r)=>n+Number(r.n),0),correct=rows.reduce((n,r)=>n+(r.actual===r.predicted?Number(r.n):0),0);comparison=`TEST ${correct} / ${total} · ${percent(total?100*correct/total:null)}`;}
  if(action==='predict'){if(assignmentPreviousPrediction){const previous=new Map(assignmentPreviousPrediction.rows.map(r=>[String(r.case_id),r]));const same=input===assignmentPreviousPrediction.input&&rows.length===previous.size&&rows.every(r=>previous.has(String(r.case_id)));comparison=same?`이전 실행 대비 예측 ${rows.filter(r=>previous.get(String(r.case_id)).predicted!==r.predicted).length}행 변경 · 확률 ${rows.filter(r=>Math.abs(Number(previous.get(String(r.case_id)).probability)-Number(r.probability))>1e-9).length}행 변경`:'입력 데이터가 달라 비교하지 않음';}assignmentPreviousPrediction={rows,input};}
  if(action==='predict')text('assignment-prediction-comparison','OML_'+assignmentKey.toUpperCase()+'_'+mode+'_MODEL · '+comparison);
  assignmentHistory.unshift({time:date(new Date()),model:`OML_${assignmentKey.toUpperCase()}_${mode}_MODEL`,action:action==='predict'?'예측':'TEST 평가',comparison});assignmentHistory=assignmentHistory.slice(0,20);
  table('assignment-lab-history',assignmentHistory,[['time','시각'],['model','실행 모델'],['action','작업'],['comparison','실제 결과']]);
}
resetAssignmentWorkspace();
// session 응답이 지연 로드 스크립트보다 먼저 도착한 경우에도 실제 DB 상태를 조회합니다.
if(assignmentKey&&person&&!assignmentState)task(null,loadAssignmentReadiness,{feedback:false});

// 배포 합성 CSV의 읽기 전용 조회. DB 준비/작업 잠금과 분리합니다.

function openMissionCsv(key){
  const item=missionDatasets.find(entry=>entry.key===key);if(!item)return;
  missionCsvKey=key;missionCsvKind='training';missionCsvPage=1;$('mission-csv-split').value='all';
  text('mission-csv-title',item.title+' · CSV 데이터 조회');text('mission-csv-description',item.description);renderMissionContext('mission-csv-learning',item);
  const roles=missionFieldRoles(item);text('mission-csv-key',roles.key);text('mission-csv-features',roles.features);text('mission-csv-target',roles.target);
  table('mission-csv-fields',item.layout,[['name','CSV 컬럼명'],['korean_name','한글 명칭'],['role','역할'],['meaning','의미·해석'],['valid','유효값·범위']]);
  HelpWindow.open($('mission-csv-dialog'),{reset:true});$('mission-csv-dialog').scrollTop=0;loadMissionCsv();
}
function renderMissionCsvRows(item,result){
  // 공통 표로 원본 셀을 표시하고 이 CSV 조회의 헤더에만 이름·라벨·역할을 붙입니다.
  table('mission-csv-rows',result.rows,result.columns.map(name=>[name,name]));
  const roles={identifier:'식별키',feature:'설명변수',target:'타깃변수',metadata:'운영값'};
  $('mission-csv-rows').querySelectorAll('thead th').forEach((heading,index)=>{
    const name=result.columns[index],field=item.layout.find(entry=>entry.name===name);
    const role=name==='case_id'?'identifier':field?.role?.includes('설명변수')?'feature':name==='label'?'target':'metadata';
    const english=document.createElement('span'),line=document.createElement('span'),korean=document.createElement('span'),badge=document.createElement('span');
    english.className='mission-column-name';english.lang='en';english.textContent=name;
    line.className='mission-column-label';korean.className='mission-column-korean';korean.textContent=field?.korean_name||'';
    badge.className='mission-column-role';badge.textContent=roles[role];
    line.append(korean,badge);heading.replaceChildren(english,line);heading.dataset.columnRole=role;
  });
}
async function loadMissionCsv(){
  const rows=$('mission-csv-rows'),dialog=$('mission-csv-dialog'),opener=document.activeElement;
  const item=missionDatasets.find(entry=>entry.key===missionCsvKey);if(!item)return;
  const ticket=++missionCsvRequest,kind=missionCsvKind,page=missionCsvPage,split=kind==='training'?$('mission-csv-split').value:'all';
  $('mission-csv-split-label').hidden=kind==='prediction';
  document.querySelectorAll('[data-mission-csv-kind]').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.missionCsvKind===kind)));
  $('mission-csv-download').href=`/download/datasets/${item.key}?kind=${kind}`;
  text('mission-csv-download',kind==='training'?'학습·TEST 전체 CSV 다운로드':'예측 전체 CSV 다운로드');
  $('mission-csv-prev').disabled=$('mission-csv-next').disabled=true;
  if(!rows.querySelector('table')){text('mission-csv-status','CSV 파일을 읽고 있습니다.');rows.textContent='조회 중입니다.';}
  rows.setAttribute('aria-busy','true');
  try{
    const result=await api(`/api/datasets/${item.key}/preview?`+new URLSearchParams({kind,split,page}));
    if(ticket!==missionCsvRequest)return;
    const view={top:dialog.scrollTop,row:rows.scrollTop,left:rows.scrollLeft};
    renderMissionCsvRows(item,result);
    const start=result.total?(result.page-1)*result.page_size+1:0,end=Math.min(result.page*result.page_size,result.total);
    text('mission-csv-status',`${result.filename} · 원본 ${number(result.original_total)}행 · ${split==='all'?'전체':split} ${number(result.total)}행 중 ${start}~${end}행`);
    text('mission-csv-page',`${result.page} / ${result.pages} 페이지`);missionCsvPages=result.pages;
    $('mission-csv-prev').disabled=result.page<=1;$('mission-csv-next').disabled=result.page>=result.pages;
    rows.scrollTop=view.row;rows.scrollLeft=view.left;dialog.scrollTop=view.top;
  }catch(error){if(ticket!==missionCsvRequest)return;text('mission-csv-status','CSV를 조회하지 못했습니다. '+error.message);text('mission-csv-rows','다시 조회를 눌러 확인하세요.');}
  finally{
    if(ticket===missionCsvRequest){
      rows.removeAttribute('aria-busy');
      if(dialog.open&&opener?.matches('#mission-csv-prev,#mission-csv-next')&&(document.activeElement===document.body||document.activeElement===dialog)){
        const next=!opener.disabled?opener:dialog.querySelector('.mission-csv-pagination button:not(:disabled)');
        next?.focus({preventScroll:true});
      }
    }
  }
}
on('mission-preview-selected','click',()=>openMissionCsv($('mission-dataset').value));
on('close-mission-csv','click',()=>HelpWindow.close($('mission-csv-dialog')));
on('mission-csv-split','change',()=>{missionCsvPage=1;loadMissionCsv();});
on('mission-csv-refresh','click',loadMissionCsv);
on('mission-csv-prev','click',()=>{if(missionCsvPage>1){--missionCsvPage;loadMissionCsv();}});
on('mission-csv-next','click',()=>{if(missionCsvPage<missionCsvPages){++missionCsvPage;loadMissionCsv();}});
$('mission-csv-dialog')?.addEventListener('close',()=>{if(!$('mission-csv-dialog').open&&!HelpWindow.isMinimized($('mission-csv-dialog'))){++missionCsvRequest;$('mission-csv-rows').replaceChildren();$('mission-csv-rows').removeAttribute('aria-busy');}});
document.addEventListener('click',event=>{
  const preview=event.target.closest('[data-mission-preview]');if(preview)openMissionCsv(preview.dataset.missionPreview);
  const kind=event.target.closest('[data-mission-csv-kind]');if(kind){missionCsvKind=kind.dataset.missionCsvKind;missionCsvPage=1;loadMissionCsv();}
});

async function showCustomSchema(kind='training'){
  const ticket=++assignmentSchemaRequest,owner=person?.db_user;
  text('assignment-schema-table','');text('assignment-schema-status','실제 테이블 컬럼을 조회하고 있습니다.');
  $('assignment-schema-columns').replaceChildren();
  document.querySelectorAll('[data-custom-schema-kind]').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.customSchemaKind===kind)));
  try{
    const result=await api('/api/assignments/'+assignmentKey+'/schema?'+new URLSearchParams({kind}));
    if(ticket!==assignmentSchemaRequest||owner!==person?.db_user)return;
    text('assignment-schema-table',result.name);text('assignment-schema-status',result.description);
    table('assignment-schema-columns',result.columns,[['name','컬럼명'],['type','Oracle 타입'],['nullable','필수 여부'],['description','컬럼 설명'],['rules','기본값']]);
  }catch(error){if(ticket===assignmentSchemaRequest&&owner===person?.db_user)text('assignment-schema-status',error.message);}
}
on('close-assignment-schema','click',()=>HelpWindow.close($('assignment-schema-dialog')));
document.addEventListener('click',event=>{
  const preview=event.target.closest('[data-custom-preview]');
  if(preview){document.querySelector('[data-assignment-tab="data"]').click();$('assignment-data-refresh').click();}
  const schema=event.target.closest('[data-custom-schema]');
  if(schema){HelpWindow.open($('assignment-schema-dialog'),{reset:true});showCustomSchema();}
  const kind=event.target.closest('[data-custom-schema-kind]');if(kind)showCustomSchema(kind.dataset.customSchemaKind);
});
