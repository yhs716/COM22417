"""[CODING-HELP] 버튼의 실제 SQL·Python·수정 위치를 공개 허용 목록에서 연결합니다."""
import ast
import re
from . import sql_trace
from .sql_files import read_sql

OPERATIONS={
 'prepare':('전처리 저장','queries/call_classifier.sql','prepare_model_data'),
 'prepared-data':('저장된 모델 입력 조회','queries/prepared_rows.sql','get_prepared_data'),
 'status':('현황 조회','queries/objects.sql','status'),
 'data':('저장 데이터 조회','queries/training_rows.sql','get_data'),
 'preview':('CSV 미리보기',None,'parse_csv'),
 'prediction-preview':('예측 CSV 미리보기',None,'parse_csv'),
 'import':('학습 CSV 적재','queries/insert_training.sql','load_csv'),
 'initialize':('테이블·프로시저 준비','schema.sql','initialize'),
 'recreate':('원본 테이블 재생성·CSV 적재','recreate_training.sql','import_data'),
 'train':('모델 생성','queries/call_classifier.sql','run_model'),
 'evaluate':('TEST 성능 조회','queries/call_classifier.sql','run_model'),
 'confirm':('기본 예측 모델 지정','queries/models.sql','confirm_model'),
 'prediction-import':('예측 CSV 적재','queries/insert_prediction.sql','load_csv'),
 'prediction-data':('예측 저장 데이터 조회','queries/prediction_rows.sql','query'),
 'predict':('예측 실행','queries/call_classifier.sql','run_model'),
 'columns':('컬럼 조회','queries/columns.sql','query'),
 'connection':('테이블·프로시저 연결 확인','queries/objects.sql','readiness'),
 'initial-train':('최초 학습','queries/call_classifier.sql','train_model'),
 'retrain':('전체 재학습','queries/call_classifier.sql','train_model'),
 'delete-model':('선택 모델 삭제','queries/call_classifier.sql','delete_model'),
 'model-dictionary':('Oracle 모델 딕셔너리 조회','queries/dictionary_model.sql','read'),
}
MODEL_ACTIONS={'prepare':'PREPARE','train':'TRAIN','initial-train':'INIT','retrain':'RETRAIN','delete-model':'DELETE','evaluate':'EVALUATE','predict':'PREDICT'}

def function_code(names,path='backend/service.py'):
    source=sql_trace.source(path)['content'];lines=source.splitlines()
    functions={n.name:n for n in ast.walk(ast.parse(source)) if isinstance(n,ast.FunctionDef)}
    return '\n\n'.join(f'# {path}:{functions[name].lineno}\n'+'\n'.join(lines[functions[name].lineno-1:functions[name].end_lineno]) for name in names)

def confirmation_code(mode):
    """함수를 실행하지 않고 허용된 service.py의 실제 정의를 발췌합니다."""
    source=sql_trace.source('backend/service.py')['content']
    lines=source.splitlines()
    functions={node.name:node for node in ast.parse(source).body if isinstance(node,ast.FunctionDef)}
    parts=[f"# 현재 선택값: {mode} · 웹 API가 로그인 계정의 conn으로 호출하는 한 줄\nservice.confirm_model(conn, {mode!r})\n\n# 아래는 backend/service.py의 실제 함수 원문 발췌입니다.\n# 기존 모듈의 import·전역값·DB 연결을 사용하는 코드이므로 모듈 안에서 수정합니다."]
    for name in ('confirm_model','model_rows','fingerprint','prepared_values','read_state','write_state','state_path'):
        node=functions[name]
        parts.append(f'# backend/service.py:{node.lineno}\n'+'\n'.join(lines[node.lineno-1:node.end_lineno]))
    return '\n\n'.join(parts)

def application_help(operation,assignment,config):
    """현재 작업의 핵심 3단계와 필요한 경우에만 펼치는 보충 설명."""
    definition = f'sql/custom/{assignment}/02_procedure.sql' if assignment != 'basic' else 'sql/classifier.sql'
    result = {'title':'수정 후 적용 방법', 'summary':'', 'steps':[], 'step_titles':[],
              'details':[], 'caution':'', 'command':'', 'verification':'', 'definition_path':definition}

    def steps(summary, *cards):
        result.update(summary=summary, step_titles=[card[0] for card in cards], steps=[card[1] for card in cards])

    if operation == 'recreate':
        steps('CSV를 검사한 뒤 원본 테이블을 다시 만들고 적재합니다.',
              ('CSV 검사','파일 선택 → 헤더·값 검사'),
              ('원본 재생성','DATA만 다시 생성 → 500행씩 묶음 적재'),
              ('다시 학습','행 수 확인 → 전처리 → 재학습'))
        result['caution'] = '기존 원본 행은 삭제됩니다. DROP 이후에는 되돌릴 수 없습니다.'
        result['details'] = [
            {'title':'적재 도중 실패했다면','text':'현황에서 테이블·행 수를 확인하세요. 테이블이 있으면 같은 CSV를 교체 적재하고, 없으면 먼저 테이블을 준비하세요.'},
            {'title':'적재 SQL을 직접 실행하려면','text':'CSV는 메모리에서 검사한 뒤 바인드로 전달합니다. INSERT SELECT나 단독 CSV 가져오기 SQL이 아닙니다. 웹의 파일 업로드·적재를 사용하세요.'}]
        result['verification'] = sql_trace.rendered(read_sql('queries/objects.sql'),config)
    elif operation in MODEL_ACTIONS or operation == 'initialize':
        after = ('현황에서 VALID 확인 → 필요한 작업 실행' if operation in ('initialize','delete-model') else
                 'VALID 확인 → 전처리 → 재학습 → TEST 평가')
        steps('DB에 저장된 프로시저를 사용합니다. 파일 수정 후 다시 등록하세요.',
              ('파일 수정', definition + ' 편집·저장'),
              ('DB 반영','현황의 프로시저 다시 등록 또는 파일 전체 F5 실행'),
              ('결과 확인',after))
        result['command'] = '.\\scripts\\db-init.ps1' if assignment == 'basic' else ''
        result['command_title'] = '터미널로 DB 정의 적용하기'
        result['command_note'] = '프로젝트 PowerShell에서 실행합니다. 저장된 로그인 계정에 적용하며 기존 행은 보존합니다.'
        result['details'] = [
            {'title':'수정이 반영되지 않았다면','text':'파일을 저장해도 로컬만 바뀝니다. 전체 파일을 F5로 적용한 뒤 USER_ERRORS 0행·USER_SOURCE 원문을 확인하세요. ALTER PROCEDURE COMPILE은 저장된 DB 원문만 재컴파일합니다.'},
            {'title':'테이블 구조를 바꾸려면','text':'CREATE는 신규 생성용입니다. 기존 컬럼은 ALTER TABLE로 수정하세요. DDL은 자동 커밋됩니다.'}]
        if operation == 'prepare':
            result['caution'] = '전처리 저장은 선택 방식의 저장값·FIT_YN을 교체합니다. 수동 조정은 전처리 후 하세요.'
        result['verification'] = '\n\n'.join(sql_trace.rendered(read_sql('queries/'+name),config)
                                               for name in ('objects.sql','procedure_errors.sql','procedure_source.sql'))
    elif operation in ('preview','prediction-preview'):
        steps('CSV 검사 로직을 수정하고 같은 파일로 다시 확인합니다.',
              ('검사 로직 수정','backend/validation.py 편집·저장'),
              ('서버 반영','서버 재시작 → 다시 로그인'),
              ('미리보기 확인','CSV 선택 → 미리보기'))
    elif operation in ('import','prediction-import'):
        path = 'sql/' + OPERATIONS[operation][1]
        steps('CSV 파일을 한 번 업로드하고 500행씩 묶음 적재합니다.',
              ('SQL 확인',path + '의 컬럼·바인드 확인'),
              ('CSV 적재','첫 줄 헤더·쉼표 구분 CSV 업로드'),
              ('결과 확인','저장 데이터에서 행 수·값 확인'))
        result['caution'] = 'CSV 교체 적재는 대상 테이블의 기존 행을 교체합니다.'
        result['details'] = [{'title':'Python 처리도 수정했다면','text':'backend/service.py 등을 수정한 뒤에는 서버를 재시작하고 다시 로그인하세요. SQL 파일만 수정하면 다음 적재부터 읽습니다.'}]
    elif operation == 'confirm':
        steps('기본 예측 모델을 저장합니다. 4단계에서 다른 모델도 직접 선택할 수 있습니다.',
              ('코드 수정','backend/service.py의 confirm_model 확인'),
              ('서버 반영','Python 수정 시 재시작 → 다시 로그인'),
              ('선택 확인','기본 모델 지정 → 4단계에서 선택·실행'))
        result['details'] = [{'title':'선택은 어디에 저장되나요?','text':'검증 후 발급 계정의 Oracle OML_WEB_STATE에 저장됩니다. 같은 DB의 로컬·Render에서 공유하며 모델 자체의 상태는 바뀌지 않습니다.'}]
    else:
        path = 'sql/' + OPERATIONS[operation][1] if OPERATIONS[operation][1] else '실행 SQL 단계의 파일'
        steps('조회 SQL은 저장 후 다음 조회부터 반영됩니다.',
              ('쿼리 수정',path),
              ('다시 조회','원래 화면의 조회·새로고침 버튼 클릭'),
              ('결과 확인','컬럼·행 수·조건 확인'))
        if operation == 'model-dictionary':
            result['details'] = [{'title':'조회 범위가 다르다면','text':'USER_: 본인 소유 · ALL_: 접근 가능한 객체 · DBA_: 별도 권한 필요. DM$ 객체 설명은 모델 정보 조회 결과에서 확인하세요.'}]
        else:
            result['details'] = [{'title':'Python 처리도 수정했다면','text':'서비스 코드는 서버 재시작 후 다시 로그인하세요. HTML·JS·CSS는 새로고침으로 확인합니다.'}]
    result['verification_title'] = 'DB 반영 확인 SQL'
    return result


def runtime_python(operation,assignment,function,py,variant):
    if operation=='recreate':
        return function_code(('import_data',),'app.py')+'\n\n'+function_code(('initialize','execute_file'),'backend/sql_files.py')+'\n\n'+function_code(('load_csv','invalidate_training_state'))
    if operation=='confirm':return '' # 현재 코드에 저장·검증 함수 전체를 표시합니다.
    if operation in MODEL_ACTIONS:
        if assignment!='basic':return function_code(('run','load_custom'),'backend/assignment_templates.py')+'\n\n'+function_code(('run_model',))
        names={'prepare':('prepare_model_data','run_model'),'initial-train':('train_model','run_model'),'retrain':('train_model','run_model'),
               'train':('train_model','run_model'),
               'delete-model':('delete_model','run_model'),'evaluate':('model_results','run_model'),
               'predict':('predictions','run_model')}[operation]
        return function_code(names)
    return function_code((function,),py)

def source_groups(operation,assignment,filename,py,function,api_function,page,variant):
    """현재 코드의 원본 → 관련 SQL → 웹 연결 순서. 파일은 여기서 지정한 목록만 읽습니다."""
    custom=assignment!='basic'
    procedure=f'sql/custom/{assignment}/02_procedure.sql' if custom else 'sql/classifier.sql'
    tables=f'sql/custom/{assignment}/01_tables.sql' if custom else 'sql/schema.sql'
    primary=[('sql/'+filename,'','선택 작업의 SQL 파일 원문')] if filename else [(py,'def '+function+'(','CSV를 검사하는 Python 원본 · DB 쿼리는 실행하지 않음')]
    related=[]
    if operation=='model-dictionary':
        from .model_dictionary import CATALOG
        primary=[('sql/queries/dictionary_'+key+'.sql','',view+' · '+title) for key,view,title,description,empty,columns in CATALOG]
        related=[('sql/queries/dictionary_detail_rows.sql','','검증된 실제 객체·일반 컬럼 최대 20행 조회')]
    if operation in MODEL_ACTIONS:
        section={'evaluate':'SQL-EVALUATE','predict':'SQL-PREDICT','delete-model':'DELETE-MODEL'}.get(operation,'SQL-TRAIN')
        if operation not in ('evaluate','predict','prepare'):
            section=('OML-DROP-' if operation in ('train','retrain','delete-model') else 'OML-CREATE-')+('RAW' if variant=='BOTH' else variant)
        if operation=='prepare':section='OML-PREPARE-'+('RAW' if variant=='BOTH' else variant)
        primary=[(procedure,'['+section+']','선택한 Oracle OML 명령·SELECT의 실제 프로시저 원문')]
        related=[('sql/examples/run.sql','[DIRECT-CALL]','SQL Developer에서 저장된 프로시저를 호출하는 실행 예제'),
                 ('sql/queries/call_classifier.sql','[PYTHON-CALL]','웹은 같은 프로시저를 바인드로 호출')]
    elif operation=='recreate':
        primary=[('sql/recreate_training.sql','','원본 DATA만 DROP · DDL 자동 커밋'),('sql/schema.sql','CREATE TABLE','빈 원본 DATA를 새로 생성'),
                 ('sql/queries/delete_training.sql','','CSV 적재 트랜잭션 시작 · 새 테이블에서는 0행'),('sql/queries/insert_training.sql','','메모리에 읽어 둔 CSV 각 행을 INSERT VALUES 바인드로 적재')]
        related=[('sql/prediction_table.sql','CREATE TABLE','공통 준비: 기존 예측 테이블 보존·없을 때만 생성'),('sql/prepared_table.sql','CREATE TABLE','공통 준비: 기존 준비 테이블 보존·없을 때만 생성'),
                 ('sql/classifier.sql','CREATE OR REPLACE PROCEDURE','공통 준비: 실행 프로시저 정의 재적용'),('sql/table_comments.sql','COMMENT ON','테이블·컬럼 설명 재적용')]
    elif operation=='initialize':
        primary=[
            ('sql/schema.sql','CREATE TABLE','학습·TEST 테이블 생성'),('sql/prediction_table.sql','CREATE TABLE','예측 테이블 생성'),
            ('sql/prepared_table.sql','CREATE TABLE','모델 입력을 저장하는 테이블 생성'),('sql/classifier.sql','CREATE OR REPLACE PROCEDURE','실행 프로시저 생성'),('sql/table_comments.sql','COMMENT ON','테이블·컬럼 설명 적용')]
    elif operation in ('import','prediction-import'):
        before='custom_delete.sql' if custom else 'delete_prediction.sql' if operation=='prediction-import' else 'delete_training.sql'
        primary=[('sql/queries/'+before,'','기존 행 삭제 · INSERT와 같은 트랜잭션'),('sql/'+filename,'','검증한 CSV 행 INSERT · 실패 시 전체 롤백')]
    elif operation=='confirm':
        primary=[('backend/service.py','def confirm_model(','선택 모델을 검증하고 확정값을 저장하는 Python')]
        related=[('sql/queries/training_rows.sql','[DATA-SELECT]','현재 데이터의 해시 검증'),('sql/queries/prepared_fingerprint_rows.sql','','선택 방식의 저장된 학습·TEST 값 검증'),('sql/queries/procedure_source.sql','','현재 DB 프로시저 원문 검증'),('sql/queries/models.sql','','모델 생성 시각·상태 검증')]
    if operation not in ('preview','prediction-preview','confirm','model-dictionary'):
        related += [(tables,'CREATE TABLE','학습·TEST 컬럼 정의')]
        if not custom:related += [('sql/prediction_table.sql','CREATE TABLE','예측 컬럼 정의'),('sql/prepared_table.sql','CREATE TABLE','저장된 모델 입력·학습제공여부 정의')]
    if operation in ('status','connection'):
        related += [('sql/queries/procedure_arguments.sql','','프로시저 인자 확인'),('sql/queries/procedure_errors.sql','','컴파일 오류 확인')]
        if operation=='status' and not custom:related += [('sql/queries/training_count.sql','','학습·TEST 실제 행 수'),('sql/queries/prediction_storage.sql','','예측 테이블 저장 정보')]
    elif operation in ('data','save','delete','import','prediction-import','prediction-data','columns'):
        related.append((procedure,'[SQL-TRAIN]','학습·전처리·예측을 수정하는 DB 프로시저'))
        if operation=='save':related.append(('sql/queries/insert_training.sql','','없는 사례번호는 새 행 INSERT'))
    support=[(py,'def '+function+'(','SQL 실행을 연결하는 Python 함수'),('app.py','def '+api_function+'(','이 버튼의 API'),
             ('static/js/assignment-template.js' if custom else 'static/js/main.js','async function assignmentTask(' if custom else 'async function api(','브라우저 요청 연결'),
             ('templates/pages/assignment-template.html' if custom else 'templates/pages/'+page+'.html','','화면 버튼·폼')]
    if custom and operation in MODEL_ACTIONS:support.insert(0,('backend/assignment_templates.py','def run(','이 과제의 CSV 적재·프로시저 호출 연결'))
    seen=set()
    def collect(items):
        result=[]
        for path,keyword,role in items:
            identity=(path,keyword)
            # 전체 파일이 이미 주요 코드로 표시되면 같은 파일을 다시 나열하지 않습니다.
            if identity in seen or any(p==path for p,k in primary_ids):continue
            seen.add(identity);result.append({**sql_trace.source(path,keyword),'role':role})
        return result
    primary_ids=[]
    origin=collect(primary);primary_ids=[(s['path'],s['keyword']) for s in origin]
    return {'primary':origin,'related_sql':collect(related),'support':collect(support)}

def oracle_sections(operation,variant,assignment,*,source=None):
    """원문 구간을 파일·줄과 함께 반환합니다. 서로 떨어진 구간을 한 PL/SQL로 조립하지 않습니다."""
    path='sql/classifier.sql' if assignment=='basic' else f'sql/custom/{assignment}/02_procedure.sql'
    if source is None:source=sql_trace.source(path)['content']
    def position(text):
        if source.count(text)!=1:raise ValueError('구분 위치를 확정할 수 없습니다.')
        return source.index(text)
    def excerpt(title,start,end,role,opened=False):
        return {'title':title,'path':path,'line':source.count('\n',0,start)+1,
                'end_line':source.count('\n',0,max(start,end-1))+1,
                'content':source[start:end],'role':role,'open':opened}
    def marked(marker,title,role,opened=False):
        start=position('  -- ['+marker+']')
        close=position('  -- [/'+marker+']')
        end=source.find('\n',close)
        return excerpt(title,start,len(source) if end<0 else end+1,role,opened)
    modes=('RAW','CLEAN') if variant=='BOTH' else (variant,)
    definitions=[];queries=[]
    try:
        for mode in modes:
            if operation=='prepare':
                definitions.append(marked('OML-PREPARE-'+mode,mode+' 전처리 내부 프로시저 정의','선언부입니다. 아래 PREPARE 실행부에서 호출될 때 INSERT SELECT를 수행합니다.'))
            elif operation=='predict':
                definitions.append(marked('OML-PREPARE-PREDICT-'+mode,mode+' 예측 입력 준비 프로시저 정의','선언부입니다. PREDICT 실행부에서 선택 방식의 예측 입력만 준비합니다.'))
            elif operation=='delete-model':
                definitions.append(marked('OML-DROP-'+mode,mode+' 모델 삭제 내부 프로시저 정의','선언부입니다. DELETE 실행부에서 호출될 때 모델을 삭제합니다.'))
            elif operation not in ('evaluate',):
                if operation in ('retrain','train'):
                    definitions.append(marked('OML-DROP-'+mode,mode+' 모델 삭제 내부 프로시저 정의','선언부입니다. 실제 DROP → CREATE 호출 순서는 아래 실행 4에서 확인합니다.'))
                definitions.append(marked('OML-CREATE-'+mode,mode+' 모델 생성 내부 프로시저 정의','선언부입니다. 여기서 즉시 실행하지 않으며, 실행 3에서 p_sql을 지정하고 실행 4에서 호출합니다.'))
            if operation not in ('prepare','delete-model'):
                marker='SQL-EVALUATE' if operation=='evaluate' else 'SQL-PREDICT' if operation=='predict' else 'SQL-TRAIN'
                start=position('    -- ['+marker+']')
                end=position("  ELSIF p_action = 'EVALUATE' THEN") if marker=='SQL-TRAIN' else position("  ELSIF p_action = 'PREDICT' THEN\n    -- [SQL-PREDICT]") if marker=='SQL-EVALUATE' else position("  ELSE\n    RAISE_APPLICATION_ERROR(-20001, 'p_action:")
                choices=list(re.finditer(r"^      p_sql := q'~\n.*?^~';",source[start:end],re.M|re.S))
                if len(choices)!=2:raise ValueError('방식별 SELECT 위치를 확정할 수 없습니다.')
                selected=choices[0 if mode=='RAW' else 1]
                queries.append(excerpt('실행 3 · '+mode+' 분기의 p_sql 지정',start+selected.start(),start+selected.end(),
                                       '선택한 방식의 원문입니다. p_sql을 먼저 지정한 뒤 아래 실행부에서 모델 생성·평가·예측에 사용합니다.',True))
        mode_check=excerpt('실행 1 · 모드 확인과 모델 이름 결정',position('\nBEGIN\n')+len('\nBEGIN\n'),position('  -- [PREPARE-ACTION]'),
                           '프로시저 본문에서 먼저 실행하는 공통 검사입니다.')
        if operation=='prepare':
            return [*definitions,mode_check,marked('PREPARE-ACTION','실행 2 · PREPARE 호출·롤백·저장·결과 반환','선택 방식의 준비 프로시저를 호출하는 실제 실행부 원문입니다.',True)]
        lifecycle=excerpt('실행 2 · 모델 존재 여부와 작업 조건 검사',position('  -- [MODEL-LIFECYCLE]'),position("  IF p_action = 'DELETE' THEN"),
                          'INIT의 기존 모델 덮어쓰기 금지와 다른 작업의 모델 존재 검사를 생략하지 않습니다.')
        if operation=='delete-model':
            execution=excerpt('실행 3 · 선택 모델 삭제와 결과 반환',position("  IF p_action = 'DELETE' THEN"),position("  IF p_action IN ('TRAIN', 'INIT', 'RETRAIN', 'ADD_TRAIN') THEN\n    -- [SQL-TRAIN]"),
                              '전체 DELETE 분기 원문입니다. 원본·준비·다른 모델을 삭제하지 않습니다.',True)
        else:
            action_start=source.rindex("  IF p_action IN ('TRAIN', 'INIT', 'RETRAIN', 'ADD_TRAIN') THEN")
            if action_start<position('    -- [SQL-PREDICT]'):raise ValueError('실행 분기 위치를 확정할 수 없습니다.')
            role='공통 실행부의 IF부터 END IF까지 그대로입니다. 현재 p_action/p_mode에 해당하는 분기 하나만 실행합니다. '
            role+=('PREDICT는 예측 준비 → 커서 OPEN → COMMIT 경로입니다. 학습 분기를 실행하지 않습니다.' if operation=='predict' else
                   'EVALUATE는 마지막 ELSE의 OPEN p_result FOR p_sql 경로입니다. 모델 DDL을 실행하지 않습니다.' if operation=='evaluate' else
                   '학습은 validate_source·validate_prepared 후에 선택 모델 DDL을 호출하고 결과 커서를 반환합니다.')
            execution=excerpt('실행 4 · 검증 → 선택 작업 → 결과 반환',action_start,source.rindex('\nEND;'),role,True)
        # 첫 블록은 Oracle 명령 참고, 이후는 번호가 있는 실행부입니다. 선언과 호출을 섞지 않습니다.
        if definitions:return [*definitions,mode_check,lifecycle,*queries,execution]
        queries[0]['title']='명령 참고 · '+modes[0]+' 평가 SELECT 원문'
        return [queries[0],mode_check,lifecycle,*queries[1:],execution]
    except (ValueError,IndexError):
        return [excerpt('전체 정의 원문 · 구분 구조가 변경되어 부분 발췌하지 않음',0,len(source),
                        '학생이 구조·구분 주석을 수정했으므로 위치를 추측하지 않고 전체 로컬 파일을 표시합니다. 실행은 아래 SQL Developer 호출 예제를 사용하세요.',True)]



def _basic_owner(value):
    owner=str(value).strip().upper()
    if not re.fullmatch(r'[A-Z][A-Z0-9_$#]{0,127}',owner):
        raise ValueError('발급받은 DB 오브젝트 생성 계정을 확인하세요.')
    return owner


def _qualify_basic_sql(sql,owner,object_prefix='OML_BASIC_'):
    """실행 식별자만 한정합니다. USER_* 메타데이터의 이름 값과 원문 소스는 바꾸지 않습니다."""
    pieces=[];position=0
    embedded=re.compile(r'^\s*(?:SELECT|WITH|INSERT|UPDATE|DELETE|MERGE|CREATE|DROP|ALTER|BEGIN|DECLARE|COMMENT)\b',re.I)
    object_name=re.compile(re.escape(object_prefix)+r'[A-Z0-9_]+\Z',re.I)
    while position<len(sql):
        if sql.startswith('--',position):
            end=sql.find('\n',position)
            if end<0:end=len(sql)
            pieces.append(sql[position:end]);position=end;continue
        if sql.startswith('/*',position):
            end=sql.find('*/',position+2)
            end=len(sql) if end<0 else end+2
            pieces.append(sql[position:end]);position=end;continue
        if sql[position:position+2].lower()=="q'" and position+2<len(sql):
            opening=sql[position+2];closing={'[':']','{':'}','(':')','<':'>'}.get(opening,opening)
            end=sql.find(closing+"'",position+3)
            if end>=0:
                value=sql[position+3:end]
                if embedded.match(value):value=_qualify_basic_sql(value,owner,object_prefix)
                pieces.append(sql[position:position+3]+value+closing+"'")
                position=end+2;continue
        if sql[position]=="'":
            start=position;position+=1;value=[]
            while position<len(sql):
                if sql[position]=="'":
                    if sql[position:position+2]=="''":value.append("'");position+=2;continue
                    position+=1;break
                value.append(sql[position]);position+=1
            literal=''.join(value)
            prefix=re.sub(r'--[^\n]*|/\*.*?\*/','',sql[max(0,start-200):start],flags=re.S)
            model_parameter=re.search(r'\bMODEL_NAME\s*=>\s*$|\bDROP_MODEL\s*\(\s*$',prefix,re.I)
            if model_parameter and object_name.fullmatch(literal):
                literal=owner+'.'+literal
            elif embedded.match(literal):
                literal=_qualify_basic_sql(literal,owner,object_prefix)
            pieces.append("'"+literal.replace("'","''")+"'");continue
        token=re.match(r'[A-Za-z][A-Za-z0-9_$#]*',sql[position:])
        if token:
            value=token.group(0)
            before=sql[:position].rstrip()
            if object_name.fullmatch(value) and (not before or before[-1] not in '.:'):
                value=owner+'.'+value
            pieces.append(value);position+=len(token.group(0));continue
        pieces.append(sql[position]);position+=1
    return ''.join(pieces)


def _guard_basic_sql(sql,owner,object_prefix='OML_BASIC_'):
    """F5 스크립트는 잘못된 접속 계정/현재 스키마에서 첫 작업 전에 중단합니다."""
    guard=("WHENEVER SQLERROR EXIT SQL.SQLCODE ROLLBACK\n"
           "-- 발급받은 DB 계정: "+owner+" · 다른 접속 계정/현재 스키마에서는 중단합니다.\n"
           "BEGIN\n"
           "  IF SYS_CONTEXT('USERENV', 'SESSION_USER') <> '"+owner+"'\n"
           "     OR SYS_CONTEXT('USERENV', 'CURRENT_SCHEMA') <> '"+owner+"' THEN\n"
           "    RAISE_APPLICATION_ERROR(-20030, '발급받은 DB 계정 "+owner+"으로 접속하고 현재 스키마를 확인하세요.');\n"
           "  END IF;\nEND;\n/\n")
    return guard+_qualify_basic_sql(sql,owner,object_prefix)

def describe(operation,*,variant='RAW',use_yn='ALL',split='ALL',assignment='basic',user='',source_kind='ALL',trigger_id='',trigger_label='',page=''):
    from .basic_lifecycle import ACTIONS as lifecycle_actions, describe as lifecycle_help
    if operation in lifecycle_actions:
        return lifecycle_help(operation,_basic_owner(user),variant,trigger_id,trigger_label,page)
    if assignment!='basic':raise ValueError('미션은 선택 미션 SQL 가이드를 사용하며 창의는 안내 쿼리를 제공하지 않습니다.')
    if operation not in OPERATIONS or variant not in ('RAW','CLEAN','BOTH'):raise ValueError('등록된 버튼·모델 구분을 선택하세요.')
    if use_yn not in ('ALL','Y','N') or split not in ('ALL','TRAIN','TEST'):raise ValueError('조회 필터를 확인하세요.')
    if source_kind not in ('ALL','TRAIN','TEST','PREDICT'):raise ValueError('준비 데이터 용도를 확인하세요.')
    if operation=='confirm' and variant=='BOTH':raise ValueError('확정할 모델은 RAW 또는 CLEAN 하나를 선택하세요.')
    if operation=='model-dictionary' and (assignment!='basic' or variant=='BOTH'):raise ValueError('기본과제의 RAW 또는 CLEAN 모델 하나를 선택하세요.')
    label,filename,function=OPERATIONS[operation]
    binds={};procedure='OML_BASIC_RUN'
    config={'training_table':'OML_BASIC_DATA','prediction_table':'OML_BASIC_PREDICT','prepared_table':'OML_BASIC_PREPARED','procedure_name':procedure}
    if operation=='model-dictionary':config['model_name']='OML_BASIC_'+variant+'_MODEL';binds={'model_name':config['model_name']}
    if operation=='prepared-data':binds={'variant':variant,'source_kind':source_kind}
    if operation=='data':binds={'use_yn':use_yn,'split':split}
    if operation in MODEL_ACTIONS:binds={'p_action':MODEL_ACTIONS[operation],'p_mode':variant}
    if assignment!='basic':
        from .assignment_templates import configuration
        config=configuration(user,assignment);procedure=config['procedure_name']
        if operation in ('data','prediction-data'):filename='queries/custom_rows.sql';binds={}
        if operation in ('import','prediction-import'):filename='queries/custom_insert.sql'
    if operation in ('status','connection'):binds={k:config[k] for k in ('training_table','prediction_table','prepared_table','procedure_name')}
    if operation=='columns':binds={'table_name':config['prediction_table']}
    py='app.py' if operation=='recreate' else 'backend/sql_files.py' if operation in ('initialize','columns','prediction-data') else 'backend/validation.py' if operation in ('preview','prediction-preview') else 'backend/service.py'
    if operation=='connection':py='backend/assignment_templates.py'
    if operation=='delete':function='delete_row'
    api_function={'prepare':'prepare_data','prepared-data':'prepared_data','model-dictionary':'models_dictionary','initial-train':'train','retrain':'train','delete-model':'delete_model','status':'status','data':'data','preview':'preview','prediction-preview':'preview_predictions','import':'import_data','save':'save_row','delete':'delete_row','initialize':'initialize_basic','recreate':'import_data','train':'train','evaluate':'models','confirm':'confirm_model','prediction-import':'import_predictions','prediction-data':'prediction_data','predict':'predict','columns':'columns','connection':'assignment_status'}[operation]
    if operation=='model-dictionary':py='backend/model_dictionary.py'
    if assignment!='basic':
        api_function='assignment_status' if operation=='connection' else 'assignment_csv' if operation in ('import','predict','prediction-import') else 'assignment_action'
        if operation in ('prepare','prepared-data','initial-train','retrain','delete-model'):py='backend/assignment_templates.py';function='run'
        if operation in ('connection','data','prediction-data','import','prediction-import'):
            py='backend/assignment_templates.py';function={'connection':'readiness','data':'run','prediction-data':'run','import':'load_custom','prediction-import':'load_custom'}[operation]
    source_page='home' if operation in ('status','initialize','connection') else 'models' if operation in ('train','evaluate','initial-train','retrain','delete-model','model-dictionary') else 'predictions' if operation.startswith('prediction') or operation in ('confirm','predict','columns') else 'data'
    sql=read_sql(filename) if filename else '-- CSV 미리보기는 Python의 parse_csv로 검사합니다. DB SQL은 실행하지 않습니다.\n-- 실제 선택한 CSV의 내용은 화면 미리보기에서 확인하세요.'
    sql=sql.replace('OML_BASIC_RUN',procedure)
    if operation=='model-dictionary':
        from .model_dictionary import CATALOG
        sql='\n\n'.join('-- '+view+' · '+title+'\n'+read_sql('queries/dictionary_'+key+'.sql') for key,view,title,description,empty,columns in CATALOG)
    if operation=='prepared-data':sql=sql.replace('{{table}}',config['prepared_table'])
    if assignment!='basic' and '{{table}}' in sql:
        sql=sql.replace('{{table}}',config['prediction_table'] if operation in ('prediction-import','prediction-data') else config['training_table'])
    if operation in ('import','prediction-import'):
        before='queries/custom_delete.sql' if assignment!='basic' else 'queries/delete_prediction.sql' if operation=='prediction-import' else 'queries/delete_training.sql'
        table=config['prediction_table'] if operation in ('prediction-import','prediction-data') else config['training_table']
        sql=read_sql(before).replace('{{table}}',table)+'\n\n'+sql+'\n\n-- CSV 값은 executemany 바인드로 전달합니다. CSV 적재는 검증한 각 행을 같은 INSERT에 바인드합니다.\n-- 모두 성공하면 COMMIT, 실패하면 ROLLBACK합니다.'
    if operation=='confirm':
        sql=confirmation_code(variant)
        binds={'mode':variant}
    if operation=='initialize':
        sql='\n\n'.join(read_sql(name) for name in ('schema.sql','prediction_table.sql','prepared_table.sql','classifier.sql','table_comments.sql'))
    if operation=='recreate':
        sql='-- 0. 업로드된 CSV 전체를 Python 메모리에 읽어 검사합니다. 검사 실패 시 아래 DROP은 실행하지 않습니다.\n-- 아래는 웹 실행 순서 확인용입니다. :바인드 값은 웹이 전달하며 단독 F5로 CSV가 적재되지는 않습니다.\n\n-- 1. 기존 원본 테이블 삭제 (자동 커밋 · ROLLBACK으로 복원 불가)\n'+read_sql('recreate_training.sql')+'\n\n-- 2. 빈 원본 테이블 새로 생성\n'+read_sql('schema.sql')+'\n\n-- 3. 공통 준비: 기존 PREPARED/PREDICT 보존 · 없는 테이블 추가 · RUN 정의와 코멘트 적용\n-- 해당 전체 정의는 호출 흐름의 관련 SQL에 제공합니다.\n\n-- 4. 메모리에 읽어 둔 CSV로 적재합니다. 새 테이블의 DELETE는 0행입니다.\n'+read_sql('queries/delete_training.sql')+'\n\n'+read_sql('queries/insert_training.sql')+'\n\n-- 위 INSERT 한 문장에 CSV 값을 500행씩 묶어 executemany로 전달합니다.\nCOMMIT;\n-- INSERT 실패 시 CSV 행 변경은 ROLLBACK. 앞서 완료한 DROP/CREATE는 롤백되지 않습니다.\n-- 5. 웹 전처리 저장은 별도 작업: DATA → INSERT SELECT → PREPARED. 그 뒤 모델을 재학습합니다.'
    sections=oracle_sections(operation,variant,assignment) if operation in MODEL_ACTIONS else []
    if sections:sql=sections[0]['content']
    groups=source_groups(operation,assignment,filename,py,function,api_function,source_page,variant)
    sources=[*groups['primary'],*groups['related_sql'],*groups['support']]
    direct='\n\n'.join(read_sql('examples/run.sql').replace('{{procedure}}',procedure).replace('{{action}}',MODEL_ACTIONS[operation]).replace('{{mode}}',mode) for mode in (('RAW','CLEAN') if variant=='BOTH' else (variant,))) if operation in MODEL_ACTIONS else ''
    result={'title':label,'operation':operation,'assignment':assignment,'variant':variant,'source_kind':source_kind,'binds':binds,
            'script':sql if operation=='confirm' or sections else sql_trace.rendered(sql,binds),'sources':sources,'source_groups':groups,
            'oracle_sections':sections,
            'script_path':sections[0]['path'] if sections else ('backend/assignment_templates.py' if assignment!='basic' else 'backend/service.py') if operation=='confirm' else 'example.sql',
            'code_title':sections[0]['title'] if sections else '원본 DROP → CREATE → CSV INSERT VALUES → COMMIT' if operation=='recreate' else '선택 모델 · Oracle 딕셔너리 메타데이터 조회 SQL과 객체별 일반 컬럼 20행 조회' if operation=='model-dictionary' else '선택 모델 · 실제 Python 확정 코드' if operation=='confirm' else '현재 선택값 · 실행 예정',
            'application':application_help(operation,assignment,config),
            'python_script':runtime_python(operation,assignment,function,py,variant),
            'direct_script':direct,
            'find':''}
    if user:
        owner=_basic_owner(user)
        # 파일/줄로 안내한 소스 발췌와 Python 원문은 그대로 둡니다.
        # SQL Developer에서 직접 실행하는 코드에만 소유자와 접속 검사를 넣습니다.
        if operation not in ('confirm','preview','prediction-preview') and not sections:
            result['script']=_guard_basic_sql(result['script'],owner)
        if result['direct_script']:
            result['direct_script']=_guard_basic_sql(result['direct_script'],owner)
        application=result['application']
        if application.get('verification'):
            application['verification']=_guard_basic_sql(application['verification'],owner)
        result['owner']=owner
        application['owner'] = owner
    result['notice'] = result['application'].get('caution', '')
    from .coding_flow import basic_flow
    result['flow']=basic_flow(result,trigger_id=trigger_id,trigger_label=trigger_label,page=page or source_page)
    return result
