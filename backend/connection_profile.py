"""메인 접속 확인 카드의 실제 Oracle 메타데이터만 읽습니다."""
import re
import time
from datetime import datetime, timezone
from .sql_files import query


def inspect_connection(conn, cfg):
    started = time.perf_counter()
    conn.ping()
    records = query(conn, 'connection_profile.sql')
    if len(records) != 1:
        raise ValueError('Oracle 접속 정보를 확인하지 못했습니다. 연결 테스트를 다시 실행하세요.')
    current = records[0]
    expected = cfg.get('DB_USER', '').upper()
    if current['session_user'] != expected or current['current_schema'] != expected:
        raise ValueError('발급 DB 계정과 실제 접속 계정·현재 스키마가 다릅니다. 본인 계정으로 접속하세요.')
    privileges = [row['privilege'] for row in query(conn, 'connection_info.sql')]
    alias = cfg.get('DB_DSN', '')
    # 전체 접속 기술자나 자격값은 응답하지 않습니다.
    alias = alias if re.fullmatch(r'[A-Za-z0-9_.-]{1,128}', alias) else 'Oracle 접속 기술자'
    return {
        **{key: current.get(key) for key in ('session_user', 'current_schema', 'database_name', 'service_name', 'server_host', 'instance_name')},
        'connection_alias': alias,
        'checked_at': datetime.now(timezone.utc).isoformat(),
        'elapsed_ms': round((time.perf_counter() - started) * 1000),
        'privileges': privileges,
        'success': True,
        'checks': ['발급 계정 인증', 'Oracle 응답 확인', '접속 계정·현재 스키마 일치', '실습 권한 조회'],
    }
