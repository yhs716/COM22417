// 요청과 후속 갱신이 끝날 때까지 유지하는 공통 진행 표시. 진행률을 임의로 만들지 않습니다.
window.RequestProgress=(()=>{
 const active=new Map();let timer=0;
 const card=document.getElementById('request-progress'),label=document.getElementById('request-progress-label');
 function hide(){clearTimeout(timer);timer=0;if(card?.matches(':popover-open'))card.hidePopover();if(card)card.hidden=true;}
 function show(){
  timer=0;if(!active.size||!card)return;
  label.textContent=[...active.values()].at(-1);card.hidden=false;
  if(card.showPopover&&!card.matches(':popover-open'))card.showPopover();
 }
 function begin(message='작업 처리 중입니다.'){
  const token=Symbol();active.set(token,message);
  if(card&&!card.hidden)show();else if(!timer)timer=setTimeout(show,160);
  return token;
 }
 function end(token){if(!active.delete(token))return;if(!active.size)hide();else if(card&&!card.hidden)show();}
 function request(path,body){
  const name=new URL(path,location.href).pathname;
  if(name==='/api/session')return null;
  let message='데이터를 조회하고 있습니다.';
  if(/\/(?:data|prepared-data|prediction-data|preview)$/.test(name))message='데이터를 조회하고 있습니다.';
  else if(/\/(?:csv|import|recreate)$/.test(name)||/\/predictions\/import$/.test(name))message='CSV 파일을 전송하고 DB에 적재하고 있습니다.';
  else if(name.endsWith('/link'))message='SQL 실행 결과를 확인하고 연계하고 있습니다.';
  else if(name.endsWith('/prepare'))message='전처리 결과를 저장하고 있습니다.';
  else if(/\/models\/(?:train|initial|retrain)$/.test(name))message='모델을 학습하고 있습니다.';
  else if(/\/(?:run|predict|evaluate)$/.test(name))message='모델을 실행하고 결과를 확인하고 있습니다.';
  else if(body!==undefined)message='요청한 작업을 처리하고 있습니다.';
  return begin(message);
 }
 function reset(){active.clear();hide();}
 window.addEventListener('pagehide',reset);
 return {begin,end,request,reset};
})();
