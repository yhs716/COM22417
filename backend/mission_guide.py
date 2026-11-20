"""선택한 배포 미션의 실행 가능한 SQL 가이드. 조회만으로 파일·DB를 변경하지 않습니다."""
import re
from pathlib import Path

from .db import ROOT

TEMPLATE_PATH = 'sql/custom/mission/guide_procedure.sql'
TABLES_PATH = 'sql/custom/mission/01_tables.sql'
PROCEDURE_PATH = 'sql/custom/mission/02_procedure.sql'
KINDS = ('training', 'prepared', 'prediction')
ACTIONS = {'prepare': 'PREPARE', 'initial-train': 'INIT', 'train': 'TRAIN',
           'retrain': 'RETRAIN', 'delete-model': 'DELETE',
           'validate': 'VALIDATE', 'evaluate': 'EVALUATE', 'predict': 'PREDICT'}


def _literal(value):
    return 'NULL' if value is None or value == '' else "'" + str(value).replace("'", "''") + "'"


def _schema(schema):
    """발급된 계정명은 따옴표 없는 안전한 Oracle 대문자 식별자만 허용합니다."""
    if not isinstance(schema, str) or (schema and not re.fullmatch(r'[A-Z][A-Z0-9_$#]{0,29}', schema)):
        raise ValueError('발급된 DB 계정의 영문 대문자 스키마명을 확인하세요.')
    return schema


def _object(name, schema):
    return schema + '.' + name if schema else name


def _guard(schema, indent='  '):
    if not schema:
        return ''
    return (indent + "IF USER <> '" + schema + "' OR SYS_CONTEXT('USERENV', 'CURRENT_SCHEMA') <> '" + schema + "' THEN\n"
            + indent + "  RAISE_APPLICATION_ERROR(-20030, '발급 계정 " + schema + "으로 접속하고 CURRENT_SCHEMA도 동일하게 사용하세요.');\n"
            + indent + "END IF;\n")


def _script_guard(schema, *, check=True):
    if not schema:
        return ''
    return ("-- 발급 계정: " + schema + ". 다른 계정에서는 실행을 중단합니다.\n"
            "WHENEVER SQLERROR EXIT SQL.SQLCODE ROLLBACK\n"
            + ("BEGIN\n" + _guard(schema) + "END;\n/\n" if check else ''))


def _status_sql(schema, *, compact=False):
    owner = "OWNER = '" + schema + "' AND " if schema else ''
    objects = 'ALL_OBJECTS' if schema else 'USER_OBJECTS'
    errors = 'ALL_ERRORS' if schema else 'USER_ERRORS'
    displayed = "OWNER || '.' || OBJECT_NAME OBJECT_NAME" if schema else 'OBJECT_NAME'
    names = "OBJECT_NAME = 'OML_MISSION_RUN'" if compact else (
        "OBJECT_NAME IN ('OML_MISSION_DATA', 'OML_MISSION_PREPARED', 'OML_MISSION_PREDICT', 'OML_MISSION_RUN')")
    return ('SELECT ' + displayed + (', STATUS' if compact else '\n     , OBJECT_TYPE\n     , STATUS')
            + '\n  FROM ' + objects + '\n WHERE ' + owner + names
            + ('\n' if compact else '\n ORDER BY OBJECT_TYPE\n     , OBJECT_NAME\n') + ';\n\n'
            'SELECT LINE\n     , POSITION\n     , TEXT\n  FROM ' + errors
            + '\n WHERE ' + owner + "NAME = 'OML_MISSION_RUN'\n ORDER BY SEQUENCE\n;\n")


def _metadata(item):
    layout = item['layout']
    fields = {field['name']: field for field in layout}
    names = [field['name'] for field in layout]
    features = [field['name'].upper() for field in layout if '설명변수' in field['role']]
    if len(features) != 3 or set(names) != {'case_id', 'label', 'split', 'use_yn', *[name.lower() for name in features]}:
        raise ValueError('배포 미션의 식별키·설명변수 3개·타깃·운영 컬럼을 확인하세요.')
    if len(names) != len(set(names)) or any(not re.fullmatch(r'[A-Z][A-Z0-9_]{0,29}', name.upper()) for name in names):
        raise ValueError('허용된 미션 컬럼명을 확인하세요.')
    labels = fields['label']['valid'].split(' / ')
    if len(labels) != 5 or len(set(labels)) != 5 or any(not re.fullmatch(r'[A-Z0-9_]{1,100}', label) for label in labels):
        raise ValueError('배포 미션의 5개 분류값을 확인하세요.')
    return layout, fields, features, labels


def table_sql(item, kind='training', *, schema=''):
    """DATA → PREPARED → PREDICT 순서의 각 생성 SQL과 표시 메타데이터."""
    schema = _schema(schema)
    if kind not in KINDS:
        raise ValueError('원본·전처리·예측 테이블을 선택하세요.')
    layout, fields, features, labels = _metadata(item)

    def field(name, datatype, rules, description):
        role = 'identifier' if name == 'CASE_ID' else 'feature' if name in features else 'target' if name == 'LABEL' else 'metadata'
        return {'name': name, 'role': role, 'type': datatype, 'rules': rules, 'description': description,
                'nullable': '필수' if 'NOT NULL' in rules or 'PRIMARY KEY' in rules else 'NULL 허용'}

    def raw(source):
        name = source['name']
        datatype = 'NUMBER' if name == 'case_id' else 'VARCHAR2(5)' if name == 'split' else 'CHAR(1)' if name == 'use_yn' else 'VARCHAR2(100)'
        rules = 'PRIMARY KEY' if name == 'case_id' else "NOT NULL CHECK (SPLIT IN ('TRAIN', 'TEST'))" if name == 'split' else "DEFAULT 'Y' NOT NULL CHECK (USE_YN IN ('Y', 'N'))" if name == 'use_yn' else ''
        return field(name.upper(), datatype, rules, source['korean_name'] + ' · ' + source['role'])

    constraints = []
    if kind == 'prepared':
        name = 'OML_MISSION_PREPARED'
        description = 'PREPARE가 저장하는 숫자 설명변수·정답·학습 제공 여부입니다. 원본 CSV를 직접 적재하지 않습니다.'
        columns = [
            field('PREP_MODE', 'VARCHAR2(5)', "NOT NULL CHECK (PREP_MODE IN ('RAW', 'CLEAN'))", '전처리 방식'),
            field('SOURCE_KIND', 'VARCHAR2(7)', "NOT NULL CHECK (SOURCE_KIND IN ('TRAIN', 'TEST', 'PREDICT'))", '원본 용도'),
            field('CASE_ID', 'NUMBER', 'NOT NULL', '사례 식별자'),
            *[field(feature, 'NUMBER', '', fields[feature.lower()]['korean_name'] + ' · 설명변수') for feature in features],
            raw(fields['label']), raw(fields['use_yn']),
            field('FIT_YN', 'CHAR(1)', "DEFAULT 'N' NOT NULL CHECK (FIT_YN IN ('Y', 'N'))", '학습 제공 여부'),
            field('EXCLUDE_REASON', 'VARCHAR2(200)', '', '학습 제외 사유'),
            field('PREPARED_AT', 'TIMESTAMP', 'DEFAULT SYSTIMESTAMP NOT NULL', '전처리 저장 시각'),
        ]
        constraints = ['PRIMARY KEY (PREP_MODE, SOURCE_KIND, CASE_ID)',
                       "CHECK (FIT_YN = 'N' OR (SOURCE_KIND = 'TRAIN' AND USE_YN = 'Y' AND LABEL IS NOT NULL AND LABEL IN (" + ', '.join(map(_literal, labels)) + ')))']
    else:
        name = 'OML_MISSION_PREDICT' if kind == 'prediction' else 'OML_MISSION_DATA'
        description = '예측 CSV의 CASE_ID와 설명변수 3개를 저장합니다. LABEL·SPLIT·USE_YN은 없습니다.' if kind == 'prediction' else '빈칸·unknown·범위 밖 숫자 등 CSV 원문을 보존하도록 설명변수를 VARCHAR2(100)으로 저장합니다.'
        selected = [source for source in layout if source['name'] == 'case_id' or source['name'].upper() in features] if kind == 'prediction' else layout
        columns = [raw(source) for source in selected]
        columns.append(field('UPDATED_AT', 'TIMESTAMP', 'DEFAULT SYSTIMESTAMP', '등록 시각 기본값 · CSV에 없는 운영 컬럼'))
    lines = [column['name'] + ' ' + column['type'] + (' ' + column['rules'] if column['rules'] else '') for column in columns] + constraints
    bare_name = name
    name = _object(name, schema)
    sql = (_script_guard(schema, check=False) + '-- ' + item['title'] + ' · 생성 SQL\n'
           '-- 기존 ' + name + '만 확인·삭제 후 재생성합니다. 기존 행은 삭제되며 ROLLBACK할 수 없습니다.\n'
           '-- 같은 계정의 SQL Developer에서 전체를 선택 해제 후 F5 실행하세요.\n'
           "DECLARE\n  v_exists PLS_INTEGER;\nBEGIN\n" + _guard(schema) + "  SELECT COUNT(*) INTO v_exists FROM USER_TABLES WHERE TABLE_NAME = '" + bare_name + "';\n"
           "  IF v_exists > 0 THEN\n    EXECUTE IMMEDIATE 'DROP TABLE " + name + "';\n  END IF;\nEND;\n/\n"
           'CREATE TABLE ' + name + '\n(\n' + '\n'.join((' , ' if index else '  ') + line for index, line in enumerate(lines)) + '\n)\n;\n'
           'COMMENT ON TABLE ' + name + ' IS ' + _literal(item['title']) + '\n;\n'
           + '\n'.join('COMMENT ON COLUMN ' + name + '.' + column['name'] + ' IS ' + _literal(column['description']) + '\n;' for column in columns) + '\n')
    return {'name': name, 'description': description, 'columns': columns, 'constraints': constraints, 'sql': sql}


def procedure_sql(item, *, schema=''):
    """템플릿의 연속된 전체 정의에 catalog 컬럼·분류값만 치환합니다."""
    schema = _schema(schema)
    _, _, features, labels = _metadata(item)
    source = (ROOT / TEMPLATE_PATH).read_text(encoding='utf-8-sig')
    replacements = {'TITLE': item['title'].replace('\n', ' ').replace('\r', ' '),
                    'CLASSES': ', '.join(map(_literal, labels)), 'OWNER_GUARD': _guard(schema)}
    replacements.update({'FEATURE_' + str(index): name for index, name in enumerate(features, 1)})
    for key, value in replacements.items():
        source = source.replace('{{' + key + '}}', value)
    if '{{' in source or '}}' in source:
        raise ValueError('미션 SQL 템플릿의 치환값을 확인하세요.')
    if schema:
        source = re.sub(r'\bOML_MISSION_(?:DATA|PREPARED|PREDICT|RUN|RAW_MODEL|CLEAN_MODEL)\b',
                        lambda match: _object(match.group(0), schema), source)
    return _script_guard(schema) + source


def schema_guide(item, kind='training', *, schema=''):
    """미션 스키마 팝업은 기존 테이블·프로시저 생성기를 함께 사용합니다."""
    if kind != 'procedure':
        return table_sql(item, kind, schema=schema)
    schema = _schema(schema)
    return {'kind':'procedure','object_type':'PROCEDURE','name':_object('OML_MISSION_RUN',schema),
            'description':'선택 미션의 전처리·학습·TEST 평가·예측을 처리하는 RUN 전체 정의입니다.',
            'columns':[],'constraints':[],'sql':procedure_sql(item,schema=schema)}


def csv_load_command(item, prediction=False, *, schema=''):
    """배포 파일 경로는 예시입니다. --file을 본인이 선택한 로컬 CSV 경로로 바꿀 수 있습니다."""
    _metadata(item)
    filename = item['prediction_filename' if prediction else 'filename']
    if not re.fullmatch(r'[a-z0-9_]+\.csv', filename) or not re.fullmatch(r'[a-z0-9_]+', item['key']):
        raise ValueError('배포 CSV 파일명·미션 키를 확인하세요.')
    owner = _schema(schema) or 'STUDENT00'
    return ('& .\\.venv\\Scripts\\python.exe .\\scripts\\load_mission_csv.py --mission ' + item['key']
            + ' --kind ' + ('prediction' if prediction else 'training')
            + ' --file "data/examples/' + filename + '" --owner ' + owner)


def csv_load_sql(item, prediction=False, *, schema=''):
    """파일 전체를 읽거나 행별 INSERT를 생성하지 않고 실제 바인드 SQL 하나를 표시합니다."""
    from .csv_import import csv_layout
    from .sql_files import read_sql
    schema = _schema(schema)
    _metadata(item)
    columns = csv_layout(item, prediction)
    table = _object('OML_MISSION_PREDICT' if prediction else 'OML_MISSION_DATA', schema)
    sql = read_sql('queries/custom_insert.sql')
    for key, value in {'table':table, 'columns':', '.join(name.upper() for name in columns),
                       'values':', '.join(':' + name for name in columns)}.items():
        sql = sql.replace('{{' + key + '}}', value)
    return ('-- 로컬 CSV 파일 → 첫 줄 헤더 / 쉼표 구분 → 검사 → 500행씩 executemany\n'
            '-- 아래는 적재기가 사용하는 바인드 SQL 한 문장입니다. 단독 F5 파일 적재용이 아닙니다.\n'
            '-- CSV 파일 선택·실행은 왼쪽의 로컬 파일 적재 명령을 사용하세요.\n'
            '-- 빈 셀은 NULL, unknown·범위 밖 숫자·공백은 보존합니다.\n'
            '-- 기존 행 교체와 모든 묶음이 성공한 뒤 한 번 COMMIT, 실패 시 전체 ROLLBACK.\n' + sql + '\n')


def _direct(action, variant, schema, assignment='mission'):
    return (_script_guard(schema, check=False) + "ALTER SESSION SET NLS_NUMERIC_CHARACTERS = '.,'\n;\n"
            '-- 같은 계정의 SQL Developer에서 전체 F5 실행합니다.\n'
            '-- PREPARE/PREDICT는 준비행을 저장하고, 모델 생성·삭제는 DDL 자동 커밋을 포함합니다.\n'
            'VARIABLE result REFCURSOR\nVARIABLE executed_sql CLOB\nBEGIN\n'
            + _guard(schema) + "  " + _object('OML_'+assignment.upper()+'_RUN', schema) + "('" + action + "', '" + variant + "', :result, :executed_sql);\n"
            'END;\n/\nPRINT result\nPRINT executed_sql\n')



RESET_ACTIONS = {'clear-training','clear-prediction','clear-prepared','drop-objects'}


def reset_sql(operation, variant, schema, assignment='mission'):
    """미션 전용 고정 객체만 정리하는 직접 실행 SQL. 조회 과정에서는 실행하지 않습니다."""
    from .sql_files import read_sql
    if operation not in RESET_ACTIONS or variant not in ('RAW','CLEAN'):
        raise ValueError('지원하는 초기화 종류를 선택하세요.')
    if assignment not in ('mission','creative'):raise ValueError('과제를 확인하세요.')
    prefix='OML_'+assignment.upper()
    if operation=='drop-objects':
        body=read_sql('reset_basic_objects.sql').replace('OML_BASIC',prefix).replace('기본과제', '미션과제' if assignment=='mission' else '창의과제')
        body=body.replace(':owner',_literal(schema))
        body=re.sub(r'(?<=DROP TABLE )'+prefix+r'_[A-Z]+|(?<=DROP PROCEDURE )'+prefix+'_RUN',
                    lambda match:_object(match.group(0),schema),body)
        return _script_guard(schema)+body+'\n'
    data=_object(prefix+'_DATA',schema);predict=_object(prefix+'_PREDICT',schema);prepared=_object(prefix+'_PREPARED',schema)
    if operation=='clear-training':body='DELETE FROM '+data+';\nDELETE FROM '+prepared+';\n'
    elif operation=='clear-prediction':body='DELETE FROM '+predict+";\nDELETE FROM "+prepared+" WHERE SOURCE_KIND = 'PREDICT';\n"
    else:body='DELETE FROM '+prepared+" WHERE PREP_MODE = '"+variant+"';\n"
    return _script_guard(schema)+body+'COMMIT;\n'


def generate(item, operation='prepare', variant='RAW', source_kind='ALL', *, schema='', trigger_id='', trigger_label='', page=''):
    """선택 미션을 유지한 채 코딩 도움말에 표시할 실제 실행 SQL을 만듭니다."""
    schema = _schema(schema)
    if variant not in ('RAW', 'CLEAN') or source_kind not in ('ALL', 'TRAIN', 'TEST', 'PREDICT'):
        raise ValueError('미션 전처리 방식·원본 용도를 확인하세요.')
    _, _, features, _ = _metadata(item)
    importing = operation in ('import', 'prediction-import')
    full_procedure = '' if importing or operation in RESET_ACTIONS else procedure_sql(item, schema=schema)
    data = _object('OML_MISSION_DATA', schema)
    prediction = _object('OML_MISSION_PREDICT', schema)
    prepared_table = _object('OML_MISSION_PREPARED', schema)
    direct = ''
    prepared = ['PREP_MODE', 'SOURCE_KIND', 'CASE_ID', *features, 'LABEL', 'USE_YN', 'FIT_YN', 'EXCLUDE_REASON', 'PREPARED_AT']
    if operation in RESET_ACTIONS:
        script=reset_sql(operation,variant,schema)
        code_title={'clear-training':'학습 데이터 비우기','clear-prediction':'예측 입력 비우기',
                    'clear-prepared':variant+' 전처리값 비우기','drop-objects':'실습 오브젝트 삭제'}[operation]
    elif operation in ACTIONS:
        direct = _direct(ACTIONS[operation], variant, schema)
        script = direct
        code_title = variant + ' · ' + ACTIONS[operation] + ' 직접 실행'
    elif operation in ('setup', 'initialize'):
        script = full_procedure
        code_title = '선택 미션 전체 프로시저 정의'
    elif operation in ('import', 'prediction-import'):
        script = csv_load_sql(item, prediction=operation == 'prediction-import', schema=schema)
        code_title = 'CSV 묶음 적재 · 바인드 SQL 한 문장'
    elif operation == 'data':
        script = 'SELECT ' + '\n     , '.join(name.upper() for name in item['columns']) + '\n  FROM ' + data + '\n ORDER BY CASE_ID\n;\n'
        code_title = '선택 미션 원본 조회'
    elif operation in ('prediction-data', 'columns'):
        script = 'SELECT CASE_ID\n     , ' + '\n     , '.join(features) + '\n  FROM ' + prediction + '\n ORDER BY CASE_ID\n;\n'
        code_title = '선택 미션 예측 원본 조회'
    elif operation == 'prepared-data':
        script = 'SELECT ' + '\n     , '.join(prepared) + "\n  FROM " + prepared_table + "\n WHERE PREP_MODE = '" + variant + "'\n"
        if source_kind != 'ALL':
            script += "   AND SOURCE_KIND = '" + source_kind + "'\n"
        script += ' ORDER BY SOURCE_KIND\n     , CASE_ID\n;\n'
        code_title = variant + ' · 저장된 전처리값 조회'
    elif operation in ('connection', 'status'):
        script = _status_sql(schema)
        code_title = '미션 객체 연결·컴파일 확인'
    elif operation in ('preview', 'prediction-preview'):
        script = '-- CSV 데이터 조회는 배포 원문을 읽으며 DB SQL을 실행하지 않습니다.\n'
        code_title = 'CSV 원문 조회'
    else:
        raise ValueError('이 미션 가이드에서 제공하는 작업을 선택하세요.')
    if operation in ('data', 'prediction-data', 'columns', 'prepared-data', 'connection', 'status'):
        script = _script_guard(schema) + script
    verification = _script_guard(schema) + _status_sql(schema, compact=True)
    application = {
        'title':'수정 후 적용 방법', 'summary':'선택 미션 SQL을 직접 실행하고 웹에서 결과를 확인합니다.',
        'owner':schema, 'step_titles':['파일 수정','DB 반영','연결 확인'],
        'steps':[PROCEDURE_PATH + ' 편집·저장', '발급 계정에서 파일 전체 F5 실행', '전처리·모델 단계에서 SQL 실행 결과 연계'],
        'details':[{'title':'수정이 반영되지 않았다면','text':'파일 저장만으로 DB 정의는 바뀌지 않습니다. 전체 프로시저를 F5로 적용하고 오류 0건·VALID를 확인하세요. 학습 로직 변경 후에는 PREPARE·RETRAIN·EVALUATE를 직접 실행하세요.'}],
        'caution':'', 'command':'', 'verification':verification,
        'verification_title':'DB 연결·컴파일 확인 SQL', 'definition_path':PROCEDURE_PATH,
    }
    if operation in RESET_ACTIONS:
        application.update(summary=code_title+' SQL을 직접 실행하고 웹에서 상태를 확인합니다.',
            step_titles=['대상 확인','직접 실행','상태 확인'],
            steps=[schema+' · '+code_title,'발급 계정의 SQL Developer에서 전체 F5 실행','웹 새로고침으로 현재 상태 확인'],
            caution='대상 데이터·객체가 삭제됩니다. 실행 전 SQL의 대상 이름을 확인하세요.',details=[])
    elif operation == 'setup':
        application.update(summary='테이블 → 프로시저 → CSV 순서로 준비합니다.',
            step_titles=['테이블 생성','프로시저 등록','CSV 적재·연결'],
            steps=['스키마 조회의 DATA → PREPARED → PREDICT', '선택 미션 RUN 전체 SQL을 F5 실행', '웹 새로고침으로 객체 준비 확인 → CSV 적재'],
            caution='생성 SQL은 해당 기존 테이블을 삭제·재생성합니다. 기존 행은 되돌릴 수 없습니다.')
    elif operation in ('data','prediction-data','columns','prepared-data','connection','status'):
        application.update(summary='직접 만든 객체와 조회 결과를 확인합니다.',
            step_titles=['SQL 확인','직접 조회','화면 확인'],
            steps=['실행 SQL 단계에서 해당 조회문 선택','발급 계정의 SQL Developer에서 실행','웹에서 조회 결과 확인'],
            details=[])
    elif operation in ('preview','prediction-preview'):
        application.update(summary='선택 미션의 CSV 원문을 확인합니다.',
            step_titles=['파일 확인','데이터 조회','값 확인'],
            steps=[item['filename'],'선택 미션의 데이터 조회 열기','헤더·값·행 수 확인'],details=[],verification='')
    elif operation in ('prepare','initial-train','retrain','delete-model','evaluate','predict'):
        application['steps'][2] = '제공된 호출 SQL 실행 → 웹에서 결과 확인'
        if operation == 'prepare':
            application['caution'] = 'PREPARE는 선택 방식의 저장값·FIT_YN을 교체합니다. 수동 조정은 실행 후 하세요.'
    steps = application['steps']
    source = {'path': TEMPLATE_PATH, 'line': 1, 'keyword': '', 'content': full_procedure,
              'role': '선택 미션의 컬럼·5개 분류값을 반영한 전체 프로시저 · ' + PROCEDURE_PATH + '에 저장 후 F5 적용'}
    groups = {'primary': [], 'related_sql': [source] if full_procedure else [], 'support': []}
    result = {'title': item['title'] + ' · SQL 가이드', 'operation': operation, 'assignment': 'mission',
            'mission_key': item['key'], 'schema': schema, 'variant': variant, 'source_kind':source_kind, 'script': script, 'procedure_sql': full_procedure,
            'script_path': '선택 미션 · SQL Developer 실행 SQL', 'code_title': code_title,
            'direct_script': direct, 'python_script': '', 'oracle_sections': [], 'source_groups': groups,
            'sources': [source] if full_procedure else [], 'application': application, 'steps': steps, 'binds': {},
            'notice': application['caution'], 'find': ''}

    if importing:
        command = csv_load_command(item, prediction=operation == 'prediction-import', schema=schema)
        result['load_command'] = command
        result['script_path'] = '선택 미션 · 적재기 바인드 SQL'
        result['application'].update(
            summary='선택 CSV를 업로드하여 헤더·실제 컬럼 검사 후 500행씩 교체 적재합니다.',
            title='CSV 업로드·교체 적재', command=command,
            step_titles=['파일 선택','교체 확인','묶음 적재'],
            steps=['미션에 맞는 학습 또는 예측 CSV 선택','대상 계정·테이블·파일을 확인하고 교체 동의','500행씩 적재 후 완료 건수 확인'],
            command_title='터미널 직접 적재 · 대안',
            command_note='UTF-8 · 첫 줄 영문 헤더 · 쉼표 구분. 최대 2 MiB / 5,000행입니다.',
            caution='대상 테이블의 기존 행 전체를 교체합니다. 오류가 나면 기존 데이터를 복구합니다.',
            details=[{'title':'적재 후 다음 단계','text':'학습 CSV를 바꾸면 PREPARE·재학습을 직접 실행하세요. 예측 CSV는 준비된 모델로 PREDICT를 실행합니다. 웹에서 결과를 확인할 수 있습니다.'}])
        result['steps'] = result['application']['steps']
        result['notice'] = result['application']['caution']
    from .coding_flow import mission_flow
    result['flow']=mission_flow(result,trigger_id=trigger_id,trigger_label=trigger_label,page=page)
    return result


def creative_manual(operation, variant, *, schema, trigger_id='', trigger_label='', page=''):
    """본인 RUN의 규약 호출·고정 객체 정리만 표시하며 창의 구현 답안은 만들지 않습니다."""
    schema=_schema(schema)
    allowed={'prepare','initial-train','retrain','delete-model',*RESET_ACTIONS}
    if operation not in allowed or variant not in ('RAW','CLEAN'):
        from fastapi import HTTPException
        raise HTTPException(404,'창의과제는 직접 수행 버튼의 호출 SQL만 제공합니다.')
    script=reset_sql(operation,variant,schema,'creative') if operation in RESET_ACTIONS else _direct(ACTIONS[operation],variant,schema,'creative')
    result={'title':'창의과제 · 직접 수행','operation':operation,'assignment':'creative','schema':schema,'variant':variant,
            'script':script,'script_path':'창의과제 · SQL Developer 실행 SQL',
            'application':{'owner':schema,'summary':'본인이 구현한 RUN과 대상 객체를 확인한 뒤 직접 실행하세요.',
                           'step_titles':['대상 확인','직접 실행','웹 연계'],
                           'steps':[schema+' · '+variant,'구문 전체 복사 → SQL Developer F5','SQL 실행 결과 연계'],
                           'caution':'본인 데이터·모델이 변경됩니다. 실행 전 대상과 작업 범위를 확인하세요.'}}
    from .coding_flow import mission_flow
    result['flow']=mission_flow(result,trigger_id=trigger_id,trigger_label=trigger_label,page=page)
    return result
