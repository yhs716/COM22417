-- 작은 실습 데이터를 직렬로 처리합니다. ADB의 병렬 DML 내부 잠금 충돌(ORA-12860)을 피합니다.
-- DB 전체 설정이 아니라 지금 연결한 세션에만 적용됩니다.
ALTER SESSION DISABLE PARALLEL DML
/
ALTER SESSION DISABLE PARALLEL DDL
/
ALTER SESSION DISABLE PARALLEL QUERY
/

-- CSV의 점(.) 소수점을 일관되게 숫자로 읽습니다. 현재 연결에만 적용됩니다.
ALTER SESSION SET NLS_NUMERIC_CHARACTERS = '.,'
/
