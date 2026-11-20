-- {{TITLE}} · 선택 미션 전체 실행 프로시저
-- DATA → PREPARED → PREDICT 테이블 생성 후 같은 계정에서 전체 F5 실행합니다.
-- 컬럼·분류값을 선택 미션으로 치환한 가이드이며 조회만으로 자동 실행하지 않습니다.
ALTER SESSION SET NLS_NUMERIC_CHARACTERS = '.,'
/
-- [CLASSIFIER-PROCEDURE] 원본 → 전처리 저장 → 모델 생성 → TEST 평가 → 예측.
-- 입력: p_action(PREPARE/INIT/RETRAIN/ADD_TRAIN/DELETE/VALIDATE/EVALUATE/PREDICT), p_mode(RAW/CLEAN).
-- PREPARE: 선택 방식의 DATA 모든 행을 INSERT SELECT로 PREPARED에 저장하고 COMMIT합니다.
-- FIT_YN=Y는 실제 학습 제공 행입니다. TEST·원본 제외 행은 준비 테이블에 보관하되 학습하지 않습니다.
-- INIT/RETRAIN/ADD_TRAIN: 준비된 숫자값을 SELECT할 뿐 전처리를 다시 실행하지 않습니다.
-- 원본 수정·추가 후에는 VALIDATE → COMMIT → PREPARE → 학습 순서로 실행하세요.
-- 준비값/FIT_YN을 직접 수정한 경우 COMMIT → 학습합니다. PREPARE를 다시 실행하면 수동 수정은 교체됩니다.
-- VALIDATE는 원본의 학습 행 수·정답 종류를 검사하며 모델 존재 여부와 관계없이 DDL·COMMIT하지 않습니다.
-- PREDICT: 선택 방식의 예측 입력만 준비 테이블에 저장하고 같은 방식의 모델로 예측합니다.
-- TRAIN은 이전 호출 호환입니다. 추가 학습도 현재 FIT_YN=Y 전체로 모델을 재생성합니다.
-- 출력: p_result 결과 행, p_sql 실제 결과 SELECT(모델 생성은 학습 SELECT, 삭제는 호출 PL/SQL).
-- 수정 위치: SQL-PREPARE의 INSERT SELECT·FIT_YN 규칙, SQL-TRAIN의 특성/정답, SQL-EVALUATE/SQL-PREDICT.
-- 원본 DATA/PREDICT 값은 수정하지 않습니다. CASE_ID·분할·사용여부는 모델 특성이 아닙니다.
CREATE OR REPLACE PROCEDURE OML_MISSION_RUN(
      p_action IN VARCHAR2
     , p_mode IN VARCHAR2
     , p_result OUT SYS_REFCURSOR
     , p_sql OUT CLOB
) AUTHID CURRENT_USER AS
  v_model VARCHAR2(261);
  v_model_name VARCHAR2(30);
  v_exists NUMBER;
  v_train NUMBER;
  v_classes NUMBER;

  -- [SQL-PREPARE] RAW는 숫자 변환·문자 표준화, CLEAN은 숫자 범위 검사까지 저장합니다.
  -- 두 방식은 같은 원본을 읽고 독립된 PREP_MODE 행을 만듭니다.
  -- [OML-PREPARE-RAW] 원본 DATA → 실제 숫자값 저장. 정제는 이 INSERT SELECT에서 끝냅니다.
  PROCEDURE prepare_raw_data IS
  BEGIN
    DELETE FROM OML_MISSION_PREPARED
     WHERE PREP_MODE = 'RAW'
       AND SOURCE_KIND IN ('TRAIN', 'TEST')
    ;
    INSERT INTO OML_MISSION_PREPARED
    (
      PREP_MODE
     , SOURCE_KIND
     , CASE_ID
     , {{FEATURE_1}}
     , {{FEATURE_2}}
     , {{FEATURE_3}}
     , LABEL
     , USE_YN
     , FIT_YN
     , EXCLUDE_REASON
    )
    SELECT 'RAW'
         , SPLIT
         , CASE_ID
         , TO_NUMBER({{FEATURE_1}} DEFAULT NULL ON CONVERSION ERROR)
         , TO_NUMBER({{FEATURE_2}} DEFAULT NULL ON CONVERSION ERROR)
         , TO_NUMBER({{FEATURE_3}} DEFAULT NULL ON CONVERSION ERROR)
         , UPPER(TRIM(LABEL))
         , USE_YN
         , CASE WHEN SPLIT = 'TRAIN' AND USE_YN = 'Y' AND UPPER(TRIM(LABEL)) IN ({{CLASSES}})
              THEN 'Y' ELSE 'N' END
         , CASE WHEN USE_YN = 'N' THEN '원본 USE_YN=N'
              WHEN SPLIT = 'TEST' THEN '고정 TEST: 학습 제외'
              WHEN UPPER(TRIM(LABEL)) IS NULL OR UPPER(TRIM(LABEL)) NOT IN ({{CLASSES}}) THEN '학습 정답 확인 필요'
         END
      FROM OML_MISSION_DATA
    ;
  END;
  -- [/OML-PREPARE-RAW]

  -- [OML-PREPARE-CLEAN] 원본 DATA → 실제 숫자값 저장. 정제는 이 INSERT SELECT에서 끝냅니다.
  PROCEDURE prepare_clean_data IS
  BEGIN
    DELETE FROM OML_MISSION_PREPARED
     WHERE PREP_MODE = 'CLEAN'
       AND SOURCE_KIND IN ('TRAIN', 'TEST')
    ;
    INSERT INTO OML_MISSION_PREPARED
    (
      PREP_MODE
     , SOURCE_KIND
     , CASE_ID
     , {{FEATURE_1}}
     , {{FEATURE_2}}
     , {{FEATURE_3}}
     , LABEL
     , USE_YN
     , FIT_YN
     , EXCLUDE_REASON
    )
    SELECT 'CLEAN'
         , SPLIT
         , CASE_ID
         , CASE WHEN TO_NUMBER({{FEATURE_1}} DEFAULT NULL ON CONVERSION ERROR) BETWEEN 0 AND 100
              THEN TO_NUMBER({{FEATURE_1}} DEFAULT NULL ON CONVERSION ERROR) END
         , CASE WHEN TO_NUMBER({{FEATURE_2}} DEFAULT NULL ON CONVERSION ERROR) BETWEEN 0 AND 100
              THEN TO_NUMBER({{FEATURE_2}} DEFAULT NULL ON CONVERSION ERROR) END
         , CASE WHEN TO_NUMBER({{FEATURE_3}} DEFAULT NULL ON CONVERSION ERROR) BETWEEN 0 AND 100
              THEN TO_NUMBER({{FEATURE_3}} DEFAULT NULL ON CONVERSION ERROR) END
         , UPPER(TRIM(LABEL))
         , USE_YN
         , CASE WHEN SPLIT = 'TRAIN' AND USE_YN = 'Y' AND UPPER(TRIM(LABEL)) IN ({{CLASSES}})
                   AND TO_NUMBER({{FEATURE_1}} DEFAULT NULL ON CONVERSION ERROR) BETWEEN 0 AND 100
                   AND TO_NUMBER({{FEATURE_2}} DEFAULT NULL ON CONVERSION ERROR) BETWEEN 0 AND 100
                   AND TO_NUMBER({{FEATURE_3}} DEFAULT NULL ON CONVERSION ERROR) BETWEEN 0 AND 100
              THEN 'Y' ELSE 'N' END
         , CASE WHEN USE_YN = 'N' THEN '원본 USE_YN=N'
              WHEN SPLIT = 'TEST' THEN '고정 TEST: 학습 제외'
              WHEN UPPER(TRIM(LABEL)) IS NULL OR UPPER(TRIM(LABEL)) NOT IN ({{CLASSES}}) THEN '학습 정답 확인 필요'
              WHEN TO_NUMBER({{FEATURE_1}} DEFAULT NULL ON CONVERSION ERROR) IS NULL OR TO_NUMBER({{FEATURE_1}} DEFAULT NULL ON CONVERSION ERROR) NOT BETWEEN 0 AND 100
                OR TO_NUMBER({{FEATURE_2}} DEFAULT NULL ON CONVERSION ERROR) IS NULL OR TO_NUMBER({{FEATURE_2}} DEFAULT NULL ON CONVERSION ERROR) NOT BETWEEN 0 AND 100
                OR TO_NUMBER({{FEATURE_3}} DEFAULT NULL ON CONVERSION ERROR) IS NULL OR TO_NUMBER({{FEATURE_3}} DEFAULT NULL ON CONVERSION ERROR) NOT BETWEEN 0 AND 100 THEN '설명변수 결측·변환 실패·0~100 범위 밖'
         END
      FROM OML_MISSION_DATA
    ;
  END;
  -- [/OML-PREPARE-CLEAN]

  -- [OML-PREPARE-PREDICT-RAW] 예측 원본 → 실제 숫자값 저장. 정제는 이 INSERT SELECT에서 끝냅니다.
  PROCEDURE prepare_raw_prediction IS
  BEGIN
    DELETE FROM OML_MISSION_PREPARED
     WHERE PREP_MODE = 'RAW'
       AND SOURCE_KIND = 'PREDICT'
    ;
    INSERT INTO OML_MISSION_PREPARED
    (
      PREP_MODE
     , SOURCE_KIND
     , CASE_ID
     , {{FEATURE_1}}
     , {{FEATURE_2}}
     , {{FEATURE_3}}
     , LABEL
     , USE_YN
     , FIT_YN
     , EXCLUDE_REASON
    )
    SELECT 'RAW'
         , 'PREDICT'
         , CASE_ID
         , TO_NUMBER({{FEATURE_1}} DEFAULT NULL ON CONVERSION ERROR)
         , TO_NUMBER({{FEATURE_2}} DEFAULT NULL ON CONVERSION ERROR)
         , TO_NUMBER({{FEATURE_3}} DEFAULT NULL ON CONVERSION ERROR)
         , NULL
         , 'Y'
         , 'N'
         , '예측 입력: 학습 제외'
      FROM OML_MISSION_PREDICT
    ;
  END;
  -- [/OML-PREPARE-PREDICT-RAW]

  -- [OML-PREPARE-PREDICT-CLEAN] 예측 원본 → 실제 숫자값 저장. 정제는 이 INSERT SELECT에서 끝냅니다.
  PROCEDURE prepare_clean_prediction IS
  BEGIN
    DELETE FROM OML_MISSION_PREPARED
     WHERE PREP_MODE = 'CLEAN'
       AND SOURCE_KIND = 'PREDICT'
    ;
    INSERT INTO OML_MISSION_PREPARED
    (
      PREP_MODE
     , SOURCE_KIND
     , CASE_ID
     , {{FEATURE_1}}
     , {{FEATURE_2}}
     , {{FEATURE_3}}
     , LABEL
     , USE_YN
     , FIT_YN
     , EXCLUDE_REASON
    )
    SELECT 'CLEAN'
         , 'PREDICT'
         , CASE_ID
         , CASE WHEN TO_NUMBER({{FEATURE_1}} DEFAULT NULL ON CONVERSION ERROR) BETWEEN 0 AND 100
              THEN TO_NUMBER({{FEATURE_1}} DEFAULT NULL ON CONVERSION ERROR) END
         , CASE WHEN TO_NUMBER({{FEATURE_2}} DEFAULT NULL ON CONVERSION ERROR) BETWEEN 0 AND 100
              THEN TO_NUMBER({{FEATURE_2}} DEFAULT NULL ON CONVERSION ERROR) END
         , CASE WHEN TO_NUMBER({{FEATURE_3}} DEFAULT NULL ON CONVERSION ERROR) BETWEEN 0 AND 100
              THEN TO_NUMBER({{FEATURE_3}} DEFAULT NULL ON CONVERSION ERROR) END
         , NULL
         , 'Y'
         , 'N'
         , '예측 입력: 학습 제외'
      FROM OML_MISSION_PREDICT
    ;
  END;
  -- [/OML-PREPARE-PREDICT-CLEAN]

  -- [SOURCE-CHECK] 고정 TRAIN/TEST와 선택 미션의 5개 정답 범주를 확인합니다.
  PROCEDURE validate_source IS
  BEGIN
    SELECT COUNT(CASE WHEN SPLIT = 'TRAIN' THEN 1 END)
         , COUNT(DISTINCT CASE WHEN SPLIT = 'TRAIN' THEN UPPER(TRIM(LABEL)) END)
      INTO v_train
         , v_classes
      FROM OML_MISSION_DATA
     WHERE USE_YN = 'Y'
       AND SPLIT IN ('TRAIN', 'TEST')
       AND UPPER(TRIM(LABEL)) IN ({{CLASSES}})
    ;
    IF v_train < 4 OR v_classes < 2 THEN
      RAISE_APPLICATION_ERROR(-20006, '원본 Y/TRAIN에 4행 이상과 두 종류 이상의 유효한 정답이 필요합니다.');
    END IF;
  END;

  -- [TRAIN-CHECK] 실제 학습 제공 행만 검사하며 TEST는 학습하지 않습니다.
  PROCEDURE validate_prepared IS
  BEGIN
    SELECT COUNT(*)
         , COUNT(DISTINCT LABEL)
      INTO v_train
         , v_classes
      FROM OML_MISSION_PREPARED
     WHERE PREP_MODE = p_mode
       AND SOURCE_KIND = 'TRAIN'
       AND USE_YN = 'Y'
       AND FIT_YN = 'Y'
       AND LABEL IN ({{CLASSES}})
    ;
    IF v_train < 4 OR v_classes < 2 THEN
      RAISE_APPLICATION_ERROR(-20022, '전처리 저장 후 FIT_YN=Y 학습 행을 확인하세요. 4행 이상·두 정답 종류가 필요합니다.');
    END IF;
  END;

  -- [OML-CREATE-RAW] 입력 p_sql은 아래 SQL-TRAIN의 RAW SELECT 원문입니다.
  PROCEDURE create_raw_model IS
    v_settings DBMS_DATA_MINING.SETTING_LIST;
  BEGIN
    v_settings('ALGO_NAME') := 'ALGO_DECISION_TREE';
    v_settings('PREP_AUTO') := 'ON';
    v_settings('TREE_TERM_MAX_DEPTH') := '6';
    -- [CREATE-MODEL] CASE_ID=행 식별자, LABEL=정답, 나머지 SELECT 컬럼=설명변수.
    DBMS_DATA_MINING.CREATE_MODEL2(
          model_name => 'OML_MISSION_RAW_MODEL'
         , mining_function => 'CLASSIFICATION'
         , data_query => p_sql
         , set_list => v_settings
         , case_id_column_name => 'CASE_ID'
         , target_column_name => 'LABEL'
    );
  END;
  -- [/OML-CREATE-RAW]

  -- [OML-DROP-RAW] 선택 모델과 그 모델의 내부 객체는 Oracle API로 정리합니다.
  PROCEDURE drop_raw_model IS
  BEGIN
    DBMS_DATA_MINING.DROP_MODEL('OML_MISSION_RAW_MODEL');
  END;
  -- [/OML-DROP-RAW]

  -- [OML-CREATE-CLEAN] 입력 p_sql은 아래 SQL-TRAIN의 CLEAN SELECT 원문입니다.
  PROCEDURE create_clean_model IS
    v_settings DBMS_DATA_MINING.SETTING_LIST;
  BEGIN
    v_settings('ALGO_NAME') := 'ALGO_DECISION_TREE';
    v_settings('PREP_AUTO') := 'ON';
    v_settings('TREE_TERM_MAX_DEPTH') := '6';
    -- [CREATE-MODEL] CASE_ID=행 식별자, LABEL=정답, 나머지 SELECT 컬럼=설명변수.
    DBMS_DATA_MINING.CREATE_MODEL2(
          model_name => 'OML_MISSION_CLEAN_MODEL'
         , mining_function => 'CLASSIFICATION'
         , data_query => p_sql
         , set_list => v_settings
         , case_id_column_name => 'CASE_ID'
         , target_column_name => 'LABEL'
    );
  END;
  -- [/OML-CREATE-CLEAN]

  -- [OML-DROP-CLEAN] 선택 모델과 그 모델의 내부 객체는 Oracle API로 정리합니다.
  PROCEDURE drop_clean_model IS
  BEGIN
    DBMS_DATA_MINING.DROP_MODEL('OML_MISSION_CLEAN_MODEL');
  END;
  -- [/OML-DROP-CLEAN]

BEGIN
{{OWNER_GUARD}}  IF p_mode IS NULL OR p_mode NOT IN ('RAW', 'CLEAN') THEN
    RAISE_APPLICATION_ERROR(-20001, 'p_mode는 RAW 또는 CLEAN입니다.');
  END IF;
  v_model := CASE p_mode WHEN 'RAW' THEN 'OML_MISSION_RAW_MODEL' ELSE 'OML_MISSION_CLEAN_MODEL' END;

  v_model_name := SUBSTR(v_model, INSTR(v_model, '.') + 1);

  -- [PREPARE-ACTION] 원본/모델/다른 방식/예측 준비행은 보존합니다.
  IF p_action = 'PREPARE' THEN
    -- INSERT 또는 제약 검사 실패 시 이 작업의 DELETE까지 되돌립니다.
    SAVEPOINT oml_prepare_rows;
    BEGIN
      IF p_mode = 'RAW' THEN prepare_raw_data; ELSE prepare_clean_data; END IF;
    EXCEPTION
      WHEN OTHERS THEN
        ROLLBACK TO oml_prepare_rows;
        RAISE;
    END;
    COMMIT;
    p_sql := '
SELECT PREP_MODE
     , SOURCE_KIND
     , CASE_ID
     , {{FEATURE_1}}
     , {{FEATURE_2}}
     , {{FEATURE_3}}
     , LABEL
     , USE_YN
     , FIT_YN
     , EXCLUDE_REASON
     , PREPARED_AT
  FROM OML_MISSION_PREPARED
 WHERE PREP_MODE = :selected_mode
   AND SOURCE_KIND IN (''TRAIN'', ''TEST'')
 ORDER BY SOURCE_KIND
     , CASE_ID
';
    OPEN p_result FOR p_sql USING p_mode;
    RETURN;
  END IF;
  -- [/PREPARE-ACTION]

  -- [VALIDATE-TRAIN] 직접 INSERT 후 검사하고 성공하면 호출자가 COMMIT합니다.
  IF p_action = 'VALIDATE' THEN
    validate_source;
    p_sql := 'SELECT ''VALIDATED'' STATUS FROM DUAL';
    OPEN p_result FOR p_sql;
    RETURN;
  END IF;

  -- [MODEL-LIFECYCLE] INIT은 기존 모델 덮어쓰기 금지, 나머지 모델 작업은 존재 여부 확인.
  SELECT COUNT(*)
    INTO v_exists
    FROM USER_MINING_MODELS
   WHERE MODEL_NAME = v_model_name
  ;
  IF p_action = 'INIT' AND v_exists > 0 THEN
    RAISE_APPLICATION_ERROR(-20020, '이미 모델이 있습니다. 전체 재학습 또는 삭제를 선택하세요.');
  END IF;
  IF p_action IN ('RETRAIN', 'ADD_TRAIN', 'DELETE', 'EVALUATE', 'PREDICT') AND v_exists = 0 THEN
    RAISE_APPLICATION_ERROR(-20021, '모델이 없습니다. 전처리 저장 후 최초 학습을 실행하세요.');
  END IF;
  IF p_action = 'DELETE' THEN
    -- [DELETE-MODEL] 선택 모델만 삭제합니다. 원본·준비 테이블과 다른 모델은 유지합니다.
    IF p_mode = 'RAW' THEN
      p_sql := 'BEGIN DBMS_DATA_MINING.DROP_MODEL(''OML_MISSION_RAW_MODEL''); END;';
      drop_raw_model;
    ELSE
      p_sql := 'BEGIN DBMS_DATA_MINING.DROP_MODEL(''OML_MISSION_CLEAN_MODEL''); END;';
      drop_clean_model;
    END IF;
    OPEN p_result FOR
      SELECT v_model MODEL_NAME
           , p_mode VARIANT
           , 'DELETED' STATUS
        FROM DUAL
      ;
    RETURN;
  END IF;

  IF p_action IN ('TRAIN', 'INIT', 'RETRAIN', 'ADD_TRAIN') THEN
    -- [SQL-TRAIN] 전처리는 저장 단계에서 끝났습니다. 실제 학습 제공 행만 읽습니다.
    IF p_mode = 'RAW' THEN
      p_sql := q'~
SELECT CASE_ID
     , {{FEATURE_1}}
     , {{FEATURE_2}}
     , {{FEATURE_3}}
     , LABEL
  FROM OML_MISSION_PREPARED
 WHERE PREP_MODE = 'RAW'
   AND SOURCE_KIND = 'TRAIN'
   AND FIT_YN = 'Y'
~';
    ELSE
      p_sql := q'~
SELECT CASE_ID
     , {{FEATURE_1}}
     , {{FEATURE_2}}
     , {{FEATURE_3}}
     , LABEL
  FROM OML_MISSION_PREPARED
 WHERE PREP_MODE = 'CLEAN'
   AND SOURCE_KIND = 'TRAIN'
   AND FIT_YN = 'Y'
~';
    END IF;
  ELSIF p_action = 'EVALUATE' THEN
    -- [SQL-EVALUATE] 정제된 같은 TEST 행을 단순 조회하여 평가합니다.
    IF p_mode = 'RAW' THEN
      p_sql := q'~
SELECT 'RAW' VARIANT
     , ACTUAL
     , PREDICTED
     , COUNT(*) N
  FROM
     (
      SELECT d.LABEL ACTUAL
           , PREDICTION(OML_MISSION_RAW_MODEL USING d.*) PREDICTED
        FROM
           (
            SELECT CASE_ID
                 , {{FEATURE_1}}
                 , {{FEATURE_2}}
                 , {{FEATURE_3}}
                 , LABEL
              FROM OML_MISSION_PREPARED
             WHERE PREP_MODE = 'RAW'
               AND SOURCE_KIND = 'TEST'
               AND USE_YN = 'Y'
               AND LABEL IN ({{CLASSES}})
           ) d
     )
 GROUP BY ACTUAL
     , PREDICTED
~';
    ELSE
      p_sql := q'~
SELECT 'CLEAN' VARIANT
     , ACTUAL
     , PREDICTED
     , COUNT(*) N
  FROM
     (
      SELECT d.LABEL ACTUAL
           , PREDICTION(OML_MISSION_CLEAN_MODEL USING d.*) PREDICTED
        FROM
           (
            SELECT CASE_ID
                 , {{FEATURE_1}}
                 , {{FEATURE_2}}
                 , {{FEATURE_3}}
                 , LABEL
              FROM OML_MISSION_PREPARED
             WHERE PREP_MODE = 'CLEAN'
               AND SOURCE_KIND = 'TEST'
               AND USE_YN = 'Y'
               AND LABEL IN ({{CLASSES}})
           ) d
     )
 GROUP BY ACTUAL
     , PREDICTED
~';
    END IF;
  ELSIF p_action = 'PREDICT' THEN
    -- [SQL-PREDICT] 아래 준비 처리 후 저장된 예측 특성만 읽습니다.
    IF p_mode = 'RAW' THEN
      p_sql := q'~
SELECT d.CASE_ID
     , PREDICTION(OML_MISSION_RAW_MODEL USING d.*) PREDICTED
     , PREDICTION_PROBABILITY(OML_MISSION_RAW_MODEL USING d.*) PROBABILITY

  FROM
     (
      SELECT CASE_ID
           , {{FEATURE_1}}
           , {{FEATURE_2}}
           , {{FEATURE_3}}
        FROM OML_MISSION_PREPARED
       WHERE PREP_MODE = 'RAW'
         AND SOURCE_KIND = 'PREDICT'
     ) d
 ORDER BY d.CASE_ID
~';
    ELSE
      p_sql := q'~
SELECT d.CASE_ID
     , PREDICTION(OML_MISSION_CLEAN_MODEL USING d.*) PREDICTED
     , PREDICTION_PROBABILITY(OML_MISSION_CLEAN_MODEL USING d.*) PROBABILITY

  FROM
     (
      SELECT CASE_ID
           , {{FEATURE_1}}
           , {{FEATURE_2}}
           , {{FEATURE_3}}
        FROM OML_MISSION_PREPARED
       WHERE PREP_MODE = 'CLEAN'
         AND SOURCE_KIND = 'PREDICT'
     ) d
 ORDER BY d.CASE_ID
~';
    END IF;
  ELSE
    RAISE_APPLICATION_ERROR(-20001, 'p_action: PREPARE/INIT/RETRAIN/ADD_TRAIN/DELETE/VALIDATE/EVALUATE/PREDICT, p_mode: RAW/CLEAN');
  END IF;

  IF p_action IN ('TRAIN', 'INIT', 'RETRAIN', 'ADD_TRAIN') THEN
    validate_source;
    validate_prepared;
    -- [MODEL-DDL] 모든 검사 성공 후에만 DDL을 실행합니다. DROP/CREATE는 자동 커밋합니다.
    -- [OML-ACTIONS] 준비된 선택 방식의 전체 FIT_YN=Y를 학습합니다. 전처리를 재실행하지 않습니다.
    IF p_action = 'INIT' THEN
      IF p_mode = 'RAW' THEN create_raw_model; ELSE create_clean_model; END IF;
    ELSIF p_action = 'RETRAIN' THEN
      IF p_mode = 'RAW' THEN
        drop_raw_model;
        create_raw_model;
      ELSE
        drop_clean_model;
        create_clean_model;
      END IF;
    ELSIF p_action = 'ADD_TRAIN' THEN
      -- 원본 추가 → VALIDATE/COMMIT → PREPARE를 마친 현재 전체 행으로 재생성합니다.
      IF p_mode = 'RAW' THEN
        drop_raw_model;
        create_raw_model;
      ELSE
        drop_clean_model;
        create_clean_model;
      END IF;
    ELSE
      -- TRAIN은 이전 호출 호환입니다. 준비행 검사는 위와 동일합니다.
      IF v_exists > 0 THEN
        IF p_mode = 'RAW' THEN drop_raw_model; ELSE drop_clean_model; END IF;
      END IF;
      IF p_mode = 'RAW' THEN create_raw_model; ELSE create_clean_model; END IF;
    END IF;
    -- [/OML-ACTIONS]
    OPEN p_result FOR
      SELECT v_model MODEL_NAME
           , p_mode VARIANT
           , 'CREATED' STATUS
        FROM DUAL
      ;
  ELSIF p_action = 'PREDICT' THEN
    -- 선택 방식의 새 입력만 INSERT SELECT로 준비하고 예측합니다.
    -- TRAIN/TEST 준비행과 모델에는 영향을 주지 않습니다.
    SAVEPOINT oml_predict_rows;
    BEGIN
      IF p_mode = 'RAW' THEN prepare_raw_prediction; ELSE prepare_clean_prediction; END IF;
      OPEN p_result FOR p_sql;
    EXCEPTION
      WHEN OTHERS THEN
        ROLLBACK TO oml_predict_rows;
        RAISE;
    END;
    COMMIT;
  ELSE
    -- [OPEN-RESULT] TEST는 PREPARED의 같은 Y/TEST 전체로 평가합니다.
    OPEN p_result FOR p_sql;
  END IF;
END;
/
