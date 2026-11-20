"""[MODEL-DICTIONARY] 선택 모델의 메타데이터와 자동 생성 객체를 SELECT로만 읽습니다."""
import re
from .sql_files import query, read_sql, execute

CATALOG=(
    ('model','USER_MINING_MODELS','모델 등록 정보','분류/알고리즘·생성 시각·학습 시간(초)·크기(MB)를 확인합니다. TEST 정확도는 이 뷰에 없으며 같은 TEST로 별도 평가합니다.','모델이 없습니다. 최초 학습 후 다시 조회하세요.',
     [('model_name','모델명'),('mining_function','학습 목적'),('algorithm','알고리즘'),('creation_date','생성 시각'),('build_duration','학습 시간(초)'),('model_size','크기(MB)'),('partitioned','파티션 여부'),('comments','설명')]),
    ('attributes','USER_MINING_MODEL_ATTRIBUTES','설명변수·타깃','모델 시그니처의 이름·논리 타입·DB 타입·정답 여부입니다. TARGET=YES가 타깃입니다. 학습 SELECT의 모든 컬럼이나 트리 분기 조건 전체를 뜻하지 않습니다.','등록된 모델 속성이 없습니다.',
     [('attribute_name','속성명'),('attribute_type','논리 타입'),('data_type','DB 타입'),('data_length','길이'),('data_precision','정밀도'),('data_scale','소수 자릿수'),('usage_type','사용 구분'),('target','타깃 여부')]),
    ('settings','USER_MINING_MODEL_SETTINGS','학습 설정','INPUT은 직접 지정한 값, DEFAULT는 Oracle 기본값입니다. PREP_AUTO는 Oracle 자동 처리이며 SQL의 수동 CASE 정제와 구분하세요.','등록된 설정이 없습니다.',
     [('setting_name','설정명'),('setting_value','설정값'),('setting_type','INPUT / DEFAULT')]),
    ('views','USER_MINING_MODEL_VIEWS','Oracle 모델 상세 뷰','Oracle이 제공하는 실제 상세 뷰 이름·종류를 찾습니다. 내용은 알고리즘·DB 버전에 따라 다르며 트리·중요도 등의 제공 여부를 이 목록에서 확인합니다.','이 모델에서 제공하는 상세 뷰가 없습니다.',
     [('view_name','상세 뷰 이름'),('view_type','상세 뷰 종류')]),
    ('xforms','USER_MINING_MODEL_XFORMS','사용자 지정 내장 변환','CREATE_MODEL2에 등록한 변환을 확인합니다. 현재 예제의 INSERT SELECT로 저장한 전처리 값은 여기 기록되지 않으므로 0행이어도 정제를 안 했다는 뜻은 아닙니다.','사용자 지정 내장 변환 0행입니다. SQL 전처리 여부와는 별개입니다.',
     [('attribute_name','속성명'),('attribute_subname','하위 속성'),('attribute_spec','속성 명세'),('expression','변환식'),('reverse','역변환 여부')]),
    ('object','USER_OBJECTS','DB 객체 상태','MINING MODEL 객체의 ID·VALID·DDL 시각입니다. VALID는 웹의 최신 학습 검증이나 사용 모델 확정을 뜻하지 않습니다.','MINING MODEL 객체가 없습니다.',
     [('object_name','객체명'),('object_type','객체 종류'),('object_id','객체 ID'),('status','DB 상태'),('created','생성 시각'),('last_ddl_time','마지막 DDL')]),
    ('generated_objects','USER_OBJECTS','자동 생성 테이블·뷰와 코드','모델 생성 시 Oracle이 만든 실제 객체입니다. DM$ + 객체 구분 코드 2자 + 지정 모델명으로 나눠 읽습니다. 코드 자체는 사용자가 모델명에 입력한 접두사가 아닙니다. 통계 행 수는 현재 COUNT(*)가 아닙니다.','이 모델의 자동 생성 객체가 없습니다.',
     [('object_name','자동 생성 객체명'),('internal_code','구분 코드'),('code_meaning','의미'),('object_type','실제 객체 종류'),('status','DB 상태'),('statistic_rows','통계 행 수')]),
    ('generated_columns','USER_TAB_COLUMNS','자동 생성 객체의 실제 컬럼','해당 테이블·뷰의 실제 컬럼과 타입입니다. 내부 저장 구조와 공개 조회용 상세 뷰를 구분하세요.','이 모델의 자동 생성 객체 컬럼이 없습니다.',
     [('object_name','객체명'),('column_id','순서'),('column_name','컬럼명'),('data_type','DB 타입'),('data_length','길이'),('data_precision','정밀도'),('data_scale','소수 자릿수'),('nullable','NULL 허용')]),
)

DOC_URL='https://docs.oracle.com/en/database/oracle/machine-learning/oml4sql/23/mlsql/model-detail-views.html'
TREE_CODES={
    'VC':'예측 시 오분류 비용 행렬','VG':'전체 모델 통계 · 이름/값',
    'VI':'의사결정나무 통계','VM':'의사결정나무 학습 시 비용 행렬',
    'VO':'의사결정나무 노드와 분기 조건','VP':'의사결정나무 계층과 분할 정보',
    'VS':'적용된 계산 설정','VT':'분류 타깃별 학습 분포','VW':'모델 학습 알림',
}
SCALAR_TYPES=re.compile(r'^(?:VARCHAR2|NVARCHAR2|CHAR|NCHAR|NUMBER|FLOAT|BINARY_FLOAT|BINARY_DOUBLE|DATE|TIMESTAMP(?:\(\d+\))?(?: WITH (?:LOCAL )?TIME ZONE)?)$')


def code_meaning(code,algorithm,view_type=''):
    if 'TREE' in algorithm.upper() and code in TREE_CODES:return TREE_CODES[code]
    if view_type:return view_type
    if code.startswith('P'):return 'Oracle 모델 내부 저장용 구분 코드 · 세부 의미를 임의로 해석하지 않습니다.'
    return '현재 DB가 생성한 내부 객체 · 공개 상세 뷰 종류에서 제공 여부를 확인하세요.'


def object_detail(conn,name,metadata,columns,view_type,algorithm):
    obj=metadata['object_name']
    detail={'object_name':obj,'object_type':metadata['object_type'],'code':obj[3:5],
            'meaning':code_meaning(obj[3:5],algorithm,view_type),'columns':columns,
            'rows':[],'row_limit':20,'sql':'','omitted_columns':[],'error':'','explanation':''}
    # 객체명은 클라이언트에서 받지 않으며 현재 계정의 실제 메타데이터 목록에 있어야 합니다.
    if not re.fullmatch(r'DM\$[A-Z0-9]{2}'+re.escape(name),obj):return detail
    owner=str(conn.username).upper()
    if not re.fullmatch(r'[A-Z][A-Z0-9_$#]{0,127}',owner):raise ValueError('현재 DB 소유자를 확인하세요.')
    selected=[r['column_name'] for r in columns if (SCALAR_TYPES.fullmatch(r['data_type']) or r['data_type']=='XMLTYPE') and re.fullmatch(r'[A-Z][A-Z0-9_$#]{0,127}',r['column_name'])]
    detail['omitted_columns']=[r['column_name']+' ('+r['data_type']+')' for r in columns if r['column_name'] not in selected]
    if not selected:return detail
    expressions=[('XMLSERIALIZE(CONTENT "'+r['column_name']+'" AS CLOB) AS "'+r['column_name']+'"') if r['data_type']=='XMLTYPE' else '"'+r['column_name']+'"' for r in columns if r['column_name'] in selected]
    replacements={'columns':', '.join(expressions),'view':'"'+owner+'"."'+obj+'"'}
    sql=read_sql('queries/dictionary_detail_rows.sql')
    for key,value in replacements.items():sql=sql.replace('{{'+key+'}}',value)
    detail['sql']=sql
    try:detail['rows']=execute(conn,'queries/dictionary_detail_rows.sql',replacements=replacements,fetch=True)
    except Exception as error:
        code=re.search(r'(?:ORA|DPY|DPI)-\d+',str(error))
        detail['error']='객체 데이터 조회 실패 ('+(code.group(0) if code else 'DB 오류')+'). 컬럼 메타데이터와 구분하여 확인하세요.'
    if obj[3:5] in ('VC','VM'):
        detail['explanation']='실제 클래스·예측 클래스별 오분류 비용을 정의하는 행렬입니다. TEST 평가의 정답/오답 건수 표와는 다릅니다.'+(' 현재 등록된 비용 행렬은 0행입니다. 모델 생성 여부는 모델 등록 정보를 확인하세요.' if not detail['rows'] and not detail['error'] else '')
    elif obj[3:5] in ('VO','VP'):
        detail['explanation']='트리의 실제 노드·분기 조건입니다. XMLTYPE 값은 XML 문자열로 직렬화하여 표시합니다.'
    return detail


def read(conn,mode):
    """입력 RAW/CLEAN → 고정 모델명으로 SELECT만 수행. DDL·학습·확정 저장은 없습니다."""
    if mode not in ('RAW','CLEAN'):raise ValueError('조회할 모델은 RAW 또는 CLEAN 하나를 선택하세요.')
    name='OML_BASIC_'+mode+'_MODEL'
    sections=[]
    for key,view,title,description,empty,columns in CATALOG:
        try:values=query(conn,'dictionary_'+key+'.sql',model_name=name)
        except Exception as error:
            code=re.search(r'(?:ORA|DPY|DPI)-\d+',str(error))
            raise ValueError(f'{view} 조회 실패 ({code.group(0) if code else "DB 오류"}). DB 버전의 뷰·컬럼 제공 여부와 현재 계정의 조회 권한·연결을 확인하세요. 조회 실패를 0행으로 처리하지 않습니다.') from error
        sections.append({'key':key,'view':view,'title':title,'description':description,'empty':empty,
                         'columns':[(field,field.upper()+' · '+label) for field,label in columns],'rows':values})
    by_key={section['key']:section for section in sections}
    algorithm=next((row.get('algorithm','') for row in by_key['model']['rows']),'')
    views={row['view_name']:row['view_type'] for row in by_key['views']['rows'] if re.fullmatch(r'DM\$V[A-Z]'+re.escape(name),row['view_name'])}
    details=[]
    for row in by_key['generated_objects']['rows']:
        obj=row['object_name'];code=obj[3:5]
        row['code_meaning']=code_meaning(code,algorithm,views.get(obj,''))
        columns=[column for column in by_key['generated_columns']['rows'] if column['object_name']==obj]
        details.append(object_detail(conn,name,row,columns,views.get(obj,''),algorithm))
    for row in by_key['views']['rows']:
        detail=next((d for d in details if d['object_name']==row['view_name']),None)
        if detail:row['example_sql']=detail['sql']
    return {'model_name':name,'variant':mode,'exists':bool(sections[0]['rows']),'sections':sections,
            'object_details':details,'naming':{'prefix':'DM$','model_name':name,'algorithm':algorithm,'documentation_url':DOC_URL,
            'description':'DM$는 Oracle 모델 관련 객체의 접두사, 뒤의 2자는 객체 구분 코드, 나머지는 지정한 모델명입니다. P5·PH·PJ 등의 P 계열은 내부 저장 객체이며 세부 코드의 뜻을 추정하지 않습니다. VC·VM 등 공개 상세 뷰의 의미는 현재 알고리즘과 USER_MINING_MODEL_VIEWS의 실제 종류를 기준으로 설명합니다.'}}
