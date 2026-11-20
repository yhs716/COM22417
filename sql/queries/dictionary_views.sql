-- Oracle이 모델에 대해 제공하는 상세 뷰 목록. 실제 이름·종류를 먼저 확인합니다.
-- 이 앱이 사용자 뷰를 새로 생성하는 것이 아닙니다. 상세 뷰 구성은 알고리즘·DB 버전에 따라 다릅니다.
SELECT MODEL_NAME
     , VIEW_NAME
     , VIEW_TYPE
  FROM USER_MINING_MODEL_VIEWS
 WHERE MODEL_NAME = :model_name
 ORDER BY VIEW_TYPE
     , VIEW_NAME
;
