-- [CUSTOM-SELECT] 검증된 현재 계정 테이블명만 치환합니다. SQL 문장은 입력받지 않습니다.
SELECT *
  FROM {{table}}
 ORDER BY CASE_ID
 FETCH FIRST 5000 ROWS ONLY
;
