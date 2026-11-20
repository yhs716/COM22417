-- 점(.) 소수점을 사용합니다. 현재 SQL Developer 세션에만 적용됩니다.
ALTER SESSION SET NLS_NUMERIC_CHARACTERS = '.,'
;
-- [DIRECT-CALL] SQL Developer에서 같은 계정·같은 데이터로 F5 실행합니다.
-- 모델 생성은 DDL 자동 커밋을 포함합니다. 객체명은 등록된 설정만 치환합니다.
VARIABLE result REFCURSOR
VARIABLE executed_sql CLOB
BEGIN
  {{procedure}}('{{action}}', '{{mode}}', :result, :executed_sql);
END;
/
PRINT result
PRINT executed_sql
