-- [PYTHON-CALL] service.run_model가 네 인자를 바인딩합니다. OUT 두 개는 결과와 실행 SQL입니다.
-- 런타임 호출문입니다. DB에 저장된 프로시저를 실행하며 classifier.sql을 생성·컴파일하지 않습니다.
-- SQL Developer 직접 호출은 sql/examples/run.sql의 OUT 변수 선언·PRINT 예제를 사용하세요.
BEGIN
  OML_BASIC_RUN(:p_action, :p_mode, :p_result, :p_sql);
END;
/
