-- [PREPARED-FINGERPRINT] 학습·TEST만 비교합니다. 예측 입력 준비는 모델을 무효화하지 않습니다.
SELECT *
  FROM {{table}}
 WHERE PREP_MODE = :variant
   AND SOURCE_KIND IN ('TRAIN', 'TEST')
 ORDER BY SOURCE_KIND
     , CASE_ID
;
