-- USER_OBJECTS / USER_MINING_MODEL_VIEWS 및 USER_TAB_COLUMNS로 확인한 객체와 일반 컬럼만 조회합니다.
-- 객체명/컬럼명은 서버에서 검증하며 BLOB·RAW 등은 컬럼 정의만 제공하고 XMLTYPE은 XML 문자열로 직렬화합니다.
SELECT {{columns}}
  FROM {{view}}
 FETCH FIRST 20 ROWS ONLY
;
