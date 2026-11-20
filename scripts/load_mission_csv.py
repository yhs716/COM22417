"""로컬 CSV 파일을 선택한 미션 테이블에 묶음 적재합니다. DDL·모델 생성은 수행하지 않습니다."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.db import connection, close_connections, safe_error, student_settings
from backend.csv_import import csv_snapshot, validate_csv, load_mission_csv


def main():
    catalog = json.loads((ROOT / 'data/catalog.json').read_text(encoding='utf-8'))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mission', required=True, choices=[item['key'] for item in catalog])
    parser.add_argument('--kind', choices=('training', 'prediction'), default='training')
    parser.add_argument('--file', required=True, type=Path, help='절대 경로 또는 프로젝트 루트 기준 CSV 경로')
    parser.add_argument('--owner', required=True, help='본인 발급 DB 계정. 비밀번호는 인수로 받지 않습니다.')
    parser.add_argument('--replace', action='store_true', help='해당 테이블의 기존 행 전체 교체에 동의')
    args = parser.parse_args()
    item = next(item for item in catalog if item['key'] == args.mission)
    path = args.file if args.file.is_absolute() else ROOT / args.file
    prediction = args.kind == 'prediction'
    try:
        with csv_snapshot(path) as stream:
            count = validate_csv(stream, item, prediction)
            if not args.replace:
                print(f'CSV 검사 완료: {count}행. DB 변경 없음. 교체하려면 명령 끝에 --replace를 추가하세요.')
                return 0
            cfg = student_settings()
            if args.owner != cfg.get('DB_USER', '').upper():
                raise ValueError('--owner와 현재 발급 DB 계정이 다릅니다. 웹 로그인 계정과 입력값을 확인하세요.')
            with connection(cfg) as conn:
                loaded = load_mission_csv(conn, stream, item, args.owner, prediction=prediction)
            print(f'{args.owner}.OML_MISSION_{"PREDICT" if prediction else "DATA"}: {loaded}행 적재·COMMIT 완료. 웹에서 다시 조회하세요.')
        return 0
    except Exception as error:
        message = '선택한 CSV 파일을 열 수 없습니다. --file 경로와 파일 읽기 권한을 확인하세요.' if isinstance(error, OSError) else safe_error(error)
        print(message, file=sys.stderr)
        return 1
    finally:
        close_connections()


if __name__ == '__main__':
    sys.exit(main())
