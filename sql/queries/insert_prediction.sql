-- [CSV-INSERT] Python executemany가 CSV 각 행을 아래 바인드에 전달합니다.
INSERT INTO OML_BASIC_PREDICT
(
  CASE_ID
 , RETURN_PCT
 , RANGE_PCT
 , VOLUME_CHANGE_PCT
 , CLOSE_PRICE
 , STOCK
 , SIGNAL
 , WEEK_ENDING
)
VALUES
(
  :case_id
 , :return_pct
 , :range_pct
 , :volume_change_pct
 , :close_price
 , :stock
 , :signal
 , :week_ending
)
;
