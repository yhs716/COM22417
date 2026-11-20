// 스키마 정의와 실행 SQL은 서버의 발급 계정별 생성기를 사용합니다.
let missionSchemaKey='',missionSchemaKind='training',missionSchemaSql='',missionSchemaRequest=0;
function resetMissionSchema(){
  ++missionSchemaRequest;missionSchemaSql='';
  if($('copy-mission-schema'))$('copy-mission-schema').disabled=true;
  if($('mission-schema-dialog')?.open)HelpWindow.close($('mission-schema-dialog'));
}
async function renderMissionSchema(){
  const item=missionDatasets.find(entry=>entry.key===missionSchemaKey);if(!item)return;
  const version=++missionSchemaRequest,owner=person?.db_user,key=missionSchemaKey,kind=missionSchemaKind;
  missionSchemaSql='';$('copy-mission-schema').disabled=true;
  const procedure=kind==='procedure';
  text('mission-schema-object-label',procedure?'프로시저명':'테이블명');
  text('mission-schema-sql-title',procedure?'CREATE OR REPLACE PROCEDURE · RUN 생성 SQL · 직접 실행':'CREATE TABLE·컬럼 설명 SQL 예시 · 직접 실행');
  $('mission-schema-columns').hidden=procedure;$('mission-schema-constraints').hidden=procedure;
  $('mission-schema-table-guide').hidden=procedure;$('mission-schema-check-guide').hidden=procedure;
  $('mission-schema-procedure-guide').hidden=!procedure;
  $('mission-schema-ddl').open=true;
  text('mission-schema-title',item.title+' · 스키마 안내');
  text('mission-schema-table','');text('mission-schema-description','로그인한 발급 DB 계정의 스키마 안내를 읽고 있습니다.');
  text('mission-schema-constraints','');text('mission-schema-copy-status','');
  $('mission-schema-columns').replaceChildren();$('mission-schema-code').replaceChildren();
  document.querySelectorAll('[data-mission-schema-kind]').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.missionSchemaKind===kind)));
  try{
    if(!owner)throw new Error('로그인 후 발급 DB 계정을 확인하고 스키마를 조회하세요.');
    const schema=await api('/api/assignments/mission/schema?'+new URLSearchParams({mission:key,kind}));
    if(version!==missionSchemaRequest||owner!==person?.db_user)return;
    missionSchemaSql=schema.sql;
    text('mission-schema-table',schema.name);text('mission-schema-description',schema.description);
    if(!procedure)schemaTable('mission-schema-columns',schema.columns);
    text('mission-schema-constraints',schema.constraints.join(' · '));
    CodeHighlight.paint($('mission-schema-code'),schema.sql,procedure?'02_procedure.sql':'01_tables.sql');
    $('mission-schema-code').scrollTop=$('mission-schema-code').scrollLeft=0;
    $('copy-mission-schema').disabled=false;
  }catch(error){
    if(version===missionSchemaRequest&&owner===person?.db_user)text('mission-schema-description',error.message);
  }
}
function openMissionSchema(key){
  if(!missionDatasets.some(item=>item.key===key))return;
  renderMissionContext('mission-schema-learning',missionDatasets.find(item=>item.key===key));
  missionSchemaKey=key;missionSchemaKind='training';renderMissionSchema();
  HelpWindow.open($('mission-schema-dialog'),{reset:true});$('mission-schema-dialog').scrollTop=0;
}
on('close-mission-schema','click',()=>HelpWindow.close($('mission-schema-dialog')));
on('copy-mission-schema','click',async()=>{
  if(!missionSchemaSql)return;
  try{await navigator.clipboard.writeText(missionSchemaSql);text('mission-schema-copy-status','전체 SQL을 복사했습니다. 발급 계정의 새 워크시트에서 선택 해제 → F5 실행하고 첫 계정 검사부터 성공했는지 확인하세요.');}
  catch{text('mission-schema-copy-status','코드에서 직접 선택해 복사하세요.');}
});
document.addEventListener('click',event=>{
  const schema=event.target.closest('[data-mission-schema]');if(schema)openMissionSchema(schema.dataset.missionSchema);
  const kind=event.target.closest('[data-mission-schema-kind]');if(kind){missionSchemaKind=kind.dataset.missionSchemaKind;renderMissionSchema();}
});
