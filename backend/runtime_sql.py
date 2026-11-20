"""Read-only coding-help rendering of real query templates with current input values."""
import re
from . import sql_trace

# Skip literals/comments when finding Oracle input binds. OUT binds remain declared variables.
TOKENS = re.compile(r"q'(?P<q>[\[({<]).*?[\])}>]'|'(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"|--[^\n]*|/\*.*?\*/|:(?P<bind>[A-Za-z][A-Za-z0-9_]*)",re.S|re.I)
OUT_BINDS = {'p_result','p_sql'}

def bind_names(sql):
    return {match['bind'] for match in TOKENS.finditer(sql) if match['bind']}

def selected_sql(source_path, sql, result, mode=None):
    """Never fetch data, invent CSV values or execute SQL; unknown inputs stay in source only."""
    from .coding_help import _basic_owner, _guard_basic_sql, MODEL_ACTIONS
    assignment=result.get('assignment','basic')
    if assignment not in ('basic','mission'):return None
    owner=result.get('owner') or result.get('schema') or result.get('application',{}).get('owner')
    if not owner:return None
    owner=_basic_owner(owner)
    operation=result['operation'];mode=mode or result.get('variant','RAW')
    if operation not in {'status','connection','data','prepared-data','prediction-data','columns','model-dictionary',*MODEL_ACTIONS}:return None
    if mode not in ('RAW','CLEAN'):return None
    prefix='OML_'+assignment.upper()
    cfg={'training_table':prefix+'_DATA','prediction_table':prefix+'_PREDICT','prepared_table':prefix+'_PREPARED','procedure_name':prefix+'_RUN'}
    filename=source_path.rsplit('/',1)[-1]
    if not source_path.startswith('sql/queries/'):return None
    # Readiness checks inspect several tables; do not guess which columns.sql call this excerpt represents.
    if filename=='columns.sql' and operation!='columns':return None
    if filename=='call_classifier.sql' and assignment=='mission':
        sql=sql.replace('OML_BASIC_RUN',cfg['procedure_name'])
    target=cfg['prepared_table'] if filename.startswith('prepared_') or filename=='clear_prepared.sql' else (
        cfg['prediction_table'] if operation in ('prediction-data','prediction-import','columns') else cfg['training_table'])
    if filename=='custom_fingerprint_rows.sql':target=cfg['training_table']
    metadata_table=cfg['prepared_table'] if operation=='prepared-data' else cfg['training_table'] if operation=='import' else cfg['prediction_table']
    values={**cfg,'owner':owner,'variant':mode,'source_kind':result.get('source_kind','ALL'),
            'use_yn':'ALL','split':'ALL','table_name':metadata_table,
            'model_name':prefix+'_'+mode+'_MODEL','raw_model':prefix+'_RAW_MODEL','clean_model':prefix+'_CLEAN_MODEL',
            'p_mode':mode}
    if operation in MODEL_ACTIONS:values['p_action']=MODEL_ACTIONS[operation]
    # Only known UI/API choices; do not accept arbitrary request data or credentials.
    values.update({key:value for key,value in result.get('binds',{}).items() if key in values or key=='p_action'})
    values['variant']=mode;values['p_mode']=mode
    placeholders=set(re.findall(r'\{\{([a-z_]+)\}\}',sql))
    replacements={'table':target}
    if placeholders-set(replacements):return None
    for name in placeholders:sql=sql.replace('{{'+name+'}}',replacements[name])
    names=bind_names(sql);outs=names&OUT_BINDS
    if names-set(values)-OUT_BINDS:return None
    # Only the RUN call has these two known OUT parameters.
    if outs and (filename!='call_classifier.sql' or outs!=OUT_BINDS):return None
    bound=sql_trace.rendered(sql,{name:values[name] for name in names if name in values})
    if bind_names(bound)-OUT_BINDS or '{{' in re.sub(r'--[^\n]*','',bound):return None
    changed=bool(names or placeholders or re.search(r'\b'+prefix+r'_[A-Z0-9_]+\b',bound))
    if not changed:return None
    if outs:
        bound='VARIABLE p_result REFCURSOR\nVARIABLE p_sql CLOB\n'+bound.rstrip().rstrip('/')+'\n/\nPRINT p_result\nPRINT p_sql\n'
    else:
        body=bound.rstrip()
        if not body.endswith((';','/')):body+=';'
        bound=body+'\n'
    header='-- 현재 선택값을 적용한 SQL Developer F5 실행용 · 도움말에서는 실행하지 않습니다.\n'
    header+='-- 원본: '+source_path+' · '+mode
    if filename=='prepared_rows.sql':header+=' · '+str(values['source_kind'])
    header+='\n'
    return header+_guard_basic_sql(bound,owner,prefix+'_')

def add_runtime_items(flow, result):
    """Keep original file ranges intact and add independent generated runtime items beside them."""
    stage=next(entry for entry in flow['stages'] if entry['id']=='sql')
    items=[];seen=set();modes=('RAW','CLEAN') if result.get('variant')=='BOTH' else (result.get('variant','RAW'),)
    for item in stage['items']:
        items.append(item)
        if item['origin']!='source':continue
        for mode in modes:
            script=selected_sql(item['path'],item['content'],result,mode)
            if not script or (item['path'],script) in seen:continue
            seen.add((item['path'],script))
            title='실행용 런타임 SQL · '+item['path'].rsplit('/',1)[-1]+' · '+mode
            items.append({'id':'sql-runtime-'+str(len(seen)),'title':title,'path':'현재 선택값 · '+item['path'],
                          'line':None,'end_line':None,'content':script,'role':'발급 계정·선택값 반영 · 전체 복사 후 SQL Developer F5 실행',
                          'kind':'sql-generated','origin':'generated','runtime_kind':'selected','source_path':item['path']})
    stage['items']=items
    return flow
