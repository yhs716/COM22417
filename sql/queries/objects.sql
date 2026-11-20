SELECT OBJECT_NAME
     , OBJECT_TYPE
     , OBJECT_ID
     , STATUS
     , CREATED
     , LAST_DDL_TIME
  FROM USER_OBJECTS
 WHERE OBJECT_NAME IN (:training_table, :prediction_table, :prepared_table, :procedure_name)
 ORDER BY OBJECT_NAME
;
