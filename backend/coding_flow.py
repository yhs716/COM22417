"""버튼 → 이벤트 → API → 서비스 → DB → SQL의 검토 가능한 소스 지도.

등록된 작업별 소스만 읽습니다. 조회는 파일 읽기이며 DB 연결·실행을 하지 않습니다.
source 항목은 정확한 연속 원문이고 generated 항목에는 소스 줄 번호를 부여하지 않습니다.
"""
import ast
import re
from contextvars import ContextVar
from functools import wraps
from . import sql_trace

STAGES = (
    ('ui', '화면', 'Jinja · HTML'),
    ('event', '이벤트', 'JavaScript'),
    ('api', 'API', 'FastAPI'),
    ('service', '서비스', 'Python'),
    ('database', 'DB 연결', 'python-oracledb'),
    ('sql', '실행 SQL', 'Oracle · PL/SQL'),
)
UI = {
    'initialize': ('templates/pages/home.html', 'id="initialize-basic"', 'initialize-basic'),
    'status': ('templates/index.html', 'id="refresh"', 'refresh'),
    'connection': ('templates/pages/assignment-template.html', 'id="assignment-check"', 'assignment-check'),
    'data': ('templates/pages/data.html', 'id="query-data"', 'query-data'),
    'preview': ('templates/pages/data.html', 'id="preview"', 'preview'),
    'import': ('templates/pages/data.html', 'id="import-submit"', 'import-submit'),
    'recreate': ('templates/pages/data.html', 'id="recreate-training"', 'recreate-training'),
    'prepare': ('templates/model-lab.html', 'id="{{ prepare }}"', 'prepare-data'),
    'prepared-data': ('templates/model-lab.html', 'id="{{ query }}"', 'query-prepared-data'),
    'train': ('templates/model-lab.html', "('initial','", 'model-initial'),
    'initial-train': ('templates/model-lab.html', "('initial','", 'model-initial'),
    'retrain': ('templates/model-lab.html', "('retrain','", 'model-retrain'),
    'delete-model': ('templates/model-lab.html', "('delete-model' if", 'model-delete'),
    'evaluate': ('templates/pages/models.html', 'id="query-models"', 'query-models'),
    'confirm': ('templates/pages/models.html', 'data-confirm="{{ v }}"', 'data-confirm'),
    'model-dictionary': ('templates/pages/models.html', 'id="query-model-dictionary"', 'query-model-dictionary'),
    'prediction-preview': ('templates/pages/predictions.html', 'id="preview-prediction"', 'preview-prediction'),
    'prediction-import': ('templates/pages/predictions.html', 'id="prediction-import-submit"', 'prediction-import-submit'),
    'prediction-data': ('templates/pages/predictions.html', 'id="query-prediction-data"', 'query-prediction-data'),
    'predict': ('templates/pages/predictions.html', 'id="run"', 'run'),
    'columns': ('templates/pages/predictions.html', 'id="query-prediction-columns"', 'query-prediction-columns'),
}
API = {
    'initialize':'initialize_basic', 'status':'status', 'data':'data', 'prepare':'prepare_data',
    'prepared-data':'prepared_data', 'preview':'preview', 'prediction-preview':'preview_predictions',
    'import':'import_data', 'recreate':'import_data', 'train':'train', 'initial-train':'train',
    'retrain':'train', 'delete-model':'delete_model', 'evaluate':'models',
    'confirm':'confirm_model', 'model-dictionary':'models_dictionary', 'prediction-import':'import_predictions',
    'prediction-data':'prediction_data', 'predict':'predict', 'columns':'columns', 'connection':'assignment_status',
}
JS = {
    'initialize': ("document.querySelectorAll('[data-basic-lifecycle]')", ('applyBasicLifecycle',)),
    'status': ("on('refresh','click'", ('refresh','loadStatus')),
    'data': ("on('query-data','click'", ('loadRows',)),
    'prepare': ("on('prepare-data','click'", ('prepareTraining',)),
    'prepared-data': ("on('query-prepared-data','click'", ('loadPreparedRows',)),
    'preview': ("on('preview','click'", ('preview',)),
    'prediction-preview': ("on('preview-prediction','click'", ('previewPrediction',)),
    'import': ("on('import-form','submit'", ('importTraining',)),
    'recreate': ("on('recreate-training','click'", ('importTraining',)),
    'train': ("for(const [id,action,label] of [['model-initial'", ('modelAction',)),
    'initial-train': ("for(const [id,action,label] of [['model-initial'", ('modelAction',)),
    'retrain': ("for(const [id,action,label] of [['model-initial'", ('modelAction',)),
    'delete-model': ("on('model-delete','click'", ('modelAction',)),
    'evaluate': ("on('query-models','click'", ('loadModels',)),
    'confirm': ("document.querySelectorAll('[data-confirm]')", ('modelAction',)),
    'model-dictionary': ("on('query-model-dictionary','click'", ('loadModelDictionary','renderDictionaryObject')),
    'prediction-import': ("on('prediction-import','submit'", ('importPrediction',)),
    'prediction-data': ("on('query-prediction-data','click'", ('loadPredictionRows',)),
    'predict': ("on('run','click'", ('selectedPredictionModel',)),
    'columns': ("on('query-prediction-columns','click'", ('loadColumns',)),
}
SERVICE = {
    'initialize': [('backend/sql_files.py','initialize')],
    'status': [('backend/service.py','status'),('backend/service.py','model_rows'),('backend/service.py','preparation_status')],
    'data': [('backend/service.py','get_data')],
    'prepare': [('backend/service.py','prepare_model_data'),('backend/service.py','fingerprint')],
    'prepared-data': [('backend/service.py','get_prepared_data')],
    'preview': [('backend/validation.py','parse_csv'),('backend/validation.py','quality')],
    'prediction-preview': [('backend/validation.py','parse_csv'),('backend/validation.py','quality')],
    'import': [('backend/validation.py','parse_csv'),('backend/sql_files.py','ensure_initialized'),('backend/service.py','load_csv'),('backend/service.py','invalidate_training_state')],
    'recreate': [('backend/validation.py','parse_csv'),('backend/service.py','invalidate_training_state'),('backend/sql_files.py','initialize'),('backend/service.py','load_csv')],
    'train': [('backend/service.py','train_model'),('backend/service.py','preparation_status'),('backend/service.py','fingerprint')],
    'initial-train': [('backend/service.py','train_model'),('backend/service.py','preparation_status'),('backend/service.py','fingerprint')],
    'retrain': [('backend/service.py','train_model'),('backend/service.py','preparation_status'),('backend/service.py','fingerprint')],
    'delete-model': [('backend/service.py','delete_model')],
    'evaluate': [('backend/service.py','model_results'),('backend/service.py','model_rows')],
    'confirm': [('backend/service.py','confirm_model'),('backend/service.py','model_rows'),('backend/service.py','fingerprint'),('backend/service.py','prepared_values'),('backend/service.py','read_state'),('backend/service.py','write_state')],
    'model-dictionary': [('backend/model_dictionary.py','read'),('backend/model_dictionary.py','object_detail'),('backend/model_dictionary.py','code_meaning')],
    'prediction-import': [('backend/validation.py','parse_csv'),('backend/sql_files.py','ensure_initialized'),('backend/service.py','load_csv')],
    'prediction-data': [],
    'predict': [('backend/service.py','predictions'),('backend/service.py','model_rows'),('backend/service.py','prediction_context')],
    'columns': [],
    'connection': [('backend/assignment_templates.py','readiness')],
}
SQL = {
    'initialize': ['sql/schema.sql','sql/prediction_table.sql','sql/prepared_table.sql','sql/classifier.sql','sql/table_comments.sql','sql/queries/procedure_errors.sql'],
    'status': ['sql/queries/objects.sql','sql/queries/prediction_storage.sql','sql/queries/training_count.sql','sql/queries/models.sql','sql/queries/prepared_count.sql'],
    'data': ['sql/queries/training_rows.sql'],
    'prepared-data': ['sql/queries/prepared_rows.sql'],
    'import': ['sql/queries/delete_training.sql','sql/queries/insert_training.sql'],
    'recreate': ['sql/recreate_training.sql','sql/schema.sql','sql/prediction_table.sql','sql/prepared_table.sql','sql/classifier.sql','sql/table_comments.sql','sql/queries/delete_training.sql','sql/queries/insert_training.sql'],
    'confirm': ['sql/queries/models.sql','sql/queries/training_rows.sql','sql/queries/procedure_source.sql','sql/queries/prepared_fingerprint_rows.sql'],
    'prediction-import': ['sql/queries/delete_prediction.sql','sql/queries/insert_prediction.sql'],
    'prediction-data': ['sql/queries/prediction_rows.sql'],
    'columns': ['sql/queries/columns.sql'],
    'connection': ['sql/queries/objects.sql','sql/queries/procedure_arguments.sql','sql/queries/procedure_errors.sql'],
}
MODEL_ACTIONS = {'prepare','train','initial-train','retrain','delete-model','evaluate','predict'}
MISSION_WEB = {'connection','status','data','prepared-data','prediction-data','evaluate','predict','import','prediction-import'}
MISSION_IDS = {
    'connection':'assignment-check', 'status':'assignment-check', 'data':'assignment-data-refresh',
    'prepared-data':'assignment-prepared-data', 'prediction-data':'assignment-prediction-data',
    'evaluate':'assignment-evaluate', 'predict':'assignment-predict', 'import':'assignment-import',
    'prediction-import':'assignment-prediction-import', 'prepare':'assignment-prepare',
    'initial-train':'assignment-initial','retrain':'assignment-retrain',
    'delete-model':'assignment-delete-model',
}

_source_snapshot = ContextVar('coding_source_snapshot', default=None)


def _file_snapshot(function):
    """도움말 한 번 안에서만 파일/AST를 재사용합니다. 다른 요청의 수정 내용을 캐시하지 않습니다."""
    @wraps(function)
    def build(*args, **kwargs):
        token = _source_snapshot.set({})
        try:
            return function(*args, **kwargs)
        finally:
            _source_snapshot.reset(token)
    return build


def _text(path):
    # 서버의 작업별 등록 경로만 읽습니다. 요청값을 파일 경로로 사용하지 않습니다.
    cache = _source_snapshot.get()
    if cache is None:
        return sql_trace.source(path)['content']
    if path not in cache:
        cache[path] = sql_trace.source(path)['content']
    return cache[path]


def _file_flow(flow,result):
    """파일 전체는 한 번만 전송하고 각 항목은 그 파일의 연속 구간을 가리킵니다."""
    op=result.get('operation')
    reads={'status','connection','prepare','train','initial-train','retrain','delete-model','evaluate','predict','confirm','import','prediction-import','recreate','unconfirm','clear-training','clear-prepared','drop-objects'}
    writes=reads-{'status','connection'}
    if flow.get('mode')=='web-execution' and op in reads:
        _unique(flow,'service',_python('backend/service.py','read_state','공유 검증 기록 조회'))
        _unique(flow,'service',_python('backend/progress_store.py','load','Oracle 계정의 검증 스냅샷'))
        _unique(flow,'sql',_whole('sql/queries/progress_read.sql','공유 검증 기록 SELECT'))
        linked=any('link_external' in item.get('content','') for item in flow['stages'][3]['items'])
        if op in writes or linked:
            _unique(flow,'service',_python('backend/progress_store.py','save','검증 기록 버전 검사·자율 트랜잭션 저장'))
            _unique(flow,'sql',_whole('sql/queries/progress_write.sql','검증 기록 저장 · 실습 COMMIT과 분리'))
    from .runtime_sql import add_runtime_items
    flow=add_runtime_items(flow,result)
    from scripts.source_files import APP_FILES, STUDENT_SCRIPTS, CONFIG
    allowed = {*APP_FILES, *('scripts/' + name for name in STUDENT_SCRIPTS), *CONFIG}
    files, by_key = {}, {}
    for stage in flow['stages']:
        for item in stage['items']:
            original = item['origin'] == 'source'
            if original and item['path'] not in allowed:
                raise ValueError('학생 배포 원본만 코딩도움말에 표시합니다.')
            key = ('source', item['path']) if original else ('generated', item['path'], item['content'])
            if key not in by_key:
                file_id = 'file-' + str(len(files) + 1)
                content = _text(item['path']) if original else item['content']
                files[file_id] = {'id':file_id, 'path':item['path'], 'origin':item['origin'],
                    'kind':item['kind'], 'content':content, 'line_count':len(content.splitlines())}
                by_key[key] = file_id
            item['file_id'] = by_key[key]
            del item['content']
    flow.update(version=2, files=files)
    return flow


def _source(path, start, end, title, role='', kind=''):
    lines = _text(path).splitlines()
    if not 1 <= start <= end <= len(lines):
        raise ValueError('등록한 소스 위치를 확인하세요: '+path)
    return {'title':title,'path':path,'line':start,'end_line':end,'content':'\n'.join(lines[start-1:end]),
            'role':role or '표시한 파일의 연속 원문입니다.','kind':kind or ('sql' if path.endswith('.sql') else 'python' if path.endswith('.py') else 'javascript' if path.endswith('.js') else 'html'),
            'origin':'source'}

def _whole(path,title,role=''):
    return _source(path,1,len(_text(path).splitlines()),title,role)

def _python(path,name,title=None,role=''):
    cache = _source_snapshot.get()
    key = ('ast',path)
    if cache is not None and key in cache:
        tree = cache[key]
    else:
        tree = ast.parse(_text(path))
        if cache is not None: cache[key] = tree
    node=next((node for node in ast.walk(tree) if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and node.name==name),None)
    if node is None:raise ValueError('등록한 Python 함수가 없습니다: '+path+' '+name)
    start=min([node.lineno]+[d.lineno for d in node.decorator_list])
    return _source(path,start,node.end_lineno,title or name+'()',role)

def _around(path,needle,title,role='',before=0,after=0):
    lines=_text(path).splitlines()
    index=next((i for i,line in enumerate(lines) if needle in line),None)
    if index is None:raise ValueError('등록한 이벤트·화면 위치가 없습니다: '+path+' '+needle)
    return _source(path,max(1,index+1-before),min(len(lines),index+1+after),title,role)

def _js_function(path,name):
    lines=_text(path).splitlines()
    start=next((i for i,line in enumerate(lines) if re.match(r'(?:async )?function '+re.escape(name)+r'\(',line)),None)
    if start is None:raise ValueError('등록한 JavaScript 함수가 없습니다: '+name)
    if lines[start].rstrip().endswith('}'):
        end=start
    else:
        end=next(i for i in range(start+1,len(lines)) if re.match(r'^}',lines[i]))
    return _source(path,start+1,end+1,name+'()')

def _handler(path,needle,title):
    lines=_text(path).splitlines()
    start=next((i for i,line in enumerate(lines) if needle in line),None)
    if start is None:raise ValueError('등록한 클릭 핸들러가 없습니다: '+needle)
    end=start
    if not lines[start].rstrip().endswith(';'):
        end=next(i for i in range(start+1,len(lines)) if lines[i].startswith('});'))
    return _source(path,start+1,end+1,title,'클릭/submit 등록과 해당 콜백의 원문입니다.')

def _generated(content,title,path,role):
    return {'title':title,'path':path,'line':None,'end_line':None,'content':content,'role':role,
            'kind':'sql-generated','origin':'generated'}

def _new(result,mode,summary):
    return {'version':1,'operation':result['operation'],'assignment':result['assignment'],'mode':mode,'summary':summary,
            'stages':[{'id':key,'label':label,'technology':tech,'summary':'','items':[]} for key,label,tech in STAGES]}

def _add(flow,stage,*items):
    target=next(item for item in flow['stages'] if item['id']==stage)
    for item in items:
        item={**item,'id':stage+'-'+str(len(target['items'])+1)}
        target['items'].append(item)
    if not target['summary'] and target['items']:
        target['summary']=target['items'][0]['title']

def _focus(item,needle):
    start=item['content'].find(needle)
    if start<0:return item
    opening=item['content'].rfind('<button',0,start+1)
    closing=item['content'].find('</button>',start)
    if opening>=0 and closing>=0 and item['content'].find('</button>',opening)>start:
        start,end=opening,closing+len('</button>')
    else:end=start+len(needle)
    item.update(focus_start=start,focus_end=end,focus_text=item['content'][start:end])
    return item


def _ui(flow,operation,title,trigger_id='',page='',mission=False):
    if mission:
        path='templates/pages/assignment-template.html'
        button=MISSION_IDS.get(operation,'')
        if operation in ('setup','initialize','validate'):
            needle='data-code="setup"'
        elif operation in ('clear-training','clear-prediction','drop-objects'):
            button={'clear-training':'assignment-clear-training','clear-prediction':'assignment-clear-prediction','drop-objects':'assignment-drop-objects'}[operation]
            needle='id="'+button+'"'
        elif operation=='clear-prepared':
            path='templates/model-lab.html';button='assignment-clear-prepared';needle='id="'+button+'"'
        elif operation in ('prepare','prepared-data'):
            path='templates/model-lab.html';needle='id="{{ prepare }}"' if operation=='prepare' else 'id="{{ query }}"'
        elif operation in ('initial-train','retrain','delete-model','train'):
            path='templates/model-lab.html';needle=UI[operation][1]
        elif operation in ('connection','status'):
            needle='id="assignment-check"'
        elif operation=='columns':
            needle='data-mission-schema='
        elif operation in ('preview','prediction-preview'):
            needle='data-mission-preview='
        else:
            needle="action_button('"+button+"'"
    else:
        path,needle,button=UI[operation]
    if mission and trigger_id=='refresh' and operation in ('connection','status'):
        path='templates/index.html';needle='id="refresh"';button='refresh'
    _add(flow,'ui',_focus(_around(path,needle,title+' · 화면 버튼','실제 Jinja 원문에서 클릭한 버튼 위치를 강조합니다. 변수 ID·라벨은 매크로/호출 인자로 렌더링됩니다.',before=1,after=1),needle))
    if path=='templates/model-lab.html' and operation in ('initial-train','retrain','delete-model','train'):
        _add(flow,'ui',_around(path,'class="model-action"><span', '공통 모델 버튼 매크로',after=1))
    if mission and path.endswith('assignment-template.html') and operation not in ('setup','initialize','validate','preview','prediction-preview','connection','status','columns'):
        _add(flow,'ui',_around(path,'{% macro action_button(', '공통 과제 버튼 매크로',after=2))
    flow['trigger']={'id':trigger_id or button,'label':title}
    flow['initial_item']=flow['stages'][0]['items'][0]['id']

def _db(flow,model=False,ddl=False,query=True):
    _add(flow,'database',_python('app.py','database','로그인 계정의 DB 연결'),
         _python('backend/db.py','connection','Oracle 풀 대여·반환'),
         _python('backend/db.py','connection_args','풀 최초 생성 · Wallet·접속 설정'),
         _python('backend/db.py','initialize_session','새 물리 연결의 세션 초기화'),
         _whole('sql/session.sql','접속 직후 공통 세션 설정','풀에서 새 물리 연결을 만들 때만 initialize_session이 적용합니다. 재사용할 때는 반복 실행하지 않습니다.'))
    if model:
        _add(flow,'database',_python('backend/service.py','run_model','프로시저 바인드·OUT 커서','DB에 적용된 RUN을 호출합니다. 로컬 SQL 파일을 다시 컴파일하지 않습니다.'))
    if ddl:
        _add(flow,'database',_python('backend/sql_files.py','execute_file','SQL 파일의 DDL 순차 실행'))
    if query:_add(flow,'database',_python('backend/sql_files.py','query','SELECT 공통 진입'))
    _add(flow,'database',_python('backend/sql_files.py','execute','cursor.execute · executemany · 결과 읽기'))


def _unique(flow,stage,item):
    items=next(entry for entry in flow['stages'] if entry['id']==stage)['items']
    key=(item['path'],item['line'],item['end_line'],item['origin'])
    if not any((entry['path'],entry['line'],entry['end_line'],entry['origin'])==key for entry in items):
        _add(flow,stage,item)

def _sql_procedure(name):
    path='sql/classifier.sql';lines=_text(path).splitlines()
    start=next((index for index,line in enumerate(lines) if line.startswith('  PROCEDURE '+name+' ')),None)
    if start is None:return None
    end=next((index for index in range(start+1,len(lines)) if lines[index]=='  END;'),None)
    if end is None:return None
    return _source(path,max(1,start),end+1,'학습 검증 정의 · '+name+'()','학습 실행 4에서 호출합니다. 선언부 자체가 즉시 실행되는 것은 아닙니다.')

def _followups(flow,operation,page):
    """Click handlers can request status and evaluation after the primary API."""
    actions={
        'initialize':['loadStatus'], 'prepare':['loadStatus','loadPreparedRows'],
        'import':['loadStatus','loadRows'], 'recreate':['loadStatus','loadRows'],
        'prediction-import':['loadStatus','loadPredictionRows','loadColumns'],
        'train':['loadStatus','loadModels'], 'initial-train':['loadStatus','loadModels'],
        'retrain':['loadStatus','loadModels'], 
        'delete-model':['loadStatus','loadModels'],
        'confirm':['loadStatus','loadModels'] if page=='models' else ['loadStatus'],
    }.get(operation,[])
    if operation=='status':
        actions={'data':['loadRows','loadPreparedRows'],'models':['loadModels'],
                 'predictions':['loadPredictionRows','loadColumns']}.get(page,[])
    routes={
        'loadStatus':('status',['status','model_rows','preparation_status','fingerprint','prepared_values'],
                      ['objects.sql','prediction_storage.sql','training_count.sql','models.sql','training_rows.sql','procedure_source.sql','prepared_fingerprint_rows.sql','prepared_count.sql']),
        'loadModels':('models',['model_results','model_rows','fingerprint','prepared_values'],
                      ['models.sql','training_rows.sql','procedure_source.sql','prepared_fingerprint_rows.sql','model_details.sql']),
        'loadPreparedRows':('prepared_data',['get_prepared_data'],['prepared_rows.sql']),
        'loadRows':('data',['get_data'],['training_rows.sql']),
        'loadPredictionRows':('prediction_data',[],['prediction_rows.sql']),
        'loadColumns':('columns',[],['columns.sql']),
    }
    for function in actions:
        route,services,queries=routes[function]
        item=_js_function('static/js/main.js',function)
        item.update(title='화면 갱신 · '+function+'()',role='주 작업 후 클릭 핸들러가 요청하는 후속 조회입니다. 원문의 조건·실패 처리 순서를 유지합니다.')
        _unique(flow,'event',item)
        _unique(flow,'api',_python('app.py',route,'화면 갱신 API · '+route+'()','주 작업 뒤 브라우저가 별도로 보내는 조회 요청입니다.'))
        for name in services:
            _unique(flow,'service',_python('backend/service.py',name,'화면 갱신 서비스 · '+name+'()','후속 상태/결과 요청에서 호출합니다. 객체·모델 존재와 최신 여부에 따라 조회·평가를 생략합니다.'))
        for filename in queries:
            _unique(flow,'sql',_whole('sql/queries/'+filename,'화면 갱신 SQL · '+filename,'후속 화면 조회에서 사용합니다. 조건부 호출은 해당 서비스 함수에서 확인하세요.'))
    if 'loadModels' in actions:
        _unique(flow,'event',_js_function('static/js/main.js','renderModels'))
        _unique(flow,'database',_python('backend/service.py','run_model','후속 TEST 평가 · 프로시저 호출','조회한 모델 중 최신 상태인 RAW/CLEAN 각각에 EVALUATE를 호출합니다.'))
        _unique(flow,'sql',_whole('sql/queries/call_classifier.sql','화면 갱신 · EVALUATE 호출','loadModels → model_results에서 최신 상태인 RAW/CLEAN 모델마다 EVALUATE를 바인드합니다. 주 작업에서 선택한 모델 하나로 제한하지 않습니다.'))
        from .coding_help import oracle_sections
        for section in oracle_sections('evaluate','BOTH','basic',source=_text('sql/classifier.sql')):
            _unique(flow,'sql',_source(section['path'],section['line'],section['end_line'],'후속 TEST 평가 · '+section['title'],
                    'model_results가 최신 상태인 RAW/CLEAN 모델에만 각각 EVALUATE를 호출합니다. 로컬 정의와 DB 적용 버전은 다를 수 있습니다.'))
        flow['summary']+=' 작업 후 화면 갱신에서 최신 상태인 RAW/CLEAN 모델을 각각 TEST 평가합니다.'

def _confirmation(flow):
    event=next(stage for stage in flow['stages'] if stage['id']=='event')
    if any('askConfirmation(' in item['content'] for item in event['items']):
        for name,title in (('askConfirmation','공통 · 실행 전 레이어 확인'),('finishLayerConfirmation','공통 · 확인/취소 결과 반환')):
            item=_js_function('static/js/layer-message.js',name)
            item.update(title=title,role='확인일 때만 다음 API 호출로 진행합니다. 취소·닫기·ESC는 실행하지 않습니다.')
            _unique(flow,'event',item)

@_file_snapshot
def basic_flow(result,*,trigger_id='',trigger_label='',page=''):
    op=result['operation']
    preview=op in ('preview','prediction-preview')
    summary='화면 버튼부터 실제 호출 소스까지 순서대로 확인합니다. 도움말을 여는 동안 작업 SQL은 실행하지 않습니다.'
    if op=='confirm':summary='모델 검증 SELECT → Oracle 공유 검증 기록에 선택 저장. 모델 자체는 변경하지 않습니다.'
    if preview:summary='업로드 CSV → Python 파싱·품질 검사 → 미리보기. DB 연결과 SQL 실행은 없습니다.'
    flow=_new(result,'local-preview' if preview else 'web-execution',summary)
    label=' '.join(str(trigger_label).split())[:80] or result['title']
    _ui(flow,op,label,trigger_id,page)
    if op in JS:
        needle,functions=JS[op]
        _add(flow,'event',_handler('static/js/main.js',needle,'버튼 이벤트 등록'))
        for name in functions:_add(flow,'event',_js_function('static/js/main.js',name))
        _add(flow,'event',_js_function('static/js/main.js','api'))
    else:
        _add(flow,'event',_handler('static/js/assignment-template.js',"on('assignment-check','click'",'연결 확인 이벤트'),
             _js_function('static/js/assignment-template.js','loadAssignmentReadiness'),_js_function('static/js/main.js','api'))
    _add(flow,'api',_python('app.py',API[op],'요청 라우트 · '+API[op]+'()'))
    for path,name in SERVICE.get(op,()):_add(flow,'service',_python(path,name))
    if op in ('evaluate','predict'):
        for name in ('begin','record','model_stamp'):
            _add(flow,'service',_python('backend/practice_evidence.py',name,'성공 증적 · '+name+'()'))
    status_response={'prepare','train','initial-train','retrain','delete-model','confirm','initialize','import','recreate','prediction-import'}
    if op in status_response:
        _add(flow,'service',_python('backend/service.py','status','작업 후 상태 응답 · status()','API가 작업 완료 뒤 현재 객체·행 수·모델·전처리 상태를 함께 반환합니다.'))
    # Follow only named helpers actually referenced by displayed service functions.
    # This avoids inventing PREPARED count reads for EVALUATE/PREDICT.
    service_items=flow['stages'][3]['items']
    seen={(item['path'],item['line']) for item in service_items}
    cursor=0
    while cursor<len(service_items):
        entry=service_items[cursor];cursor+=1
        if entry['path']!='backend/service.py':continue
        calls=[node.func.id for node in ast.walk(ast.parse(entry['content'])) if isinstance(node,ast.Call) and isinstance(node.func,ast.Name)]
        for name in ('model_rows','preparation_status','fingerprint','prepared_values','state_path'):
            if name not in calls:continue
            helper=_python('backend/service.py',name,'검증 함수 · '+name+'()','상위 서비스에서 호출하는 검사 원문입니다. 실행 조건과 호출 시점은 상위 함수에 표시되어 있습니다.')
            key=(helper['path'],helper['line'])
            if key not in seen:
                _add(flow,'service',helper);seen.add(key)
    if not flow['stages'][3]['items']:
        flow['stages'][3]['summary']='별도 업무 서비스 없음 · API에서 공통 query() 호출'
    if preview:
        flow['stages'][4]['summary']='사용하지 않음 · CSV는 메모리에서 검사'
        flow['stages'][5]['summary']='실행 SQL 없음'
        return _file_flow(flow,result)
    _db(flow,model=op in MODEL_ACTIONS,ddl=op in ('initialize','recreate','import','prediction-import'),query=op!='prepared-data')
    if op in MODEL_ACTIONS:
        _add(flow,'sql',_whole('sql/queries/call_classifier.sql','1. 웹이 바인드하는 RUN 호출','service.run_model이 소유자·프로시저명과 p_action/p_mode를 적용하여 실행합니다.'))
        sections=[dict(section) for section in result.get('oracle_sections',[])]
        for section in sections:
            if section['title'].startswith('명령 참고') and 'p_sql :=' in section['content']:
                section['title']=section['title'].replace('명령 참고 · ','실행 3 · ').replace(' 원문',' 지정')
        execution=sorted([section for section in sections if section['title'].startswith('실행 ')],key=lambda section:section['title'])
        reference=[section for section in sections if section not in execution]
        for section in [*execution,*reference]:
            _add(flow,'sql',_source(section['path'],section['line'],section['end_line'],section['title'],section.get('role','')+' 로컬 정의 원문이며 DB에 적용한 버전과 다를 수 있습니다.'))
    else:
        paths=SQL.get(op,[])
        if op=='model-dictionary':
            from .model_dictionary import CATALOG
            paths=['sql/queries/dictionary_'+key+'.sql' for key,*rest in CATALOG]+['sql/queries/dictionary_detail_rows.sql']
        for path in paths:_add(flow,'sql',_whole(path,path.rsplit('/',1)[-1]))
        if op in ('import','prediction-import'):
            _add(flow,'sql',_whole('sql/queries/objects.sql','객체 준비 확인 · 조건부 DDL','API의 ensure_initialized가 객체 누락/INVALID일 때만 initialize를 호출합니다.'))
        if op not in ('confirm',) and result.get('script') and op not in ('initialize','recreate'):
            _add(flow,'sql',_generated(result['script'],'현재 선택값 · 직접 확인용 SQL',result.get('script_path','example.sql'),'바인드·소유자를 반영한 생성 예제입니다. 파일 원문의 줄 번호는 부여하지 않습니다.'))
    checks=[]
    if op in MODEL_ACTIONS or op in ('confirm','status'):
        checks=['models.sql','training_rows.sql','procedure_source.sql','prepared_fingerprint_rows.sql']
        if op not in ('evaluate','predict'):checks+=['prepared_count.sql']
    if op in ('prepare','train','initial-train','retrain','delete-model','confirm','initialize','import','recreate','prediction-import'):
        checks+=['objects.sql','prediction_storage.sql','training_count.sql']
        if op not in ('prepare','train','initial-train','retrain','delete-model','confirm'):
            checks+=['models.sql','training_rows.sql','procedure_source.sql','prepared_fingerprint_rows.sql','prepared_count.sql']
    if op=='evaluate':checks+=['model_details.sql']
    if op=='predict':checks+=['prediction_rows.sql','columns.sql']
    existing={item['path'] for item in flow['stages'][5]['items'] if item['origin']=='source'}
    for filename in checks:
        path='sql/queries/'+filename
        if path not in existing:
            _add(flow,'sql',_whole(path,'검증·상태 조회 · '+filename,'서비스의 존재/최신 검사 또는 작업 완료 후 상태 조회입니다. 준비 여부에 따라 일부 SELECT는 생략합니다.'))
            existing.add(path)
    if op in ('import','prediction-import'):
        _add(flow,'service',_python('backend/sql_files.py','initialize','객체 누락·INVALID일 때 정의 준비'))
        for path in ('sql/schema.sql','sql/prediction_table.sql','sql/prepared_table.sql','sql/classifier.sql','sql/table_comments.sql','sql/queries/procedure_errors.sql'):
            if path not in existing:
                _add(flow,'sql',_whole(path,'조건부 객체 준비 · '+path.rsplit('/',1)[-1],'ensure_initialized에서 객체 누락·INVALID일 때만 적용합니다. 기존 테이블 행은 유지합니다.'))
                existing.add(path)
    if op in ('train','initial-train','retrain'):
        for name in ('validate_source','validate_prepared'):
            item=_sql_procedure(name)
            if item:_unique(flow,'sql',item)
    if op in MODEL_ACTIONS and result.get('direct_script'):
        _add(flow,'sql',_generated(result['direct_script'],'선택값으로 만든 SQL Developer 호출','sql/examples/run.sql','직접 실행용 생성 예제입니다. 웹 cursor 실행 원문은 첫 항목이며, 도움말에서 SQL을 실행하지 않습니다.'))
    _followups(flow,op,page)
    if op=='confirm':flow['stages'][3]['summary']='검증 후 write_state()로 Oracle 공유 기록 저장'
    _confirmation(flow)
    return _file_flow(flow,result)

@_file_snapshot
def mission_flow(result,*,trigger_id='',trigger_label='',page=''):
    op=result['operation'];web=op in MISSION_WEB
    creative=result['assignment']=='creative'
    if not creative and op in ('connection','status') and not trigger_id:trigger_id='refresh'
    summary=('직접 만든 미션 객체를 웹에서 조회·평가·예측하는 실제 호출 흐름입니다. 로컬 미션 SQL과 DB 적용 버전은 다를 수 있습니다.' if web else
             '웹은 선택 미션의 SQL을 생성·표시합니다. DB 연결·실행은 없으며, 생성 SQL은 SQL Developer에서 직접 실행합니다.')
    flow=_new(result,'web-execution' if web else 'manual-guide',summary)
    flow['context']=('' if creative else '미션과제 · ')+result['title'].removesuffix(' · SQL 가이드')+' · '+result['variant']
    label=' '.join(str(trigger_label).split())[:80] or result['title']
    _ui(flow,op,label,trigger_id,page,mission=True)
    if op in ('import','prediction-import'):
        flow['mode_label']='CSV 업로드·묶음 적재'
        flow['summary']='파일 선택 → 교체 확인 → 업로드 API → 헤더·대상 컬럼 검사 → 500행 바인드 → 한 번 COMMIT. 실패하면 ROLLBACK합니다.'
        _add(flow,'event',_js_function('static/js/assignment-template.js','assignmentImportUnavailable'),
             _js_function('static/js/assignment-template.js','importAssignmentCsv'),
             _js_function('static/js/layer-message.js','askConfirmation'),_js_function('static/js/main.js','api'))
        _add(flow,'api',_python('app.py','assignment_csv','CSV 업로드 POST · 인증·CSRF·용량 검사'),
             _python('app.py','import_assignment_csv','작업 스레드 · 파일 전체 검사 후 DB 연결'))
        _add(flow,'service',_python('backend/csv_import.py','mission_rows','선택 미션 헤더·식별자·구분 검사'),
             _python('backend/assignment_templates.py','import_csv','현재 계정·스키마·고정 대상 검사'),
             _python('backend/assignment_templates.py','load_custom','실제 컬럼 검사 · 교체/묶음 적재/COMMIT·ROLLBACK'))
        if not creative:_add(flow,'service',_python('backend/mission_binding.py','table_issues','선택 미션의 적재 대상 규약 검사'))
        _db(flow)
        if not creative:_add(flow,'sql',_whole('sql/queries/schema_columns.sql','선택 미션과 대상 테이블 자료형 검사'))
        _add(flow,'sql',_whole('sql/queries/csv_owner.sql','발급 계정·스키마 확인'),
             _whole('sql/queries/columns.sql','대상 테이블의 실제 컬럼·필수값 확인'),
             _whole('sql/queries/custom_delete.sql','대상 테이블의 기존 행 교체'),
             _whole('sql/queries/custom_insert.sql','단일 INSERT · 500행씩 executemany'),
             _generated(result['script'],result['code_title'],result['script_path'],'선택 미션의 소유자·컬럼·바인드 이름만 반영합니다. CSV 행 수만큼 SQL을 생성하지 않습니다.'))
        return _file_flow(flow,result)
    if op in ('preview','prediction-preview'):
        flow['mode']='local-preview'
        flow['summary']='배포 CSV 원문 → Python CSV 읽기 → 페이지별 표시. DB 연결·SQL 실행은 없습니다.'
        _add(flow,'event',_around('static/js/assignment-template.js',"const preview=event.target.closest('[data-mission-preview]')",'CSV 조회 클릭',before=1,after=2),
             _js_function('static/js/assignment-template.js','openMissionCsv'),_js_function('static/js/assignment-template.js','loadMissionCsv'),
             _js_function('static/js/main.js','api'))
        _add(flow,'api',_python('app.py','dataset_preview','배포 CSV 조회 GET'))
        _add(flow,'service',_python('app.py','dataset_source','허용된 catalog CSV 선택'))
        flow['stages'][4]['summary']='사용하지 않음 · 로컬 배포 CSV 읽기'
        flow['stages'][5]['summary']='실행 SQL 없음'
        return _file_flow(flow,result)
    if web:
        button=MISSION_IDS[op]
        refresh_only=trigger_id=='refresh' and op in ('connection','status')
        if refresh_only:
            _add(flow,'event',_handler('static/js/main.js',"on('refresh','click'",'상단 새로고침 이벤트'),_js_function('static/js/main.js','refresh'))
        else:
            _add(flow,'event',_handler('static/js/assignment-template.js',"on('"+button+"','click'",'미션 버튼 이벤트'))
        if op in ('connection','status'):
            _add(flow,'event',_js_function('static/js/assignment-template.js','loadAssignmentReadiness'))
            if not refresh_only:_add(flow,'api',_python('app.py','link_assignment','객체·모델 연계 POST'))
            _add(flow,'api',_python('app.py','assignment_status','연결 상태 GET'))
            for name in (('readiness','verification_state','preparation_status','model_state') if refresh_only else ('link_external','readiness','preparation_status','model_state')):
                _add(flow,'service',_python('backend/assignment_templates.py',name))
            paths=['sql/queries/objects.sql','sql/queries/columns.sql','sql/queries/procedure_arguments.sql','sql/queries/procedure_errors.sql','sql/queries/assignment_models.sql','sql/queries/prepared_count.sql']
        else:
            _add(flow,'event',_js_function('static/js/assignment-template.js','assignmentTask'))
            _add(flow,'api',_python('app.py','assignment_action','허용된 미션 작업 POST'))
            _add(flow,'service',_python('backend/assignment_templates.py','run'),_python('backend/assignment_templates.py','readiness'))
            if op=='prepared-data':_add(flow,'service',_python('backend/service.py','get_prepared_data'))
            if op in ('evaluate','predict'):_add(flow,'service',_python('backend/assignment_templates.py','model_state'))
            if op in ('evaluate','predict'):
                for name in ('begin','record','model_stamp'):_add(flow,'service',_python('backend/practice_evidence.py',name,'성공 증적 · '+name+'()'))
            paths=['sql/queries/prepared_rows.sql'] if op=='prepared-data' else ['sql/queries/call_classifier.sql'] if op in ('evaluate','predict') else ['sql/queries/custom_rows.sql']
        if op in ('connection','status','evaluate','predict'):
            if not creative:
                _add(flow,'service',_python('backend/mission_binding.py','inspect','선택·DB 적용 미션 일치 검사'),_python('backend/mission_binding.py','table_issues','세 테이블 규약 검사'))
                _add(flow,'api',_python('app.py','mission_context','요청 미션과 DB 선택값 대조'))
                if op in ('evaluate','predict') or not refresh_only:
                    _add(flow,'service',_python('backend/mission_binding.py','model_matches','실제 모델의 선택 미션 속성 확인'))
                if op in ('connection','status') and not refresh_only:
                    _add(flow,'service',_python('backend/mission_binding.py','bind','일치 검증 후 적용 미션 기록'))
            _add(flow,'service',_python('backend/assignment_templates.py','training_fingerprint','검증 함수 · training_fingerprint()'),
                 _python('backend/service.py','prepared_values','검증 함수 · prepared_values()'))
        if op in ('connection','status') and not refresh_only:
            _add(flow,'service',_python('backend/service.py','write_state','연계 결과의 DB 공유 저장','객체·모델을 만든 뒤 연계한 검증값을 OML_WEB_STATE에 저장합니다. 모델 자체는 변경하지 않습니다.'),
                 _python('backend/service.py','state_path','연계 기록 파일 위치'))
        _add(flow,'event',_js_function('static/js/main.js','api'))
        _db(flow,model=op in ('evaluate','predict'))
        for path in paths:_add(flow,'sql',_whole(path,path.rsplit('/',1)[-1],'검증된 미션 객체 이름과 선택값을 Python에서 바인드/치환합니다.'))
        checks=['objects.sql','columns.sql','procedure_arguments.sql','procedure_errors.sql']
        if not creative and op in ('connection','status','evaluate','predict'):checks+=['schema_columns.sql']
        if op in ('connection','status','evaluate','predict'):
            checks+=['assignment_models.sql','custom_fingerprint_rows.sql','procedure_source.sql','prepared_fingerprint_rows.sql']
        if op in ('connection','status'):checks+=['prepared_count.sql']
        if not creative and (op in ('evaluate','predict') or op in ('connection','status') and not refresh_only):checks+=['dictionary_attributes.sql']
        existing=set(paths)
        for filename in checks:
            path='sql/queries/'+filename
            if path not in existing:
                _add(flow,'sql',_whole(path,'검증·연계 조회 · '+filename,'미션 객체·인자·적용 정의·모델 최신 여부를 확인합니다. 호출 조건은 서비스 원문에서 확인하세요.'))
                existing.add(path)
        if op in ('evaluate','predict'):
            _add(flow,'sql',_whole('sql/custom/mission/02_procedure.sql','로컬 RUN 정의 · DB 적용 여부 확인','이 파일을 DB에 적용한 경우에만 실행 정의와 일치합니다. 선택 미션 생성본은 아래 별도 항목입니다.'))
        _add(flow,'sql',_generated(result['script'],'선택 미션 · 직접 실행용 SQL',result['script_path'],'선택 미션 컬럼·소유자를 반영한 생성 예제입니다. 웹이 실행한 SQL 기록이 아닙니다.'))
    else:
        _add(flow,'event',_around('static/js/execution-dialog.js',"const button=event.target.closest('[data-code],[data-execution],[data-manual-action]')",'코딩 도움말 클릭 이벤트',before=1,after=1),
             _js_function('static/js/execution-dialog.js','openExecution'),_js_function('static/js/main.js','api'))
        _add(flow,'api',_python('app.py','coding_help','선택 미션 도움말 GET'))
        _add(flow,'service',_python('backend/mission_guide.py','creative_manual' if creative else 'generate','직접 수행 SQL 생성'))
        generator='csv_load_sql' if op in ('import','prediction-import') else 'procedure_sql' if op in ('setup','initialize') else 'reset_sql' if op in ('clear-training','clear-prediction','clear-prepared','drop-objects') else '_direct'
        if op in ('preview','prediction-preview'):generator='procedure_sql'
        _add(flow,'service',_python('backend/mission_guide.py',generator))
        if not creative and generator not in ('procedure_sql','reset_sql'):
            _add(flow,'service',_python('backend/mission_guide.py','procedure_sql','선택 미션의 전체 RUN 정의 생성','generate가 공통으로 읽는 템플릿에 선택 미션 컬럼·라벨·소유자를 반영합니다.'))
        flow['stages'][4]['summary']='웹 DB 연결 없음 · SQL Developer에서 직접 실행'
        _add(flow,'sql',_generated(result['script'],result.get('code_title','직접 실행 SQL'),result['script_path'],'직접 실행용 생성 SQL입니다. 가이드 조회·복사는 DB를 변경하지 않습니다.'))
    if creative:
        flow['summary']='본인 RUN의 호출·고정 객체 정리만 안내합니다. 구현·실행은 SQL Developer에서 직접 수행하세요.'
        _add(flow,'sql',_whole('sql/custom/creative/02_procedure.sql','본인이 작성하는 RUN 파일'))
        return _file_flow(flow,result)
    if op not in ('preview','prediction-preview','clear-training','clear-prediction','clear-prepared','drop-objects'):
        if result['script']!=result['procedure_sql']:
            _add(flow,'sql',_generated(result['procedure_sql'],'선택 미션 전체 RUN 정의','sql/custom/mission/02_procedure.sql','선택 미션을 반영한 생성본입니다. 이 경로에 저장하고 발급 계정에서 F5 적용하세요. 기존 파일 원문과 구분합니다.'))
        _add(flow,'sql',_whole('sql/custom/mission/guide_procedure.sql','미션 RUN 생성 템플릿 원문','생성 서비스가 실제 읽는 템플릿입니다. {{...}} 값은 선택 미션의 컬럼·분류값·소유자로 치환되며 템플릿 자체를 실행하지 않습니다.'))
    _confirmation(flow)
    return _file_flow(flow,result)


@_file_snapshot
def lifecycle_flow(result,*,trigger_id='',trigger_label='',page=''):
    from .basic_lifecycle import sql_paths
    op=result['operation']
    targets={'create-tables':('templates/pages/home.html','initialize-basic'),
             'register-procedure':('templates/pages/home.html','register-basic'),
             'reregister-procedure':('templates/pages/home.html','reregister-basic'),
             'clear-training':('templates/pages/data.html','clear-training'),
             'clear-prediction':('templates/pages/predictions.html','clear-prediction'),
             'clear-prepared':('templates/model-lab.html','clear-prepared'),
             'drop-objects':('templates/pages/home.html','drop-basic-objects'),
             'unconfirm':('templates/pages/models.html','unconfirm-model')}
    path,button=targets[op]
    flow=_new(result,'web-execution','대상 확인 → 레이어 확인 → 현재 계정의 고정 작업 실행 → 상태 새로고침')
    label=trigger_label or result['title']
    _add(flow,'ui',_focus(_around(path,'id="'+button+'"',label+' · 화면 버튼',before=0,after=0),'id="'+button+'"'))
    flow['trigger']={'id':trigger_id or button,'label':label}
    flow['initial_item']=flow['stages'][0]['items'][0]['id']
    _add(flow,'event',_around('static/js/main.js',"document.querySelectorAll('[data-basic-lifecycle]')",'고정 작업 버튼 이벤트',before=0,after=0),
         _js_function('static/js/main.js','applyBasicLifecycle'),_js_function('static/js/main.js','loadStatus'),_js_function('static/js/main.js','api'))
    _add(flow,'api',_python('app.py','basic_lifecycle_action'))
    _add(flow,'service',_python('backend/basic_lifecycle.py','apply'),_python('backend/service.py','status'),
         _python('backend/service.py','write_state'))
    _db(flow,ddl=op in ('create-tables','register-procedure','reregister-procedure'),query=True)
    if op=='unconfirm':
        flow['stages'][5]['summary']='작업 SQL 없음 · 서버 로컬 모델 선택만 해제'
    else:
        _add(flow,'sql',_whole('sql/queries/csv_owner.sql','발급 계정·CURRENT_SCHEMA 검사'))
        for path in sql_paths(op):_add(flow,'sql',_whole(path,path.rsplit('/',1)[-1]))
    _confirmation(flow)
    return _file_flow(flow,result)
