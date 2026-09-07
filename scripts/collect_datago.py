#!/usr/bin/env python3
"""공공데이터포털(apis.data.go.kr) 수집기 — 레이어 A.

정부 보도자료와 나라장터 용역 입찰공고를 받아 모빌리티 관련 항목만 걸러
`data/inbox/YYYY-MM-DD.json`에 **후보**로 저장한다.

역할 분담이 중요하다: 이 스크립트는 '수집'만 한다. `analysis` 4개 필드(왜 지금 /
정책 계보 / 기술 쟁점 / 시사점)는 판단이 필요하므로 Claude 세션이 후보를 검토해
`data/policy_items.json`으로 승격시킨다. 이 스크립트는 절대 policy_items.json을
직접 수정하지 않는다.

사용법:
    export DATA_GO_KR_KEY="발급받은 Decoding 인증키"
    python3 scripts/collect_datago.py --days 7

실행 위치 (중요):
  이 스크립트는 **사용자 로컬 PC에서 실행하는 것을 전제**로 한다. Claude Code 클라우드
  세션의 egress 정책에서는 apis.data.go.kr 터널이 간헐적으로만 열리고(성공/리셋이 뒤섞임)
  www.data.go.kr·NTIS·IRIS·SROME·빅카인즈는 아예 403으로 차단되므로, 클라우드에서
  상시 자동 수집을 돌리면 신뢰할 수 없다. 클라우드 세션은 WebSearch 기반 수집(레이어 B)과
  분석(레이어 C)을 담당한다.

주의:
  * 인증키는 절대 저장소에 커밋하지 않는다 (환경변수로만 전달).
  * 공공데이터포털은 인증키를 Encoding/Decoding 두 형태로 준다. requests가 자체적으로
    인코딩하므로 **Decoding 키**를 넣어야 한다.
  * 각 API는 data.go.kr에서 '활용신청'을 해야 키가 그 API에 대해 활성화된다.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

ROOT = pathlib.Path(__file__).resolve().parent.parent
INBOX = ROOT / "data" / "inbox"
KST = timezone(timedelta(hours=9))
BASE = "https://apis.data.go.kr"

# 이 세션의 egress 정책상 apis.data.go.kr 만 열려 있다 (www.data.go.kr, NTIS, IRIS,
# SROME, 빅카인즈는 403). 따라서 수집은 전부 이 호스트를 통해서만 한다.

MOBILITY_KEYWORDS = [
    "자율주행", "모빌리티", "전기차", "전기자동차", "배터리", "이차전지",
    "UAM", "도심항공", "드론", "자동차", "차량", "SDV", "충전", "수소차",
    "로보택시", "물류", "교통", "미래차", "부품", "반도체",
]

# 검증 완료: 키 없이 호출 시 원 서버가 SERVICE_KEY_IS_NOT_REGISTERED_ERROR JSON을 반환함.
BID_ENDPOINT = f"{BASE}/1230000/ad/BidPublicInfoService/getBidPblancListInfoServcPPSSrch"

# 부처 보도자료 API.
# data.go.kr에서 활용신청하면 상세 페이지에 정확한 요청 URL이 표시된다.
# 확인하지 않은 경로를 추측해 넣지 않았으므로, 신청 후 아래 endpoint를 채워 넣을 것.
#   과학기술정보통신부_보도자료 : https://www.data.go.kr/data/15074632/openapi.do
#   과학기술정보통신부_보도설명 : https://www.data.go.kr/data/15074633/openapi.do
# 국토교통부·산업통상부도 같은 계열 데이터셋을 검색해 추가한다.
PRESS_SOURCES: list[dict] = [
    # 예시 형태 — endpoint 를 채우면 활성화된다:
    # {"name": "과학기술정보통신부_보도자료",
    #  "endpoint": f"{BASE}/<기관코드>/<서비스>/<오퍼레이션>",
    #  "agency": "과학기술정보통신부",
    #  "params": {"numOfRows": 100, "pageNo": 1, "type": "json"}},
]


def get_key() -> str:
    key = os.environ.get("DATA_GO_KR_KEY", "").strip()
    if not key:
        sys.exit(
            "DATA_GO_KR_KEY 환경변수가 없습니다.\n"
            "  1) https://www.data.go.kr 가입 후 필요한 API마다 '활용신청'\n"
            "  2) 마이페이지에서 'Decoding' 인증키 복사\n"
            "  3) export DATA_GO_KR_KEY='...'"
        )
    return key


def _http_get(full_url: str, timeout: int) -> str | None:
    """curl 우선, 실패 시 urllib 폴백.

    프록시 환경에 따라 Python HTTP 스택이 연결 리셋을 겪는 경우가 있어 curl을 먼저
    시도한다. curl도 같은 HTTPS_PROXY를 경유하므로 정책 우회가 아니다.
    """
    if shutil.which("curl"):
        r = subprocess.run(
            ["curl", "-sS", "-m", str(timeout), "-H", "Accept: application/json", full_url],
            capture_output=True, text=True,
        )
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout
    try:
        req = urllib.request.Request(full_url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", "replace")
    except Exception:  # noqa: BLE001
        return None


def fetch(url: str, params: dict, timeout: int = 30, retries: int = 4) -> dict | None:
    full = f"{url}?{urllib.parse.urlencode(params, doseq=True)}"
    raw = None
    for attempt in range(1, retries + 1):
        raw = _http_get(full, timeout)
        if raw:
            break
        if attempt < retries:
            wait = 2 ** attempt
            print(f"  · 연결 실패, {wait}s 후 재시도 ({attempt}/{retries})", file=sys.stderr)
            time.sleep(wait)
    if not raw:
        print("  ! 요청 실패 (재시도 소진). 네트워크나 egress 정책을 확인하세요.", file=sys.stderr)
        return None

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # 오류는 XML로 오는 경우가 많다
        snippet = raw[:200].replace("\n", " ")
        print(f"  ! JSON 아님 (인증키/활용신청 확인 필요): {snippet}", file=sys.stderr)
        return None

    if "OpenAPI_ServiceResponse" in data:
        hdr = data["OpenAPI_ServiceResponse"].get("cmmMsgHeader", {})
        print(f"  ! API 오류: {hdr.get('errMsg')} / {hdr.get('returnAuthMsg')}", file=sys.stderr)
        return None
    return data


def is_mobility(text: str) -> bool:
    return any(k in text for k in MOBILITY_KEYWORDS)


def collect_bids(key: str, days: int) -> list[dict]:
    """나라장터 용역 입찰공고 중 모빌리티 관련 건."""
    now = datetime.now(KST)
    params = {
        "serviceKey": key,
        "pageNo": 1,
        "numOfRows": 300,
        "type": "json",
        "inqryDiv": 1,  # 공고게시일시 기준
        "inqryBgnDt": (now - timedelta(days=days)).strftime("%Y%m%d0000"),
        "inqryEndDt": now.strftime("%Y%m%d2359"),
    }
    print(f"[나라장터] 최근 {days}일 용역 입찰공고 조회…")
    data = fetch(BID_ENDPOINT, params)
    if not data:
        return []

    items = (data.get("response", {}).get("body", {}) or {}).get("items") or []
    if isinstance(items, dict):
        items = items.get("item", [])
    if not isinstance(items, list):
        return []

    out = []
    for it in items:
        title = str(it.get("bidNtceNm", ""))
        if not is_mobility(title):
            continue
        out.append({
            "candidate_source": "나라장터",
            "title": title,
            "date": str(it.get("bidNtceDt", ""))[:10].replace("/", "-"),
            "agency": it.get("ntceInsttNm") or it.get("dminsttNm"),
            "doc_no": it.get("bidNtceNo"),
            "deadline": str(it.get("bidClseDt", ""))[:10].replace("/", "-") or None,
            "budget_raw": it.get("presmptPrce") or it.get("asignBdgtAmt"),
            "url": it.get("bidNtceDtlUrl") or it.get("bidNtceUrl"),
            "raw_keys": sorted(it.keys())[:0],  # 원본 전체는 저장하지 않음
        })
    print(f"  → 전체 {len(items)}건 중 모빌리티 관련 {len(out)}건")
    return out


def collect_press(key: str, days: int) -> list[dict]:
    """부처 보도자료 중 모빌리티 관련 건."""
    if not PRESS_SOURCES:
        print("[보도자료] 설정된 소스가 없습니다 — PRESS_SOURCES 에 endpoint 를 채우세요.")
        return []

    cutoff = (datetime.now(KST) - timedelta(days=days)).strftime("%Y-%m-%d")
    out: list[dict] = []
    for src in PRESS_SOURCES:
        print(f"[보도자료] {src['name']} 조회…")
        params = dict(src.get("params", {}))
        params["serviceKey"] = key
        data = fetch(src["endpoint"], params)
        if not data:
            continue

        body = (data.get("response", {}) or {}).get("body", {}) or {}
        items = body.get("items") or []
        if isinstance(items, dict):
            items = items.get("item", [])
        if not isinstance(items, list):
            items = []

        hit = 0
        for it in items:
            title = str(it.get("title") or it.get("bbsTitle") or "")
            date = str(it.get("regDate") or it.get("createDate") or "")[:10].replace(".", "-")
            if not is_mobility(title) or (date and date < cutoff):
                continue
            hit += 1
            out.append({
                "candidate_source": src["name"],
                "title": title,
                "date": date,
                "agency": src.get("agency"),
                "doc_no": None,
                "deadline": None,
                "budget_raw": None,
                "url": it.get("url") or it.get("linkUrl") or it.get("detailUrl"),
            })
        print(f"  → 전체 {len(items)}건 중 모빌리티 관련 {hit}건")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="공공데이터포털 정책·사업 수집기")
    ap.add_argument("--days", type=int, default=7, help="조회 기간 (일, 기본 7)")
    ap.add_argument("--stdout", action="store_true", help="파일 대신 표준출력으로")
    args = ap.parse_args()

    key = get_key()
    today = datetime.now(KST).strftime("%Y-%m-%d")

    candidates = collect_bids(key, args.days) + collect_press(key, args.days)

    # 이미 승격된 URL은 후보에서 제외
    db_path = ROOT / "data" / "policy_items.json"
    known = set()
    if db_path.exists():
        known = {i["url"] for i in json.loads(db_path.read_text(encoding="utf-8"))["items"]}
    fresh = [c for c in candidates if c.get("url") and c["url"] not in known]

    payload = {
        "collected_at": today,
        "window_days": args.days,
        "note": "수집 후보. Claude 세션이 검토·분석해 data/policy_items.json으로 승격한다.",
        "candidates": fresh,
    }
    blob = json.dumps(payload, ensure_ascii=False, indent=2)

    if args.stdout:
        print(blob)
    else:
        INBOX.mkdir(parents=True, exist_ok=True)
        out = INBOX / f"{today}.json"
        out.write_text(blob, encoding="utf-8")
        print(f"\n후보 {len(fresh)}건 → {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
