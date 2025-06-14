import logging
import os
import re
import sys

import requests

from .retry_decorator import retry, retry_request  # retry_request import

logger = logging.getLogger(__name__)

def validate_repo_format(repo: str) -> bool:
    pattern = r'^[\w\-]+/[\w\-]+$'
    if re.fullmatch(pattern, repo):
        return True
    else:
        print("저장소 형식이 올바르지 않습니다. 'owner/repo' 형식으로 입력해주세요.")
        return False

def validate_token() -> None:
    """환경변수에서 GitHub 토큰을 읽어서 검증"""
    token = os.getenv('GITHUB_TOKEN')
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "reposcore-py"
    }
    if token:
        headers["Authorization"] = f"token {token}"

    session = requests.Session()
    try:
        response = retry_request(session, "https://api.github.com/user", headers=headers)
    except Exception as e:
        logger.error(f"❌ 인증 API 요청 자체가 실패했습니다: {e}")
        sys.exit(1)
    if response.status_code != 200:
        logger.error('❌ 인증 실패: 잘못된 GitHub 토큰입니다. 토큰 값을 확인해 주세요.')
        sys.exit(1)

def check_github_repo_exists(repo: str) -> bool:
    """GitHub 저장소 존재 여부를 확인하는 함수 (환경변수에서 토큰 자동 읽기)"""
    token = os.getenv('GITHUB_TOKEN')
    url = f"https://api.github.com/repos/{repo}"
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "reposcore-py"
    }
    if token:
        headers["Authorization"] = f"token {token}"

    session = requests.Session()
    try:
        response = retry_request(session, url, headers=headers)
    except Exception as e:
        logger.warning(f"⚠️ 저장소 존재 확인 API 요청 자체가 실패했습니다: {e}")
        return False

    if response.status_code == 200:
        return True
    elif response.status_code == 403:
        logger.warning("⚠️ GitHub API 요청 실패: 403 (요청 횟수 초과 또는 인증 오류)")
        logger.info("ℹ️ 해결 방법: --token 옵션 또는 GITHUB_TOKEN 환경 변수 사용")
    elif response.status_code == 404:
        logger.warning(f"⚠️ 저장소 '{repo}'가 존재하지 않습니다.")
    else:
        logger.warning(f"⚠️ 요청 실패: HTTP 상태 코드 {response.status_code}")

    return False

def check_rate_limit() -> None:
    """현재 GitHub API 요청 가능 횟수와 전체 한도를 확인하고 출력하는 함수 (환경변수에서 토큰 자동 읽기)"""
    token = os.getenv('GITHUB_TOKEN')
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "reposcore-py"
    }
    if token:
        headers["Authorization"] = f"token {token}"

    session = requests.Session()
    try:
        response = retry_request(session, "https://api.github.com/rate_limit", headers=headers)
    except Exception as e:
        logger.error(f"API 요청 제한 정보를 가져오는데 실패했습니다: {e}")
        return
    if response.status_code == 200:
        data = response.json()
        core = data.get("resources", {}).get("core", {})
        remaining = core.get("remaining", "N/A")
        limit = core.get("limit", "N/A")
        logger.info(f"GitHub API 요청 가능 횟수: {remaining} / {limit}")
    else:
        logger.error(f"API 요청 제한 정보를 가져오는데 실패했습니다 (status code: {response.status_code}).")

@retry(max_retries=3, retry_delay=1.0)
def retry_request(
    session: requests.Session,
    url: str,
    params: dict[str, str] | None = None,
    headers: dict[str, str] | None = None
) -> requests.Response:
    """
    단순히 한 번만 요청을 보내고,
    네트워크 오류 시 retry_decorator가 재시도 처리합니다.
    
    Note: 이 함수는 이미 세션에 토큰이 설정되어 있다고 가정합니다.
    """
    return session.get(url, params=params, headers=headers)