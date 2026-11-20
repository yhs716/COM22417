-- [CSV-INSERT] Python executemany가 CSV를 500행씩 아래 한 문장의 바인드에 전달합니다.
INSERT INTO OML_BASIC_DATA
(
  CASE_ID
 , RETURN_PCT
 , RANGE_PCT
 , VOLUME_CHANGE_PCT
 , CLOSE_PRICE
 , STOCK
 , SIGNAL
 , WEEK_ENDING
 , SPLIT
 , USE_YN
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
 , :split
 , :use_yn
)
;
