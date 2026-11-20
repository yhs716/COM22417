// [HELP-WINDOW] 도움말·메시지 창 이동. 도움말은 최대화·최소화·복원을 추가로 제공합니다.
const HelpWindow=(()=>{
  const states=new Map();
  const dock=document.createElement('div');dock.id='help-window-dock';dock.setAttribute('aria-label','최소화한 도움말');document.body.append(dock);
  function state(dialog){return states.get(dialog);}
  function clamp(dialog,left,top){
    const r=dialog.getBoundingClientRect();
    Object.assign(dialog.style,{margin:'0',left:Math.max(0,Math.min(left,document.documentElement.clientWidth-r.width))+'px',top:Math.max(0,Math.min(top,innerHeight-Math.min(r.height,80)))+'px'});
  }
  // Async help/SQL content can grow after the loading layer was positioned.
  // Keep the current user position where it still fits; only move back inside the viewport.
  function fit(dialog){
    if(!dialog.open||state(dialog)?.maximized)return;
    const r=dialog.getBoundingClientRect(),gap=Math.min(12,Math.max(0,(innerHeight-r.height)/2));
    clamp(dialog,r.left,Math.max(gap,Math.min(r.top,innerHeight-r.height-gap)));
  }
  const sizeObserver=new ResizeObserver(entries=>{for(const {target} of entries)fit(target);});
  function label(dialog){return document.getElementById(dialog.getAttribute('aria-labelledby'))?.textContent||'도움말';}
  function maximize(dialog){
    const s=state(dialog);if(s.maximized){dialog.classList.remove('help-maximized');dialog.setAttribute('style',s.beforeMaxStyle);s.maximized=false;const r=dialog.getBoundingClientRect();clamp(dialog,r.left,r.top);}
    else{s.beforeMaxStyle=dialog.getAttribute('style')||'';dialog.removeAttribute('style');s.maximized=true;dialog.classList.add('help-maximized');}
    const button=dialog.querySelector('[data-window-action="maximize"]');button.textContent=s.maximized?'❐':'□';button.setAttribute('aria-label',s.maximized?'이전 크기로 복원':'도움말 최대화');button.title=s.maximized?'이전 크기로 복원':'최대화';button.setAttribute('aria-pressed',String(s.maximized));
  }
  function minimize(dialog){
    const s=state(dialog);s.focus=document.activeElement;s.scroll=dialog.scrollTop;dialog.dataset.windowMinimized='true';
    s.restore.textContent=label(dialog)+' · 복원';s.bar.hidden=false;dialog.close('minimize');s.restore.focus({preventScroll:true});
  }
  function open(dialog,{reset=false}={}){
    const s=state(dialog),wasMinimized=dialog.dataset.windowMinimized==='true';
    if(!dialog.open&&!wasMinimized)s.origin=document.activeElement;
    delete dialog.dataset.windowMinimized;s.bar.hidden=true;
    if(reset){if(s.maximized)maximize(dialog);dialog.removeAttribute('style');s.scroll=0;}
    if(!dialog.open)dialog.showModal();
    if(wasMinimized&&!reset){dialog.scrollTop=s.scroll;(s.focus?.isConnected?s.focus:dialog.querySelector('[data-window-action="maximize"]'))?.focus({preventScroll:true});}
  }
  function close(dialog){const s=state(dialog);delete dialog.dataset.windowMinimized;s.bar.hidden=true;if(dialog.open)dialog.close();}
  function attachDrag(surface,handle,move=(left,top)=>clamp(surface,left,top)){
    let drag=null;
    handle.addEventListener('pointerdown',event=>{if(event.target.closest('button,a,input')||state(surface)?.maximized)return;const r=surface.getBoundingClientRect();drag={dx:event.clientX-r.left,dy:event.clientY-r.top};handle.setPointerCapture(event.pointerId);event.preventDefault();});
    handle.addEventListener('pointermove',event=>{if(drag)move(event.clientX-drag.dx,event.clientY-drag.dy);});
    for(const name of ['pointerup','pointercancel','lostpointercapture'])handle.addEventListener(name,()=>drag=null);
    handle.addEventListener('keydown',event=>{if(event.target!==handle||state(surface)?.maximized||!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(event.key))return;event.preventDefault();const r=surface.getBoundingClientRect();move(r.left+(event.key==='ArrowLeft'?-10:event.key==='ArrowRight'?10:0),r.top+(event.key==='ArrowUp'?-10:event.key==='ArrowDown'?10:0));});
  }
  for(const dialog of document.querySelectorAll('[data-help-window],[data-movable-window]')){
    const bar=document.createElement('div'),restore=document.createElement('button'),dismiss=document.createElement('button');
    bar.className='help-minimized';bar.hidden=true;restore.type=dismiss.type='button';restore.className=dismiss.className='secondary';dismiss.textContent='×';dismiss.setAttribute('aria-label','최소화한 도움말 닫기');
    bar.append(restore,dismiss);dock.append(bar);states.set(dialog,{bar,restore,maximized:false,scroll:0});
    restore.addEventListener('click',()=>open(dialog));dismiss.addEventListener('click',()=>{close(dialog);state(dialog).origin?.focus({preventScroll:true});});
    dialog.addEventListener('cancel',event=>{event.preventDefault();close(dialog);});
    dialog.addEventListener('keydown',event=>{if(event.key==='Escape'){event.preventDefault();close(dialog);}});
    dialog.addEventListener('click',event=>{const action=event.target.closest('[data-window-action]')?.dataset.windowAction;if(action==='minimize')minimize(dialog);if(action==='maximize')maximize(dialog);});
    attachDrag(dialog,dialog.querySelector('[data-window-drag]'));
    sizeObserver.observe(dialog);
  }
  const notification=document.getElementById('operation-status');
  attachDrag(notification,document.getElementById('operation-status-text'),(left,top)=>{
    Object.assign(notification.style,{right:'auto',bottom:'auto',transform:'none'});clamp(notification,left,top);notification.dataset.moved='true';
  });
  window.addEventListener('resize',()=>{if(notification.dataset.moved&&!notification.hidden){const r=notification.getBoundingClientRect();clamp(notification,r.left,r.top);}});
  window.addEventListener('resize',()=>{for(const dialog of states.keys())fit(dialog);});
  return {open,close,closeAll:()=>{for(const dialog of states.keys())close(dialog);},isMinimized:dialog=>dialog.dataset.windowMinimized==='true'};
})();
