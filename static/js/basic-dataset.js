// 기본과제 고정 CSV·스키마 조회. DB 생성·적재·모델 작업을 실행하지 않습니다.
let basicCsvKind='training',basicCsvPage=1,basicCsvPages=1,basicCsvRequest=0;
let basicSchemaKind='training',basicSchemaRequest=0,basicSchemaSql='';
function basicDatasetIdentity(){return person?JSON.stringify([person.student_id,person.db_user]):'';}
function renderBasicCsvRows(result){
  table('basic-csv-rows',result.rows,result.columns.map(name=>[name,name]));
  const roles={identifier:'식별키',feature:'설명변수',target:'타깃변수',metadata:'운영값'};
  $('basic-csv-rows').querySelectorAll('thead th').forEach((heading,index)=>{
    const name=result.columns[index],field=result.layout?.find(item=>item.name===name),role=field?.role||'metadata';
    const english=document.createElement('span'),line=document.createElement('span'),korean=document.createElement('span'),badge=document.createElement('span');
    english.className='mission-column-name';english.lang='en';english.textContent=name;
    line.className='mission-column-label';korean.className='mission-column-korean';korean.textContent=field?.korean_name||'';
    badge.className='mission-column-role';badge.textContent=roles[role]||roles.metadata;
    line.append(korean,badge);heading.replaceChildren(english,line);heading.dataset.columnRole=role;
  });
}
async function loadBasicCsv(){
  const rows=$('basic-csv-rows'),dialog=$('basic-csv-dialog'),opener=document.activeElement;
  const ticket=++basicCsvRequest,kind=basicCsvKind,page=basicCsvPage,split=kind==='training'?$('basic-csv-split').value:'all';
  const identity=basicDatasetIdentity();
  $('basic-csv-split-label').hidden=kind==='prediction';
  document.querySelectorAll('[data-basic-csv-kind]').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.basicCsvKind===kind)));
  $('basic-csv-download').href=kind==='training'?'/download/sample.csv':'/download/prediction.csv';
  text('basic-csv-download',kind==='training'?'학습·TEST 전체 CSV 다운로드':'예측 전체 CSV 다운로드');
  $('basic-csv-prev').disabled=$('basic-csv-next').disabled=true;
  if(!rows.querySelector('table')){text('basic-csv-status','기본 CSV 원문을 읽고 있습니다.');rows.textContent='조회 중입니다.';}
  rows.setAttribute('aria-busy','true');
  try{
    const result=await api('/api/basic/dataset/preview?'+new URLSearchParams({kind,split,page}));
    if(ticket!==basicCsvRequest||identity!==basicDatasetIdentity())return;
    const view={top:dialog.scrollTop,row:rows.scrollTop,left:rows.scrollLeft};
    renderBasicCsvRows(result);basicCsvPages=result.pages;
    const start=result.total?(result.page-1)*result.page_size+1:0,end=Math.min(result.page*result.page_size,result.total);
    text('basic-csv-status',result.filename+' · 원본 '+number(result.original_total)+'행 · '+(split==='all'?'전체':split)+' '+number(result.total)+'행 중 '+start+'~'+end+'행'+(split==='TRAIN'?' · USE_YN=N 경계 주 30행 포함':''));
    text('basic-csv-page',result.page+' / '+result.pages+' 페이지');
    $('basic-csv-prev').disabled=result.page<=1;$('basic-csv-next').disabled=result.page>=result.pages;
    rows.scrollTop=view.row;rows.scrollLeft=view.left;dialog.scrollTop=view.top;
  }catch(error){if(ticket===basicCsvRequest&&identity===basicDatasetIdentity()){text('basic-csv-status','CSV를 조회하지 못했습니다. '+error.message);text('basic-csv-rows','다시 조회를 눌러 확인하세요.');}}
  finally{
    if(ticket===basicCsvRequest){
      rows.removeAttribute('aria-busy');
      if(dialog.open&&opener?.matches('#basic-csv-prev,#basic-csv-next')&&(document.activeElement===document.body||document.activeElement===dialog)){
        const next=!opener.disabled?opener:dialog.querySelector('.mission-csv-pagination button:not(:disabled)');
        next?.focus({preventScroll:true});
      }
    }
  }
}
function openBasicCsv(){
  basicCsvKind='training';basicCsvPage=1;$('basic-csv-split').value='all';
  HelpWindow.open($('basic-csv-dialog'),{reset:true});loadBasicCsv();
}
async function loadBasicSchema(){
  const ticket=++basicSchemaRequest,kind=basicSchemaKind,identity=basicDatasetIdentity();
  basicSchemaSql='';text('basic-schema-code','');text('basic-schema-table','');
  text('basic-schema-description','배포 테이블 정의를 읽고 있습니다.');text('basic-schema-columns','조회 중입니다.');text('basic-schema-constraints','');text('basic-schema-source','');text('basic-schema-copy-status','');
  $('copy-basic-schema').disabled=true;
  document.querySelectorAll('[data-basic-schema-kind]').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.basicSchemaKind===kind)));
  try{
    const result=await api('/api/basic/dataset/schema?'+new URLSearchParams({kind}));
    if(ticket!==basicSchemaRequest||identity!==basicDatasetIdentity())return;
    basicSchemaSql=result.sql||'';text('basic-schema-table',result.name);text('basic-schema-description',result.description+' · '+result.notice);
    schemaTable('basic-schema-columns',result.columns,{korean:true});
    text('basic-schema-constraints',(result.constraints||[]).join(' · '));text('basic-schema-source',(result.source_paths||[result.source_path]).join(' + ')+' · 소유자 '+result.owner);
    CodeHighlight.paint($('basic-schema-code'),basicSchemaSql,result.source_path);$('basic-schema-code').scrollTop=$('basic-schema-code').scrollLeft=0;
    $('copy-basic-schema').disabled=!basicSchemaSql;
  }catch(error){if(ticket===basicSchemaRequest&&identity===basicDatasetIdentity()){text('basic-schema-description','스키마를 조회하지 못했습니다. '+error.message);text('basic-schema-columns','로그인 계정과 조회 상태를 확인한 뒤 다시 여세요.');}}
}
function openBasicSchema(){
  basicSchemaKind='training';$('basic-schema-ddl').open=false;
  HelpWindow.open($('basic-schema-dialog'),{reset:true});loadBasicSchema();
}
function resetBasicDatasetViewers(){
  ++basicCsvRequest;++basicSchemaRequest;basicSchemaSql='';
  for(const id of ['basic-csv-dialog','basic-schema-dialog'])if($(id))HelpWindow.close($(id));
  for(const id of ['basic-csv-rows','basic-schema-columns','basic-schema-code','basic-schema-table','basic-schema-source','basic-schema-copy-status'])text(id,'');
  $('copy-basic-schema')?.setAttribute('disabled','');
}
on('close-basic-csv','click',()=>HelpWindow.close($('basic-csv-dialog')));
on('close-basic-schema','click',()=>HelpWindow.close($('basic-schema-dialog')));
on('basic-csv-split','change',()=>{basicCsvPage=1;loadBasicCsv();});
on('basic-csv-refresh','click',loadBasicCsv);
on('basic-csv-prev','click',()=>{if(basicCsvPage>1){--basicCsvPage;loadBasicCsv();}});
on('basic-csv-next','click',()=>{if(basicCsvPage<basicCsvPages){++basicCsvPage;loadBasicCsv();}});
on('copy-basic-schema','click',async()=>{
  if(!basicSchemaSql)return;
  try{await navigator.clipboard.writeText(basicSchemaSql);text('basic-schema-copy-status','배포 정의 SQL을 복사했습니다. 기본과제는 화면 버튼으로 실행할 수 있습니다.');}
  catch{text('basic-schema-copy-status','코드에서 직접 선택해 복사하세요.');}
});
$('basic-csv-dialog')?.addEventListener('close',()=>{
  if(!$('basic-csv-dialog').open&&!HelpWindow.isMinimized($('basic-csv-dialog'))){++basicCsvRequest;text('basic-csv-rows','');$('basic-csv-rows').removeAttribute('aria-busy');}
});
$('basic-schema-dialog')?.addEventListener('close',()=>{
  if(!$('basic-schema-dialog').open&&!HelpWindow.isMinimized($('basic-schema-dialog'))){++basicSchemaRequest;basicSchemaSql='';text('basic-schema-code','');}
});
document.addEventListener('click',event=>{
  const preview=event.target.closest('[data-basic-preview]');if(preview)openBasicCsv();
  const schema=event.target.closest('[data-basic-schema]');if(schema)openBasicSchema();
  const csvKind=event.target.closest('[data-basic-csv-kind]');if(csvKind){basicCsvKind=csvKind.dataset.basicCsvKind;basicCsvPage=1;loadBasicCsv();}
  const schemaKind=event.target.closest('[data-basic-schema-kind]');if(schemaKind){basicSchemaKind=schemaKind.dataset.basicSchemaKind;loadBasicSchema();}
});
