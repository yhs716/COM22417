"""[SQL-RUNNER] SQL은 sql/ 파일에서 읽습니다. Python에는 SQL 문장을 내장하지 않습니다."""
import hashlib
import re
import time
from itertools import islice
from .db import ROOT, rows
from . import sql_trace

SQL_ROOT=ROOT/'sql'
COMMENT_FILES=('table_comments.sql',)
CSV_BATCH_SIZE = 500

def definition_files():
    return ('schema.sql','prediction_table.sql','prepared_table.sql','classifier.sql')

def identifier(name):
    name=str(name).strip().upper()
    if not re.fullmatch(r'OML_[A-Z0-9_]{1,120}',name):
        raise ValueError('같은 계정의 OML_로 시작하는 영문·숫자·밑줄 객체명을 입력하세요.')
    return name

def read_sql(filename):
    path=SQL_ROOT/filename
    if path.is_symlink() or not path.resolve().is_relative_to(SQL_ROOT.resolve()):
        raise ValueError('허용한 SQL 경로만 읽습니다.')
    return path.read_text(encoding='utf-8-sig').strip()

def execute(conn, filename, binds=None, *, replacements=None, many=None, fetch=False):
    """[EXECUTE-SQL] 필터는 binds, CSV는 executemany. 객체명은 검증된 설정만 사용합니다."""
    sql=read_sql(filename).rstrip('/').rstrip().rstrip(';')
    if re.sub(r'--[^\n]*','',sql).lstrip().upper().startswith(('BEGIN','DECLARE')):sql+=';'
    for key,value in (replacements or {}).items():sql=sql.replace('{{'+key+'}}',value)
    binds=binds or {};started=time.perf_counter()
    batch_count = batches = affected = 0
    try:
        with conn.cursor() as cursor:
            cursor.arraysize = 500
            if many is not None:
                iterator = iter(many)
                while batch := list(islice(iterator, CSV_BATCH_SIZE)):
                    batch_count += len(batch)
                    batches += 1
                    cursor.executemany(sql, batch)
                    affected += cursor.rowcount
                result = affected
            else:
                cursor.execute(sql,binds)
                result=rows(cursor) if fetch else cursor.rowcount
            count=len(result) if fetch else result
        extra={'batch_count':batch_count,'batch_size':CSV_BATCH_SIZE,'batches':batches} if many is not None else {}
        sql_trace.add(sql,binds,path='sql/'+filename,elapsed=time.perf_counter()-started,row_count=count,**extra)
        return result
    except Exception:
        extra={'batch_count':batch_count,'batch_size':CSV_BATCH_SIZE,'batches':batches} if many is not None else {}
        sql_trace.add(sql,binds,path='sql/'+filename,elapsed=time.perf_counter()-started,status='error',**extra)
        raise


def query(conn,filename,**binds):
    return execute(conn,'queries/'+filename,binds,fetch=True)

def execute_file(conn,filename,*,existing_tables=False):
    """/ 구분자로 SQL을 순서대로 실행합니다. 기존 테이블의 행은 삭제하지 않습니다."""
    source=read_sql(filename)
    for block in re.split(r'^/\s*$',source,flags=re.M):
        block=block.strip();upper=re.sub(r'--[^\n]*','',block).lstrip().upper()
        if not upper:continue
        plsql=upper.startswith(('BEGIN','DECLARE','CREATE OR REPLACE PROCEDURE'))
        sql=block if plsql else block.rstrip(';');started=time.perf_counter()
        try:
            with conn.cursor() as cursor:cursor.execute(sql)
            sql_trace.add(sql,path='sql/'+filename,kind='DDL',elapsed=time.perf_counter()-started)
        except Exception as error:
            if existing_tables and upper.startswith('CREATE TABLE ') and 'ORA-00955' in str(error):continue
            sql_trace.add(sql,path='sql/'+filename,kind='DDL',status='error')
            raise

def code_fingerprint():
    return hashlib.sha256((SQL_ROOT/'classifier.sql').read_bytes()).hexdigest()

def ready(conn):
    objs=query(conn,'objects.sql',training_table='OML_BASIC_DATA',prediction_table='OML_BASIC_PREDICT',prepared_table='OML_BASIC_PREPARED',procedure_name='OML_BASIC_RUN')
    return {r['object_name'] for r in objs if r['status']=='VALID'}=={'OML_BASIC_DATA','OML_BASIC_PREDICT','OML_BASIC_PREPARED','OML_BASIC_RUN'}

def initialize(conn):
    """[DB-INIT] 테이블 3개와 프로시저 1개만 준비합니다. 기존 테이블의 행은 보존합니다."""
    for name in definition_files():execute_file(conn,name,existing_tables=True)
    execute_file(conn,'table_comments.sql')
    errors=query(conn,'procedure_errors.sql',procedure_name='OML_BASIC_RUN')
    if errors:raise ValueError('sql/classifier.sql 컴파일 오류: '+ '\n'.join(f"DB {r['line']}행: {r['text']}" for r in errors))

def ensure_initialized(conn):
    if not ready(conn):initialize(conn);return True
    return False
