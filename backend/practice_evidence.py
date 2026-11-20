"""실제 평가·예측의 성공 영수증과 현재 DB 상태를 대조합니다. DB 객체를 변경하지 않습니다."""
from datetime import datetime, timezone
import math
from . import service
from .sql_files import query, execute

MODES = ('RAW', 'CLEAN')


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def model_stamp(saved, key, mode):
    models = saved.get('models', {}) if key == 'basic' else saved.get('assignments', {}).get(key, {})
    entry = models.get(mode, {})
    return ({'fingerprint': entry['fingerprint'], 'created': entry['created']}
            if entry.get('fingerprint') and entry.get('created') else None)


def begin(conn, key, kind, mode=None):
    """새 실행이 실패하면 과거 성공을 현재 실행의 성공으로 표시하지 않습니다."""
    saved = service.read_state(conn)
    proof = saved.setdefault('practice_evidence', {}).setdefault(key, {})
    if kind == 'evaluate':
        if mode: proof.setdefault('evaluate', {}).pop(mode, None)
        else: proof.pop('evaluate', None)
    else: proof.pop('predict', None)
    service.write_state(conn, saved)


def record(conn, key, kind, mode, rows, *, inputs=None, mission_key=''):
    """결과 규약·건수·모델 버전이 유효할 때만 서버에서 성공을 기록합니다."""
    saved = service.read_state(conn)
    stamp = model_stamp(saved, key, mode)
    receipt = {'mode': mode, 'stamp': stamp, 'mission_key': mission_key, 'at': now()}
    valid = bool(stamp and rows and mode in MODES)
    try:
        if kind == 'evaluate':
            counts = [float(row['n']) for row in rows]
            valid = valid and all(math.isfinite(n) and n >= 0 and n.is_integer() for n in counts)
            valid = valid and all(row['variant'] == mode and row['actual'] is not None and row['predicted'] is not None for row in rows)
            total = sum(counts)
            correct = sum(n for row, n in zip(rows, counts) if row['actual'] == row['predicted'])
            receipt.update(total=int(total), correct=int(correct))
            valid = valid and total > 0
        else:
            inputs = inputs or []
            source_ids = [str(row['case_id']) for row in inputs]
            result_ids = [str(row['case_id']) for row in rows]
            valid = valid and bool(inputs) and len(source_ids) == len(set(source_ids))
            valid = valid and len(result_ids) == len(set(result_ids)) and set(source_ids) == set(result_ids)
            valid = valid and all(row['predicted'] is not None and str(row['predicted']).strip()
                                  and math.isfinite(float(row['probability'])) and 0 <= float(row['probability']) <= 1 for row in rows)
            receipt.update(total=len(rows), input_fingerprint=service.json_fingerprint(inputs))
    except (KeyError, TypeError, ValueError, OverflowError):
        valid = False
    proof = saved.setdefault('practice_evidence', {}).setdefault(key, {})
    if kind == 'evaluate':
        target = proof.setdefault('evaluate', {})
        if valid: target[mode] = receipt
        else: target.pop(mode, None)
    elif valid: proof['predict'] = receipt
    else: proof.pop('predict', None)
    service.write_state(conn, saved)
    return bool(valid)


def summarize(key, state, saved, *, inputs=None, mission=None, mission_columns=True, source_count=None, input_count=None):
    """현재 검증 상태와 실제 성공 기록으로만 요약표를 판정합니다."""
    proof = saved.get('practice_evidence', {}).get(key, {})
    models = {m['variant']: m for m in state.get('models', [])}
    preparations = state.get('preparation', {})
    topic = (mission or {}).get('key', '')
    ready = bool(state.get('initialized') if key == 'basic' else state.get('ready'))
    ready = ready and (key != 'mission' or bool(topic and mission_columns))

    def matches(receipt, mode):
        return bool(receipt and models.get(mode, {}).get('is_current') and models.get(mode, {}).get('exists')
                    and receipt.get('stamp') and receipt['stamp'] == model_stamp(saved, key, mode)
                    and receipt.get('mission_key', '') == topic)

    if source_count is None:source_count=state.get('state',{}).get('total_rows',0)
    if input_count is None:input_count=len(inputs) if inputs is not None else state.get('prediction_storage',{}).get('rows',0)
    prepared = ready and source_count > 0 and all(preparations.get(mode, {}).get('ready')
                             and preparations[mode].get('fit_rows', 0) > 0
                             and preparations[mode].get('test_rows', 0) > 0 for mode in MODES)
    evaluations = {}
    for mode in MODES:
        receipt = proof.get('evaluate', {}).get(mode)
        expected = preparations.get(mode, {}).get('test_rows', 0)
        if matches(receipt, mode) and receipt.get('total', 0) == expected and expected > 0:
            evaluations[mode] = receipt
    tests = [preparations.get(mode, {}).get('test_rows', 0) for mode in MODES]
    fixed_test = (mission or {}).get('baseline', {}).get('test_rows')
    compared = prepared and len(evaluations) == 2 and tests[0] == tests[1] and (not fixed_test or tests[0] == fixed_test)
    confirmed = next((mode for mode, m in models.items() if m.get('is_current') and m.get('is_confirmed')), None)
    model_ok = compared and (key != 'basic' or bool(confirmed))
    prediction = proof.get('predict') or {}
    mode = prediction.get('mode')
    prediction_ok = bool(model_ok and matches(prediction, mode) and inputs
                         and prediction.get('input_fingerprint') == service.json_fingerprint(inputs)
                         and prediction.get('total') == len(inputs)
                         and (key != 'basic' or confirmed == mode))
    prep_detail = ' / '.join(mode + ' 학습 ' + str(preparations.get(mode, {}).get('fit_rows', 0))
                             + ' · TEST ' + str(preparations.get(mode, {}).get('test_rows', 0)) + '행' for mode in MODES)
    scores = ' / '.join(mode + ' ' + format(100 * evaluations[mode]['correct'] / evaluations[mode]['total'], '.1f') + '%'
                        for mode in MODES if mode in evaluations)
    stages = [
        ('home', '객체·연결 준비', ready, '준비 적합', '테이블 3개 · 실행 프로시저 VALID' if ready else
         '본인 계정의 테이블·프로시저와 선택 미션을 확인하세요.'),
        ('data', '학습데이터·전처리', prepared, '데이터 준비 성공', prep_detail if prepared else
         'RAW·CLEAN 전처리와 학습·TEST 행을 준비한 뒤 상태를 확인하세요.'),
        ('models', '모델 생성·TEST 평가', model_ok, '평가 성공', scores + (' · ' + confirmed + ' 확정' if key == 'basic' and confirmed else '')
         if model_ok else '현재 모델의 RAW·CLEAN TEST 평가를 완료하세요.' + (' 사용할 모델도 확정하세요.' if key == 'basic' else '')),
        ('predictions', '새 입력 예측 실행', prediction_ok, '예측 성공',
         str(prediction.get('total', 0)) + '행 · ' + str(mode) + ' · 입력·결과 건수 일치' if prediction_ok else
         '현재 모델과 예측 입력으로 예측을 실행하세요.')]
    def check(name, success, detail=''):
        return dict(label=name,success=bool(success),detail=detail)

    prefix='OML_'+key.upper()
    cfg=state.get('config') or {'training_table':prefix+'_DATA','prepared_table':prefix+'_PREPARED','prediction_table':prefix+'_PREDICT','procedure_name':prefix+'_RUN'}
    metadata=state.get('objects')
    objects=[];owner=state.get('user','')
    for field,label in (('training_table','원본 DATA 테이블'),('prepared_table','전처리 PREPARED 테이블'),('prediction_table','예측 PREDICT 테이블'),('procedure_name','실행 RUN 프로시저')):
        name=cfg[field];kind='PROCEDURE' if field=='procedure_name' else 'TABLE'
        found=next((obj for obj in metadata or [] if obj['object_name']==name and obj['object_type']==kind),None)
        issues=[issue['message'] for issue in state.get('issues',[]) if issue.get('object_name')==name]
        ok=(found is not None and found.get('status')=='VALID' and not issues) if metadata is not None else ready
        if field=='training_table' and key=='mission':
            ok=ok and bool(topic and mission_columns)
            if not topic:issues.append('미션을 선택하세요.')
            elif not mission_columns:issues.append('선택 미션과 DATA 컬럼이 다릅니다.')
        qualified=(owner+'.' if owner else '')+name
        objects.append(check(label,ok,qualified+' · '+(' / '.join(issues) if issues else found.get('status','확인 전') if found else '전체 규약 검증 완료' if ready else '오브젝트 없음')))
    if not ready and all(c['success'] for c in objects):
        objects.append(check('객체 규약 최종 확인',False,'현황에서 객체·모델 연계 상태를 다시 확인하세요.'))
    data_checks=[check('학습 CSV 원본 적재',source_count>0,str(source_count)+'행 · DATA'),
                 check('객체·연결 준비',ready,'테이블 3개와 RUN 규약 확인')]
    for variant in MODES:
        prep=preparations.get(variant,{})
        data_checks.append(check(variant+' 전처리·학습/TEST 준비',
                                 prep.get('ready') and prep.get('fit_rows',0)>0 and prep.get('test_rows',0)>0,
                                 '학습 제공 '+str(prep.get('fit_rows',0))+'행 · TEST '+str(prep.get('test_rows',0))+'행'+
                                 ('' if prep.get('ready') else ' · 전처리 저장 또는 변경 후 연계 확인 필요')))
    model_checks=[]
    for variant in MODES:
        current=models.get(variant,{})
        model_checks.append(check(variant+' 최신 모델 생성',current.get('exists') and current.get('is_current'),
                                  '현재 원본·전처리·프로시저와 모델의 일치 여부'))
        model_checks.append(check(variant+' TEST 평가 성공',variant in evaluations,
                                  str(evaluations[variant]['total'])+'행 평가 완료' if variant in evaluations else '현재 모델의 TEST 평가 결과가 필요합니다.'))
    model_checks.append(check('같은 전체 TEST 비교',prepared and tests[0]>0 and tests[0]==tests[1] and (not fixed_test or tests[0]==fixed_test),
                              'RAW '+str(tests[0])+'행 / CLEAN '+str(tests[1])+'행'))
    if key=='basic':model_checks.append(check('기본 예측 모델 지정',bool(confirmed),confirmed or 'RAW/CLEAN 중 사용할 모델을 지정하세요.'))
    prediction_checks=[
        check('모델 생성·평가 완료',model_ok,'모델 단계의 남은 작업을 완료하세요.' if not model_ok else '현재 모델 검증 완료'),
        check('예측 CSV 입력 적재',input_count>0,str(input_count)+'행 · PREDICT'),
        check('현재 모델로 예측 실행',matches(prediction,mode) and (key!='basic' or confirmed==mode),
              str(mode)+' · '+str(prediction.get('at') or '성공 기록 없음')),
        check('현재 예측 입력 일치',bool(inputs and prediction.get('input_fingerprint')==service.json_fingerprint(inputs)),
              'CSV 재적재·입력 수정 후에는 다시 예측하세요.'),
        check('입력·예측 결과 건수 일치',bool(inputs and prediction.get('total')==len(inputs)),
              '입력 '+str(input_count)+'행 / 성공 결과 '+str(prediction.get('total',0))+'행')]
    groups={'home':objects,'data':data_checks,'models':model_checks,'predictions':prediction_checks}
    steps=[]
    for i,label,ok,badge,detail in stages:
        checks=groups[i]
        if key=='mission' and not ready:
            for c in checks:
                c['success']=False
                c['detail']+=' · 선택 미션·DB 적용·연계 확인 필요'
        completed=sum(c['success'] for c in checks);total=len(checks)
        steps.append(dict(id=i,label=label,success=bool(ok),badge=badge if ok else str(completed)+'/'+str(total)+' 완료',
                          detail=detail,checks=checks,completed=completed,total=total,remaining=total-completed))
    return {'assignment': key, 'checked_at': now(), 'complete': all(s['success'] for s in steps),
            'passed': sum(s['success'] for s in steps), 'steps': steps,
            'prediction_at': prediction.get('at') if prediction_ok else None}


def collect(conn, key, mission=None, state=None):
    """명시적 최종 확인 시만 DB 최신 상태를 읽으며 평가·예측을 대신 실행하지 않습니다."""
    if key == 'basic':
        if state is None: state = service.status(conn)
        cfg = service.BASIC
    else:
        from . import assignment_templates as assignments
        if state is None:
            state = assignments.readiness(conn, key,mission=(mission or {}).get('key','') if key=='mission' else None)
            state.update(assignments.verification_state(conn,key,state))
        cfg = state['config']
    saved = service.read_state(conn)
    ready = state.get('initialized') if key == 'basic' else state.get('ready')
    inputs = None
    if ready and saved.get('practice_evidence', {}).get(key, {}).get('predict'):
        inputs = (query(conn, 'prediction_rows.sql') if key == 'basic' else
                  execute(conn, 'queries/custom_fingerprint_rows.sql', replacements={'table': cfg['prediction_table']}, fetch=True))
    def count_input(field,known=None):
        if known is not None:return known
        if not any(obj['object_name']==cfg[field] and obj['object_type']=='TABLE' and obj['status']=='VALID' for obj in state.get('objects',[])):return 0
        return execute(conn,'queries/custom_count.sql',replacements={'table':conn.username.upper()+'.'+cfg[field]},fetch=True)[0]['rows_count']
    source_count=count_input('training_table',state.get('state',{}).get('total_rows'))
    input_count=len(inputs) if inputs is not None else count_input('prediction_table',state.get('prediction_storage',{}).get('rows'))
    columns_match = True
    if key == 'mission' and mission and any(obj['object_name']==cfg['training_table'] and obj['object_type']=='TABLE' for obj in state.get('objects',[])):
        columns = {r['column_name'].lower() for r in query(conn, 'columns.sql', table_name=cfg['training_table'])}
        columns_match = set(mission['columns']).issubset(columns)
    return summarize(key, {**state,'user':conn.username.upper()}, saved, inputs=inputs, mission=mission, mission_columns=columns_match,source_count=source_count,input_count=input_count)
