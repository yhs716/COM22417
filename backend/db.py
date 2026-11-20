"""작업마다 연결을 대여·반환합니다. 단일 계정의 작은 풀만 유지합니다."""
from __future__ import annotations
import os
import atexit
import hashlib
import json
import re
import threading
import tempfile
import zipfile
from pathlib import Path
from contextlib import contextmanager
import oracledb
from dotenv import dotenv_values
from dotenv import set_key

ROOT = Path(__file__).resolve().parents[1]
_init_lock = threading.Lock()
_driver_ready = False
_pool_lock = threading.RLock()
_pool_entry = None
_wallet_stamp = None


def save_credentials(username, password):
    """로그인에 성공한 계정·비밀번호만 student.env에 원자적으로 반영합니다."""
    target = ROOT / 'security/student.env'
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix='.login-', suffix='.env', dir=target.parent)
    os.close(descriptor)
    temporary = Path(name)
    try:
        # Wallet·DSN·Client 등 기존 설정은 그대로 둡니다.
        temporary.write_bytes(target.read_bytes() if target.is_file() else b'')
        if not target.is_file():
            for key, value in student_settings().items():
                set_key(str(temporary), key, value, quote_mode='always')
        set_key(str(temporary), 'DB_USER', username, quote_mode='always')
        set_key(str(temporary), 'DB_PASSWORD', password, quote_mode='always')
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)

def settings(env_file=None):
    relative = env_file if env_file is not None else os.environ.get('OML_ENV_FILE', 'security/student.env')
    path = Path(relative)
    if not path.is_absolute():
        path = ROOT / path
    # 로컬 환경파일에 입력한 값이 우선입니다. 다른 터미널의 DB 환경변수가 덮어쓰지 않습니다.
    if path.is_file():
        return {k: v or '' for k, v in dotenv_values(path, interpolate=False).items()}
    # 환경파일을 배치하지 않는 클라우드 실행에서만 플랫폼 환경변수를 사용합니다.
    keys = ('DB_USER', 'DB_PASSWORD', 'DB_DSN', 'WALLET_PASSWORD', 'WALLET_ZIP', 'WALLET_DIR', 'ORACLE_CLIENT_LIB')
    return {key: os.environ[key] for key in keys if key in os.environ}


def student_settings():
    """웹 로그인과 작업은 항상 같은 student.env를 사용합니다."""
    return settings(ROOT / 'security/student.env')

def wallet_directory(cfg):
    if cfg.get('WALLET_DIR'):
        target = Path(cfg['WALLET_DIR'])
        if not target.is_absolute(): target = ROOT / target
        if cfg.get('ORACLE_CLIENT_LIB'):
            raise ValueError('WALLET_DIR 방식은 Thin 연결용입니다. ORACLE_CLIENT_LIB를 비우세요.')
        if not all((target / name).is_file() for name in ('tnsnames.ora', 'ewallet.pem')):
            raise ValueError('Thin Wallet 폴더에 tnsnames.ora와 ewallet.pem이 필요합니다.')
        return target
    archive = ROOT / cfg.get('WALLET_ZIP', 'security/Wallet_PCUORA.zip')
    if not archive.is_file():
        raise ValueError('security/Wallet_PCUORA.zip 파일이 없습니다. 강사에게 제공받은 Wallet을 확인하세요.')
    target = ROOT / 'runtime' / 'wallet'
    target.mkdir(parents=True, exist_ok=True)
    # Only the four Oracle files needed by our driver are extracted. Never extract arbitrary paths.
    with zipfile.ZipFile(archive) as source:
        for name in ('tnsnames.ora', 'ewallet.pem', 'cwallet.sso', 'sqlnet.ora'):
            data = source.read(name)
            if name == 'tnsnames.ora':
                text = data.decode('utf-8')
                text = re.sub(r'(?i)(retry_count\s*=\s*)\d+', r'\g<1>0', text)
                text = re.sub(r'(?i)(retry_delay\s*=\s*)\d+', r'\g<1>0', text)
                text = re.sub(r'(?i)\(description\s*=', '(description=(connect_timeout=12)(transport_connect_timeout=5)', text)
                data = text.encode('utf-8')
            path = target / name
            if not path.exists() or path.read_bytes() != data:
                path.write_bytes(data)
    # Thick mode must use this project's wallet rather than the path embedded in its original sqlnet.ora.
    (target / 'sqlnet.ora').write_text(
        'WALLET_LOCATION=(SOURCE=(METHOD=file)(METHOD_DATA=(DIRECTORY="' +
        target.as_posix() + '")))\nSSL_SERVER_DN_MATCH=yes\n', encoding='utf-8')
    return target

def connection_args(cfg):
    """Wallet은 변경 때만 준비하며 로그인 확인과 풀이 동일한 접속 설정을 사용합니다."""
    global _driver_ready, _wallet_stamp
    if not cfg.get('DB_USER') or not cfg.get('DB_PASSWORD'):
        raise ValueError('DB 인증정보가 없습니다. 환경 설정 가이드에 따라 security/student.env를 작성하세요.')
    with _init_lock:
        location = Path(cfg.get('WALLET_DIR') or cfg.get('WALLET_ZIP', 'security/Wallet_PCUORA.zip'))
        if not location.is_absolute(): location = ROOT / location
        files = [location / name for name in ('tnsnames.ora', 'ewallet.pem')] if cfg.get('WALLET_DIR') else [location]
        stamp = (str(location), cfg.get('ORACLE_CLIENT_LIB'), tuple((f.stat().st_mtime_ns, f.stat().st_size) for f in files))
        if _wallet_stamp is None or _wallet_stamp[0] != stamp or not _wallet_stamp[1].is_dir():
            _wallet_stamp = (stamp, wallet_directory(cfg))
        wallet = _wallet_stamp[1]
        if cfg.get('ORACLE_CLIENT_LIB') and not _driver_ready:
            client = Path(cfg['ORACLE_CLIENT_LIB'])
            if not client.is_absolute(): client = ROOT / client
            oracledb.init_oracle_client(lib_dir=str(client), config_dir=str(wallet))
        _driver_ready = True
    args = dict(user=cfg['DB_USER'], password=cfg['DB_PASSWORD'], dsn=cfg.get('DB_DSN', 'pcuora_low'))
    if oracledb.is_thin_mode():
        if not cfg.get('WALLET_PASSWORD'):
            raise ValueError('Thin 연결에는 Wallet 다운로드 당시의 비밀번호가 필요합니다. WALLET_PASSWORD를 입력하세요.')
        args.update(config_dir=str(wallet), wallet_location=str(wallet),
                    wallet_password=cfg['WALLET_PASSWORD'], tcp_connect_timeout=12, retry_count=0)
    return args


def initialize_session(conn, requested_tag=None):
    """물리 연결이 처음 만들어질 때만 적용합니다. 대여할 때마다 ALTER하지 않습니다."""
    conn.call_timeout = 120000
    from .sql_files import execute_file
    execute_file(conn, 'session.sql')


def close_connections():
    """로그아웃·계정 전환·종료: 사용 중 작업은 반환 시 닫고 유휴 풀은 즉시 닫습니다."""
    global _pool_entry
    with _pool_lock:
        entry, _pool_entry = _pool_entry, None
        if entry:
            entry['retired'] = True
            if not entry['users']:
                entry['pool'].close()


@contextmanager
def connection(config=None, *, pooled=True):
    """로그인 검증은 새 연결, 업무는 최대 1개 물리 연결을 재사용합니다."""
    global _pool_entry
    cfg = settings() if config is None else config
    # 직접 입력한 비밀번호는 이미 인증된 풀로 검사하지 않습니다.
    if not pooled:
        with oracledb.connect(**connection_args(cfg)) as conn:
            initialize_session(conn)
            yield conn
        return
    # 키는 메모리 안의 비공개 해시입니다. 비밀번호·키는 응답/로그에 내보내지 않습니다.
    key = hashlib.sha256(json.dumps(cfg, sort_keys=True).encode()).digest()
    with _pool_lock:
        if _pool_entry and _pool_entry['key'] != key:
            if _pool_entry['users']:
                raise ValueError('이전 DB 작업이 끝난 뒤 계정을 변경하세요.')
            close_connections()
        if _pool_entry is None:
            pool = oracledb.create_pool(**connection_args(cfg),
                min=0, max=1, increment=1, timeout=60, max_lifetime_session=1800,
                getmode=oracledb.POOL_GETMODE_TIMEDWAIT, wait_timeout=5000,
                ping_interval=60, ping_timeout=3000, stmtcachesize=30,
                session_callback=initialize_session)
            _pool_entry = dict(key=key, pool=pool, users=0, retired=False)
        entry = _pool_entry
        entry['users'] += 1
    try:
        # close()는 미커밋 작업을 롤백하고 풀에 반환합니다. COMMIT은 서비스만 결정합니다.
        with entry['pool'].acquire() as conn:
            conn.autocommit = False
            conn.call_timeout = 120000
            yield conn
    finally:
        with _pool_lock:
            entry['users'] -= 1
            if entry['retired'] and not entry['users']:
                entry['pool'].close()


atexit.register(close_connections)


def rows(cursor):
    names = [c[0].lower() for c in cursor.description or []]
    def clean(value):
        if isinstance(value, oracledb.LOB):
            return value.read()
        if hasattr(value, 'isoformat'):
            return value.isoformat()
        return value
    return [dict(zip(names, map(clean, row))) for row in cursor]

def safe_error(error):
    """Return actionable errors without DSNs, passwords, paths, or stack traces."""
    if isinstance(error, ValueError):
        return str(error)
    import re
    text = str(error)
    code = re.search(r'(ORA-\d{5}|DPY-\d{4}|DPI-\d{4})', text)
    code = code.group(0) if code else 'DB-CONNECTION'
    hints = {
        'ORA-01017': 'DB 사용자명과 비밀번호를 확인하세요.',
        'ORA-01031': '실습 객체 생성 권한이 부족합니다. 권한 가이드를 확인하세요.',
        'ORA-28000': '계정이 잠겨 있습니다. 강사에게 계정 상태 확인을 요청하세요.',
        'ORA-00942': '초기 테이블이 없습니다. db-init 스크립트를 먼저 실행하세요.',
        'ORA-06550': '프로시저가 없거나 유효하지 않습니다. db-init의 파일·줄 번호를 확인하세요.',
        'ORA-04063': '프로시저 컴파일 오류가 있습니다. db-init을 실행해 진단하세요.',
        'ORA-20001': '정제 미적용 또는 정제 적용 조건을 선택하세요.',
        'ORA-20002': '지원하는 예측 입력 구성을 선택하세요.',
        'ORA-20003': '입력 JSON 배열을 확인하세요.',
        'ORA-20004': '행 수와 중복 없는 양의 정수 CASE_ID를 확인하세요.',
        'ORA-20005': '삭제할 데이터가 없습니다.',
        'ORA-20006': 'TRAIN에 유효한 BUY/SELL 두 종류와 4행 이상이 필요합니다.',
        'ORA-20007': '학습 중 데이터가 변경되었습니다. 다시 생성하세요.',
        'ORA-20008': '현재 데이터로 모델을 먼저 생성하세요.',
        'ORA-20009': '현재 데이터로 학습한 모델을 먼저 확정하세요.',
        'ORA-20010': '이전 학습 테이블과 새 학습 테이블이 함께 있습니다. 데이터를 확인하고 하나로 정리하세요.',
        'ORA-20011': '사용 여부 Y/N과 구분 TRAIN/TEST를 확인하세요.',
        'ORA-20012': '주식 CSV의 WEEK_ENDING 날짜를 확인하세요. TRAIN 마지막 날짜 + 7일보다 TEST 시작일이 뒤여야 합니다. 경계 주는 USE_YN=N으로 제외하세요.',
        'ORA-01722': '숫자 입력 속성을 변환할 수 없습니다. 입력 컬럼 타입과 값을 확인하세요.',
        'ORA-12545': 'DB 네트워크와 Wallet의 접속 주소를 확인하세요.',
        'DPY-6005': 'DB에 연결할 수 없습니다. 네트워크·Wallet·서비스명을 확인하세요.',
        'DPI-1047': 'Oracle Client 경로/64비트를 확인하거나 Thin 연결로 설정하세요.',
    }
    return code + ': ' + hints.get(code, 'Oracle 접속·권한·Wallet 설정을 확인하세요. CLI 진단에서 오류 코드를 확인할 수 있습니다.')
