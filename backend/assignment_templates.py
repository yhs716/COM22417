"""[ASSIGNMENT-CONNECTION] 원본·예측·전처리 테이블과 단일 프로시저의 고정 규약으로 연결합니다."""
import csv
import io
import json
import re
import hashlib
from pathlib import Path
from .db import ROOT
from .sql_files import query, execute
from . import service, sql_trace, progress_store

ASSIGNMENTS={
    'mission':{'title':'미션과제','route':'/mission','points':30,'training_table':'OML_MISSION_DATA','prediction_table':'OML_MISSION_PREDICT','prepared_table':'OML_MISSION_PREPARED','procedure_name':'OML_MISSION_RUN'},
    'creative':{'title':'창의과제','route':'/creative','points':20,'training_table':'OML_CREATIVE_DATA','prediction_table':'OML_CREATIVE_PREDICT','prepared_table':'OML_CREATIVE_PREPARED','procedure_name':'OML_CREATIVE_RUN'},
}
BASIC_POINTS=50
CREATIVE_MAX_CASES=10000
BASE_NAVIGATION=(('basic','/basic','기본과제'),)
BASIC_SCREENS=(('home','현황'),('data','학습데이터'),('models','모델 생성·비교'),('predictions','예측 실행'))
ACTIONS={key:{'label':label} for key,label in [('prepare','전처리 저장'),('prepared-data','저장된 모델 입력 조회'),('import','학습 CSV 적재'),('data','저장 데이터 조회'),('train','모델 생성'),('evaluate','TEST 평가'),('predict','예측 실행')]}
ACTIONS.update({key:{'label':label} for key,label in [('initial-train','최초 학습'),('retrain','전체 재학습'),('append-train','TRAIN 추가·전체 재생성'),('delete-model','선택 모델 삭제')]})

def navigation():
    return (*BASE_NAVIGATION,*((key,cfg['route'],cfg['title']) for key,cfg in ASSIGNMENTS.items()))

def assignment(key):
    if key not in ASSIGNMENTS:raise ValueError('미션 또는 창의과제를 선택하세요.')
    return dict(ASSIGNMENTS[key])

def mission_selection(conn, person, keys, value=None):
    if person['db_user'].upper()!=str(conn.username).upper():
        raise ValueError('미션 선택의 발급 계정을 확인하세요.')
    state=progress_store.load(conn,progress_store.mission_key(person))
    if value is None:
        saved=state.get('key','')
        if saved and saved not in keys:return ''
        return saved
    if not isinstance(value,str) or (value and value not in keys):
        raise ValueError('등록된 미션을 선택하세요.')
    state['key']=value
    progress_store.save(conn,state)
    return value


def configuration(user,key):
    """[FIXED-CONTRACT] DB 객체를 공개한 고정 이름에 맞춥니다. 웹 연결 설정 파일은 사용하지 않습니다."""
    return assignment(key)


def save_config(user,key,data):
    # 이전 클라이언트에서도 고정 규약 이외 이름을 저장하지 않습니다.
    cfg=assignment(key)
    if any(data.get(field)!=cfg[field] for field in ('training_table','prediction_table','procedure_name')):
        raise ValueError('테이블·프로시저 이름은 과제별 고정입니다. 안내된 이름으로 DB 객체를 만드세요.')

class AssignmentNotReady(Exception):
    def __init__(self,diagnostic):self.diagnostic=diagnostic;super().__init__(diagnostic['title'])

def readiness(conn,key,mission=None):
    cfg=configuration(conn.username,key)
    objects=query(conn,'objects.sql',**{field:cfg[field] for field in ('training_table','prediction_table','prepared_table','procedure_name')})
    issues=[]
    def issue(kind,name,object_type,message):
        issues.append({'kind':kind,'object_name':name,'object_type':object_type,'message':message})
    for field,kind in [('training_table','TABLE'),('prediction_table','TABLE'),('prepared_table','TABLE'),('procedure_name','PROCEDURE')]:
        match=next((r for r in objects if r['object_name']==cfg[field] and r['object_type']==kind),None)
        if not match:issue('missing',cfg[field],kind,cfg[field]+' '+kind+' 없음')
        elif match['status']!='VALID':issue('invalid',cfg[field],kind,cfg[field]+' 컴파일 오류')
    if any(r['object_name']==cfg['prepared_table'] and r['object_type']=='TABLE' for r in objects):
        columns={r['column_name'] for r in query(conn,'columns.sql',table_name=cfg['prepared_table'])}
        required={'PREP_MODE','SOURCE_KIND','CASE_ID','USE_YN','FIT_YN','EXCLUDE_REASON','PREPARED_AT'}
        if required-columns:issue('columns',cfg['prepared_table'],'TABLE',cfg['prepared_table']+' 운영 컬럼 누락: '+', '.join(sorted(required-columns)))
    args=query(conn,'procedure_arguments.sql',procedure_name=cfg['procedure_name'])
    expected=[('VARCHAR2','IN'),('VARCHAR2','IN'),('REF CURSOR','OUT'),('CLOB','OUT')]
    if any(r['object_name']==cfg['procedure_name'] for r in objects) and ([(r['data_type'],r['in_out']) for r in args]!=expected or [r['argument_name'] for r in args]!=['P_ACTION','P_MODE','P_RESULT','P_SQL']):
        issue('arguments',cfg['procedure_name'],'PROCEDURE','인자 불일치: P_ACTION VARCHAR2 IN, P_MODE VARCHAR2 IN, P_RESULT SYS_REFCURSOR OUT, P_SQL CLOB OUT')
    errors=query(conn,'procedure_errors.sql',procedure_name=cfg['procedure_name'])
    missing=[item['message'] for item in issues]
    result={'connected':True,'issues':issues,'config':cfg,'objects':objects,'arguments':args,'errors':errors,'missing':missing,'ready':not missing,
            'actions':{key:{'ready':not missing,'label':value['label'],'procedure':cfg['procedure_name']} for key,value in ACTIONS.items()}}
    if key=='mission' and mission is not None:
        from . import mission_binding
        result['mission']=mission_binding.inspect(conn,mission,result)
        result['ready']=result['ready'] and result['mission']['ready']
        if not result['mission']['ready']:
            issue('mission',cfg['procedure_name'],'PROCEDURE',result['mission']['reason'])
            missing.append(result['mission']['reason'])
        for action in result['actions'].values():action['ready']=result['ready']
    return result

def table_schema(conn,key,kind='training'):
    fields={'training':'training_table','prepared':'prepared_table','prediction':'prediction_table'}
    if kind not in fields:raise ValueError('원본·전처리·예측 테이블을 선택하세요.')
    name=configuration(conn.username,key)[fields[kind]]
    columns=query(conn,'schema_columns.sql',table_name=name)
    if not columns:raise ValueError('본인 계정에 '+name+' 테이블을 먼저 생성하세요.')
    result=[]
    for column in columns:
        datatype=column['data_type']
        if datatype in ('NVARCHAR2','NCHAR'):
            datatype+='('+str(column['char_length'])+')'
        elif datatype in ('VARCHAR2','CHAR'):
            size=column['char_length'] if column['char_used']=='C' else column['data_length']
            datatype+='('+str(size)+(' CHAR' if column['char_used']=='C' else ' BYTE')+')'
        elif datatype=='NUMBER' and column['data_precision'] is not None:
            datatype+='('+str(column['data_precision'])+((','+str(column['data_scale'])) if column['data_scale'] else '')+')'
        result.append({'name':column['column_name'],'type':datatype,'nullable':'필수' if column['nullable']=='N' else 'NULL 허용',
                       'description':column['comments'] or '', 'rules':column['data_default'] or ''})
    return {'name':conn.username.upper()+'.'+name,'kind':kind,'columns':result,
            'description':'본인 계정의 실제 테이블 컬럼입니다. 창의과제는 생성·처리 SQL을 제공하지 않습니다.'}


def diagnostic(key,action,state=None,error=None):
    cfg=(state or {}).get('config') or assignment(key)
    codes=re.findall(r'ORA-\d{5}|PLS-\d{5}|DPY-\d{4}|DPI-\d{4}',str(error or ''))
    path=f'sql/custom/{key}/02_procedure.sql'
    locations=[{'path':'DB USER_SOURCE · '+cfg['procedure_name'],'line':int(r['line']),
                'object':cfg['procedure_name'],'db_line':r['line'],'text':r['text'],
                'object_type':'PROCEDURE','object_line':r['line'],'code':r['text'],
                'source':'USER_SOURCE','source_line':int(r['line'])}
               for r in (state or {}).get('errors',[])]
    issues=(state or {}).get('issues',[])
    absent=[item['object_name'] for item in issues if item['kind']=='missing']
    title=('다음 객체를 생성하세요: '+', '.join(absent)) if absent else '테이블·프로시저의 수정할 내용을 확인하세요.'
    steps=(state or {}).get('missing',[])+[
        '현황에서 미션을 선택하고 선택 미션 SQL 가이드의 DATA → PREPARED → PREDICT → RUN 순서로 생성·수정하세요.' if key=='mission' else '직접 작성한 테이블·프로시저 SQL을 확인하고 표시된 연결 이름과 입출력 규약에 맞춰 수정하세요.',
        'SQL Developer에서 웹과 같은 계정으로 테이블 → 프로시저 순서로 F5 실행하세요.',
        '생성·수정 후 웹에서 테이블·프로시저 확인을 누르면 연결됩니다. 서버를 다시 켤 필요는 없습니다.']
    if error is not None:
        title='DB에는 접속했지만 과제 작업을 완료하지 못했습니다.'
        steps=['오류 코드와 작업한 SQL을 확인하세요. 테이블이 없다는 뜻으로 단정하지 마세요.',
               'SQL Developer의 같은 계정에서 객체 이름·조회 권한·프로시저를 확인한 뒤 다시 실행하세요.']
    return {'title':title,'code':codes[0] if codes else 'ASSIGNMENT-QUERY' if error is not None else 'OBJECT-NOT-READY',
            'category':'query' if error is not None else 'objects','db_connected':True,
            'stage':cfg['title'],'steps':steps,'issues':issues,
            'examples':[],
            'locations':locations,'help_screen':key,'sources':[], 'commands':[],
            'procedure':f"{cfg['procedure_name']}(p_action, p_mode, p_result, p_sql)"}

def csv_payload(raw, *, encoded=True):
    """[CUSTOM-CSV] 헤더와 원문만 확인합니다. 전처리·라벨을 Python에서 만들지 않습니다."""
    if len(raw)>2*1024*1024:raise ValueError('CSV는 2 MiB 이하입니다.')
    try:
        reader=csv.DictReader(io.StringIO(raw.decode('utf-8-sig')),strict=True)
        names=reader.fieldnames or []
        if not names or len(set(n.upper() for n in names))!=len(names) or any(not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,127}',n) for n in names):
            raise ValueError('중복 없는 영문 컬럼명 헤더를 확인하세요.')
        values=[]
        for count,row in enumerate(reader,1):
            if count>5000 or None in row or None in row.values():raise ValueError('CSV는 1~5,000행이며 열 수가 일치해야 합니다.')
            values.append(row)
        if not values:raise ValueError('CSV 데이터 행이 없습니다.')
        return (json.dumps(values,ensure_ascii=False) if encoded else values),len(values)
    except (UnicodeError,csv.Error):raise ValueError('UTF-8 CSV 형식을 확인하세요.') from None

def load_custom(conn,cfg,payload,prediction=False,*,append=False,mode='RAW',owner=None):
    table=cfg['prediction_table'] if prediction else cfg['training_table']
    values=json.loads(payload) if isinstance(payload,str) else payload
    headers=list(values[0]);columns=query(conn,'columns.sql',table_name=table)
    if not columns:raise ValueError('본인 계정에 '+table+' 테이블을 먼저 생성하세요. CSV에 맞는 테이블 정의를 확인하세요.')
    allowed={r['column_name']:r for r in columns}
    if any(name.upper() not in allowed for name in headers):raise ValueError('CSV와 테이블 컬럼이 다릅니다. 01_tables.sql을 CSV에 맞게 수정하세요. 없는 컬럼: '+', '.join(n for n in headers if n.upper() not in allowed))
    if 'CASE_ID' not in [h.upper() for h in headers]:raise ValueError('행 식별자 CASE_ID가 필요합니다.')
    missing=[r['column_name'] for r in columns if r['nullable']=='N' and not r['data_default'] and r['column_name'] not in [h.upper() for h in headers]]
    if missing:raise ValueError('CSV 필수 컬럼 누락: '+', '.join(missing))
    if append and any({k.upper():v for k,v in row.items()}.get('SPLIT')!='TRAIN' or {k.upper():v for k,v in row.items()}.get('USE_YN')!='Y' for row in values):raise ValueError('추가 CSV는 공백 없는 대문자로 USE_YN=Y, SPLIT=TRAIN 행만 포함하세요.')
    # 이름은 위에서 검증하고 값은 반드시 바인드합니다. UPDATE/DELETE 조건 SQL을 입력받지 않습니다.
    replacements={'table':owner+'.'+table if owner else table,'columns':'\n , '.join(n.upper() for n in headers),'values':'\n , '.join(':'+n for n in headers)}
    try:
        if not append:execute(conn,'queries/custom_delete.sql',replacements={'table':replacements['table']})
        loaded=execute(conn,'queries/custom_insert.sql',replacements=replacements,many=values)
        if owner is not None and loaded!=len(values):raise ValueError('CSV 적재 행 수가 일치하지 않아 기존 데이터를 복구했습니다.')
        if append:service.run_model(conn,'VALIDATE',mode,procedure=cfg['procedure_name'],source_file=f"sql/custom/{cfg['route'].strip('/')}/02_procedure.sql")
        conn.commit();sql_trace.add('COMMIT',kind='TRANSACTION')
        return loaded
    except Exception:conn.rollback();sql_trace.add('ROLLBACK',kind='TRANSACTION');raise

def import_csv(conn,key,values,owner,*,prediction=False,mission=None):
    """선택 파일을 같은 계정의 고정 대상 1개에 교체합니다. DDL·전처리·학습은 실행하지 않습니다."""
    cfg=assignment(key)
    if not re.fullmatch(r'[A-Z][A-Z0-9_$#]{0,29}',owner) or conn.username.upper()!=owner:
        raise ValueError('발급 DB 계정과 실제 연결 계정이 다릅니다.')
    execute(conn,'queries/csv_owner.sql',{'owner':owner})
    if key=='mission' and mission is not None:
        from .mission_binding import table_issues
        issues=table_issues(mission,'prediction' if prediction else 'training',query(conn,'schema_columns.sql',table_name=cfg['prediction_table' if prediction else 'training_table']))
        if issues:raise ValueError('선택 미션과 적재 대상 테이블이 다릅니다: '+', '.join(issues))
    if key=='creative':
        other=cfg['training_table'] if prediction else cfg['prediction_table']
        count=query(conn,'columns.sql',table_name=other)
        total=execute(conn,'queries/custom_count.sql',replacements={'table':owner+'.'+other},fetch=True)[0]['rows_count'] if count else 0
        if total+len(values)>CREATIVE_MAX_CASES:
            raise ValueError('창의과제는 학습·TEST·예측 원본 합계 10,000행 이하여야 합니다.')
    loaded=load_custom(conn,cfg,values,prediction,owner=owner)
    saved=service.read_state(conn)
    proof=saved.get('practice_evidence',{}).get(key,{})
    if prediction:
        proof.pop('predict',None)
    else:
        saved.get('assignment_preparations',{}).pop(key,None)
        saved.get('assignments',{}).pop(key,None)
        saved.get('practice_evidence',{}).pop(key,None)
    service.write_state(conn,saved)
    return {'loaded_rows':loaded,'table':owner+'.'+cfg['prediction_table' if prediction else 'training_table'],
            'message':('예측' if prediction else '학습·TEST')+' CSV 적재 완료 · '+str(loaded)+'행'}


def run(conn,key,action,payload=None,mode='RAW',source_kind='ALL',mission_key=''):
    if action not in ('data','prepared-data','prediction-data','evaluate','predict'):
        raise ValueError('미션·창의과제의 생성·적재·전처리·학습·삭제는 SQL Developer에서 직접 수행한 뒤 객체·모델 연계를 확인하세요.')
    cfg=configuration(conn.username,key)
    if action in ('data','prediction-data'):
        target=cfg['training_table' if action=='data' else 'prediction_table']
        if not query(conn,'columns.sql',table_name=target):raise ValueError('본인 계정에 '+target+' 테이블을 먼저 생성하세요.')
        return {'rows':execute(conn,'queries/custom_rows.sql',replacements={'table':conn.username.upper()+'.'+target},fetch=True)}
    state=readiness(conn,key,mission=mission_key if key=='mission' else None)
    if not state['ready']:raise AssignmentNotReady(diagnostic(key,action,state))
    if mode not in ('RAW','CLEAN'):raise ValueError('RAW 또는 CLEAN을 선택하세요.')
    if action=='prepared-data':return {'rows':service.get_prepared_data(conn,mode,source_kind,table=cfg['prepared_table'])}
    actions={'evaluate':'EVALUATE','predict':'PREDICT'}
    if action in ('evaluate','predict'):
        if key=='mission' and not state['mission']['linked']:
            raise ValueError('객체 준비는 확인됐습니다. 전처리·모델 단계에서 SQL 실행 결과를 연계한 뒤 평가·예측하세요.')
        if not any(m['variant']==mode and m['is_current'] for m in model_state(conn,key)):
            raise ValueError('직접 SQL로 전처리·모델 생성을 완료한 뒤 현황의 객체·모델 연계 확인을 누르세요. 연계 후 원본이나 프로시저가 바뀌면 직접 재학습하고 다시 확인하세요.')
        if key=='mission':
            from .mission_binding import model_matches
            if not model_matches(conn,'OML_MISSION_'+mode+'_MODEL',mission_key):
                raise ValueError('모델 속성이 선택 미션과 다릅니다. 직접 재학습하고 다시 연계하세요.')
    from . import practice_evidence
    practice_evidence.begin(conn,key,action,mode)
    result=service.run_model(conn,actions[action],mode,
                             procedure=cfg['procedure_name'],source_file=f'sql/custom/{key}/02_procedure.sql')
    if action in ('evaluate','predict') and result:
        required={'variant','actual','predicted','n'} if action=='evaluate' else {'case_id','predicted','probability'}
        if any(not required.issubset(row) for row in result):raise ValueError('프로시저 OUT 컬럼 규약을 확인하세요: '+', '.join(sorted(required)))
    context={}
    if action=='predict':
        values=execute(conn,'queries/custom_fingerprint_rows.sql',replacements={'table':cfg['prediction_table']},fetch=True)
        context['input_fingerprint']=hashlib.sha256(json.dumps(values,sort_keys=True,default=str).encode()).hexdigest()
    verified=practice_evidence.record(conn,key,action,mode,result,inputs=values if action=='predict' else None,mission_key=mission_key)
    return {'rows':result,'verified':verified,'message':ACTIONS[action]['label']+(' 성공' if verified else ' · 결과 확인 필요'),**context}


def input_state(conn,state):
    counts={}
    for field,name in (('training_table','training'),('prediction_table','prediction')):
        table=state['config'][field]
        exists=any(o['object_name']==table and o['object_type']=='TABLE' and o['status']=='VALID' for o in state['objects'])
        counts[name]=execute(conn,'queries/custom_count.sql',replacements={'table':table},fetch=True)[0]['rows_count'] if exists else 0
    return {'state':{'total_rows':counts['training']},'prediction_storage':{'rows':counts['prediction']}}


def verification_state(conn,key,state):
    """객체 존재는 조회로 확인하고 전처리·모델 성공은 현재 연계 지문으로 제한합니다."""
    linked=state['ready'] and (key!='mission' or state.get('mission',{}).get('linked',False))
    preparation=preparation_status(conn,key) if state['ready'] else {}
    if not linked:
        preparation={mode:{**item,'ready':False} for mode,item in preparation.items()}
    return {'models':model_state(conn,key,verify=linked),'preparation':preparation}


def link_external(conn,key,mission=None):
    state=readiness(conn,key,mission=mission if key=='mission' else None)
    if key=='mission':
        from . import mission_binding
        if 'mission' not in state:raise ValueError('연계할 미션을 먼저 선택하세요.')
        mission_binding.require(state['mission'],linking=True)
    elif not state['ready']:raise AssignmentNotReady(diagnostic(key,'status',state))
    cfg=state['config']
    counts={r['prep_mode']:r for r in execute(conn,'queries/prepared_count.sql',replacements={'table':cfg['prepared_table']},fetch=True)}
    source=training_fingerprint(conn,key)
    saved=service.read_state(conn)
    if key=='mission':mission_binding.bind(saved,state['mission'])
    preparations=saved.setdefault('assignment_preparations',{}).setdefault(key,{})
    linked=saved.setdefault('assignments',{}).setdefault(key,{})
    for model in model_state(conn,key,verify=False):
        mode=model['variant'];count=counts.get(mode,{})
        if count.get('rows_count'):
            preparations[mode]={'source':source,'origin':'external'}
        else:preparations.pop(mode,None)
        newer=key!='mission' or bool(model.get('trained_at') and str(model['trained_at'])>=state['mission']['model_after'])
        if key=='mission' and model['exists'] and newer:
            newer=mission_binding.model_matches(conn,model['model_name'],mission)
        if model['exists'] and count.get('fit_rows',0)>0 and newer:
            linked[mode]={'fingerprint':training_fingerprint(conn,key,mode),'created':model['trained_at'],'origin':'external'}
        else:linked.pop(mode,None)
    service.write_state(conn,saved)
    return {'message':'본인이 직접 생성한 객체·모델을 연계했습니다. 학습 내용의 타당성은 TEST 평가로 확인하세요.','models':model_state(conn,key),'preparation':preparation_status(conn,key)}


def training_source(conn,cfg):
    return [execute(conn,'queries/custom_fingerprint_rows.sql',replacements={'table':cfg['training_table']},fetch=True),
            query(conn,'procedure_source.sql',procedure_name=cfg['procedure_name'])]


def training_fingerprint(conn,key,mode=None,*,source_material=None):
    """자유 컬럼의 모든 행과 DB 프로시저 원문을 비교해 외부 SQL 변경도 감지합니다."""
    cfg=configuration(conn.username,key)
    material=list(source_material if source_material is not None else training_source(conn,cfg))
    if mode is not None:material.append(service.prepared_values(conn,cfg['prepared_table'],mode))
    return service.json_fingerprint(material)


def model_state(conn,key,*,verify=True):
    cfg=configuration(conn.username,key);prefix=cfg['procedure_name'][:-4]
    found=query(conn,'assignment_models.sql',raw_model=prefix+'_RAW_MODEL',clean_model=prefix+'_CLEAN_MODEL')
    saved=service.read_state(conn).get('assignments',{}).get(key,{})
    source_material=training_source(conn,cfg) if verify and found else None
    result=[]
    for mode in ('RAW','CLEAN'):
        name=prefix+'_'+mode+'_MODEL';model=next((m for m in found if m['model_name']==name),{})
        entry=saved.get(mode,{})
        result.append({'variant':mode,'model_name':name,'exists':bool(model),'trained_at':model.get('creation_date'),
                       'is_current':bool(verify and model and entry.get('fingerprint')==training_fingerprint(conn,key,mode,source_material=source_material) and entry.get('created')==model.get('creation_date'))})
    return result


def preparation_status(conn,key):
    cfg=configuration(conn.username,key);source=training_fingerprint(conn,key)
    saved=service.read_state(conn).get('assignment_preparations',{}).get(key,{})
    counts={r['prep_mode']:r for r in execute(conn,'queries/prepared_count.sql',replacements={'table':cfg['prepared_table']},fetch=True)}
    return {mode:{'ready':bool(counts.get(mode,{}).get('rows_count') and saved.get(mode,{}).get('source')==source),
                  'rows':counts.get(mode,{}).get('rows_count',0),'fit_rows':counts.get(mode,{}).get('fit_rows',0),
                  'test_rows':counts.get(mode,{}).get('test_rows',0)} for mode in ('RAW','CLEAN')}
