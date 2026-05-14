"""
발급받은 API 키가 실제로 동작하는지 확인하는 헬스체크.

사용:
  python verify_keys.py
"""

from __future__ import annotations

import os
import sys
import requests

TIMEOUT = 10


def check(name: str, ok: bool, detail: str = "") -> None:
    mark = "✅" if ok else "❌"
    print(f"{mark} {name}  {detail}")


def test_neis() -> None:
    key = os.environ.get("SCHOOLINFO_KEY")
    if not key:
        check("NEIS 학교정보 (SCHOOLINFO_KEY)", False, "환경변수 미설정")
        return
    try:
        r = requests.get(
            "https://open.neis.go.kr/hub/schoolInfo",
            params={
                "KEY": key, "Type": "json",
                "pIndex": 1, "pSize": 1,
                "ATPT_OFCDC_SC_CODE": "B10",  # 서울
            },
            timeout=TIMEOUT,
        )
        data = r.json()
        # NEIS는 정상 응답일 때 schoolInfo 배열에 head/row가 있음
        if "schoolInfo" in data:
            rows = data["schoolInfo"][1].get("row", [])
            check("NEIS 학교정보", True, f"샘플 학교명: {rows[0].get('SCHUL_NM') if rows else '(empty)'}")
        else:
            # 에러 응답
            result = data.get("RESULT", {})
            check("NEIS 학교정보", False, f"{result.get('CODE')}: {result.get('MESSAGE')}")
    except Exception as e:
        check("NEIS 학교정보", False, f"예외: {e}")


def test_library() -> None:
    key = os.environ.get("LIBSEOUL_KEY")
    if not key:
        check("도서관정보나루 (LIBSEOUL_KEY)", False, "환경변수 미설정 (승인 대기 중일 수 있음)")
        return
    try:
        r = requests.get(
            "http://data4library.kr/api/libSrch",
            params={"authKey": key, "region": "서울특별시", "pageSize": 1, "format": "json"},
            timeout=TIMEOUT,
        )
        data = r.json()
        libs = data.get("response", {}).get("libs", [])
        if libs:
            check("도서관정보나루", True, f"샘플 도서관명: {libs[0].get('lib', {}).get('libName')}")
        else:
            err = data.get("response", {}).get("error") or data
            check("도서관정보나루", False, f"응답 비정상: {str(err)[:120]}")
    except Exception as e:
        check("도서관정보나루", False, f"예외: {e}")


def test_data_go_kr() -> None:
    key = os.environ.get("DATA_GO_KR_KEY")
    if not key:
        check("공공데이터포털 (DATA_GO_KR_KEY)", False, "환경변수 미설정")
        return
    try:
        r = requests.get(
            "https://apis.data.go.kr/1741000/StanReginCd/getStanReginCdList",
            params={
                "serviceKey": key, "type": "json",
                "pageNo": 1, "numOfRows": 1,
                "locatadd_nm": "서울특별시",
            },
            timeout=TIMEOUT,
        )
        if "OpenAPI_ServiceResponse" in r.text:
            # 인증 실패 시 XML 에러 반환
            check("공공데이터포털", False, "인증 실패 — 키 확인 또는 활용신청 승인 여부 확인 필요")
            return
        data = r.json()
        result = data.get("StanReginCd")
        if isinstance(result, list) and len(result) >= 2:
            rows = result[1].get("row", [])
            check("공공데이터포털", True, f"샘플 지역: {rows[0].get('locatadd_nm') if rows else '(empty)'}")
        else:
            check("공공데이터포털", False, f"응답 구조 비정상: {str(data)[:120]}")
    except Exception as e:
        check("공공데이터포털", False, f"예외: {e}")


def main() -> None:
    print("\n=== 요기보 B2B 영업 API 키 헬스체크 ===\n")
    test_neis()
    test_library()
    test_data_go_kr()
    print()


if __name__ == "__main__":
    main()
