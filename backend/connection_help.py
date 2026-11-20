"""접속 실패를 학생이 확인할 설정과 조치로 안내합니다. 원본 오류의 비밀값은 반환하지 않습니다."""
import re
import ssl
import zipfile


def explain(error):
    text = str(error)
    codes = re.findall(r'ORA-\d{5}|DPY-\d{4}|DPI-\d{4}', text)
    code = next((value for value in codes if value.startswith('ORA-')), codes[0] if codes else 'DB-CONNECTION')
    title = 'DB 연결을 완료하지 못했습니다.'
    steps = ['student.env의 DB_DSN이 제공된 Wallet의 서비스명과 같은지 확인하세요.',
             '인터넷·VPN·방화벽과 DB 서비스 실행 상태를 확인하세요.',
             '아래 오류 코드와 확인 내용을 담당자에게 전달하세요. 비밀번호는 보내지 마세요.']
    if 'ORA-01017' in codes:
        code = 'ORA-01017'; title = '발급된 DB 계정의 비밀번호를 확인하세요.'
        steps = ['화면의 DB 계정이 본인에게 발급된 계정인지 확인하세요. 계정은 students.json의 db_user에서 가져옵니다.',
                 '그 계정의 DB 비밀번호를 대소문자·붙여넣은 공백까지 확인해 다시 입력하세요. Wallet 비밀번호와는 별개입니다.',
                 '계정과 비밀번호가 맞는데 계속 실패하면 해당 DB의 계정 사용 권한을 담당자에게 확인하세요.']
    elif 'ORA-28000' in codes or 'ORA-28001' in codes:
        code = 'ORA-28000' if 'ORA-28000' in codes else 'ORA-28001'
        title = 'DB 계정이 잠겨 있습니다.' if code == 'ORA-28000' else 'DB 비밀번호가 만료되었습니다.'
        steps = ['담당자에게 계정 잠금 해제 또는 비밀번호 재발급을 요청하세요.',
                 '조치가 끝난 뒤 새로 발급받은 DB 비밀번호로 다시 테스트하세요.']
    elif 'DPI-1047' in codes:
        code = 'DPI-1047'; title = 'Oracle Client를 불러오지 못했습니다.'
        steps = ['Thick 연결을 사용한다면 student.env의 ORACLE_CLIENT_LIB가 oci.dll이 있는 폴더인지 확인하세요.',
                 'Python과 Oracle Client가 모두 x64인지 확인하세요.',
                 '경로·x64가 맞을 때만 VC++ x64 Runtime의 미설치·버전 부족을 확인하세요.',
                 '기본 Thin 연결로 사용할 경우 ORACLE_CLIENT_LIB를 비우고 WALLET_PASSWORD를 입력한 뒤 서비스를 재시작하세요.']
    elif 'ORA-12154' in codes:
        title = 'DB 서비스 이름을 찾지 못했습니다.'
        steps = ['student.env의 DB_DSN을 Wallet 안 tnsnames.ora에 등록된 별칭과 맞추세요.',
                 '현재 DB에서 발급한 Wallet인지 확인하고 이름을 임의로 바꾸지 마세요.',
                 '외부 WALLET_DIR를 사용한다면 그 폴더의 tnsnames.ora를 확인하세요.']
    elif 'ORA-29024' in codes or isinstance(error, ssl.SSLError) or 'CERTIFICATE_VERIFY_FAILED' in text:
        code = 'ORA-29024' if 'ORA-29024' in codes else 'TLS-CERTIFICATE'
        title = 'DB 인증서 검증에 실패했습니다.'
        steps = ['현재 DB에서 제공한 최신 Wallet인지 담당자에게 확인하세요.',
                 'Windows 날짜·시간이 맞는지 확인하세요.',
                 '인증서 확인을 끄지 말고 학교 네트워크·보안 프록시 또는 인증서 상태를 담당자에게 확인하세요.']
    elif 'ORA-28759' in codes or isinstance(error, (zipfile.BadZipFile, KeyError)) or 'Wallet' in text or 'WALLET_' in text:
        title = 'Wallet 설정을 확인하세요.'
        if 'WALLET_PASSWORD' in text:
            code = 'WALLET-PASSWORD'
        elif not codes:
            code = 'WALLET-FILES'
        steps = ['security/Wallet_PCUORA.zip이 제공된 원본 파일인지, student.env의 WALLET_ZIP 경로가 맞는지 확인하세요.',
                 '기본 Thin 연결은 WALLET_PASSWORD에 Wallet 다운로드 당시 비밀번호가 필요합니다. 로그인 화면의 DB 비밀번호와 혼동하지 마세요.',
                 'Wallet 안의 tnsnames.ora·ewallet.pem·cwallet.sso·sqlnet.ora가 손상되거나 누락되지 않았는지 확인하세요.',
                 'WALLET_DIR를 직접 지정했다면 tnsnames.ora와 ewallet.pem이 있는 폴더를 사용하고 ORACLE_CLIENT_LIB는 비우세요.']
    elif isinstance(error, PermissionError):
        code = 'LOCAL-PERMISSION'; title = '실습 파일에 접근할 수 없습니다.'
        steps = ['프로젝트 security와 runtime 폴더의 읽기·쓰기 권한을 확인하세요.',
                 '압축파일 안에서 실행하지 말고 본인 작업 폴더에 압축 해제한 뒤 다시 실행하세요.']
    elif any(value in codes for value in ('DPY-6005','DPY-4011','ORA-12545','ORA-12541','ORA-12170','ORA-12535','ORA-12514')) or isinstance(error, (TimeoutError, ConnectionError)):
        title = 'DB에 도달하지 못했거나 연결이 종료되었습니다.'
        steps = ['인터넷 연결과 수업에서 안내한 VPN 사용 여부를 확인하세요.',
                 '방화벽·보안 프로그램이 Wallet에 지정된 DB 주소와 포트의 통신을 차단하는지 확인하세요.',
                 'student.env의 DB_DSN과 Wallet이 같은 DB용인지 확인하세요.',
                 '담당자에게 DB 서비스가 실행 중인지와 네트워크 접속 허용 상태를 확인하세요.']
    return {'success': False, 'code': code, 'title': title, 'steps': steps,
            'message': '연결 실패 시 기존 student.env와 로그인 상태는 바뀌지 않습니다. 확인 항목을 수정한 뒤 다시 시도하세요.'}
