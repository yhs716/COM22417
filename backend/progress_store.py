"""계정별 공유 검증 기록. 저장은 호출자의 실습 COMMIT과 분리합니다."""
import hashlib
import json
from pathlib import Path
import re
import oracledb
from .db import ROOT, rows
from .sql_files import read_sql, identifier
from . import sql_trace

TABLE = 'OML_WEB_STATE'
PRACTICE = 'practice-v1'
MAX_BYTES = 131072


class Snapshot(dict):
    def __init__(self, data, key, revision, owner):
        super().__init__(data)
        self.key, self.revision, self.owner = key, revision, owner


def _sql(path):
    source = read_sql(path).replace('OML_WEB_STATE', identifier(TABLE)).rstrip('/').strip().rstrip(';')
    return source + (';' if path.endswith(('web_state.sql', 'progress_write.sql')) else '')


def load(conn, key=PRACTICE):
    """DB 오류를 로컬 파일이나 빈 성공 기록으로 대체하지 않습니다."""
    try:
        with conn.cursor() as cursor:
            cursor.execute(_sql('queries/progress_read.sql'), {'state_key': key})
            found = rows(cursor)
    except Exception as error:
        if 'ORA-00942' in str(error):
            raise ValueError('공유 검증 저장소가 없습니다. 다시 로그인하여 준비하세요.') from None
        raise
    if len(found) != 1:
        raise ValueError('공유 검증 저장소의 키·구조를 확인하세요.')
    row = found[0]
    owner = str(conn.username).upper()
    if not re.fullmatch(r'[A-Z][A-Z0-9_$#]{0,127}', owner) or row['session_user'] != owner or row['current_schema'] != owner:
        raise ValueError('검증 기록은 발급 계정과 SESSION_USER/CURRENT_SCHEMA가 같아야 합니다.')
    data = json.loads(row['state_json']) if row['state_json'] is not None else {'models': {}} if key == PRACTICE else {}
    if not isinstance(data, dict):
        raise ValueError('공유 검증 기록의 JSON 형식을 확인하세요.')
    return Snapshot(data, key, int(row['revision'] or 0), owner)


def save(conn, state):
    """다른 환경이 먼저 변경한 버전을 덮어쓰지 않습니다."""
    if not isinstance(state, Snapshot) or state.owner != str(conn.username).upper():
        raise ValueError('최신 공유 검증 기록을 조회한 뒤 다시 실행하세요.')
    payload = json.dumps(state, ensure_ascii=False, allow_nan=False)
    if len(payload.encode('utf-8')) > MAX_BYTES:
        raise ValueError('공유 검증 기록의 허용 크기를 초과했습니다.')
    with conn.cursor() as cursor:
        written = cursor.var(oracledb.DB_TYPE_NUMBER)
        cursor.setinputsizes(payload=oracledb.DB_TYPE_CLOB)
        cursor.execute(_sql('queries/progress_write.sql'), dict(state_key=state.key, revision=state.revision, payload=payload, written=written))
        if int(written.getvalue() or 0) != 1:
            raise ValueError('다른 환경에서 검증 기록이 변경되었습니다. 현황을 다시 조회한 뒤 실행하세요.')
    state.revision += 1
    # 전체 JSON·지문·로그인 값은 실행 기록에 복제하지 않습니다.
    sql_trace.add('공유 검증 기록 저장', path='sql/queries/progress_write.sql', kind='STATE', row_count=1)


def initialize(conn):
    """로그인 인증 후 관리 테이블만 준비하며 기존 행을 유지합니다."""
    with conn.cursor() as cursor:
        cursor.execute(_sql('web_state.sql'))
    return load(conn)


def mission_key(person):
    return 'mission-' + hashlib.sha256(str(person['student_id']).encode()).hexdigest()[:32]


def legacy_path(conn, root=ROOT):
    key = hashlib.sha256((conn.username + '@' + str(conn.dsn)).encode()).hexdigest()[:24]
    return Path(root)/'runtime'/('model-choice-' + key + '.json')


def _legacy(path, default):
    if not path.is_file():
        return default
    if path.is_symlink() or path.stat().st_size > MAX_BYTES:
        raise ValueError('기존 검증 기록의 경로·크기를 확인하세요.')
    value = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(value, dict):
        raise ValueError('기존 검증 기록의 형식을 확인하세요.')
    return value


def migrate(conn, person, root=ROOT):
    """DB 행이 없을 때만 1회 이관합니다. 이후 파일은 판정에 쓰지 않습니다."""
    if person['db_user'].upper() != str(conn.username).upper():
        raise ValueError('이관할 발급 계정을 확인하세요.')
    result = []
    state = load(conn)
    if state.revision == 0:
        old = _legacy(legacy_path(conn, root), {'models': {}})
        allowed = {'models','confirmed','preparations','assignments','assignment_preparations','practice_evidence'}
        if set(old) - allowed:
            raise ValueError('기존 검증 기록에 허용되지 않은 항목이 있습니다.')
        state.update(old)
        save(conn, state)
        result.append('practice')
    selection = load(conn, mission_key(person))
    if selection.revision == 0:
        digest = hashlib.sha256(json.dumps([person['student_id'],person['db_user']], ensure_ascii=False).encode()).hexdigest()[:32]
        value = _legacy(Path(root)/'runtime'/('mission-selection-' + digest + '.json'), {}).get('key', '')
        if not isinstance(value, str):
            raise ValueError('기존 미션 선택값을 확인하세요.')
        selection['key'] = value
        save(conn, selection)
        result.append('mission')
    return result


if __name__ == '__main__':
    import argparse
    from .db import connection
    parser = argparse.ArgumentParser()
    parser.add_argument('--owner', required=True)
    parser.add_argument('--student-id', required=True)
    args = parser.parse_args()
    with connection() as conn:
        if str(conn.username).upper() != args.owner.upper():
            raise ValueError('접속 계정과 --owner가 다릅니다.')
        initialize(conn)
        print(json.dumps({'migrated': migrate(conn, {'student_id':args.student_id,'db_user':args.owner.upper()})}))
