"""Git·백업·배포가 공유하는 명시적 공개 소스 목록입니다."""
import hashlib
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
APP_FILES=(
    'app.py',
    'manage.py',
    'backend/__init__.py',
    'backend/hosting.py',
    'backend/assignment_templates.py',
    'backend/basic_lifecycle.py',
    'backend/practice_evidence.py',
    'templates/practice-evidence.html',
    'static/js/practice-evidence.js',
    'sql/queries/clear_prepared.sql',
    'sql/reset_basic_objects.sql',
    'backend/basic_dataset.py',
    'backend/coding_help.py',
    'backend/coding_flow.py',
    'backend/runtime_sql.py',
    'backend/connection_help.py',
    'backend/connection_profile.py',
    'backend/db.py',
    'backend/csv_import.py',
    'sql/queries/custom_count.sql',
    'backend/execution_scripts.py',
    'backend/identity.py',
    'backend/model_dictionary.py',
    'backend/mission_guide.py',
    'backend/mission_binding.py',
    'backend/operation_help.py',
    'backend/service.py',
    'backend/progress_store.py',
    'sql/web_state.sql',
    'sql/queries/progress_read.sql',
    'sql/queries/progress_write.sql',
    'backend/source_help.py',
    'backend/sql_files.py',
    'backend/sql_trace.py',
    'backend/validation.py',
    'templates/dataset-overview.html',
    'templates/dataset-viewer.html',
    'templates/execution-dialog.html',
    'templates/index.html',
    'templates/login-gate.html',
    'templates/object-names.html',
    'templates/model-lab.html',
    'templates/workflow-sections.html',
    'templates/object-naming-guide.html',
    'templates/pages/assignment-template.html',
    'templates/pages/basic.html',
    'templates/pages/data.html',
    'templates/pages/home.html',
    'templates/pages/main.html',
    'templates/pages/models.html',
    'templates/pages/predictions.html',
    'templates/pages/prediction-contract.html',
    'static/css/studio.css',
    'static/css/intro.css',
    'static/images/paichai-campus-night.jpg',
    'static/css/main-page.css',
    'static/css/style.css',
    'static/js/assignment-template.js',
    'static/js/basic-dataset.js',
    'static/js/mission-schema.js',
    'static/js/mission-learning.js',
    'static/js/execution-dialog.js',
    'static/js/help-window.js',
    'static/js/layer-message.js',
    'static/js/code-highlight.js',
    'static/js/main.js',
    'static/js/request-progress.js',
    'static/js/main-page.js',
    'sql/classifier.sql',
    'sql/custom/creative/01_tables.sql',
    'sql/custom/creative/02_procedure.sql',
    'sql/custom/mission/01_tables.sql',
    'sql/custom/mission/02_procedure.sql',
    'sql/custom/mission/guide_procedure.sql',
    'sql/prediction_table.sql',
    'sql/prepared_table.sql',
    'sql/queries/prepared_rows.sql',
    'sql/queries/prepared_fingerprint_rows.sql',
    'sql/queries/prepared_count.sql',
    'sql/queries/call_classifier.sql',
    'sql/queries/csv_owner.sql',
    'sql/queries/dictionary_model.sql',
    'sql/queries/dictionary_attributes.sql',
    'sql/queries/dictionary_settings.sql',
    'sql/queries/dictionary_views.sql',
    'sql/queries/dictionary_xforms.sql',
    'sql/queries/dictionary_object.sql',
    'sql/queries/dictionary_detail_example.sql',
    'sql/queries/dictionary_generated_objects.sql',
    'sql/queries/dictionary_generated_columns.sql',
    'sql/queries/dictionary_detail_rows.sql',
    'sql/queries/columns.sql',
    'sql/queries/schema_columns.sql',
    'sql/queries/compile_errors.sql',
    'sql/queries/connection_info.sql',
    'sql/queries/connection_profile.sql',
    'sql/queries/custom_delete.sql',
    'sql/queries/custom_insert.sql',
    'sql/queries/custom_rows.sql',
    'sql/queries/delete_prediction.sql',
    'sql/queries/delete_row.sql',
    'sql/queries/delete_training.sql',
    'sql/queries/insert_prediction.sql',
    'sql/queries/insert_training.sql',
    'sql/queries/model_details.sql',
    'sql/queries/models.sql',
    'sql/queries/assignment_models.sql',
    'sql/queries/custom_fingerprint_rows.sql',
    'sql/queries/objects.sql',
    'sql/queries/prediction_rows.sql',
    'sql/queries/prediction_storage.sql',
    'sql/queries/procedure_arguments.sql',
    'sql/queries/procedure_errors.sql',
    'sql/queries/procedure_source.sql',
    'sql/queries/save_row.sql',
    'sql/queries/training_count.sql',
    'sql/queries/training_rows.sql',
    'sql/recreate_training.sql',
    'sql/schema.sql',
    'sql/session.sql',
    'sql/table_comments.sql',
    'data/catalog.json',
    'data/classification.csv',
    'data/examples/esports.csv',
    'data/examples/esports_prediction.csv',
    'data/examples/festival.csv',
    'data/examples/festival_prediction.csv',
    'data/examples/ott.csv',
    'data/examples/ott_prediction.csv',
    'data/examples/resale.csv',
    'data/examples/resale_prediction.csv',
    'data/examples/space.csv',
    'data/examples/space_prediction.csv',
    'data/examples/wifi.csv',
    'data/examples/wifi_prediction.csv',
    'data/examples/bike.csv',
    'data/examples/bike_prediction.csv',
    'data/examples/maker.csv',
    'data/examples/maker_prediction.csv',
    'data/examples/package.csv',
    'data/examples/package_prediction.csv',
    'data/examples/greenhouse.csv',
    'data/examples/greenhouse_prediction.csv',
    'data/examples/delivery.csv',
    'data/examples/delivery_prediction.csv',
    'data/examples/appux.csv',
    'data/examples/appux_prediction.csv',
    'data/prediction.csv',
    'data/stock-source.json',
    'reference/student/assignment-template-guide.html',
)
APP_FILES=(*APP_FILES,'sql/examples/run.sql')
STUDENT_SCRIPTS=('render-build.sh','render-start.sh','load_mission_csv.py','common.ps1','setup.ps1','terminal-init.ps1','check-environment.ps1','db-init.ps1','deploy-github.ps1','git_publish.py',
'start.ps1','stop.ps1','restart.ps1','submit.ps1','package_submission.py','source_files.py','distribution_guard.py')
STUDENT_GUIDE='COM22417_과제설명및평가.html'
CONFIG=('.gitignore','.gitattributes','.vscode/settings.json','.vscode/extensions.json','.vscode/launch.json',
'requirements.txt','security/student.env.example','security/students.example.json')
# 강사 운영·검증 파일 목록은 학생 실행 소스와 분리합니다.
_PUBLIC_CATALOG=ROOT/'reference/distribution/public-files.json'
_PUBLIC_EXTRAS=json.loads(_PUBLIC_CATALOG.read_text(encoding='utf-8')) if _PUBLIC_CATALOG.is_file() else []
PUBLIC=(*APP_FILES,*('scripts/'+n for n in STUDENT_SCRIPTS),*CONFIG,*_PUBLIC_EXTRAS)

def safe_path(name):
    if not isinstance(name,str) or '\\' in name or ':' in name or '..' in name.split('/'): return False
    path=Path(name)
    if path.is_absolute() or any(p.startswith('.') and p!='.vscode' for p in path.parts):
        return name in ('.gitignore','.gitattributes')
    return name in PUBLIC or (name.startswith('submission/') and path.suffix.lower() in {'.pdf','.html','.txt','.pptx','.ppt','.png','.jpg','.json','.csv'})
def student_git_path(name):
    """학생 배포 목록 및 학생이 추가한 실행 소스만 Git 대상 경로로 허용합니다."""
    if not isinstance(name,str) or '\\' in name or ':' in name:
        return False
    path=Path(name)
    if path.is_absolute() or any(p in ('','..','.') for p in name.split('/')):
        return False
    if name in (STUDENT_GUIDE,'security/students.json'): return True
    if name in (*APP_FILES,*('scripts/'+n for n in STUDENT_SCRIPTS),*CONFIG):
        return True
    if any(part.startswith('.') or part=='__pycache__' for part in path.parts):
        return False
    return (len(path.parts)==1 and path.suffix.lower()=='.py') or (
        path.parts[0] in ('backend','sql','templates','static','data')
        and path.suffix.lower() in ('.py','.sql','.html','.css','.js','.json','.csv','.svg','.png','.jpg','.webp'))

def inventory(root=ROOT,audience='all'):
    root=Path(root).resolve()
    if audience not in ('all','student','submission','student-git'): raise ValueError('Unknown audience')
    if audience=='all' and not _PUBLIC_CATALOG.is_file():
        raise ValueError('Public source catalog is missing: reference/distribution/public-files.json')
    names=PUBLIC if audience=='all' else (*APP_FILES,*('scripts/'+n for n in STUDENT_SCRIPTS),*CONFIG)
    if audience in ('submission','student-git'):
        # 학생의 제출·Git 업로드는 추가 Python·SQL·화면·데이터도 수집합니다.
        # 강사의 공통 배포 ZIP과 백업은 명시적 목록만 사용합니다.
        candidates=list(root.glob('*.py'))
        if audience=='student-git': candidates.extend((root/STUDENT_GUIDE,root/'security/students.json'))
        for folder in ('backend','sql','templates','static','data'):
            candidates.extend((root/folder).rglob('*'))
        additions=(path.relative_to(root).as_posix() for path in candidates
                   if path.is_file() and student_git_path(path.relative_to(root).as_posix()))
        names=tuple(dict.fromkeys((*names,*additions)))
    result={}
    for name in names:
        path=root/name
        if not path.is_file(): continue
        if not path.resolve().is_relative_to(root): raise ValueError('Source outside project')
        for part in (path,*path.parents):
            if part==root: break
            if part.is_symlink() or part.is_junction(): raise ValueError('Linked source: '+name)
        if audience!='all' and path.suffix.lower() in ('.md','.markdown'): continue
        result[name]=path.read_bytes()
    if audience=='submission':
        for path in (root/'submission').rglob('*'):
            if path.is_file():
                name=path.relative_to(root).as_posix()
                if safe_path(name) and not path.is_symlink() and path.resolve().is_relative_to(root):
                    result[name]=path.read_bytes()
    from distribution_guard import validate_files, validate_student_roster
    if audience=='student-git':
        if 'security/students.json' not in result:
            raise ValueError('본인 정보로 작성한 security/students.json이 필요합니다.')
        validate_student_roster(result['security/students.json'])
    validate_files(result,root)
    return result
def manifest(files):
    return json.dumps({name:hashlib.sha256(raw).hexdigest() for name,raw in sorted(files.items())},indent=2)+'\n'
