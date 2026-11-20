-- [DATA-SELECT] 필터 선택값은 :use_yn, :split에 바인딩됩니다.
SELECT CASE_ID
     , RETURN_PCT
     , RANGE_PCT
     , VOLUME_CHANGE_PCT
     , CLOSE_PRICE
     , STOCK
     , SIGNAL
     , WEEK_ENDING
     , SPLIT
     , USE_YN
  FROM OML_BASIC_DATA
 WHERE (:use_yn = 'ALL' OR USE_YN = :use_yn)
   AND (:split = 'ALL' OR SPLIT = :split)
 ORDER BY CASE_ID
;
