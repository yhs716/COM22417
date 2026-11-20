-- [CUSTOM-INSERT] CSV 헤더를 실제 컬럼과 비교한 뒤 이름을 검증합니다. 값은 바인드합니다.
INSERT INTO {{table}}
(
  {{columns}}
)
VALUES
(
  {{values}}
)
;
