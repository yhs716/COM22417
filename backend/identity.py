"""전체 JSON 명단에서 학번·이름에 발급된 DB 계정을 찾습니다."""
import json
import os
import re
from pathlib import Path
from .db import ROOT

ROSTER = ROOT / 'security/students.json'
# 학생 Git의 명단을 우선하며 강사 운영의 기존 비밀 명단 경로는 파일이 없을 때만 사용합니다.
if not ROSTER.is_file() and os.environ.get('OML_ROSTER_FILE'):
    ROSTER = Path(os.environ['OML_ROSTER_FILE'])
if not ROSTER.is_absolute():
    ROSTER = ROOT / ROSTER
FIELDS = ('student_id', 'name', 'department', 'grade', 'db_user')


def is_instructor(person):
    """인증 후 명단에서 확인한 학번만 사용합니다. DB 계정명·요청의 권한 표시는 쓰지 않습니다."""
    return bool(person and str(person.get('student_id', '')) == 'V01041')


def roster():
    if not ROSTER.is_file():
        return []
    try:
        data = json.loads(ROSTER.read_text(encoding='utf-8-sig'))
        if not isinstance(data, list):
            raise ValueError()
        seen = set()
        for row in data:
            if not isinstance(row, dict) or any(key not in row for key in ('student_id', 'name', 'db_user')):
                raise ValueError()
            # 학번의 접두사·길이를 정해 놓지 않고 명단에 등록한 값을 사용합니다.
            if not isinstance(row['student_id'], (str, int)) or isinstance(row['student_id'], bool):
                raise ValueError()
            student_id = str(row['student_id']).strip()
            if not student_id or not isinstance(row['name'], str) or not row['name'].strip():
                raise ValueError()
            if student_id in seen:
                raise ValueError()
            if not isinstance(row['db_user'], str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,127}', row['db_user'].strip()):
                raise ValueError()
            row['student_id'] = student_id
            row['name'] = row['name'].strip()
            row['db_user'] = row['db_user'].strip().upper()
            seen.add(student_id)
        return data
    except (ValueError, TypeError, KeyError) as error:
        raise ValueError('security/students.json의 배열 형식과 필수 항목을 확인하세요.') from error


def confirm(student_id, name):
    """매번 JSON을 읽어 등록된 학번·이름을 찾습니다. 학생 정보는 고정하지 않습니다."""
    for row in roster():
        if str(row['student_id']) == str(student_id).strip() and row['name'] == str(name).strip():
            person = {key: row.get(key, '') for key in FIELDS}
            return person
    raise ValueError('등록된 학번과 이름을 확인하세요.')


def current(session):
    """JSON 명단을 수정하면 기존 사용자 확인도 최신 등록값으로 검사합니다."""
    value = session.get('identity')
    if not value:
        return None
    try:
        return confirm(value['student_id'], value['name'])
    except (ValueError, KeyError):
        session.pop('identity', None)
        return None
