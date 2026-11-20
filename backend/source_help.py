"""인증된 소스 도움말. 등록된 경로만 읽고 개인 환경파일·명단·Wallet은 읽지 않습니다."""
from . import sql_trace
SOURCES={
 'schema':('sql/schema.sql','CREATE TABLE'),
 'prepared-table':('sql/prepared_table.sql','CREATE TABLE'),
 'prepare-procedure':('sql/classifier.sql','[OML-PREPARE-RAW]'),
 'prepared-selection':('sql/queries/prepared_rows.sql','[PREPARED-SELECT]'),
 'prediction-table':('sql/prediction_table.sql','CREATE TABLE'),
 'train-procedure':('sql/classifier.sql','[CREATE-MODEL]'),
 'predict-procedure':('sql/classifier.sql','[SQL-PREDICT]'),
 'metrics':('sql/classifier.sql','[SQL-EVALUATE]'),
 'service':('backend/service.py','[CALL-PROCEDURE]'),
 'sql-runner':('backend/sql_files.py','[EXECUTE-SQL]'),
 'selection':('sql/queries/training_rows.sql','[DATA-SELECT]'),
 'import-procedure':('sql/queries/insert_training.sql','[CSV-INSERT]'),
 'assignment-backend':('backend/assignment_templates.py','[ASSIGNMENT-CONNECTION]'),
 'assignment-html':('templates/pages/assignment-template.html','data-assignment'),
 'assignment-js':('static/js/assignment-template.js','async function assignmentTask'),
 'web-entry':('app.py','def create_app('),
 'browser':('static/js/main.js','async function api('),
 'table-comments':('sql/table_comments.sql','COMMENT ON'),
 'html-data':('templates/pages/data.html','id="import-form"'),
 'html-models':('templates/model-lab.html','macro model_lab('),
 'html-predictions':('templates/pages/predictions.html','id="run"'),
 'prediction-contract':('templates/pages/prediction-contract.html','[PREDICTION-CONTRACT]'),
 'html-home':('templates/pages/home.html','id="project-title"'),
 'compile-script':('scripts/db-init.ps1','param('),
 'assignment-guide':('reference/student/assignment-template-guide.html','<h1>'),
 'dictionary-model':('sql/queries/dictionary_model.sql','[MODEL-DICTIONARY]'),
 'dictionary-backend':('backend/model_dictionary.py','def read('),
 'layer-confirmation':('static/js/layer-message.js','function askConfirmation('),
 'layer-window':('static/js/help-window.js','function attachDrag('),
 'object-names':('templates/object-names.html','macro object_names('),
 'object-naming-guide':('templates/object-naming-guide.html','공통 명명규칙'),
}
for task in ('mission','creative'):
    SOURCES[task+'-tables']=(f'sql/custom/{task}/01_tables.sql','--')
    SOURCES[task+'-procedure']=(f'sql/custom/{task}/02_procedure.sql','--')

def read_source(key):
    path,keyword=SOURCES[key]
    return {**sql_trace.source(path,keyword),'key':key,'symbol':keyword}
