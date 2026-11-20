"""기존 실행 안내 주소의 호환 진입점. 새 코딩도움말을 사용합니다."""
from .coding_help import describe
EXPERIMENTS=('baseline',)
def execution_script(operation,variant='RAW',experiment='baseline'):
    return describe(operation,variant=variant)
def assignment_script(key,action,payload=None):
    raise ValueError('미션은 선택 미션 SQL 가이드를 사용하며 창의는 안내 쿼리를 제공하지 않습니다.')
