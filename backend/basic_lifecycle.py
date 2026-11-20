"""기본과제의 명시적 준비·등록·초기화. 호출 계정의 고정 OML_BASIC 객체만 변경합니다."""
from . import service, sql_trace
from .sql_files import execute, execute_file, query


ACTIONS = {'create-tables', 'register-procedure', 'reregister-procedure', 'clear-training', 'clear-prediction',
           'clear-prepared', 'drop-objects', 'unconfirm'}


def apply(conn, action, owner, mode='RAW'):
    if action not in ACTIONS or mode not in ('RAW', 'CLEAN'):
        raise ValueError('지원하는 준비·초기화 작업과 RAW/CLEAN을 선택하세요.')
    if conn.username.upper() != owner:
        raise ValueError('로그인한 발급 DB 계정과 실제 접속 계정이 다릅니다.')
    execute(conn, 'queries/csv_owner.sql', {'owner':owner})
    if action == 'create-tables':
        for path in ('schema.sql','prepared_table.sql','prediction_table.sql'):
            execute_file(conn,path,existing_tables=True)
        execute_file(conn,'table_comments.sql')
        return '실습 테이블 3개를 준비했습니다. 프로시저 등록을 진행하세요.'
    if action in ('register-procedure','reregister-procedure'):
        objects=query(conn,'objects.sql',**service.BASIC)
        if not all(any(row['object_name']==name and row['object_type']=='TABLE' for row in objects)
                   for name in ('OML_BASIC_DATA','OML_BASIC_PREPARED','OML_BASIC_PREDICT')):
            raise ValueError('테이블 3개를 먼저 생성하세요.')
        exists=any(row['object_name']=='OML_BASIC_RUN' and row['object_type']=='PROCEDURE' for row in objects)
        if action=='register-procedure' and exists:raise ValueError('프로시저가 있습니다. 프로시저 다시 등록을 사용하세요.')
        if action=='reregister-procedure' and not exists:raise ValueError('프로시저가 없습니다. 프로시저 최초 등록을 사용하세요.')
        execute_file(conn,'classifier.sql')
        errors=query(conn,'procedure_errors.sql',procedure_name='OML_BASIC_RUN')
        if errors:
            raise ValueError('프로시저 컴파일 오류: '+'\n'.join(f"{r['line']}행: {r['text']}" for r in errors))
        service.invalidate_training_state(conn)
        return '프로시저를 등록했습니다. 수정 후에도 같은 버튼으로 다시 등록합니다.'
    if action == 'drop-objects':
        # DDL 일부만 성공해도 이전 웹 최신/확정 기록을 재사용하지 않습니다.
        try:
            execute(conn,'reset_basic_objects.sql',{'owner':owner})
        finally:
            state=service.read_state(conn)
            for field in ('models','confirmed','preparations'):
                state.pop(field,None)
            state['models']={}
            state.get('practice_evidence',{}).pop('basic',None)
            service.write_state(conn,state)
        return '기본과제 모델 2개·테이블 3개·프로시저를 삭제했습니다.'
    if action == 'unconfirm':
        state=service.read_state(conn);state['confirmed']=None;service.write_state(conn,state)
        return '모델 확정을 해제했습니다. 생성된 모델은 유지됩니다.'
    objects=query(conn,'objects.sql',**service.BASIC)
    tables={r['object_name'] for r in objects if r['object_type']=='TABLE'}
    target={'clear-training':'OML_BASIC_DATA','clear-prediction':'OML_BASIC_PREDICT',
            'clear-prepared':'OML_BASIC_PREPARED'}[action]
    if target not in tables:
        raise ValueError('초기화할 테이블이 없습니다.')
    try:
        if action == 'clear-training':
            execute(conn,'queries/delete_training.sql')
            if 'OML_BASIC_PREPARED' in tables:
                execute(conn,'queries/clear_prepared.sql',{'variant':'ALL','source_kind':'ALL'})
        elif action == 'clear-prediction':
            execute(conn,'queries/delete_prediction.sql')
            if 'OML_BASIC_PREPARED' in tables:
                execute(conn,'queries/clear_prepared.sql',{'variant':'ALL','source_kind':'PREDICT'})
        else:
            execute(conn,'queries/clear_prepared.sql',{'variant':mode,'source_kind':'ALL'})
        conn.commit();sql_trace.add('COMMIT',kind='TRANSACTION')
    except Exception:
        conn.rollback();sql_trace.add('ROLLBACK',kind='TRANSACTION');raise
    if action == 'clear-training':
        service.invalidate_training_state(conn)
    elif action == 'clear-prepared':
        state=service.read_state(conn)
        state.setdefault('preparations',{}).pop(mode,None)
        state.setdefault('models',{}).pop(mode,None)
        if state.get('confirmed')==mode:state['confirmed']=None
        service.write_state(conn,state)
    return {'clear-training':'학습 원본과 전처리 저장값을 비웠습니다.',
            'clear-prediction':'예측 입력과 예측 전처리값을 비웠습니다.',
            'clear-prepared':mode+' 전처리 저장값을 비웠습니다.'}[action]


LABELS = {'create-tables':'테이블 생성','register-procedure':'프로시저 최초 등록','reregister-procedure':'프로시저 다시 등록',
          'clear-training':'학습 데이터 비우기','clear-prediction':'예측 입력 비우기',
          'clear-prepared':'선택 전처리값 비우기','drop-objects':'실습 오브젝트 삭제','unconfirm':'모델 확정 해제'}


def sql_paths(action):
    return {'create-tables':['sql/schema.sql','sql/prepared_table.sql','sql/prediction_table.sql','sql/table_comments.sql'],
            'register-procedure':['sql/classifier.sql','sql/queries/procedure_errors.sql'],
            'reregister-procedure':['sql/classifier.sql','sql/queries/procedure_errors.sql'],
            'clear-training':['sql/queries/delete_training.sql','sql/queries/clear_prepared.sql'],
            'clear-prediction':['sql/queries/delete_prediction.sql','sql/queries/clear_prepared.sql'],
            'clear-prepared':['sql/queries/clear_prepared.sql'],
            'drop-objects':['sql/reset_basic_objects.sql'],'unconfirm':[]}[action]


def describe(action, owner, mode='RAW', trigger_id='', trigger_label='', page=''):
    from .coding_flow import lifecycle_flow
    if action not in ACTIONS or mode not in ('RAW','CLEAN'):
        raise ValueError('지원하는 준비·초기화 작업을 선택하세요.')
    title=LABELS[action]
    caution={'drop-objects':'기본과제 객체와 모든 실습 데이터를 삭제합니다. 되돌릴 수 없습니다.',
             'clear-training':'원본·전처리 저장값을 삭제합니다. 모델을 사용하려면 다시 적재·전처리·학습하세요.',
             'clear-prediction':'예측 원본·예측 전처리값을 삭제합니다.',
             'clear-prepared':mode+' 전처리 저장값과 해당 모델의 최신·확정 기록을 해제합니다.'}.get(action,'')
    result={'title':title,'operation':action,'assignment':'basic','variant':mode,'schema':owner,
            'application':{'title':title+' · 적용 범위','owner':owner,
                'summary':'화면의 고정 버튼에서 확인 후 실행합니다.',
                'step_titles':['대상 확인','실행 확인','상태 확인'],
                'steps':[owner+' · '+(mode+' · ' if action=='clear-prepared' else '')+title,'확인 레이어에서 적용 범위 확인','현황·행 수·모델 상태 새로고침'],
                'caution':caution,'details':[],'command':'','verification':''},
            'notice':caution,'find':''}
    result['flow']=lifecycle_flow(result,trigger_id=trigger_id,trigger_label=trigger_label,page=page)
    return result
