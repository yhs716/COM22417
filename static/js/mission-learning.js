// [MISSION-CONTEXT] Same catalog explanations in the data and schema layers; no DB requests.
function missionContextNode(tag,className,value){
  const node=document.createElement(tag);if(className)node.className=className;
  if(value!==undefined&&value!==null)node.textContent=value;return node;
}
function renderMissionContext(id,item){
  const root=$(id);if(!root)return;root.replaceChildren();root.hidden=!item?.learning;if(!item?.learning)return;
  root.dataset.mission=item.key;
  const overview=missionContextNode('div','mission-context-overview');
  for(const [label,value] of [['미션 목적',item.learning.purpose],['활용 사례',item.learning.use_case]]){
    const card=missionContextNode('div','mission-context-fact');card.append(missionContextNode('h3','',label),missionContextNode('p','',value));overview.append(card);
  }
  const heading=missionContextNode('div','mission-context-heading');
  heading.append(missionContextNode('h3','','설명변수 이해'),missionContextNode('span','','교육용 합성 데이터 · 0~100 점수 · 단위 없음'));
  const features=missionContextNode('div','mission-context-features');
  for(const field of item.layout.filter(field=>field.role.includes('설명변수'))){
    const card=missionContextNode('article','mission-feature-card'),code=missionContextNode('code','',field.name);
    code.lang='en';card.dataset.field=field.name;
    card.append(missionContextNode('h4','',field.korean_name),code,missionContextNode('p','',field.meaning));
    const scale=missionContextNode('div','mission-feature-scale');
    scale.append(missionContextNode('span','','낮음 · '+field.low_meaning),missionContextNode('span','','높음 · '+field.high_meaning));card.append(scale);features.append(card);
  }
  const target=item.layout.find(field=>field.name==='label'),targetNote=missionContextNode('p','mission-target-note');
  targetNote.append(missionContextNode('strong','','타깃 · '+target.korean_name+' '),missionContextNode('span','',target.meaning));
  const quality=missionContextNode('details','mission-quality'),summary=missionContextNode('summary','','정상값·이상치 판단 · 0~100 정상 / 빈칸·unknown·범위 밖 확인');
  const rules=missionContextNode('div','mission-quality-rules');
  for(const [kind,title,body] of [
    ['valid','정상 · 0~100','0과 100도 유효합니다. 52.983 같은 소수도 정상입니다.'],
    ['missing','결측 · 빈칸','수집되지 않은 값입니다. 숫자 0과 구분합니다.'],
    ['invalid','형식 오류 · unknown','숫자가 아닌 문자열입니다. 숫자 변환 시 NULL이 됩니다.'],
    ['outlier','범위 밖 · 999999','숫자지만 0~100 밖입니다. RAW는 유지하고 CLEAN은 NULL로 처리합니다.']
  ]){
    const rule=missionContextNode('div');rule.dataset.quality=kind;
    rule.append(missionContextNode('strong','',title),missionContextNode('p','',body));rules.append(rule);
  }
  quality.append(summary,rules,missionContextNode('p','mission-quality-note','빈칸·unknown·999999는 TRAIN에 넣은 정제 연습용 수집 오류입니다. 원본을 보존하고 PREPARED의 FIT_YN·제외 사유를 확인하세요. TEST 300행과 정답은 바꾸지 않습니다.'));
  root.append(overview,heading,features,targetNote,quality);
}
