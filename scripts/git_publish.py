"""학생 본인의 저장소로 공개 소스만 전달합니다. 기본 동작은 파일 목록 미리보기입니다."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile
from urllib.parse import urlsplit
from source_files import ROOT, inventory, manifest, student_git_path

MARKER = 'OML_SOURCE_MANIFEST.json'
PROJECT = 'oml-student-source-v1'
# 강사용 주소 원문을 학생에게 배포하지 않고, 잘못 지정한 대상은 접속 전에 차단합니다.
PROTECTED_REPOSITORY = '41e9ae4b8c53406649479c63524647295f92dd11d473c3e432ccfe948eeaad58'


def repository_url(value):
    """토큰 없는 본인 GitHub HTTPS 주소를 검증합니다. 저장된 remote를 자동 사용하지 않습니다."""
    value = value.strip()
    if not value or any(char.isspace() or ord(char) < 32 for char in value):
        raise ValueError('-Repository에 본인 GitHub 저장소 HTTPS 주소를 지정하세요.')
    url = urlsplit(value)
    if (url.scheme != 'https' or url.netloc.lower() != 'github.com'
            or url.username or url.password or url.query or url.fragment):
        raise ValueError('https://github.com/소유자/저장소.git 형식만 지원합니다. 토큰·비밀번호를 주소에 넣지 마세요.')
    path = url.path.removesuffix('/')
    if path.lower().endswith('.git'):
        path = path[:-4]
    parts = path.lstrip('/').split('/')
    if (len(parts) != 2 or path.startswith('//')
            or not re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?', parts[0])
            or not re.fullmatch(r'[A-Za-z0-9_.-]{1,100}', parts[1])
            or parts[1] in ('.', '..') or any(p.upper().startswith('YOUR_') for p in parts)):
        raise ValueError('GitHub에서 본인 저장소의 Code → HTTPS 주소를 복사하세요. 예시 문자열은 바꿔야 합니다.')
    identity = '/'.join(parts).lower()
    if hashlib.sha256(identity.encode('ascii')).hexdigest() == PROTECTED_REPOSITORY:
        raise ValueError('강사용 저장소는 학생 배포 대상으로 사용할 수 없습니다. 본인 저장소 주소를 지정하세요.')
    return 'https://github.com/' + '/'.join(parts) + '.git'


def git(cwd, *args, check=True):
    result = subprocess.run(
        ['git', '-c', 'http.followRedirects=false', '-c', 'core.autocrlf=false', *args],
        cwd=cwd, text=True, encoding='utf-8', errors='replace', capture_output=True, timeout=120)
    if check and result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or 'Git 명령이 실패했습니다.')
    return result


def publish(root, repository, branch='main', message='Update my OML assignment',
            push=False, author_name='', author_email=''):
    repository = repository_url(repository)
    root = Path(root).resolve()
    files = inventory(root, audience='student-git')
    git(root, 'check-ref-format', '--branch', branch)
    runtime = root / 'runtime'
    if runtime.is_symlink() or runtime.is_junction() or not runtime.resolve().is_relative_to(root):
        raise ValueError('runtime은 이 프로젝트 안의 일반 폴더여야 합니다.')
    runtime.mkdir(exist_ok=True)
    checkout = Path(tempfile.mkdtemp(prefix='student-github-', dir=runtime))
    print('대상 저장소: ' + repository + ' [' + branch + ']')
    print('검토 폴더: ' + str(checkout))
    # 작업 폴더의 Git 설정을 바꾸지 않습니다. 원격 소스는 실행하지 않습니다.
    git(root, 'clone', '--no-checkout', '--template=', '--', repository, str(checkout))
    no_hooks = checkout / '.git' / 'oml-no-hooks'
    no_hooks.mkdir()
    git(checkout, 'config', 'core.hooksPath', str(no_hooks))
    refs = git(checkout, 'for-each-ref', '--format=%(refname)', 'refs/remotes/origin/').stdout.splitlines()
    wanted = 'refs/remotes/origin/' + branch
    if wanted in refs:
        git(checkout, 'checkout', '-B', branch, wanted)
    elif refs:
        raise ValueError('원격에 지정한 브랜치가 없습니다. -Branch에 기존 브랜치를 지정하세요.')
    else:
        git(checkout, 'checkout', '--orphan', branch)
    tracked = set(git(checkout, 'ls-files', '-z').stdout.rstrip('\0').split('\0')) - {''}
    previous = set()
    marker = checkout / MARKER
    if tracked:
        if MARKER not in tracked or marker.is_symlink():
            raise ValueError('이 스크립트로 관리한 저장소가 아닙니다. README·라이선스 없이 만든 본인의 빈 저장소를 사용하세요.')
        data = json.loads(marker.read_text(encoding='utf-8'))
        if not isinstance(data, dict) or data.get('project') != PROJECT or not isinstance(data.get('files'), dict):
            raise ValueError('학생용 배포 기록이 아닙니다. 저장소 주소와 기존 파일을 확인하세요.')
        previous = set(data['files'])
        if any(not student_git_path(name) for name in previous):
            raise ValueError('원격 배포 기록에 허용되지 않은 경로가 있습니다.')
        if tracked - previous - {MARKER}:
            raise ValueError('원격에 스크립트가 관리하지 않는 파일이 있습니다. 기존 파일을 직접 확인하세요.')
    # 덮어쓰기·삭제 전에 경로가 방금 만든 검토 폴더 안인지 확인합니다.
    for name in set(files) | previous | {MARKER}:
        target = checkout / name
        if not target.resolve().is_relative_to(checkout.resolve()):
            raise ValueError('검토 폴더 밖의 경로는 처리할 수 없습니다.')
        for part in (target, *target.parents):
            if part == checkout:
                break
            if part.is_symlink() or part.is_junction():
                raise ValueError('원격에 링크 경로가 있습니다: ' + name)
    for name in previous - files.keys():
        (checkout / name).unlink(missing_ok=True)
    for name, raw in files.items():
        target = checkout / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    marker.write_text(json.dumps({'project': PROJECT, 'files': json.loads(manifest(files))}, indent=2) + '\n', encoding='utf-8')
    paths = sorted(set(files) | previous | {MARKER})
    # 공통 ignore 규칙은 실제 명단을 보호합니다. 검증한 본인 명단 한 파일만 명시적으로 올립니다.
    paths = [name for name in paths if name != 'security/students.json']
    for offset in range(0, len(paths), 50):
        git(checkout, 'add', '-A', '--', *paths[offset:offset + 50])
    git(checkout, 'add', '-f', '--', 'security/students.json')
    print(git(checkout, 'diff', '--cached', '--stat').stdout.strip() or '소스 변경 없음')
    changed = git(checkout, 'diff', '--cached', '--quiet', check=False).returncode
    if changed not in (0, 1):
        raise RuntimeError('변경 파일을 확인하지 못했습니다.')
    if changed:
        if author_name:
            git(checkout, 'config', 'user.name', author_name)
        if author_email:
            git(checkout, 'config', 'user.email', author_email)
        if not all(git(checkout, 'config', '--get', key, check=False).stdout.strip() for key in ('user.name', 'user.email')):
            raise ValueError('-AuthorName과 -AuthorEmail을 지정하세요. 검토 폴더의 로컬 Git 설정에만 적용됩니다.')
        git(checkout, '-c', 'commit.gpgsign=false', 'commit', '-m', message)
    if push:
        git(checkout, 'push', '--set-upstream', 'origin', 'HEAD:refs/heads/' + branch)
        print('업로드 완료: ' + repository + ' [' + branch + ']')
    else:
        print('로컬 준비 완료: GitHub 업로드 없음. 검토 폴더에서 git log / git show로 확인하세요.')
    return checkout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository', required=True)
    parser.add_argument('--branch', default='main')
    parser.add_argument('--message', default='Update my OML assignment')
    parser.add_argument('--author-name', default='')
    parser.add_argument('--author-email', default='')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--prepare', action='store_true')
    mode.add_argument('--push', action='store_true')
    args = parser.parse_args()
    repository = repository_url(args.repository)
    if not (args.prepare or args.push):
        files = inventory(audience='student-git')
        print('미리보기: ' + repository + ' [' + args.branch + ']')
        for name in files:
            print('  ' + name)
        print(f'{len(files)}개 파일. GitHub 접속·업로드 없음. 실제 업로드는 -Push를 지정하세요.')
        return
    publish(ROOT, repository, args.branch, args.message, args.push, args.author_name, args.author_email)


if __name__ == '__main__':
    try:
        main()
    except FileNotFoundError:
        raise SystemExit('Git for Windows 설치와 파일 경로를 확인하세요. 설치 후 VS Code 터미널을 다시 여세요.') from None
    except (ValueError, RuntimeError, OSError, subprocess.TimeoutExpired) as error:
        raise SystemExit(str(error)) from None
