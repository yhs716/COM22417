"""Reject credentials in distributable bytes without ever printing secret values."""
from pathlib import Path
import io
import json
import re
from dotenv import dotenv_values

SHARED_WALLET_PASSWORD = 'Pcuora2026'


def validate_student_environment(raw):
    cfg = dotenv_values(stream=io.StringIO(raw.decode('utf-8')), interpolate=False)
    if cfg.get('DB_USER') or any(value for key,value in cfg.items()
                               if any(word in key.upper() for word in ('PASSWORD','SECRET','TOKEN'))
                               and not (key=='WALLET_PASSWORD' and value==SHARED_WALLET_PASSWORD)):
        raise ValueError('Student environment must have blank DB_USER and private passwords; only the approved shared Wallet password is allowed.')
    return cfg


def secret_values(root):
    values = set()
    security = Path(root) / 'security'
    for path in security.glob('*'):
        if path.is_file() and '.env' in path.name.lower() and not path.name.endswith('.example'):
            for key, value in dotenv_values(path, interpolate=False).items():
                if key=='WALLET_PASSWORD' and value==SHARED_WALLET_PASSWORD:
                    continue
                if value and any(word in key.upper() for word in ('PASSWORD', 'SECRET', 'TOKEN')):
                    if len(value) < 8:
                        raise ValueError('A configured secret is too short for reliable distribution scanning. Review local settings.')
                    values.add(value.encode('utf-8'))
    return values


def validate_files(files, root, allow_wallet=False, allow_student_env=False):
    secrets = secret_values(root)
    for name, raw in files.items():
        lower = name.lower()
        if lower == 'security/wallet_pcuora.zip' and allow_wallet:
            continue
        student_env = name == 'security/student.env' and allow_student_env
        if student_env:
            validate_student_environment(raw)
            if raw != files.get('security/student.env.example'):
                raise ValueError('Student environment must match the public example.')
        if ('.env' in Path(lower).name and not lower.endswith('.example') and not student_env) or re.search(r'(^|/)(teacher|tearher)[^/]*', lower):
            raise ValueError('Private configuration file in distribution: ' + name)
        if Path(lower).suffix in {'.pem', '.sso', '.p12', '.key', '.log'} or 'wallet' in Path(lower).name:
            raise ValueError('Private key or runtime file in distribution: ' + name)
        if any(value in raw for value in secrets):
            raise ValueError('Configured secret detected in distribution: ' + name)
    example = files.get('security/student.env.example')
    if example is not None:
        validate_student_environment(example)

def validate_student_roster(raw):
    """본인 Git에는 비밀번호 없는 본인 한 행의 명단만 포함합니다."""
    data=json.loads(raw.decode('utf-8-sig'))
    fields={'student_id','name','department','grade','db_user'}
    if not isinstance(data,list) or len(data)!=1:
        raise ValueError('본인 Git의 security/students.json에는 본인 한 명만 등록하세요.')
    person=data[0]
    if not isinstance(person,dict) or set(person)-fields or not {'student_id','name','db_user'}<=person.keys():
        raise ValueError('students.json에는 학번·이름·DB 계정과 선택 학과·학년만 작성하세요.')
    if (not isinstance(person['student_id'],(str,int)) or isinstance(person['student_id'],bool)
            or not str(person['student_id']).strip() or not isinstance(person['name'],str)
            or not person['name'].strip() or not isinstance(person['db_user'],str)
            or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,127}',person['db_user'])):
        raise ValueError('students.json의 student_id·name·db_user 형식을 확인하세요.')
