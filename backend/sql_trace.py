"""교육용 실행 기록. 실제 실행 SQL과 바인드를 함께 보여 줍니다."""
from contextvars import ContextVar
from datetime import datetime, timezone
import re
from .db import ROOT

_records = ContextVar('sql_records', default=None)
MAX_RECORDS = 100

def begin():
    _records.set([])

def records():
    return list(_records.get() or [])

def literal(value):
    if value is None: return 'NULL'
    if isinstance(value, (int, float)): return str(value)
    return "'" + str(value).replace("'", "''") + "'"

def rendered(sql, binds):
    # 문자열·주석 안의 :문자는 바인드가 아닙니다. 표시용 결과를 실행하지 않습니다.
    tokens = r"q'(?P<q>[\[({<]).*?[\])}>]'|'(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"|--[^\n]*|/\*.*?\*/|:([A-Za-z][A-Za-z0-9_]*)"
    return re.sub(tokens, lambda m: literal(binds[m[2]]) if m[2] in binds else m[0], sql, flags=re.S | re.I)

def source(path, keyword=None):
    p=ROOT/path
    if p.is_symlink() or not p.resolve().is_relative_to(ROOT.resolve()) or not p.is_file():
        return {'path':path,'line':1,'keyword':keyword or '', 'content':'이 파일이 없습니다. 안내된 경로에 작성하세요.'}
    text=p.read_text(encoding='utf-8-sig');offset=text.find(keyword) if keyword else 0
    return {'path':path,'line':text.count('\n',0,max(offset,0))+1,'keyword':keyword or '', 'content':text}

def add(sql, binds=None, *, path='', kind='SQL', elapsed=0, status='success', row_count=None, **extra):
    entries = _records.get()
    if entries is None: return None
    if len(entries) >= MAX_RECORDS:
        entries[-1]['omitted_records'] = entries[-1].get('omitted_records', 0) + 1
        return None
    binds=binds or {}
    item={'sql':sql,'binds':binds,'rendered_sql':rendered(sql,binds),'path':path,'kind':kind,
          'status':status,'elapsed_ms':round(elapsed*1000,2),'row_count':row_count,
          'at':datetime.now(timezone.utc).isoformat(),**extra}
    if _records.get() is not None: _records.get().append(item)
    return item

def response(data):
    return {**data,'trace':records()}
