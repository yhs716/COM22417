-- Oracle 스키마 객체의 유효 상태입니다. 웹의 최신 학습·선택 확정 상태와는 다릅니다.
SELECT OBJECT_NAME
     , OBJECT_TYPE
     , OBJECT_ID
     , STATUS
     , CREATED
     , LAST_DDL_TIME
  FROM USER_OBJECTS
 WHERE OBJECT_NAME = :model_name
   AND OBJECT_TYPE = 'MINING MODEL'
;
