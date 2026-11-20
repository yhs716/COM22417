-- CREATE_MODEL2에 등록한 사용자 지정 내장 변환. 학습 SELECT의 CASE 식 목록이 아닙니다.
-- 현재 예제처럼 SELECT 안에서 전처리하면 0행일 수 있으며, 정제가 없다는 뜻이 아닙니다.
SELECT MODEL_NAME
     , ATTRIBUTE_NAME
     , ATTRIBUTE_SUBNAME
     , ATTRIBUTE_SPEC
     , EXPRESSION
     , REVERSE
  FROM USER_MINING_MODEL_XFORMS
 WHERE MODEL_NAME = :model_name
 ORDER BY ATTRIBUTE_NAME
     , ATTRIBUTE_SUBNAME
;
