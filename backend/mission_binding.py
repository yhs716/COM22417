"""선택 미션과 실제 DB 규약을 대조합니다. 조회는 연계 기록을 만들지 않습니다."""
import json
import re
from pathlib import Path
from . import service
from .sql_files import query
from .mission_guide import table_sql


def catalog():
    return json.loads((Path(__file__).resolve().parents[1]/'data/catalog.json').read_text(encoding='utf-8'))


def table_issues(item, kind, columns):
    actual={row['column_name']:row for row in columns}
    issues=[]
    for expected in table_sql(item,kind)['columns']:
        name=expected['name'];row=actual.get(name);typ=expected['type']
        if not row or row['data_type'].split('(')[0]!=typ.split('(')[0]:
            issues.append(name+' '+typ+' 필요')
        elif '(' in typ and row.get('char_length',0)<int(re.search(r'\d+',typ)[0]):
            issues.append(name+' 길이 부족')
        elif expected['nullable']=='필수' and row.get('nullable')!='N':
            issues.append(name+' NOT NULL 필요')
    return issues


def inspect(conn, selected, state):
    items=catalog();item=next((i for i in items if i['key']==selected),None)
    cfg=state['config'];objects=state['objects']
    tables={kind:query(conn,'schema_columns.sql',table_name=cfg[field]) if any(o['object_name']==cfg[field] and o['object_type']=='TABLE' for o in objects) else []
            for kind,field in [('training','training_table'),('prepared','prepared_table'),('prediction','prediction_table')]}
    source=query(conn,'procedure_source.sql',procedure_name=cfg['procedure_name']) if any(o['object_name']==cfg['procedure_name'] for o in objects) else []
    # 주석은 증거로 쓰지 않습니다. SQL 문자열 안의 컬럼·라벨은 검사합니다.
    sql=re.sub(r'/\*.*?\*/|--[^\n]*','', ''.join(row['text'] or '' for row in source),flags=re.S).upper()
    features={i['key']:{name.upper() for name in i['columns'][1:4]} for i in items}
    tokens=set(re.findall(r'[A-Z][A-Z0-9_]*',sql))
    candidates=[]
    for candidate in items:
        own=features[candidate['key']]
        foreign=set.union(*(v for k,v in features.items() if k!=candidate['key']))-own
        labels=next(field['valid'] for field in candidate['layout'] if field['name']=='label').split(' / ')
        if (all(not table_issues(candidate,kind,rows) for kind,rows in tables.items())
                and own<=tokens and not foreign&tokens and all("'"+label+"'" in sql for label in labels)):
            candidates.append(candidate)
    detected=candidates[0] if len(candidates)==1 else None
    saved=service.read_state(conn).get('mission_binding',{})
    applied=next((i for i in items if i['key']==saved.get('key')),None)
    stamp=service.json_fingerprint([tables,objects,source])
    can_link=bool(item and state['ready'] and detected and detected['key']==selected)
    linked=bool(can_link and saved.get('key')==selected and saved.get('stamp')==stamp)
    code='matched' if can_link else 'mismatch' if detected and item else 'unknown'
    reason='' if can_link else '선택 미션과 DB가 다르거나 적용 중입니다. DATA → PREPARED → PREDICT → RUN을 확인하세요.' if item else '미션을 선택하세요.'
    problems=[]
    if item:
        for kind,title in [('training','DATA'),('prepared','PREPARED'),('prediction','PREDICT')]:
            wrong=table_issues(item,kind,tables[kind])
            if wrong:problems.append(title+': '+', '.join(wrong))
        if not features[selected]<=tokens:problems.append('RUN: 선택 미션 설명변수 확인 필요')
    return dict(selected=selected,selected_title=item['title'] if item else '선택 전',
                detected=detected['key'] if detected else '',detected_title=detected['title'] if detected else '미확인 · 객체별 확인 필요',
                applied=saved.get('key',''),applied_title=applied['title'] if applied else '연계 기록 없음',
                ready=can_link,linked=linked,can_link=can_link,code=code,reason=reason,stamp=stamp,
                problems=problems,
                model_after=max((str(o['last_ddl_time']) for o in objects if o.get('last_ddl_time') and o['object_name']!=cfg['prediction_table']),default=''),
                tables={kind:bool(item and not table_issues(item,kind,rows)) for kind,rows in tables.items()})


def require(info, *, linking=False):
    if not info['can_link' if linking else 'ready']:
        raise ValueError(info['reason'])


def bind(saved, info):
    require(info,linking=True)
    previous=saved.get('mission_binding',{}).get('key')
    if previous and previous!=info['selected']:
        saved.get('practice_evidence',{}).pop('mission',None)
    saved['mission_binding']={'key':info['selected'],'stamp':info['stamp']}


def model_matches(conn, name, selected):
    items=catalog();own=next(i for i in items if i['key']==selected)
    features={n.upper() for n in own['columns'][1:4]}
    foreign={n.upper() for i in items if i['key']!=selected for n in i['columns'][1:4]}-features
    rows=query(conn,'dictionary_attributes.sql',model_name=name)
    inputs={r['attribute_name'] for r in rows if r['target']=='NO'}
    return bool(inputs&features and not inputs&foreign and any(r['target']=='YES' and r['attribute_name']=='LABEL' for r in rows))
