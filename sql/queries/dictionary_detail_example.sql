-- [MODEL-DETAIL-VIEW] USER_MINING_MODEL_VIEWS에서 확인한 실제 뷰 이름으로 조회합니다.
-- SQL Developer에서 같은 계정으로 실행하세요. 읽기 전용이며 화면에 보여 줄 100행만 조회합니다.
SELECT *
  FROM {{view}}
 FETCH FIRST 100 ROWS ONLY
;
