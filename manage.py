"""프로젝트 경로를 기준으로 실행합니다. Wallet은 로컬 설정, DB 계정은 웹 로그인에서 등록합니다."""
import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main(application_factory=None):
    parser = argparse.ArgumentParser(description='COM22417 Classification Studio')
    parser.add_argument('command', nargs='?', default='serve', choices=('check', 'init', 'verify', 'serve'))
    parser.add_argument('--port', type=int, default=int(os.environ.get('PORT', '22417')))
    parser.add_argument('--log-files', action='store_true', help='Write background server output under this project runtime directory.')
    args = parser.parse_args()
    if args.command == 'serve':
        if args.log_files:
            # 한글·공백·대괄호가 있는 경로도 실제 폴더 이름 그대로 엽니다.
            # 패키지를 읽기 전에 로그를 열어 설치 오류도 기록합니다. F5는 콘솔을 씁니다.
            runtime = ROOT / 'runtime'
            runtime.mkdir(parents=True, exist_ok=True)
            sys.stdout = (runtime / 'server.out.log').open('w', encoding='utf-8', buffering=1)
            sys.stderr = (runtime / 'server.err.log').open('w', encoding='utf-8', buffering=1)
        import uvicorn
        if application_factory is None:
            from app import create_app
            application_factory = create_app
        # Keep the running login/DB pool when source files are saved. Restart explicitly for Python changes.
        uvicorn.run(application_factory(), host='127.0.0.1', port=args.port, log_level='info', reload=False)
        return
    from backend.db import connection, safe_error
    from backend.sql_files import initialize, query
    from backend import service
    try:
        with connection() as conn:
            if args.command == 'check':
                print(json.dumps(query(conn, 'connection_info.sql'), ensure_ascii=False))
            elif args.command == 'init':
                initialize(conn)
                print('SQL 컴파일 완료 · 기존 데이터 보존')
                print('테이블: sql/schema.sql + sql/prediction_table.sql + sql/prepared_table.sql')
                print('프로시저: sql/classifier.sql → OML_BASIC_RUN')
                print('모델 학습은 아직 실행하지 않았습니다. 다음: 웹에서 최초 학습(모델 없음) 또는 전체 재학습 → TEST 비교 → 모델 선택·확정')
            else:
                print(json.dumps(service.status(conn), ensure_ascii=False, default=str))
    except Exception as error:
        print(str(error) if isinstance(error, RuntimeError) else safe_error(error), file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
