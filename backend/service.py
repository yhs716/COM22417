"""[WEB-TO-SQL] 조회/적재는 SQL 파일, 모델 작업은 OML_BASIC_RUN 한 개를 호출합니다."""
import hashlib
import json
import re
import time
import oracledb
from .db import ROOT, rows
from .sql_files import query, execute, read_sql
from . import sql_trace
from . import progress_store

BASIC={'training_table':'OML_BASIC_DATA','prediction_table':'OML_BASIC_PREDICT','prepared_table':'OML_BASIC_PREPARED','procedure_name':'OML_BASIC_RUN'}

def state_path(conn):
    # 이전 파일의 1회 이관·운영 점검용입니다. 현재 판정은 DB만 읽습니다.
    return progress_store.legacy_path(conn, ROOT)

def read_state(conn):
    return progress_store.load(conn)

def write_state(conn,state):
    progress_store.save(conn,state)

def prepared_values(conn,table,mode):
    """자유 컬럼도 해시에 포함하되 저장 시각과 예측 입력은 모델 최신 판정에서 제외합니다."""
    from .sql_files import identifier
    values=execute(conn,'queries/prepared_fingerprint_rows.sql',{'variant':mode},replacements={'table':identifier(table)},fetch=True)
    return [{k:v for k,v in row.items() if k!='prepared_at'} for row in values]

def json_fingerprint(value):
    """이전 json.dumps와 같은 해시를 만들되 큰 JSON 문자열 사본은 만들지 않습니다."""
    digest = hashlib.sha256()
    for chunk in json.JSONEncoder(sort_keys=True, default=str).iterencode(value):
        digest.update(chunk.encode())
    return digest.hexdigest()


def fingerprint_source(conn):
    return [query(conn,'training_rows.sql',use_yn='ALL',split='ALL'),
            query(conn,'procedure_source.sql',procedure_name='OML_BASIC_RUN')]


def fingerprint(conn,mode=None,*,source_material=None):
    # SQL Developer에서 직접 수정한 행·프로시저도 감지합니다. 개인 정보나 접속값은 해시에 넣지 않습니다.
    material=list(source_material if source_material is not None else fingerprint_source(conn))
    if mode is not None:material.append(prepared_values(conn,BASIC['prepared_table'],mode))
    return json_fingerprint(material)

def get_prepared_data(conn,mode='RAW',source_kind='ALL',*,table=None):
    """[QUERY-PREPARED] 전처리로 저장한 값과 FIT_YN을 읽습니다. 행 변경은 DB에서 합니다."""
    from .sql_files import identifier
    if mode not in ('RAW','CLEAN') or source_kind not in ('ALL','TRAIN','TEST','PREDICT'):raise ValueError('준비 방식·용도를 확인하세요.')
    return execute(conn,'queries/prepared_rows.sql',{'variant':mode,'source_kind':source_kind},replacements={'table':identifier(table or BASIC['prepared_table'])},fetch=True)

def preparation_status(conn):
    source=fingerprint(conn);saved=read_state(conn).get('preparations',{})
    counts={r['prep_mode']:r for r in execute(conn,'queries/prepared_count.sql',replacements={'table':BASIC['prepared_table']},fetch=True)}
    return {mode:{'ready':bool(counts.get(mode,{}).get('rows_count') and saved.get(mode,{}).get('source')==source),
                  'rows':counts.get(mode,{}).get('rows_count',0),'fit_rows':counts.get(mode,{}).get('fit_rows',0),
                  'test_rows':counts.get(mode,{}).get('test_rows',0)} for mode in ('RAW','CLEAN')}

def prepare_model_data(conn,mode):
    """[PREPARE-DATA] 원본 → INSERT SELECT → PREPARED. 선택 방식만 교체하며 모델은 생성하지 않습니다."""
    if mode not in ('RAW','CLEAN'):raise ValueError('RAW 또는 CLEAN을 선택하세요.')
    before=fingerprint(conn)
    result=run_model(conn,'PREPARE',mode)
    after=fingerprint(conn)
    if before!=after:
        saved=read_state(conn);saved.setdefault('preparations',{}).pop(mode,None);write_state(conn,saved)
        raise ValueError('전처리 중 원본이나 프로시저가 변경되었습니다. 전처리를 다시 저장하세요.')
    saved=read_state(conn);saved.setdefault('preparations',{})[mode]={'source':after};write_state(conn,saved)
    return result

def model_rows(conn,stamp=None,*,verify=True):
    saved=read_state(conn)
    existing={r['model_name']:r for r in query(conn,'models.sql')}
    source_material=fingerprint_source(conn) if verify and existing else None
    result=[]
    for mode in ('RAW','CLEAN'):
        name='OML_BASIC_'+mode+'_MODEL';entry=saved.get('models',{}).get(mode,{})
        db=existing.get(name,{});current=bool(verify and db and entry.get('fingerprint')==fingerprint(conn,mode,source_material=source_material) and entry.get('created')==db.get('creation_date'))
        result.append({'variant':mode,'model_name':name,'trained_at':db.get('creation_date'),
                       'exists':int(bool(db)),
                       'trained_rev':entry.get('fingerprint','')[:10] or None,'is_current':int(current),
                       'is_confirmed':int(current and saved.get('confirmed')==mode)})
    return result

def get_data(conn,use_yn='ALL',split='ALL'):
    """[QUERY-DATA] 화면 필터를 그대로 바인드합니다. 값이 SQL 문법으로 해석되지 않습니다."""
    return query(conn,'training_rows.sql',use_yn=use_yn,split=split)

def invalidate_training_state(conn):
    """원본 교체·삭제 후 이전 준비·학습·확정 기록을 해제합니다. DB 모델은 삭제하지 않습니다."""
    state=read_state(conn)
    state.pop('preparations',None)
    state['models']={}
    state['confirmed']=None
    write_state(conn,state)


def load_csv(conn,values,*,prediction=False,initial=False):
    """[LOAD-CSV] DELETE + 500행 executemany + 마지막 COMMIT. 오류가 나면 원래 행으로 ROLLBACK합니다."""
    kind='prediction' if prediction else 'training'
    columns=('case_id','return_pct','range_pct','volume_change_pct','close_price','stock','signal','week_ending')+(() if prediction else ('split','use_yn'))
    bindings=({key:row.get(key) for key in columns} for row in values)
    try:
        if not initial:execute(conn,'queries/delete_'+kind+'.sql')
        execute(conn,'queries/insert_'+kind+'.sql',many=bindings)
        conn.commit();sql_trace.add('COMMIT',kind='TRANSACTION')
    except Exception:
        conn.rollback();sql_trace.add('ROLLBACK',kind='TRANSACTION');raise
    if not prediction:invalidate_training_state(conn)

def save_row(conn,value):
    try:
        if execute(conn,'queries/save_row.sql',value)==0:execute(conn,'queries/insert_training.sql',value)
        conn.commit();sql_trace.add('COMMIT',kind='TRANSACTION')
    except Exception:conn.rollback();raise
    saved=read_state(conn);saved['confirmed']=None;write_state(conn,saved)

def delete_row(conn,case_id):
    execute(conn,'queries/delete_row.sql',{'case_id':case_id});conn.commit()
    sql_trace.add('COMMIT',kind='TRANSACTION')
    saved=read_state(conn);saved['confirmed']=None;write_state(conn,saved)

def run_model(conn,action,mode,*,procedure='OML_BASIC_RUN',source_file='sql/classifier.sql'):
    """[CALL-PROCEDURE] Python에서 한 프로시저를 호출하는 실제 코드입니다.
    IN: action, mode / OUT: output(행), executed_sql(실제 SELECT).
    DB에 마지막으로 적용한 프로시저를 호출합니다. classifier.sql을 읽어 컴파일하지 않습니다.
    source_file은 실행 기록의 수정 위치 표시용입니다. 정의 적용은 별도의 db-init/F5 작업입니다.
    """
    if action not in ('PREPARE','TRAIN','INIT','RETRAIN','ADD_TRAIN','DELETE','VALIDATE','EVALUATE','PREDICT') or mode not in ('RAW','CLEAN'):raise ValueError('작업·모델 구분을 확인하세요.')
    from .sql_files import identifier
    procedure=identifier(procedure)
    owner=conn.username.upper()
    if not re.fullmatch(r'[A-Z][A-Z0-9_$#]{0,29}',owner):raise ValueError('발급된 DB 소유 계정을 확인하세요.')
    sql=read_sql('queries/call_classifier.sql').rstrip('/').strip().replace('OML_BASIC_RUN',owner+'.'+procedure)
    started=time.perf_counter()
    db_source=query(conn,'procedure_source.sql',procedure_name=procedure)
    with conn.cursor() as cursor,conn.cursor() as output:
        executed_sql=cursor.var(oracledb.DB_TYPE_CLOB)
        try:
            cursor.execute(sql,{'p_action':action,'p_mode':mode,'p_result':output,'p_sql':executed_sql})
            result=rows(output)
            raw=executed_sql.getvalue();actual=raw.read() if hasattr(raw,'read') else raw
            sql_trace.add(sql,{'p_action':action,'p_mode':mode},path='backend/service.py',kind='PL/SQL',
                          elapsed=time.perf_counter()-started,row_count=len(result),
                          out_parameters=['p_result: SYS_REFCURSOR','p_sql: CLOB'],
                          procedure_source=''.join(r['text'] for r in db_source),source_file=source_file,
                          runtime_sql=actual,action=action,mode=mode)
            return result
        except Exception:
            sql_trace.add(sql,{'p_action':action,'p_mode':mode},path='backend/service.py',kind='PL/SQL',status='error',
                          procedure_source=''.join(r['text'] for r in db_source),source_file=source_file)
            raise

def train_model(conn,mode,action='TRAIN'):
    """[TRAIN-LIFECYCLE] INIT=모델 없을 때, RETRAIN/ADD_TRAIN=기존 모델 전체 재생성."""
    if mode not in ('RAW','CLEAN') or action not in ('TRAIN','INIT','RETRAIN','ADD_TRAIN'):raise ValueError('학습 종류와 RAW/CLEAN을 확인하세요.')
    exists=any(r['model_name']=='OML_BASIC_'+mode+'_MODEL' for r in query(conn,'models.sql'))
    if action=='INIT' and exists:raise ValueError('이미 모델이 있습니다. 전체 재학습을 선택하세요.')
    if action in ('RETRAIN','ADD_TRAIN') and not exists:raise ValueError('모델이 없습니다. 최초 학습을 먼저 실행하세요.')
    if not preparation_status(conn)[mode]['ready']:raise ValueError('학습데이터 화면에서 선택 방식의 전처리 저장을 먼저 실행하세요. 원본·프로시저 변경 후에는 다시 저장해야 합니다.')
    before=fingerprint(conn,mode);saved=read_state(conn)
    saved.setdefault('models',{}).pop(mode,None);saved['confirmed']=None;write_state(conn,saved)
    result=run_model(conn,action,mode)
    after=fingerprint(conn,mode)
    if before!=after:raise ValueError('학습 중 데이터나 프로시저가 변경되었습니다. 다시 학습하세요.')
    model=next(r for r in query(conn,'models.sql') if r['model_name']=='OML_BASIC_'+mode+'_MODEL')
    saved['models'][mode]={'fingerprint':after,'created':model['creation_date']};write_state(conn,saved)
    return result

def append_training(conn,values,mode):
    """[APPEND-TRAIN] 새 Y/TRAIN만 INSERT → SQL 조건 검사 → COMMIT → 전체 TRAIN 재학습.
    INSERT/조건 검사 실패는 롤백합니다. 모델 DDL 시작 뒤에는 새 행을 복구하지 않습니다.
    """
    if mode not in ('RAW','CLEAN'):raise ValueError('RAW 또는 CLEAN을 선택하세요.')
    if not any(r['model_name']=='OML_BASIC_'+mode+'_MODEL' for r in query(conn,'models.sql')):raise ValueError('추가 학습 전에 최초 학습을 실행하세요.')
    if not values or any(r['split']!='TRAIN' or r['use_yn']!='Y' for r in values):raise ValueError('추가 CSV는 USE_YN=Y, SPLIT=TRAIN 행만 포함해야 합니다. TEST·제외 행은 추가하지 않습니다.')
    if any(r.get('signal') not in ('BUY','SELL') for r in values):raise ValueError('추가 TRAIN의 정답 SIGNAL은 BUY 또는 SELL이어야 합니다.')
    try:
        execute(conn,'queries/insert_training.sql',many=values)
        run_model(conn,'VALIDATE',mode)
        conn.commit();sql_trace.add('COMMIT',kind='TRANSACTION')
    except Exception:
        conn.rollback();sql_trace.add('ROLLBACK',kind='TRANSACTION');raise
    try:
        saved=read_state(conn);saved['confirmed']=None;write_state(conn,saved)
        prepare_model_data(conn,mode)
        return train_model(conn,mode,'ADD_TRAIN')
    except Exception as error:
        raise ValueError(f'추가 TRAIN {len(values)}행은 적재되었습니다. 모델 재학습은 실패했습니다. 원인을 수정한 뒤 전체 재학습을 실행하세요. CSV를 다시 추가하면 중복됩니다. '+str(error)) from error

def delete_model(conn,mode):
    """[DROP-MODEL] 선택한 모델만 삭제하고 확정 상태를 해제합니다. 테이블은 유지합니다."""
    result=run_model(conn,'DELETE',mode)
    saved=read_state(conn);saved.setdefault('models',{}).pop(mode,None)
    if saved.get('confirmed')==mode:saved['confirmed']=None
    write_state(conn,saved);return result

def confirm_model(conn,mode):
    """[CONFIRM-MODEL] 최신 모델을 검증한 뒤 웹에서 사용할 RAW/CLEAN 선택을 저장합니다.
    입력: 로그인 계정의 conn, mode(RAW 또는 CLEAN). 출력: 없음.
    model_rows의 SELECT로 데이터·프로시저 해시·모델 생성 시각을 대조합니다.
    확정 값은 write_state가 같은 계정의 OML_WEB_STATE에 저장합니다.
    Oracle 모델 자체는 변경하지 않고 웹 검증 메타데이터만 갱신합니다.
    """
    if not any(r['variant']==mode and r['is_current'] for r in model_rows(conn)):raise ValueError('현재 데이터·프로시저로 모델을 먼저 생성하세요.')
    saved=read_state(conn);saved['confirmed']=mode;write_state(conn,saved)

def predictions(conn,mode=None):
    if mode is not None and mode not in ('RAW','CLEAN'):raise ValueError('RAW 또는 CLEAN 모델을 선택하세요.')
    selected=next((r for r in model_rows(conn) if r['is_current'] and (r['variant']==mode if mode else r['is_confirmed'])),None)
    if not selected:raise ValueError('현재 데이터로 학습한 RAW 또는 CLEAN 모델을 선택하세요.')
    from . import practice_evidence
    practice_evidence.begin(conn,'basic','predict')
    inputs=query(conn,'prediction_rows.sql');values={r['case_id']:r for r in inputs}
    result=run_model(conn,'PREDICT',selected['variant'])
    rows=[{**r,'prediction':r['predicted'],'probability':r['buy_probability'] if r['predicted']=='BUY' else r['sell_probability'],
             'stock':values[r['case_id']]['stock'],'week_ending':values[r['case_id']]['week_ending'],
             'actual':values[r['case_id']]['signal']} for r in result]
    verified=practice_evidence.record(conn,'basic','predict',selected['variant'],rows,inputs=inputs)
    if verified and mode is not None:
        saved=read_state(conn);saved['confirmed']=selected['variant'];write_state(conn,saved)
    return rows

def model_results(conn):
    from . import practice_evidence
    practice_evidence.begin(conn,'basic','evaluate')
    models=model_rows(conn);metrics=[];details={}
    for item in models:
        mode=item['variant']
        if item['is_current']:metrics.extend(run_model(conn,'EVALUATE',mode))
        details[mode]=query(conn,'model_details.sql',model_name=item['model_name'])
    for model in models:
        if model['is_current']:practice_evidence.record(conn,'basic','evaluate',model['variant'],[r for r in metrics if r['variant']==model['variant']])
    return {'models':models,'metrics':metrics,'details':details}

def status(conn):
    objects=query(conn,'objects.sql',**BASIC)
    def storage(name):
        found=next((r for r in objects if r['object_name']==name and r['object_type']=='TABLE'),{})
        return {'name':name,'qualified_name':conn.username.upper()+'.'+name,'exists':bool(found),'object_id':found.get('object_id'),'created_at':found.get('created')}
    training=storage(BASIC['training_table']);prediction=storage(BASIC['prediction_table']);prepared=storage(BASIC['prepared_table'])
    if prediction['exists']:
        p=query(conn,'prediction_storage.sql')[0];prediction.update(rows=p['row_count'],loaded_at=p['loaded_at'])
    ready=all(any(r['object_name']==name and r['status']=='VALID' for r in objects) for name in BASIC.values())
    counts=query(conn,'training_count.sql')[0] if training['exists'] else {}
    state=dict(counts);models=model_rows(conn,verify=ready)
    if ready:
        stamp=fingerprint(conn);state['data_rev']=stamp[:10]
        state['confirmed_variant']=next((m['variant'] for m in models if m['is_confirmed']),None)
        state['confirmed_current']=int(bool(state['confirmed_variant']))
    return {'connected':True,'initialized':ready,'user':conn.username,'version':conn.version,
            'state':state,'models':models,'storage':training,'prediction_storage':prediction,'prepared_storage':prepared,
            'preparation':preparation_status(conn) if ready else {},'objects':objects,
            'counts':{'total':counts.get('total_rows',0),'used':counts.get('used_rows',0),'disabled':counts.get('disabled_rows',0)}}


def prediction_context(conn,mode=None):
    """결과 비교용 해시입니다. 같은 입력의 이전 실행만 비교하도록 합니다."""
    values=query(conn,'prediction_rows.sql')
    digest=hashlib.sha256(json.dumps(values,sort_keys=True,default=str).encode()).hexdigest()
    selected=next((m for m in model_rows(conn) if m['is_current'] and (m['variant']==mode if mode else m['is_confirmed'])),{})
    return {'input_fingerprint':digest,'model_name':selected.get('model_name')}
