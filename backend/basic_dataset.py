"""기본과제의 고정 배포 CSV와 테이블 정의를 읽기 전용으로 안내합니다."""
import csv
import re

from .db import ROOT
from .sql_files import read_sql

SOURCES = {
    'training': ('classification.csv', 'schema.sql', 'OML_BASIC_DATA', '원본 TRAIN·TEST'),
    'prepared': (None, 'prepared_table.sql', 'OML_BASIC_PREPARED', '전처리 저장·모델 입력'),
    'prediction': ('prediction.csv', 'prediction_table.sql', 'OML_BASIC_PREDICT', '예측 입력 원본'),
}
FIELD_LABELS = {
    'CASE_ID': ('사례번호', 'identifier', '사례 식별 키 · 모델 설명변수에서 제외'),
    'RETURN_PCT': ('주간등락률', 'feature', '이번 주 등락률(%) · 모델 설명변수'),
    'RANGE_PCT': ('주간고저폭', 'feature', '이번 주 고저폭(%) · 모델 설명변수'),
    'VOLUME_CHANGE_PCT': ('거래량증감률', 'feature', '전주 대비 거래량 증감률(%) · 모델 설명변수'),
    'CLOSE_PRICE': ('종가', 'feature', '이번 주 종가(USD) · 모델 설명변수'),
    'STOCK': ('종목코드', 'feature', '종목 코드 · 모델 설명변수'),
    'SIGNAL': ('매매신호', 'target', '다음 주 종가가 시가보다 높으면 BUY, 나머지는 SELL'),
    'WEEK_ENDING': ('주마감일', 'metadata', '판단 기준 주의 마지막 거래일 · 모델 설명변수에서 제외'),
    'SPLIT': ('데이터구분', 'metadata', 'TRAIN / TEST · 자동 분할 기능이 아닌 고정 구분값'),
    'USE_YN': ('사용여부', 'metadata', 'Y / N · 경계 주는 N으로 학습·평가에서 제외'),
    'PREP_MODE': ('전처리 방식', 'metadata', 'RAW / CLEAN'),
    'SOURCE_KIND': ('원본 용도', 'metadata', 'TRAIN / TEST / PREDICT'),
    'FIT_YN': ('학습 제공 여부', 'metadata', 'Y인 TRAIN 행만 모델 학습에 제공'),
    'EXCLUDE_REASON': ('학습 제외 사유', 'metadata', '전처리에서 판단한 학습 제외 사유'),
    'UPDATED_AT': ('등록·수정 시각', 'metadata', 'CSV에 없는 운영 컬럼'),
    'PREPARED_AT': ('전처리 저장 시각', 'metadata', 'CSV에 없는 운영 컬럼'),
}


def _source(kind):
    if kind not in ('training', 'prediction'):
        raise ValueError('학습·TEST 또는 예측 CSV를 선택하세요.')
    filename = SOURCES[kind][0]
    folder = ROOT / 'data'
    path = folder / filename
    if path.is_symlink() or path.resolve().parent != folder.resolve():
        raise ValueError('허용된 기본 CSV만 조회할 수 있습니다.')
    with path.open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        columns = reader.fieldnames or []
        rows = list(reader)
    return filename, columns, rows


def _field(name):
    korean, role, description = FIELD_LABELS.get(name.upper(), (name, 'metadata', ''))
    return {'name': name, 'korean_name': korean, 'role': role, 'description': description}


def metadata():
    filename, columns, rows = _source('training')
    prediction_filename, prediction_columns, prediction_rows = _source('prediction')
    return {
        'key': 'basic', 'title': '기본 미션 · 주간 매매 신호 분류', 'fixed': True,
        'description': 'UCI Dow Jones Index의 2011년 시세로 다음 주 BUY·SELL 신호를 분류합니다.',
        'filename': filename, 'prediction_filename': prediction_filename,
        'columns': columns, 'prediction_columns': prediction_columns,
        'layout': [_field(name) for name in columns],
        'rows': len(rows), 'prediction_rows': len(prediction_rows),
        'train_rows': sum(row.get('split') == 'TRAIN' and row.get('use_yn') == 'Y' for row in rows),
        'test_rows': sum(row.get('split') == 'TEST' and row.get('use_yn') == 'Y' for row in rows),
        'excluded_rows': sum(row.get('use_yn') == 'N' for row in rows),
        'training_download': '/download/sample.csv',
        'prediction_download': '/download/prediction.csv',
    }


def preview(kind='training', split='all', page=1):
    filename, columns, rows = _source(kind)
    if split not in ('all', 'TRAIN', 'TEST') or kind == 'prediction' and split != 'all':
        raise ValueError('CSV 종류와 조회 구분을 확인하세요.')
    if not isinstance(page, int) or page < 1:
        raise ValueError('조회할 페이지를 확인하세요.')
    original_total = len(rows)
    if split != 'all':
        rows = [row for row in rows if row.get('split') == split]
    page_size = 50
    pages = max(1, (len(rows) + page_size - 1) // page_size)
    if page > pages:
        raise ValueError('조회할 페이지 범위를 확인하세요.')
    start = (page - 1) * page_size
    return {
        'key': 'basic', 'kind': kind, 'filename': filename, 'columns': columns,
        'layout': [_field(name) for name in columns],
        'rows': rows[start:start + page_size], 'total': len(rows), 'original_total': original_total,
        'page': page, 'pages': pages, 'page_size': page_size, 'split': split,
    }


def table_schema(kind='training', owner=None):
    """실제 배포 DDL에서 컬럼·제약을 읽습니다. DB 연결이나 DDL 실행은 하지 않습니다."""
    if kind not in SOURCES:
        raise ValueError('DATA·PREPARED·PREDICT 중 조회할 테이블을 선택하세요.')
    owner = str(owner or '').strip().upper()
    if not re.fullmatch(r'[A-Z][A-Z0-9_$#]{0,127}', owner):
        raise ValueError('로그인 후 발급받은 DB 객체 생성 계정을 확인하세요.')
    _, source, name, description = SOURCES[kind]
    sql = read_sql(source)
    match = re.search(r'CREATE\s+TABLE\s+' + name + r'\s*\((.*)\)\s*;', sql, re.S | re.I)
    if not match:
        raise ValueError('기본과제 테이블 정의를 확인하세요.')
    comment_source = read_sql('table_comments.sql')
    comments = dict(re.findall(
        r"COMMENT\s+ON\s+COLUMN\s+" + name + r"\.([A-Z_]+)\s+IS\s+'((?:''|[^'])*)'",
        comment_source, re.I,
    ))
    parts = re.split(r'\n\s*,\s*', match.group(1).strip())
    columns, constraints = [], []
    for part in parts:
        definition = re.sub(r'\s+', ' ', part).strip()
        if definition.startswith(('PRIMARY KEY ', 'CHECK ')):
            constraints.append(definition)
            continue
        column = re.fullmatch(
            r'([A-Z][A-Z0-9_]*)\s+((?:VARCHAR2|CHAR|NUMBER|TIMESTAMP)(?:\([0-9 ,]+\))?)(?:\s+(.*))?',
            definition, re.I,
        )
        if not column:
            raise ValueError('기본과제 컬럼 정의를 확인하세요.')
        column_name, data_type, rules = column.groups()
        field = _field(column_name)
        columns.append({
            **field, 'type': data_type, 'rules': rules or '',
            'nullable': '필수' if re.search(r'NOT NULL|PRIMARY KEY', rules or '') else 'NULL 허용',
            'description': comments.get(column_name, field['description']).replace("''", "'"),
        })
    # 선택한 테이블의 배포 COMMENT만 CREATE 뒤에 포함합니다.
    comment_statements = re.findall(
        r"COMMENT\s+ON\s+(?:TABLE\s+" + name + r"|COLUMN\s+" + name
        + r"\.[A-Z_]+)\s+IS\s+'(?:''|[^'])*'", comment_source, re.I,
    )
    sql += '\n\n' + '\n'.join(statement + ';' for statement in comment_statements)
    qualified_sql = re.sub(r'\bOML_BASIC_[A-Z0-9_]+\b', lambda value: owner + '.' + value.group(0), sql)
    from .coding_help import _guard_basic_sql
    qualified_sql = _guard_basic_sql(qualified_sql, owner)
    return {
        'kind': kind, 'owner': owner, 'name': owner + '.' + name, 'object_name': name,
        'description': description, 'columns': columns, 'constraints': constraints,
        'sql': qualified_sql, 'source_path': 'sql/' + source,
        'source_paths': ['sql/' + source, 'sql/table_comments.sql'],
        'notice': '배포 원본의 테이블 정의 안내입니다. 실제 DB 구조 조회나 생성·삭제를 실행하지 않습니다. 기본과제는 화면의 준비·적재·실행 버튼으로 진행하세요.',
    }
