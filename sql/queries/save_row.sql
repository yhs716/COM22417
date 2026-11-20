-- [ROW-UPDATE] 기존 행 수정. 없는 CASE_ID는 Python에서 insert_training.sql로 추가합니다.
UPDATE OML_BASIC_DATA
   SET RETURN_PCT = :return_pct
     , RANGE_PCT = :range_pct
     , VOLUME_CHANGE_PCT = :volume_change_pct
     , CLOSE_PRICE = :close_price
     , STOCK = :stock
     , SIGNAL = :signal
     , WEEK_ENDING = :week_ending
     , SPLIT = :split
     , USE_YN = :use_yn
     , UPDATED_AT = SYSTIMESTAMP
 WHERE CASE_ID = :case_id
;
