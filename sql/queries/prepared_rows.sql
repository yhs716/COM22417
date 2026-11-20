-- [PREPARED-SELECT] 저장된 모델 입력을 확인합니다. 전처리를 다시 실행하지 않습니다.
SELECT *
  FROM {{table}}
 WHERE PREP_MODE = :variant
   AND (:source_kind = 'ALL' OR SOURCE_KIND = :source_kind)
 ORDER BY SOURCE_KIND
     , CASE_ID
 FETCH FIRST 5000 ROWS ONLY
;
