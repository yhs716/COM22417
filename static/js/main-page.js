// 메인 접속 카드는 실제 읽기 전용 연결 검사 결과만 표시합니다.
let mainConnectionRequest=0,mainConnectionBusy=false;
const mainConnectionFields=['main-db-session','main-db-alias','main-db-name','main-db-service','main-db-host','main-db-instance','main-checked-time'];
function resetMainConnection(){
  ++mainConnectionRequest;mainConnectionBusy=false;
  for(const id of mainConnectionFields)text(id,'—');
  $('main-connection-checks').replaceChildren();text('main-db-privileges','');
  text('main-connection-message','접속 정보를 조회하고 있습니다.');
  $('main-account').dataset.connection='pending';
  $('main-test-connection').disabled=false;$('main-test-connection').removeAttribute('aria-busy');
}
function renderMainPage(){
  $('main-login').hidden=!loginView;
  $('main-account').hidden=!person||loginView;
  $('main-task-links').hidden=!person||loginView;
  if(!person){resetMainConnection();return;}
  text('main-person-name',person.name);text('main-person-id',person.student_id);
  text('main-person-department',person.department||'등록 정보 없음');text('main-person-grade',person.grade?person.grade+'학년':'등록 정보 없음');
  text('main-db-owner',person.db_user);
  text('main-web-address',location.origin+'/');
  text('main-login-time',loginAt?date(new Date(loginAt*1000)):'확인 중');
}
async function loadMainConnection(){
  if(!person||mainConnectionBusy)return;
  mainConnectionBusy=true;const ticket=++mainConnectionRequest,generation=sessionGeneration,owner=person.db_user;
  $('main-test-connection').disabled=true;$('main-test-connection').setAttribute('aria-busy','true');
  $('main-account').dataset.connection='pending';
  for(const id of mainConnectionFields)text(id,'—');
  $('main-connection-checks').replaceChildren();text('main-db-privileges','');
  text('main-connection-message','발급 계정의 실제 Oracle 접속 정보를 확인하고 있습니다.');
  try{
    const result=await api('/api/account/connection');
    if(ticket!==mainConnectionRequest||generation!==sessionGeneration||owner!==person?.db_user)return;
    const connection=result.connection;
    renderMainPage();
    text('main-db-session',connection.session_user+' / '+connection.current_schema);
    for(const [id,key] of [['main-db-alias','connection_alias'],['main-db-name','database_name'],['main-db-service','service_name'],['main-db-host','server_host'],['main-db-instance','instance_name']])text(id,connection[key]||'DB에서 제공하지 않음');
    text('main-checked-time',date(connection.checked_at)+' · '+number(connection.elapsed_ms)+' ms');
    text('main-connection-message','연결 성공 · 발급 계정과 실제 접속 계정·현재 스키마가 일치합니다.');
    $('main-account').dataset.connection='success';
    for(const item of connection.checks){const li=document.createElement('li');li.textContent='✓ '+item;$('main-connection-checks').append(li);}
    const expected=['CREATE TABLE','CREATE PROCEDURE','CREATE MINING MODEL'],missing=expected.filter(value=>!connection.privileges.includes(value));
    text('main-db-privileges','확인한 실습 권한: '+(connection.privileges.join(' · ')||'없음')+(missing.length?' · 미확인 권한: '+missing.join(' · '):''));
    text('connection','Oracle 연결됨');$('connection').className='pill good';
  }catch(error){
    if(ticket!==mainConnectionRequest||generation!==sessionGeneration||owner!==person?.db_user)return;
    $('main-account').dataset.connection='failure';
    text('main-connection-message','연결 확인 실패 · '+error.message);
    text('connection','DB 조회 실패');$('connection').className='pill bad';
  }finally{
    if(ticket===mainConnectionRequest){mainConnectionBusy=false;$('main-test-connection').disabled=false;$('main-test-connection').removeAttribute('aria-busy');}
  }
}
on('main-test-connection','click',loadMainConnection);
renderMainPage();
