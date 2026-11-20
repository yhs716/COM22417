// [LAYER-CONFIRM] 브라우저 confirm 대신 확인/취소를 Promise로 돌려줍니다.
// 확인 버튼만 true입니다. 닫기·ESC·로그아웃은 false이며 중복 요청은 실행하지 않습니다.
let pendingLayerConfirmation=null;
function askConfirmation(message,{title='작업 확인',accept='확인',danger=false,opener=document.activeElement}={}){
  if(pendingLayerConfirmation)return Promise.resolve(false);
  const dialog=document.getElementById('confirm-dialog');
  document.getElementById('confirm-title').textContent=title;
  document.getElementById('confirm-description').textContent=message;
  const acceptButton=document.getElementById('accept-confirm');acceptButton.textContent=accept;acceptButton.className=danger?'danger':'';
  return new Promise(resolve=>{
    pendingLayerConfirmation={resolve,opener};
    if(typeof dismissMessage==='function')dismissMessage();
    HelpWindow.open(dialog,{reset:true});document.getElementById('cancel-confirm').focus({preventScroll:true});
  });
}
function finishLayerConfirmation(accepted=false){
  const pending=pendingLayerConfirmation;if(!pending)return;
  pendingLayerConfirmation=null;HelpWindow.close(document.getElementById('confirm-dialog'));
  pending.opener?.focus?.({preventScroll:true});pending.resolve(accepted);
}
document.getElementById('accept-confirm').addEventListener('click',()=>finishLayerConfirmation(true));
for(const id of ['cancel-confirm','close-confirm'])document.getElementById(id).addEventListener('click',()=>finishLayerConfirmation(false));
document.getElementById('confirm-dialog').addEventListener('close',event=>{if(!event.currentTarget.open)finishLayerConfirmation(false);});
