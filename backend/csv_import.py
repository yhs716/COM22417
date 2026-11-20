"""로컬 미션 CSV: 헤더 기반 검사 → 500행 바인드 묶음 → 한 번 COMMIT."""
import csv
import io
import re
import tempfile
from contextlib import contextmanager
from .validation import MAX_BYTES, MAX_ROWS
from .sql_files import execute


@contextmanager
def csv_snapshot(path):
    """최대 2 MiB 입력을 고정합니다. 256 KiB를 넘으면 임시 디스크로 넘깁니다."""
    with tempfile.SpooledTemporaryFile(max_size=256 * 1024, mode='w+b') as snapshot:
        total = 0
        with path.open('rb') as source:
            while chunk := source.read(64 * 1024):
                total += len(chunk)
                if total > MAX_BYTES:
                    raise ValueError('CSV는 2MB 이하로 선택하세요.')
                snapshot.write(chunk)
        snapshot.seek(0)
        text = io.TextIOWrapper(snapshot, encoding='utf-8-sig', newline='')
        try:
            yield text
        finally:
            text.detach()


def csv_layout(item, prediction=False):
    columns = ['case_id', *item['columns'][1:4]] if prediction else item['columns']
    if any(not re.fullmatch(r'[a-z][a-z0-9_]*', name) for name in columns):
        raise ValueError('등록된 미션 컬럼을 확인하세요.')
    return list(columns)


def mission_rows(stream, item, prediction=False):
    """첫 줄은 컬럼 헤더, 구분자는 쉼표. 인용부호 안 쉼표·줄바꿈도 csv 모듈로 읽습니다."""
    columns = csv_layout(item, prediction)
    reader = csv.DictReader(stream, delimiter=',', strict=True)
    try:
        headers = reader.fieldnames or []
    except (csv.Error, UnicodeDecodeError) as error:
        raise ValueError('UTF-8 CSV의 첫 줄 헤더와 쉼표 구분을 확인하세요.') from error
    if len(headers) != len(set(headers)) or set(headers) != set(columns):
        raise ValueError('CSV 첫 줄의 컬럼명을 확인하세요: ' + ', '.join(columns))
    ids = set()
    count = 0
    try:
        for count, row in enumerate(reader, 1):
            if count > MAX_ROWS:
                raise ValueError('CSV는 5,000행 이하로 선택하세요.')
            if None in row or any(value is None for value in row.values()):
                raise ValueError(f'{reader.line_num}행의 컬럼 개수를 확인하세요.')
            if any(len(value) > 100 for value in row.values()):
                raise ValueError(f'{reader.line_num}행의 값은 100자 이하여야 합니다.')
            key = row['case_id']
            if not re.fullmatch(r'[1-9][0-9]{0,8}', key):
                raise ValueError(f'{reader.line_num}행의 case_id는 1~999999999 정수여야 합니다.')
            key = int(key)
            if key in ids:
                raise ValueError(f'{reader.line_num}행의 case_id가 중복됩니다.')
            ids.add(key)
            if not prediction and (row['split'] not in ('TRAIN', 'TEST') or row['use_yn'] not in ('Y', 'N')):
                raise ValueError(f'{reader.line_num}행의 SPLIT(TRAIN/TEST)·USE_YN(Y/N)을 확인하세요.')
            # 특성·정답은 정제하지 않습니다. unknown, 범위 밖 숫자, 공백을 그대로 보존합니다.
            yield {name: key if name == 'case_id' else (row[name] if row[name] != '' else None) for name in columns}
        if not count:
            raise ValueError('데이터 행이 없습니다.')
    except (csv.Error, UnicodeDecodeError) as error:
        raise ValueError('UTF-8 CSV의 인용부호와 쉼표 구분을 확인하세요.') from error


def validate_csv(stream, item, prediction=False):
    count = sum(1 for _ in mission_rows(stream, item, prediction))
    stream.seek(0)
    return count


def load_mission_csv(conn, stream, item, owner, *, prediction=False):
    """사전 검사를 마친 고정 파일을 전달합니다. 대상 테이블 1개의 행만 원자적으로 교체합니다."""
    if not re.fullmatch(r'[A-Z][A-Z0-9_$#]{0,29}', owner) or conn.username.upper() != owner:
        raise ValueError('발급 DB 계정과 실제 연결 계정이 다릅니다.')
    columns = csv_layout(item, prediction)
    table = owner + ('.OML_MISSION_PREDICT' if prediction else '.OML_MISSION_DATA')
    replacements = {'table': table, 'columns': ', '.join(name.upper() for name in columns),
                    'values': ', '.join(':' + name for name in columns)}
    try:
        execute(conn, 'queries/csv_owner.sql', {'owner': owner})
        execute(conn, 'queries/custom_delete.sql', replacements={'table': table})
        count = execute(conn, 'queries/custom_insert.sql', replacements=replacements,
                        many=mission_rows(stream, item, prediction))
        conn.commit()
        return count
    except Exception:
        conn.rollback()
        raise
