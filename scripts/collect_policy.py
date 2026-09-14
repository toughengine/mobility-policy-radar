#!/usr/bin/env python3
"""대한민국 정책브리핑(korea.kr) 보도자료 수집기 — 정책 동향 주력 소스.

전 부처 보도자료가 한 곳에 모이는 정책브리핑을 최신순으로 훑어, 모빌리티 관련
정책 발표를 `data/inbox/policy-YYYY-MM-DD.json`에 후보로 적재한다.

NTIS 공고 수집기(`collect_ntis.py`)와 역할이 다르다. 저쪽은 사업이 확정된 뒤의
'공고'를 잡고, 이쪽은 그 앞단의 '정책 발표'를 잡는다.

이 스크립트는 '수집'만 한다. analysis 4개 필드(왜 지금 / 정책 계보 / 기술 쟁점 /
시사점)는 판단이 필요하므로 Claude 세션이 후보를 검토해 data/policy_items.json으로
승격시킨다.

설계 근거 (2026-09-14 실측):
  * 목록(pressReleaseList.do)은 **서버 렌더링**이라 HTML만 받아도 제목·리드요약·
    newsId가 다 들어 있다.
  * **최신순 훑기는 쓰지 않는다.** 최신 240건(약 1주일치)을 받아보니 제목에 모빌리티
    키워드가 있는 것이 **0건**이었다. 필터 문제가 아니라 정책브리핑 전체 흐름에서
    모빌리티 정책 발표의 밀도가 그만큼 낮다는 뜻이다. 매일 최신순으로 훑으면
    대부분의 날이 0건이 되고 드물게 나오는 것도 페이지 밖으로 밀려 놓친다.
  * 대신 **키워드 검색 + 제목 필터**를 쓴다. 검색만 쓰면 전문 검색이라 노이즈가
    크지만(본문에 스치기만 해도 걸림), **제목에 그 키워드가 실제로 있는 것만**
    남기면 정밀도가 확보된다. 실측: '자율주행' 20건→3건(전부 유효),
    'UAM' 20건→13건, '전기차' 20건→4건.
  * `startDate`/`endDate` 날짜 필터는 GET 파라미터로 **동작하지 않는다**(다른 날짜를
    넣어도 같은 결과). 그래서 날짜 대신 `newsId`로 중복을 거른다.
  * 전송은 curl로 한다. korea.kr 도 간헐적으로 연결이 끊기므로 재시도가 필수다.

사용법:
    python3 scripts/collect_policy.py                # 키워드 전체, 검색 2페이지씩
    python3 scripts/collect_policy.py --pages 4      # 재고를 더 깊이 훑을 때
    python3 scripts/collect_policy.py --stdout       # 파일로 저장하지 않고 출력만
"""
from __future__ import annotations

import argparse
import html
import json
import pathlib
import re
import shutil
import subprocess
import sys
import urllib.parse
import time
from datetime import datetime, timedelta, timezone

ROOT = pathlib.Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "policy_items.json"
INBOX = ROOT / "data" / "inbox"
KST = timezone(timedelta(hours=9))

SEARCH_URL = "https://www.korea.kr/briefing/pressReleaseList.do?srchWord={q}&pageIndex={page}"
VIEW_URL = "https://www.korea.kr/briefing/pressReleaseView.do?newsId={nid}"

# 검색어이자 제목 필터. 검색으로 후보를 넓게 받고, **제목에 이 말이 실제로 있는
# 것만** 남긴다. 그래서 다른 분야와 겹치지 않는 구체적인 말만 넣는다.
# '교통'·'물류'·'항공' 같은 넓은 말은 넣지 않는다 — 국방 드론 기술전, 기상항공기
# 방재훈련 같은 무관한 것이 제목 매칭으로도 걸린다(실측).
KEYWORDS = [
    "자율주행", "자율주행차", "자율차", "모빌리티", "첨단모빌리티",
    "전기차", "전기자동차", "수소차", "수소전기차",
    "UAM", "도심항공교통", "무인이동체", "로보택시",
    "미래차", "이차전지", "배터리", "충전인프라", "충전기",
    "자동차산업", "자동차부품", "완성차", "차량용 반도체",
]

# 제목에 이 말이 있으면 모빌리티 맥락이 아닐 가능성이 높아 버린다.
EXCLUDE = [
    "명절", "성묘", "벌초", "농기계", "산림", "수목원", "가뭄", "축산", "어촌",
]


def http_get(url: str, timeout: int = 30, retries: int = 5) -> str:
    """curl로 GET. korea.kr 은 간헐적으로 연결이 끊기므로 재시도한다."""
    if not shutil.which("curl"):
        sys.exit("curl이 필요합니다.")
    for attempt in range(1, retries + 1):
        r = subprocess.run(
            ["curl", "-sS", "-m", str(timeout), "-L", "-A", "Mozilla/5.0", url],
            capture_output=True, text=True,
        )
        if r.returncode == 0 and len(r.stdout) > 5000:
            return r.stdout
        if attempt < retries:
            time.sleep(min(2 ** attempt, 12))
    return ""


def _text(fragment: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", fragment))).strip()


def parse_list(page_html: str) -> list[dict]:
    """보도자료 목록 HTML에서 항목을 뽑는다."""
    rows = []
    pattern = (
        r'pressReleaseView\.do\?newsId=(\d+)[^>]*>\s*'
        r'<span class="text">\s*<strong>(.*?)</strong>\s*'
        r'(?:<span class="lead">(.*?)</span>)?'
    )
    for nid, title, lead in re.findall(pattern, page_html, re.S):
        rows.append({
            "news_id": nid,
            "title": _text(title),
            "lead": _text(lead or "")[:300],
            "url": VIEW_URL.format(nid=nid),
        })
    return rows


def title_matches(row: dict, keyword: str) -> bool:
    """검색으로 받은 항목 중 제목에 그 키워드가 실제로 있는 것만 채택한다."""
    if any(x in row["title"] for x in EXCLUDE):
        return False
    return keyword in row["title"]


def known_ids() -> set[str]:
    """이미 승격됐거나 이미 후보로 잡아둔 보도자료는 다시 올리지 않는다."""
    ids: set[str] = set()
    if DB.exists():
        for item in json.loads(DB.read_text(encoding="utf-8"))["items"]:
            m = re.search(r"newsId=(\d+)", item.get("url", ""))
            if m:
                ids.add(m.group(1))
    if INBOX.exists():
        for f in INBOX.glob("policy-*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            ids |= {c.get("news_id", "") for c in data.get("candidates", [])}
    return ids


def main() -> None:
    now = datetime.now(KST)
    ap = argparse.ArgumentParser(description="정책브리핑 보도자료 수집기")
    ap.add_argument("--pages", type=int, default=2,
                    help="키워드당 받을 검색 페이지 수 (기본 2, 약 40건)")
    ap.add_argument("--stdout", action="store_true", help="파일 대신 표준출력으로")
    args = ap.parse_args()

    verbose = not args.stdout
    seen: dict[str, dict] = {}
    queries_ok = queries_failed = 0
    searched_total = 0

    if verbose:
        print(f"정책브리핑 수집 — 키워드 {len(KEYWORDS)}개 × {args.pages}페이지")

    for i, kw in enumerate(KEYWORDS, 1):
        kw_hits = 0
        for page in range(1, args.pages + 1):
            url = SEARCH_URL.format(q=urllib.parse.quote(kw), page=page)
            page_html = http_get(url)
            if not page_html:
                queries_failed += 1
                continue
            queries_ok += 1
            rows = parse_list(page_html)
            searched_total += len(rows)
            for r in rows:
                if r["news_id"] in seen or not title_matches(r, kw):
                    continue
                r["matched_by"] = kw
                seen[r["news_id"]] = r
                kw_hits += 1
        if verbose:
            print(f"  [{i}/{len(KEYWORDS)}] {kw}: 제목매칭 {kw_hits}건 (누적 {len(seen)})")

    known = known_ids()
    fresh = [v for k, v in seen.items() if k not in known]
    fresh.sort(key=lambda r: r["news_id"], reverse=True)

    payload = {
        "source": "대한민국 정책브리핑 (korea.kr)",
        "collected_at": now.strftime("%Y-%m-%d"),
        "method": "키워드 검색 + 제목 필터",
        # 0건이 '없어서'인지 '고장나서'인지 구분하려면 이 숫자들이 필요하다.
        "queries_ok": queries_ok,
        "queries_failed": queries_failed,
        "searched_total": searched_total,
        "matched_total": len(seen),
        "already_known": len(seen) - len(fresh),
        "note": "수집 후보. Claude 세션이 검토·분석해 data/policy_items.json으로 승격한다.",
        "candidates": fresh,
    }
    blob = json.dumps(payload, ensure_ascii=False, indent=2)

    if args.stdout:
        print(blob)
        return

    INBOX.mkdir(parents=True, exist_ok=True)
    out = INBOX / f"policy-{now.strftime('%Y-%m-%d')}.json"
    out.write_text(blob, encoding="utf-8")
    print(f"\n질의 성공 {queries_ok} / 실패 {queries_failed} · 검색결과 {searched_total}건 훑음")
    print(f"제목매칭 {len(seen)}건 · 기존 제외 후 신규 {len(fresh)}건 → {out.relative_to(ROOT)}")
    for c in fresh[:15]:
        print(f"  · [{c['matched_by']}] {c['title'][:64]}")
    if len(fresh) > 15:
        print(f"  … 외 {len(fresh)-15}건")


if __name__ == "__main__":
    main()
