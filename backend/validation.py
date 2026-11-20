"""CSV 구조만 확인합니다. 결측값·이상치는 SQL 정제 전까지 보존합니다."""
import csv
import io
import math
from datetime import date

COLUMNS = ('case_id', 'return_pct', 'range_pct', 'volume_change_pct', 'close_price', 'stock', 'signal', 'week_ending', 'split', 'use_yn')
FEATURES = COLUMNS[1:6]
RANGES = {'return_pct': (-100, 1000), 'range_pct': (0, 1000), 'volume_change_pct': (-100, 10000), 'close_price': (0.000001, 100000)}
MAX_BYTES = 2 * 1024 * 1024
MAX_ROWS = 5000


def parse_csv(raw: bytes, *, prediction=False):
    """숫자 오류도 원본으로 적재하여 정제 전후를 비교할 수 있습니다."""
    if len(raw) > MAX_BYTES:
        raise ValueError('CSV는 2MB 이하로 선택하세요.')
    try:
        reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig'), newline=''))
        # 이전 CSV에 사용 여부가 없으면 Y로 읽습니다. 새 다운로드 CSV에는 use_yn이 포함됩니다.
        expected = set(COLUMNS) - {'use_yn'} if not prediction else set(('case_id', *FEATURES, 'week_ending'))
        headers = reader.fieldnames or []
        if len(headers) != len(set(headers)) or not expected.issubset(headers):
            raise ValueError('CSV 컬럼을 확인하세요: ' + ', '.join(sorted(expected)))
        if set(headers) - set(COLUMNS):
            raise ValueError('공통 샘플과 다른 컬럼입니다. 추가 데이터의 적재 구조는 SQL에서 직접 구현하세요.')
        result, ids = [], set()
        for line, row in enumerate(reader, 2):
            if len(result) >= MAX_ROWS:
                raise ValueError('CSV는 5,000행 이하로 선택하세요.')
            if None in row or any(value is None for value in row.values()):
                raise ValueError(f'{line}행의 컬럼 개수를 확인하세요.')
            cleaned = {key: (row.get(key) or '').strip() for key in COLUMNS}
            if any(len(value) > 100 for value in cleaned.values()):
                raise ValueError(f'{line}행의 값은 100자 이하여야 합니다.')
            case_id = cleaned['case_id']
            if not case_id.isascii() or not case_id.isdigit() or not 0 < int(case_id) <= 999999999:
                raise ValueError(f'{line}행의 case_id는 1~999999999 사이 정수여야 합니다.')
            cleaned['case_id'] = int(case_id)
            if cleaned['case_id'] in ids:
                raise ValueError(f'{line}행의 case_id가 중복됩니다. 중복 키를 먼저 수정하세요.')
            ids.add(cleaned['case_id'])
            try:
                if date.fromisoformat(cleaned['week_ending']).isoformat() != cleaned['week_ending']:
                    raise ValueError()
            except ValueError:
                raise ValueError(f'{line}행의 week_ending은 유효한 YYYY-MM-DD 날짜여야 합니다.') from None
            cleaned['split'] = cleaned['split'].upper()
            cleaned['use_yn'] = row.get('use_yn', 'Y').strip().upper()
            if not prediction and cleaned['use_yn'] not in ('Y', 'N'):
                raise ValueError(f'{line}행의 use_yn은 Y 또는 N이어야 합니다.')
            if not prediction and cleaned['split'] not in ('TRAIN', 'TEST'):
                raise ValueError(f'{line}행의 split은 TRAIN 또는 TEST여야 합니다.')
            result.append(cleaned)
        if not result:
            raise ValueError('데이터 행이 없습니다.')
        return result
    except (UnicodeDecodeError, csv.Error) as error:
        raise ValueError('UTF-8 CSV 파일로 저장한 뒤 다시 선택하세요.') from error


def quality(data, *, prediction=False):
    """화면 미리보기용 집계. DB 정제는 sql/classifier.sql에서만 수행합니다."""
    missing = invalid = outliers = invalid_target = 0
    for row in data:
        missing += sum(row[key] == '' for key in FEATURES)
        invalid_target += row['signal'].upper() not in ('BUY', 'SELL')
        for key, (low, high) in RANGES.items():
            if row[key] == '':
                continue
            try:
                value = float(row[key])
                if not math.isfinite(value):
                    raise ValueError()
                outliers += not low <= value <= high
            except ValueError:
                invalid += 1
    if prediction:
        return {'rows': len(data), 'missing': missing, 'invalid': invalid, 'outliers': outliers,
                'labeled': sum(row['signal'].upper() in ('BUY','SELL') for row in data)}
    return {'rows': len(data), 'missing': missing, 'invalid': invalid,
            'outliers': outliers, 'invalid_target': invalid_target,
            'train': sum(row['split'] == 'TRAIN' and row['use_yn']=='Y' for row in data),
            'test': sum(row['split'] == 'TEST' and row['use_yn']=='Y' for row in data),
            'used': sum(row['use_yn']=='Y' for row in data), 'disabled': sum(row['use_yn']=='N' for row in data)}
