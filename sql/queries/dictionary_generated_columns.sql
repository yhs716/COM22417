-- 내부 저장 테이블 및 공개 모델 상세 뷰의 실제 컬럼 메타데이터입니다.
SELECT TABLE_NAME AS OBJECT_NAME
     , COLUMN_ID
     , COLUMN_NAME
     , DATA_TYPE
     , DATA_LENGTH
     , DATA_PRECISION
     , DATA_SCALE
     , NULLABLE
  FROM USER_TAB_COLUMNS
 WHERE SUBSTR(TABLE_NAME, 1, 3) = 'DM$'
   AND SUBSTR(TABLE_NAME, 6) = :model_name
 ORDER BY TABLE_NAME, COLUMN_ID
;
