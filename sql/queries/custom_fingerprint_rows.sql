-- 화면의 5,000행 제한과 별개로 모든 학습 원본을 읽어 최신 모델 여부를 검사합니다.
SELECT *
  FROM {{table}}
 ORDER BY CASE_ID
;
