-- 모델 시그니처입니다. TARGET=YES는 정답, NO는 입력 속성입니다.
-- 학습 SELECT의 모든 컬럼이나 트리의 모든 분기 조건을 뜻하지는 않습니다.
SELECT MODEL_NAME
     , ATTRIBUTE_NAME
     , ATTRIBUTE_TYPE
     , DATA_TYPE
     , DATA_LENGTH
     , DATA_PRECISION
     , DATA_SCALE
     , USAGE_TYPE
     , TARGET
  FROM USER_MINING_MODEL_ATTRIBUTES
 WHERE MODEL_NAME = :model_name
 ORDER BY TARGET DESC
     , ATTRIBUTE_NAME
;
