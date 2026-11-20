-- 고정 과제 접두어의 모델 2개만 조회합니다. DM$ 객체는 직접 조작하지 않습니다.
SELECT MODEL_NAME
     , CREATION_DATE
     , ALGORITHM
  FROM USER_MINING_MODELS
 WHERE MODEL_NAME IN (:raw_model, :clean_model)
 ORDER BY MODEL_NAME
;
