"""기본과제 네 화면과 미션·창의과제 연결 템플릿. SQL은 sql/에서만 수정합니다."""
from __future__ import annotations
from backend import sql_trace
import csv
import io
import hmac
import base64
import hashlib
import json
import os
import re
import secrets
import threading
import time
from contextlib import contextmanager, asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from starlette.concurrency import run_in_threadpool
from starlette.middleware.trustedhost import TrustedHostMiddleware
from backend.db import ROOT, connection, safe_error, student_settings, save_credentials, close_connections
from backend import identity, service
from backend.validation import parse_csv, quality, COLUMNS
from backend.sql_files import initialize, ensure_initialized, execute_file, query, ready
from backend.connection_help import explain as connection_help
from backend.operation_help import explain as operation_help
from backend.source_help import read_source
from backend.execution_scripts import execution_script
from backend import assignment_templates, connection_profile

_operation = threading.Lock()
# Cookie names are shared across ports on localhost. Isolate each project copy.
SESSION_COOKIE_NAME = 'oml_com22417_' + hashlib.sha256(str(ROOT.resolve()).encode('utf-8')).hexdigest()[:12]
SESSION_IDLE_SECONDS = 30 * 60
EXPERIMENTS = {'baseline', 'reordered', 'renamed', 'numeric_text', 'wrong_type', 'with_target', 'extra', 'missing'}


def session_secret():
    if os.environ.get('SECRET_KEY'):
        return os.environ['SECRET_KEY']
    target = ROOT / 'runtime/session.key'
    target.parent.mkdir(exist_ok=True)
    try:
        with target.open('x', encoding='ascii') as stream:
            stream.write(secrets.token_hex(32))
    except FileExistsError:
        pass
    return target.read_text(encoding='ascii')


def variant_name(value):
    value = str(value).upper()
    if value not in ('RAW', 'CLEAN'):
        raise ValueError('정제 미적용 또는 정제 적용 조건을 선택하세요.')
    return value


def experiment_name(value):
    if value not in EXPERIMENTS:
        raise ValueError('예측 조건을 선택하세요.')
    return value


def create_app(config=None):
    config = config or {}
    hosted_database = config.get('HOSTED_DATABASE')
    @asynccontextmanager
    async def lifespan(app):
        try:
            yield
        finally:
            close_connections()

    app = FastAPI(lifespan=lifespan, title='COM22417 Classification Studio', docs_url=None, redoc_url=None, openapi_url=None)
    secret = config.get('SECRET_KEY') or session_secret()
    app.add_middleware(SessionMiddleware, secret_key=secret, session_cookie=SESSION_COOKIE_NAME,
                       same_site='strict', https_only=config.get('SECURE_COOKIE', False))
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=config.get('ALLOWED_HOSTS', ['127.0.0.1', 'localhost', '[::1]', 'testserver']))
    # templates의 HTML을 렌더링하고 static의 CSS·JS를 브라우저에 제공합니다.
    # 경로는 이 파일 위치를 기준으로 하므로 실행한 터미널 폴더와 무관합니다.
    templates = Jinja2Templates(directory=str(Path(__file__).parent / 'templates'))
    templates.env.globals['environment_db_password'] = hosted_database is not None
    templates.env.globals['navigation'] = assignment_templates.navigation()
    templates.env.globals['assignments'] = assignment_templates.ASSIGNMENTS
    templates.env.globals['basic_points'] = assignment_templates.BASIC_POINTS
    templates.env.globals['basic_objects'] = service.BASIC
    templates.env.globals['creative_max_cases'] = assignment_templates.CREATIVE_MAX_CASES
    templates.env.globals['basic_screens'] = assignment_templates.BASIC_SCREENS
    app.mount('/static', StaticFiles(directory=Path(__file__).parent / 'static'), name='static')
    # 로컬 프로젝트는 student.env 하나를 사용합니다. 재로그인하면 이전 세션을 무효화합니다.
    login_state = {'token': None, 'credentials': None, 'expires_at': 0}
    session_lock = threading.RLock()
    session_clock = config.get('SESSION_CLOCK', time.time)
    session_timeout = int(config.get('SESSION_TIMEOUT_SECONDS', SESSION_IDLE_SECONDS))

    def database_settings():
        if hosted_database is None:
            return student_settings()
        cfg = dict(hosted_database)
        if login_state.get('db_user'):
            cfg['DB_USER'] = login_state['db_user']
        return cfg

    def session_info(request):
        return {'expires_at': getattr(request.state, 'session_expires_at', None),
                'server_time': session_clock(), 'timeout_seconds': session_timeout,
                'expired': getattr(request.state, 'session_expired', False),
                'logged_at': login_state.get('logged_at') if request.session.get('login_token') == login_state['token'] and login_state['token'] else None}


    def credential_stamp(cfg):
        raw = json.dumps([cfg.get('DB_USER', '').upper(), cfg.get('DB_PASSWORD', '')]).encode('utf-8')
        return hmac.new(secret.encode('utf-8'), raw, hashlib.sha256).hexdigest()

    def current_user(request, *, touch=False):
        with session_lock:
            person = identity.current(request.session)
            token = request.session.get('login_token')
            cfg = database_settings()
            if (person and token and login_state['token']
                    and hmac.compare_digest(token, login_state['token'])
                    and person['db_user'] == cfg.get('DB_USER', '').upper()
                    and login_state['credentials'] == credential_stamp(cfg)):
                now = session_clock()
                if now >= login_state['expires_at']:
                    request.state.session_expired = True
                    login_state.update(token=None, credentials=None)
                    close_connections()
                else:
                    if touch:
                        login_state['expires_at'] = now + session_timeout
                    request.state.session_expires_at = login_state['expires_at']
                    return person
            request.session.pop('identity', None)
            request.session.pop('login_token', None)
            return None

    @app.middleware('http')
    async def protect(request: Request, next_call):
        sql_trace.begin()
        response = await next_call(request)
        if request.url.path.startswith(('/api/data', '/api/models', '/api/predictions', '/api/status', '/api/assignments', '/api/initialize', '/api/basic/lifecycle')) and sql_trace.records():
            body = b''.join([chunk async for chunk in response.body_iterator])
            content = json.loads(body)
            content['trace'] = sql_trace.records()
            headers = dict(response.headers)
            headers.pop('content-length', None)
            response = JSONResponse(content, status_code=response.status_code, headers=headers)
        if hasattr(request.state, 'session_expires_at'):
            response.headers['X-Session-Expires-At'] = str(request.state.session_expires_at)
            response.headers['X-Session-Server-Time'] = str(session_clock())
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'same-origin'
        response.headers.setdefault('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'self'; form-action 'self'")
        if request.url.path.startswith(('/api/', '/instructor/')) or 'text/html' in response.headers.get('content-type',''):
            response.headers['Cache-Control'] = 'no-store'
        return response

    @app.exception_handler(ValueError)
    async def invalid(request, error):
        return JSONResponse({'error': str(error)}, status_code=400)

    @app.exception_handler(HTTPException)
    async def rejected(request, error):
        content = error.detail if isinstance(error.detail, dict) else {'error': error.detail}
        return JSONResponse(content, status_code=error.status_code)

    def csrf(request):
        token = request.session.setdefault('csrf', secrets.token_hex(24))
        if request.method == 'POST' and not hmac.compare_digest(request.headers.get('X-CSRF-Token', ''), token):
            raise HTTPException(403, '화면을 새로고침한 뒤 다시 실행하세요.')

    def authorized(request):
        csrf(request)
        person = current_user(request, touch=True)
        if not person:
            raise HTTPException(401, {'error': '로그인 세션이 만료되었습니다. 다시 로그인하세요.' if getattr(request.state, 'session_expired', False) else '로그인 상태가 종료되었습니다. 다시 로그인하세요.',
                                      'code': 'SESSION_TIMEOUT' if getattr(request.state, 'session_expired', False) else 'SESSION_ENDED'})
        return person

    lecture_path = ROOT / 'instructor/python-web-lecture.html'
    lecture_route = '/instructor/python-web-lecture.html'

    def lecture_url(person):
        return lecture_route if identity.is_instructor(person) and lecture_path.is_file() else None

    def lecture_document(request):
        person = authorized(request)
        if not identity.is_instructor(person):
            raise HTTPException(403, '강사 계정으로만 열 수 있는 교재입니다.')
        if not lecture_path.is_file():
            raise HTTPException(404, '이 배포본에는 강사용 교재가 없습니다.')
        return lecture_path.read_text(encoding='utf-8')

    @app.get('/instructor/python-web-lecture.html')
    def instructor_lecture(request: Request):
        document = lecture_document(request)
        # 독립 HTML의 신뢰된 스크립트 본문만 허용합니다. 서비스의 일반 CSP는 유지합니다.
        scripts = re.findall(r'<script>(.*?)</script>', document, re.S)
        hashes = ["'sha256-" + base64.b64encode(hashlib.sha256(code.encode('utf-8')).digest()).decode('ascii') + "'" for code in scripts]
        policy = "default-src 'self'; script-src " + (' '.join(hashes) or "'none'") + "; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'none'; frame-ancestors 'none'; base-uri 'self'; form-action 'none'"
        return HTMLResponse(document, headers={'Content-Security-Policy': policy})

    @app.get('/instructor/lecture-source/{key}')
    def instructor_lecture_source(request: Request, key: str):
        document = lecture_document(request)
        match = re.search(r'<script type="application/json" id="source-manifest">(.*?)</script>', document, re.S)
        snippets = json.loads(match[1]) if match else {}
        if key not in snippets:
            raise HTTPException(404, '교재에 등록된 코드 발췌를 선택하세요.')
        # HTML에 이미 포함한 고정 발췌만 반환합니다. 임의 파일·경로는 읽지 않습니다.
        return PlainTextResponse(snippets[key]['text'], headers={'Content-Security-Policy': "default-src 'none'; frame-ancestors 'none'"})

    @contextmanager
    def database(request):
        person=authorized(request)
        if not _operation.acquire(blocking=False):
            raise HTTPException(409, '다른 DB 작업이 진행 중입니다. 완료 후 다시 실행하세요.')
        connected = False
        try:
            authorized(request)
            with connection(database_settings()) as conn:
                if str(conn.username).upper()!=person['db_user'].upper():
                    raise ValueError('실제 DB 연결 계정이 발급 계정과 다릅니다. 발급 계정으로 다시 로그인하세요.')
                connected = True
                yield conn
        except ValueError as error:
            if getattr(request.state,'training_dropped',False):
                diagnostic=operation_help(error,getattr(request.state,'db_stage','테이블 재생성'),training_dropped=True)
                raise HTTPException(400,{'error':diagnostic['title'],'diagnostic':diagnostic}) from error
            raise
        except HTTPException:
            raise
        except assignment_templates.AssignmentNotReady as error:
            raise HTTPException(409, {'error': error.diagnostic['title'], 'diagnostic': error.diagnostic}) from None
        except Exception as error:
            key = getattr(request.state, 'assignment_key', None)
            disconnected = not connected or any(code in str(error) for code in ('ORA-03113','ORA-03114','ORA-03135','ORA-12170','ORA-12514','ORA-12541','DPY-1001','DPY-4011','DPY-6005'))
            if disconnected:
                diagnostic = {**connection_help(error), 'category':'connection', 'db_connected':False}
            else:
                diagnostic = assignment_templates.diagnostic(key, getattr(request.state, 'assignment_action', 'status'), error=error) if key else operation_help(error, getattr(request.state, 'db_stage', 'DB 작업'),training_dropped=getattr(request.state,'training_dropped',False))
            raise HTTPException(503, {'error': diagnostic['title'], 'diagnostic': diagnostic}) from error
        finally:
            _operation.release()

    @app.get('/healthz')
    def health():
        return {'status': 'ok'}

    def page(active, title):
        def screen(request: Request):
            return templates.TemplateResponse(request=request, name='index.html', context={
                'active': active, 'title': title, 'is_assignment': active in assignment_templates.ASSIGNMENTS,
                'is_basic': active in dict(assignment_templates.BASIC_SCREENS),
                'mission_datasets': dataset_catalog() if active=='mission' else []})
        return screen

    # 이전 주소도 같은 기본과제 작업 공간의 해당 단계로 엽니다.
    for route, active, title in [('/', 'main', '나의 실습 공간'), ('/basic', 'home', '기본과제'),
                                ('/data', 'data', '기본과제'), ('/models', 'models', '기본과제'),
                                ('/predictions', 'predictions', '기본과제')]:
        app.add_api_route(route, page(active, title), methods=['GET'], include_in_schema=False)

    # 메뉴 추가 3: 설정에 등록한 과제는 공통 화면·API를 그대로 재사용합니다.
    for key, workspace in assignment_templates.ASSIGNMENTS.items():
        app.add_api_route(workspace['route'], page(key, workspace['title']), methods=['GET'], include_in_schema=False)

    @app.get('/api/execution-script')
    def show_execution_script(request: Request, operation: str, variant: str = 'RAW', experiment: str = 'baseline'):
        authorized(request)
        return execution_script(operation, variant, experiment)

    @app.get('/download/assignment-guide.html')
    def assignment_guide(request: Request):
        authorized(request)
        name = 'COM22417_과제설명및평가.html'
        # 개발 원본은 downloads, 학생 ZIP은 루트에 같은 통합 문서를 담습니다.
        source = next((path for path in (ROOT / 'downloads' / name, ROOT / name)
                       if path.is_file() and not path.is_symlink()
                       and path.resolve().is_relative_to(ROOT.resolve())), None)
        if source is None:
            raise HTTPException(404, '과제 설명 및 평가 문서가 없습니다. 배포 파일을 확인하세요.')
        document = source.read_bytes()
        # HTML 파서는 줄바꿈을 LF로 정규화하므로 CSP 해시도 같은 본문으로 계산합니다.
        scripts = re.findall(r'<script>(.*?)</script>', document.decode('utf-8').replace('\r\n', '\n').replace('\r', '\n'), re.S)
        hashes = ["'sha256-" + base64.b64encode(hashlib.sha256(code.encode('utf-8')).digest()).decode('ascii') + "'" for code in scripts]
        policy = "default-src 'self'; script-src " + (' '.join(hashes) or "'none'") + "; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'none'; frame-ancestors 'none'; base-uri 'self'; form-action 'none'"
        return HTMLResponse(document, headers={'Content-Security-Policy': policy})

    @app.get('/download/assignment-template-guide.html')
    def assignment_template_guide():
        return FileResponse(ROOT / 'reference/student/assignment-template-guide.html', media_type='text/html')

    @app.get('/api/assignments/mission/selection')
    def get_mission_selection(request: Request):
        person=authorized(request)
        with database(request) as conn:
            return {'key': assignment_templates.mission_selection(conn,person,{item['key'] for item in dataset_catalog()})}

    @app.post('/api/assignments/mission/selection')
    def save_mission_selection(request: Request, data: dict):
        person=authorized(request)
        if not isinstance(data.get('key'),str):raise ValueError('선택할 미션을 지정하세요.')
        with database(request) as conn:
            return {'key': assignment_templates.mission_selection(conn,person,{item['key'] for item in dataset_catalog()},data['key'])}

    def selected_mission(request, key=''):
        person=authorized(request)
        catalog=dataset_catalog()
        if not key:
            with database(request) as conn:
                key=assignment_templates.mission_selection(conn,person,{item['key'] for item in catalog})
        item=next((item for item in catalog if item['key']==key),None)
        if not item:raise ValueError('현황에서 미션을 먼저 선택하세요.')
        return item

    def mission_context(request, conn, expected=None):
        value=assignment_templates.mission_selection(conn,authorized(request),{item['key'] for item in dataset_catalog()})
        if expected is not None and expected!=value:
            raise ValueError('선택 미션이 바뀌었습니다. 현황을 다시 확인하세요.')
        return value

    @app.get('/api/assignments/mission/guide')
    def mission_sql_guide(request: Request, operation: str='setup', variant: str='RAW', source_kind: str='ALL', mission: str='', trigger_id: str='', trigger_label: str='', page: str=''):
        from backend.mission_guide import generate
        return generate(selected_mission(request,mission),operation,variant,source_kind,schema=current_user(request)['db_user'],trigger_id=trigger_id,trigger_label=trigger_label,page=page)

    @app.get('/api/assignments/mission/schema')
    def mission_schema(request: Request, kind: str='training', mission: str=''):
        from backend.mission_guide import schema_guide
        return schema_guide(selected_mission(request,mission),kind,schema=current_user(request)['db_user'])

    @app.get('/api/basic/dataset/preview')
    def basic_dataset_preview(kind: str='training', split: str='all', page: int=1):
        from backend.basic_dataset import preview
        return preview(kind,split,page)

    @app.get('/api/basic/dataset/schema')
    def basic_dataset_schema(request: Request, kind: str='training'):
        from backend.basic_dataset import table_schema
        person=authorized(request)
        return table_schema(kind,person['db_user'])

    @app.get('/api/assignments/mission/guide/download')
    def mission_sql_download(request: Request, file: str, mission: str=''):
        from backend.mission_guide import table_sql,procedure_sql
        item=selected_mission(request,mission)
        if file=='tables':
            sql='\n\n'.join(table_sql(item,kind,schema=current_user(request)['db_user'])['sql'] for kind in ('training','prepared','prediction'))
            filename='01_tables.sql'
        elif file=='procedure':
            sql=procedure_sql(item,schema=current_user(request)['db_user']);filename='02_procedure.sql'
        else:raise ValueError('테이블 또는 프로시저 SQL을 선택하세요.')
        return PlainTextResponse(sql,headers={'Content-Disposition':'attachment; filename="'+filename+'"'})

    def practice_summary(request, conn, key, state=None):
        person = authorized(request)
        mission = None
        if key == 'mission':
            catalog = dataset_catalog()
            selected = assignment_templates.mission_selection(conn,person,{item['key'] for item in catalog})
            mission = next((item for item in catalog if item['key']==selected),None)
        from backend.practice_evidence import collect
        result = collect(conn,key,mission,state)
        return {**result,'student':{'student_id':person['student_id'],'name':person['name'],'db_user':person['db_user']},
                'title':{'basic':'기본과제','mission':'미션과제','creative':'창의과제'}[key],
                'mission_title':(mission or {}).get('title','미션 선택 전' if key=='mission' else '')}

    @app.get('/api/practice/{key}/evidence')
    def practice_evidence_status(request: Request, key: str):
        authorized(request)
        if key not in ('basic','mission','creative'):raise HTTPException(404,'과제를 확인하세요.')
        with database(request) as conn:
            return practice_summary(request,conn,key)

    @app.get('/api/assignments/{key}/schema')
    def assignment_table_schema(request: Request, key: str, kind: str='training'):
        assignment_templates.assignment(key)
        request.state.assignment_key=key
        with database(request) as conn:
            return assignment_templates.table_schema(conn,key,kind)

    @app.post('/api/assignments/{key}/link')
    def link_assignment(request: Request, key: str, data: dict):
        assignment_templates.assignment(key)
        request.state.assignment_key=key
        request.state.assignment_action='status'
        with database(request) as conn:
            mission=mission_context(request,conn,data.get('mission','')) if key=='mission' else None
            return assignment_templates.link_external(conn,key,mission=mission)

    @app.post('/api/assignments/{key}/connection')
    def assignment_connection(request: Request, key: str, data: dict):
        authorized(request)
        assignment_templates.save_config(current_user(request)['db_user'], key, data)
        return {'message':'과제별 고정 연결 이름을 확인했습니다. 실제 DB 객체를 연결 확인으로 조회하세요.'}

    @app.post('/api/assignments/{key}/{action}')
    def assignment_action(request: Request, key: str, action: str, data: dict):
        authorized(request)
        assignment_templates.assignment(key)
        if action not in ('prepared-data','data','prediction-data','predict','evaluate'):
            raise HTTPException(403,'미션·창의과제는 SQL Developer에서 직접 생성·적재·전처리·학습한 뒤 화면에 연계하세요.')
        request.state.assignment_key = key
        request.state.assignment_action = action
        request.state.db_stage = assignment_templates.assignment(key)['title'] + ' · ' + action
        with database(request) as conn:
            mission=mission_context(request,conn,data.get('mission','') if action in ('evaluate','predict') else None) if key=='mission' else ''
            return assignment_templates.run(conn, key, action, mode=data.get('variant','RAW'), source_kind=data.get('source_kind','ALL'), mission_key=mission)

    @app.get('/api/assignments/{key}/status')
    def assignment_status(request: Request, key: str, include_evidence: bool=False):
        assignment_templates.assignment(key)
        request.state.assignment_key = key
        request.state.assignment_action = 'status'
        with database(request) as conn:
            state = assignment_templates.readiness(conn, key,mission=mission_context(request,conn) if key=='mission' else None)
            state.update(assignment_templates.input_state(conn,state))
            pending = next((action for action,item in state['actions'].items() if not item['ready']), None)
            result = {**state, **assignment_templates.verification_state(conn,key,state), 'diagnostic': assignment_templates.diagnostic(key, pending, state) if pending else None}
            if include_evidence:result['practice']=practice_summary(request,conn,key,result)
            return result

    @app.post('/api/assignments/{key}/script/{action}')
    def assignment_execution(request: Request, key: str, action: str, file: UploadFile | None = File(None)):
        authorized(request)
        if key=='creative':raise HTTPException(404,'창의과제는 안내 쿼리를 제공하지 않습니다. 직접 작성한 SQL을 적용하세요.')
        if key=='mission':
            from backend.mission_guide import generate
            return generate(selected_mission(request),action,schema=current_user(request)['db_user'])
        raise ValueError('미션 또는 창의과제를 선택하세요.')

    def import_assignment_csv(request, key, action, raw, mission):
        """업로드 전체 검사를 마친 후 한 번 대여한 DB 연결로 묶음 적재합니다."""
        person=authorized(request)
        if len(raw)>2*1024*1024:raise ValueError('CSV는 2 MiB 이하로 선택하세요.')
        prediction=action=='prediction-import'
        if key=='mission':
            item=next((item for item in dataset_catalog() if item['key']==mission),None)
            if not item:raise ValueError('선택 미션을 확인하고 파일을 다시 선택하세요.')
            from backend.csv_import import mission_rows
            try:
                values=list(mission_rows(io.StringIO(raw.decode('utf-8-sig'),newline=''),item,prediction))
            except UnicodeError:raise ValueError('UTF-8 CSV 파일을 선택하세요.') from None
        else:
            values,_=assignment_templates.csv_payload(raw,encoded=False)
        request.state.assignment_key=key
        request.state.assignment_action=action
        request.state.db_stage=assignment_templates.assignment(key)['title']+' · CSV 적재'
        with database(request) as conn:
            if key=='mission' and assignment_templates.mission_selection(conn,person,{item['key'] for item in dataset_catalog()})!=mission:
                raise ValueError('선택 미션이 바뀌었습니다. 파일을 다시 선택하세요.')
            return assignment_templates.import_csv(conn,key,values,person['db_user'],prediction=prediction,mission=item if key=='mission' else None)

    @app.post('/api/assignments/{key}/{action}/csv')
    async def assignment_csv(request: Request, key: str, action: str, file: UploadFile = File(...), variant: str = Form('RAW'), mission: str = Form('')):
        authorized(request)
        assignment_templates.assignment(key)
        if action not in ('import','prediction-import'):
            raise HTTPException(403,'학습 또는 예측 CSV 적재만 허용합니다.')
        try:
            raw=await file.read(2*1024*1024+1)
            return await run_in_threadpool(import_assignment_csv,request,key,action,raw,mission)
        finally:
            await file.close()

    @app.get('/api/session')
    def get_session(request: Request):
        csrf(request)
        person = current_user(request)
        return {'csrf': request.session['csrf'], 'identity': person, 'configured': bool(identity.roster()),
                'instructor_lecture_url': lecture_url(person), 'session': session_info(request)}

    @app.post('/api/session/extend')
    def extend_session(request: Request):
        authorized(request)
        return {'session': session_info(request)}

    @app.post('/api/identity/lookup')
    def lookup_identity(request: Request, data: dict):
        csrf(request)
        person = identity.confirm(data.get('student_id', ''), data.get('name', ''))
        return {'identity': person}

    def login_values(data):
        person = identity.confirm(data.get('student_id', ''), data.get('name', ''))
        cfg = database_settings()
        password = cfg.get('DB_PASSWORD') if hosted_database is not None else data.get('db_password')
        if not isinstance(password, str) or not password:
            raise ValueError('Render 환경변수 DB_PASSWORD를 설정하세요.' if hosted_database is not None
                             else '발급받은 DB 비밀번호를 입력하세요.')
        if hosted_database is not None:
            supplied = data.get('db_password')
            if not isinstance(supplied, str) or not supplied:
                raise ValueError('발급받은 DB 비밀번호를 입력하세요.')
            if not hmac.compare_digest(supplied.encode('utf-8'), password.encode('utf-8')):
                raise ValueError('DB 비밀번호가 일치하지 않습니다.')
        cfg.update(DB_USER=person['db_user'], DB_PASSWORD=password)
        return person, cfg

    def connection_failure(error):
        diagnostic = connection_help(error)
        return JSONResponse({'error': diagnostic['title'], 'diagnostic': diagnostic}, status_code=503)

    def verify_connection(cfg, *, details=False, person=None):
        with connection(cfg, pooled=False) as conn:
            if details:return connection_profile.inspect_connection(conn,cfg)
            conn.ping()
            if person is not None:
                from backend import progress_store
                progress_store.initialize(conn)
                progress_store.migrate(conn,person)

    @app.post('/api/identity/test')
    def test_connection(request: Request, data: dict):
        csrf(request)
        person, cfg = login_values(data)
        if not _operation.acquire(blocking=False):
            raise HTTPException(409, 'DB 작업이 진행 중입니다. 완료 후 테스트하세요.')
        try:
            profile=verify_connection(cfg,details=True)
            return {'success': True, 'code': 'CONNECTED', 'title': 'DB 연결 성공',
                    'db_user': person['db_user'], 'connection': profile,
                    'steps': ['발급된 DB 계정의 인증에 성공했습니다.', 'Oracle DB의 응답을 확인했습니다.'],
                    'message': '환경의 DB 연결 확인을 마쳤습니다. 로그인 버튼을 눌러 작업을 시작하세요.'}
        except Exception as error:
            return connection_failure(error)
        finally:
            _operation.release()

    @app.post('/api/identity')
    def set_identity(request: Request, data: dict):
        csrf(request)
        person, cfg = login_values(data)
        if not _operation.acquire(blocking=False):
            raise HTTPException(409, 'DB 작업이 진행 중입니다. 완료 후 로그인하세요.')
        try:
            # 비밀번호가 맞는지 Oracle에서 먼저 확인합니다. 실패하면 기존 파일을 보존합니다.
            try:
                verify_connection(cfg,person=person)
            except Exception as error:
                return connection_failure(error)
            if hosted_database is None:
                save_credentials(person['db_user'], cfg['DB_PASSWORD'])
            close_connections()
            with session_lock:
                login_state.update(token=secrets.token_hex(32), credentials=credential_stamp(cfg), db_user=person['db_user'],
                                   expires_at=session_clock() + session_timeout, logged_at=session_clock())
                request.state.session_expires_at = login_state['expires_at']
            request.session.clear()
            request.session.update(identity={'student_id': person['student_id'], 'name': person['name']},
                                   login_token=login_state['token'], csrf=secrets.token_hex(24))
            return {'identity': person, 'csrf': request.session['csrf'], 'instructor_lecture_url': lecture_url(person),
                    'session': session_info(request)}
        except ValueError:
            raise
        except OSError:
            raise HTTPException(503, 'student.env를 저장할 수 없습니다. 프로젝트 폴더의 쓰기 권한을 확인하세요.') from None
        except Exception as error:
            raise HTTPException(503, safe_error(error)) from None
        finally:
            _operation.release()

    @app.post('/api/logout')
    def logout(request: Request):
        csrf(request)
        if request.session.get('login_token') == login_state['token']:
            login_state.update(token=None, credentials=None)
            close_connections()
        request.session.clear()
        return {'message': '로그아웃되었습니다.'}

    @app.get('/api/account/connection')
    def account_connection(request: Request):
        person=authorized(request)
        with database(request) as conn:
            profile=connection_profile.inspect_connection(conn,database_settings())
        return {'identity':person, 'connection':profile, 'session':session_info(request)}

    @app.get('/api/status')
    def status(request: Request, include_evidence: bool=False):
        with database(request) as conn:
            result=service.status(conn)
            if include_evidence:result['practice']=practice_summary(request,conn,'basic',result)
            return result

    @app.post('/api/initialize')
    def initialize_basic(request: Request):
        with database(request) as conn:
            initialize(conn)
            return {'message': '테이블 3개와 프로시저 1개를 준비했습니다.', **service.status(conn)}

    @app.post('/api/basic/lifecycle')
    def basic_lifecycle_action(request: Request, data: dict):
        from backend.basic_lifecycle import apply
        person=authorized(request)
        action=data.get('action','')
        with database(request) as conn:
            request.state.db_stage='기본과제 · '+action
            message=apply(conn,action,person['db_user'],variant_name(data.get('variant','RAW')))
            return {'message':message,**service.status(conn)}

    @app.get('/api/coding-help')
    def coding_help(request: Request, operation: str = 'data', variant: str = 'RAW', use_yn: str = 'ALL', split: str = 'ALL', assignment: str = 'basic', source_kind: str = 'ALL', trigger_id: str = '', trigger_label: str = '', page: str = '', mission: str = ''):
        authorized(request)
        if assignment=='creative':
            from backend.mission_guide import creative_manual
            result=creative_manual(operation,variant,schema=current_user(request)['db_user'],trigger_id=trigger_id,trigger_label=trigger_label,page=page)
        elif assignment=='mission':
            from backend.mission_guide import generate
            result=generate(selected_mission(request,mission),operation,variant,source_kind,schema=current_user(request)['db_user'],trigger_id=trigger_id,trigger_label=trigger_label,page=page)
        else:
            from backend.coding_help import describe
            result=describe(operation, variant=variant, use_yn=use_yn, split=split, assignment=assignment, source_kind=source_kind, user=current_user(request)['db_user'], trigger_id=trigger_id, trigger_label=trigger_label, page=page)
        # 파일 원문은 flow.files에서 한 번만 보냅니다. 이전 조각/전체 원문 응답을 중복 직렬화하지 않습니다.
        return {key:result[key] for key in ('title','operation','assignment','schema','variant','mission_key','flow','application','notice','find') if key in result}

    @app.get('/api/sources/{key}')
    def source_file(request: Request, key: str):
        authorized(request)
        try:
            return read_source(key)
        except (KeyError, OSError):
            raise HTTPException(404, '공개 허용된 소스 파일만 확인할 수 있습니다.') from None

    @app.get('/api/data')
    def data(request: Request, use_yn: str = 'ALL', split: str = 'ALL'):
        use_yn, split = use_yn.upper(), split.upper()
        if use_yn not in ('ALL','Y','N') or split not in ('ALL','TRAIN','TEST'):
            raise ValueError('사용 여부와 TRAIN/TEST 필터를 확인하세요.')
        with database(request) as conn:
            return {'rows': service.get_data(conn, use_yn, split)}

    @app.post('/api/data/prepare')
    def prepare_data(request: Request, data: dict):
        with database(request) as conn:
            result=service.prepare_model_data(conn,data.get('variant','RAW'))
            return {'rows':result,'message':'선택 방식의 전처리 결과를 저장했습니다. FIT_YN과 값을 확인한 뒤 학습하세요.',**service.status(conn)}

    @app.get('/api/data/prepared')
    def prepared_data(request: Request, variant: str = 'RAW', source_kind: str = 'ALL'):
        with database(request) as conn:
            return {'rows':service.get_prepared_data(conn,variant,source_kind)}

    @app.post('/api/data/preview')
    def preview(request: Request, file: UploadFile = File(...)):
        authorized(request)
        values = parse_csv(file.file.read(2 * 1024 * 1024 + 1))
        return {'rows': values[:100], 'summary': quality(values)}

    @app.post('/api/data/import')
    def import_data(request: Request, file: UploadFile = File(...), mode: str = Form('replace')):
        authorized(request)
        if mode not in ('initial', 'replace', 'recreate'):
            raise ValueError('데이터 교체 또는 테이블 재생성을 선택하세요.')
        # CSV 검증이 끝난 뒤에만 DB를 변경합니다. 임의 테이블명·SQL은 받지 않습니다.
        values = parse_csv(file.file.read(2 * 1024 * 1024 + 1))
        with database(request) as conn:
            existed = any(item['object_name'] == 'OML_BASIC_DATA' for item in query(conn, 'objects.sql', **service.BASIC))
            if mode == 'initial':
                if not existed or not ready(conn):raise ValueError('현황에서 테이블 생성과 프로시저 등록을 먼저 진행하세요.')
                if query(conn,'training_count.sql')[0]['total_rows']:
                    raise ValueError('원본 데이터가 있습니다. CSV 교체 적재 또는 데이터 비우기를 사용하세요.')
            if mode == 'recreate':
                request.state.db_stage = '테이블 재생성 · 원본 삭제 전'
                execute_file(conn, 'recreate_training.sql')
                request.state.training_dropped = True
                request.state.db_stage = '테이블 재생성 · 원본 삭제 완료 · 새 정의 적용'
                service.invalidate_training_state(conn)
                initialize(conn)
            else:
                request.state.db_stage = '테이블 준비 · SQL 컴파일'
                ensure_initialized(conn)
            request.state.db_stage = '테이블 재생성 · CSV 적재' if mode == 'recreate' else 'CSV 데이터 교체 적재'
            service.load_csv(conn, values, initial=mode=='initial')
            request.state.db_stage = '적재 완료 · 테이블 상태 조회'
            operation = 'recreated' if mode == 'recreate' else 'replaced' if existed else 'created'
            return {'operation': operation, 'loaded_rows': len(values), 'summary': quality(values), **service.status(conn)}

    @app.get('/api/models')
    def models(request: Request):
        with database(request) as conn:
            return service.model_results(conn)

    @app.get('/api/models/dictionary')
    def models_dictionary(request: Request, variant: str = 'RAW'):
        from backend.model_dictionary import read
        with database(request) as conn:
            request.state.db_stage = '기본과제 · Oracle 모델 딕셔너리 조회'
            return read(conn, variant_name(variant))

    @app.post('/api/models/train')
    def train(request: Request, data: dict):
        # 알고리즘·학습 입력·전처리는 Python이 아닌 OML_BASIC_RUN 프로시저에서 수정합니다.
        action=data.get('action','TRAIN')
        if action not in ('TRAIN','INIT','RETRAIN','ADD_TRAIN'):raise ValueError('학습 종류를 확인하세요.')
        label={'TRAIN':'모델 생성·재생성','INIT':'최초 학습','RETRAIN':'전체 재학습','ADD_TRAIN':'DB 추가 데이터 반영'}[action]
        with database(request) as conn:
            request.state.db_stage = '기본과제 · ' + ('정제 적용' if data.get('variant') == 'CLEAN' else '정제 미적용') + ' '+label
            service.train_model(conn, variant_name(data.get('variant', '')),action)
            return {'message':label+'이 완료되었습니다.', **service.status(conn)}

    @app.post('/api/models/delete')
    def delete_model(request: Request, data: dict):
        with database(request) as conn:
            request.state.db_stage='기본과제 · 선택 모델 삭제'
            result=service.delete_model(conn,variant_name(data.get('variant','')))
            return {'message':'선택 모델을 삭제했습니다. 학습·TEST·예측 데이터는 유지됩니다.','rows':result,**service.status(conn)}

    @app.post('/api/models/confirm')
    def confirm_model(request: Request, data: dict):
        with database(request) as conn:
            request.state.db_stage = '기본과제 · 모델 확정'
            service.confirm_model(conn, variant_name(data.get('variant', '')))
            return {'message': '예측에 사용할 모델을 확정했습니다.', **service.status(conn)}

    @app.post('/api/predictions/preview')
    def preview_predictions(request: Request, file: UploadFile = File(...)):
        authorized(request)
        values = parse_csv(file.file.read(2 * 1024 * 1024 + 1), prediction=True)
        return {'rows': values[:100], 'summary': quality(values, prediction=True)}

    @app.get('/api/predictions/data')
    def prediction_data(request: Request):
        with database(request) as conn:
            return {'rows': query(conn, 'prediction_rows.sql')}

    @app.post('/api/predictions/import')
    def import_predictions(request: Request, file: UploadFile = File(...), mode: str = Form('replace')):
        authorized(request)
        if mode not in ('initial','replace'):raise ValueError('최초 적재 또는 교체 적재를 선택하세요.')
        values = parse_csv(file.file.read(2 * 1024 * 1024 + 1), prediction=True)
        with database(request) as conn:
            if mode=='initial' and not ready(conn):raise ValueError('현황에서 테이블 생성과 프로시저 등록을 먼저 진행하세요.')
            if mode=='initial' and query(conn,'prediction_storage.sql')[0]['row_count']:
                raise ValueError('예측 입력이 있습니다. CSV 교체 적재 또는 입력 비우기를 사용하세요.')
            request.state.db_stage = '예측 테이블 준비 · SQL 확인'
            ensure_initialized(conn)
            request.state.db_stage = '예측 CSV 교체 적재'
            service.load_csv(conn, values, prediction=True, initial=mode=='initial')
            request.state.db_stage = '적재 완료 · 예측 테이블 상태 조회'
            return {'message': f'예측 데이터 {len(values)}행을 적재했습니다.',
                    'loaded_rows': len(values), **service.status(conn)}

    @app.get('/api/predictions/columns')
    def columns(request: Request, experiment: str = 'baseline'):
        with database(request) as conn:
            return {'columns': query(conn, 'columns.sql', table_name='OML_BASIC_PREDICT')}

    @app.post('/api/predictions/run')
    def predict(request: Request, data: dict):
        # 사용자에게 임의 SQL을 받지 않습니다. 고정한 실험 종류만 DB로 전달합니다.
        authorized(request)
        experiment = experiment_name(data.get('experiment', 'baseline'))
        mode=variant_name(data['variant']) if 'variant' in data else None
        with database(request) as conn:
            request.state.db_stage = '기본과제 · 예측 실행'
            rows=service.predictions(conn,mode)
            verified=bool(service.read_state(conn).get('practice_evidence',{}).get('basic',{}).get('predict'))
            return {'rows':rows, 'verified':verified, **service.prediction_context(conn,mode),
                    'columns': query(conn, 'columns.sql', table_name='OML_BASIC_PREDICT'), 'experiment': 'baseline'}

    def dataset_catalog():
        return json.loads((ROOT / 'data/catalog.json').read_text(encoding='utf-8'))

    def dataset_source(key, kind):
        # 배포 카탈로그의 합성 CSV만 읽습니다. DB 연결·사용자 파일 경로는 받지 않습니다.
        if kind not in ('training', 'prediction'):
            raise HTTPException(404, 'CSV 종류를 확인하세요.')
        item = next((item for item in dataset_catalog() if item['key'] == key), None)
        if not item:
            raise HTTPException(404, '미션 데이터를 찾을 수 없습니다.')
        name = item['filename'] if kind == 'training' else item['prediction_filename']
        folder = ROOT / 'data/examples'
        source = folder / name
        if Path(name).name != name or source.is_symlink() or source.resolve().parent != folder.resolve() or not source.is_file():
            raise HTTPException(404, 'CSV 파일을 찾을 수 없습니다.')
        return item, source

    @app.get('/api/datasets/{key}/preview')
    def dataset_preview(key: str, kind: str = 'training', split: str = 'all', page: int = 1):
        item, source = dataset_source(key, kind)
        if split not in ('all', 'TRAIN', 'TEST') or (kind == 'prediction' and split != 'all') or page < 1:
            raise HTTPException(400, '조회 구분과 페이지를 확인하세요.')
        # 숫자 변환·공백 제거·결측 보정 없이 CSV의 문자열을 그대로 표시합니다.
        with source.open(encoding='utf-8-sig', newline='') as stream:
            reader = csv.DictReader(stream)
            columns = reader.fieldnames or []
            rows = list(reader)
        original_total = len(rows)
        if split != 'all':
            rows = [row for row in rows if row.get('split') == split]
        page_size = 50
        pages = max(1, (len(rows) + page_size - 1) // page_size)
        if page > pages:
            raise HTTPException(400, '조회할 페이지 범위를 확인하세요.')
        start = (page - 1) * page_size
        return {'key': item['key'], 'kind': kind, 'filename': source.name, 'columns': columns,
                'rows': rows[start:start + page_size], 'total': len(rows), 'original_total': original_total,
                'page': page, 'pages': pages, 'page_size': page_size, 'split': split}

    @app.get('/api/datasets')
    def datasets():
        return {'datasets': dataset_catalog()}

    @app.get('/download/sample.csv')
    def sample_file():
        return FileResponse(ROOT / 'data/classification.csv', filename='classification.csv')

    @app.get('/download/prediction.csv')
    def prediction_file():
        return FileResponse(ROOT / 'data/prediction.csv', filename='prediction.csv')

    @app.get('/download/stock-source.json')
    def stock_source_file():
        return FileResponse(ROOT / 'data/stock-source.json', filename='stock-source.json', media_type='application/json')

    @app.get('/download/datasets/{key}')
    def dataset_file(key: str, kind: str = 'training'):
        _, source = dataset_source(key, kind)
        return FileResponse(source, filename=source.name)

    return app


if __name__ == '__main__':
    # VS Code에서 이 파일을 실행하거나 터미널에서 python app.py로 시작합니다.
    from manage import main
    main(create_app)
