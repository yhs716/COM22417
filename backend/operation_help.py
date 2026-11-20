"""업무 오류를 작업 단계·원인·재시도 방법으로 안내합니다. 원본 접속 문자열은 내보내지 않습니다."""
import re
from .db import safe_error

HINTS = {
    'ORA-20022': ('저장된 모델 입력의 학습 제공 행이 부족합니다.', [
        '학습데이터에서 RAW/CLEAN을 선택해 전처리 저장을 실행하세요.',
        'PREPARED의 SOURCE_KIND=TRAIN, FIT_YN=Y 행이 4개 이상이고 정답이 두 종류인지 확인하세요.',
        '준비값·FIT_YN은 DB에서 수정·COMMIT할 수 있습니다. 다시 전처리 저장하면 이 수정값을 교체합니다.']),
    'ORA-20012': ('학습 정답 기간과 평가 기간이 겹치거나 기준 날짜가 잘못되었습니다.', [
        'WEEK_ENDING을 YYYY-MM-DD로 입력하세요. 이전 고객 예제라면 학습데이터에서 기본 주식 CSV를 교체 적재하세요.',
        '마지막 Y·TRAIN 날짜에 7일을 더한 날보다 첫 Y·TEST가 뒤여야 합니다. 기본 CSV의 2011-03-25는 USE_YN=N을 유지하세요.',
        'TEST 정답을 바꾸거나 무작위로 섞지 말고 날짜·SPLIT·USE_YN을 확인한 뒤 다시 생성하세요.']),
    'ORA-20006': ('학습 데이터가 부족하거나 정답 종류가 한 가지뿐입니다.', [
        '기본과제의 학습데이터 단계에서 USE_YN=Y·SPLIT=TRAIN을 확인하세요.',
        '유효한 BUY/SELL 두 종류와 4행 이상을 준비한 뒤 모델을 생성하세요. TEST 라벨을 바꾸지 마세요.']),
    'ORA-20007': ('학습 중 데이터가 변경되어 모델을 최신으로 사용할 수 없습니다.', [
        '원본 수정 후 전처리 저장을 마친 뒤 모델 생성·비교 단계에서 모델을 다시 생성하세요.']),
    'ORA-20008': ('현재 학습데이터로 생성한 모델이 없습니다.', [
        '모델 생성·비교 단계에서 정제 미적용 또는 적용 모델을 생성한 뒤 사용 모델을 확정하세요.']),
    'ORA-20009': ('예측에 사용할 최신 모델을 아직 확정하지 않았습니다.', [
        '4단계 · 예측 실행에서 최신 RAW/CLEAN 모델을 선택하고 예측 실행을 누르세요.',
        '선택할 최신 모델이 없으면 모델 생성·비교 단계에서 먼저 생성하세요.']),
    'ORA-40478': ('CSV 값이 SQL에 정의된 문자열 길이를 초과했습니다.', [
        'insert_training.sql의 적재 컬럼와 schema.sql의 컬럼 길이를 함께 확인하세요.']),
    'ORA-12899': ('적재할 값이 테이블 컬럼의 허용 길이를 초과했습니다.', [
        'CSV 값의 길이와 테이블 DDL의 VARCHAR2 길이를 비교하세요. 일반 교체 적재는 기존 행을 복원하지만, 재생성의 DROP은 롤백되지 않습니다.']),
    'ORA-12860': ('병렬 처리 내부의 행 잠금이 충돌했습니다.', [
        'session.sql의 병렬 DML·DDL·조회 비활성화 설정이 적용되는지 확인하세요.',
        '진행 중인 DB 작업이 끝난 뒤 다시 적재하세요. 계속 발생하면 담당자에게 오류 코드를 전달하세요.']),
    'ORA-12838': ('병렬 변경 작업과 후속 조회가 충돌했습니다.', [
        'session.sql의 직렬 실행 설정을 확인하고 서비스를 재시작한 뒤 다시 실행하세요.']),
    'ORA-00060': ('다른 트랜잭션과 잠금이 충돌했습니다.', [
        '같은 계정의 다른 SQL 작업을 완료하거나 롤백하고 다시 실행하세요.']),
    'ORA-00054': ('다른 작업이 테이블을 사용하고 있어 재생성하지 못했습니다.', [
        '같은 계정의 SQL 편집기와 실행 중인 DB 작업을 확인하고 완료 후 다시 재생성하세요.']),
    'ORA-00955': ('같은 이름의 객체가 이미 있습니다.', [
        '표시된 적재 테이블 ID를 확인하세요. 데이터만 바꾸려면 데이터 교체 적재를 사용하세요.',
        '테이블 구조를 처음부터 적용하려면 테이블 재생성 및 적재를 선택하세요.']),
    'ORA-00904': ('SQL에서 참조한 컬럼이 현재 테이블 구조와 다릅니다.', [
        'schema.sql의 DDL과 현재 컬럼을 비교하세요. 기존 컬럼은 CREATE TABLE 수정만으로 바뀌지 않습니다.',
        '데이터를 보존하려면 별도 ALTER를 적용하고, 초기화해도 된다면 테이블을 재생성하세요.']),
    'ORA-04063': ('SQL 객체에 컴파일 오류가 있습니다.', [
        '개발 도움말에서 DDL·프로시저를 확인한 뒤 .\\scripts\\db-init.ps1로 컴파일 결과를 확인하세요.']),
    'ORA-06550': ('프로시저 호출 또는 SQL 컴파일을 확인해야 합니다.', [
        'classifier.sql의 OML_BASIC_RUN 선언과 호출 이름을 확인한 뒤 SQL을 다시 컴파일하세요.']),
}


def explain(error, stage='DB 작업', *, training_dropped=False):
    codes = re.findall(r'ORA-\d{5}|DPY-\d{4}|DPI-\d{4}', str(error))
    code = next((item for item in codes if item in HINTS), codes[0] if codes else 'DB-OPERATION')
    title, steps = HINTS.get(code, (safe_error(error), ['관련 소스와 입력값을 확인하고 다시 실행하세요.']))
    sources = ['train-procedure','service'] if '모델 생성' in stage else ['service'] if '모델 확정' in stage else ['predict-procedure'] if '예측' in stage else []
    if code == 'ORA-06550':
        steps = ['기본과제의 OML_BASIC_RUN과 sql/classifier.sql의 선언·인자가 일치하는지 확인하세요.',
                 '프로젝트 터미널에서 아래 명령으로 컴파일하고 출력된 파일·객체·줄 번호를 수정하세요.']
    if training_dropped and not stage.startswith('적재 완료'):
        steps=[*steps,'원본 테이블의 DROP은 완료되어 이전 행이 복원되지 않습니다. 현황을 새로고침하여 테이블 존재 여부와 행 수를 확인하세요.',
               '테이블이 생성되어 있으면 오류 수정 후 같은 CSV를 일반 교체 적재하세요. 미생성이면 테이블·프로시저 준비 후 CSV를 적재하세요. 이후 전처리 저장 → 재학습 → 확정이 필요합니다.']
    return {'code': code, 'title': title, 'stage': stage, 'steps': steps, 'sources': sources,
            'commands': ['.\\scripts\\db-init.ps1'] if code in ('ORA-06550','ORA-04063') else [],
            'message': '데이터 적재는 완료되었습니다. 새로고침하여 테이블 상태를 다시 확인하세요.'
                       if stage.startswith('적재 완료') else '원본 삭제 완료 후 후속 작업이 실패했습니다. CSV INSERT는 롤백되어도 DROP 전의 데이터는 돌아오지 않습니다. 같은 CSV를 다시 적재해 복구하세요.'
                       if training_dropped else '원본 테이블의 DROP을 완료하지 못했습니다. 기존 테이블을 확인한 뒤 오류 원인을 해결하세요.'
                       if stage.startswith('테이블 재생성') else '적재 실패 시 DELETE·INSERT 데이터 변경은 롤백됩니다.'
                       if stage == 'CSV 데이터 교체 적재' else '오류 코드와 관련 소스를 확인한 뒤 다시 실행하세요.',
            'help_screen': 'data'}
