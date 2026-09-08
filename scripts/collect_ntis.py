#!/usr/bin/env python3
"""NTIS 국가R&D통합공고 수집기 — 레이어 A(주력).

전 부처 R&D 공고가 모이는 NTIS 통합공고를 키워드로 훑어 모빌리티 관련 신규공고
후보를 `data/inbox/ntis-YYYY-MM-DD.json`에 적재한다.

이 스크립트는 '수집'만 한다. analysis 4개 필드(왜 지금 / 정책 계보 / 기술 쟁점 /
시사점)는 판단이 필요하므로 Claude 세션이 후보를 검토해 data/policy_items.json으로
승격시킨다. 이 스크립트는 policy_items.json을 직접 수정하지 않는다.

동작 방식과 그 근거 (2026-09 실측):
  * NTIS 통합공고 검색(ThSearchResultAnnouncementList.do)은 서버 렌더링이라
    HTML만 받아도 공고ID·제목·소관부처·접수기간이 다 들어 있다. 상세 페이지를
    열 필요가 없다.
  * 검색 결과는 **키워드당 10건 고정**이고 정렬이 최신순이 아니라 관련도순이다.
    rows/pageNo/sort 파라미터를 시도했지만 먹지 않았다. 그래서 '자율주행'으로
    검색하면 2017년 공고가 상단에 나온다(실측 0/10이 최신).
  * 해결책은 **질의에 연도를 붙이는 것**이다. '2026 자율주행'은 10/10,
    '2026년도 자동차'는 8/8이 2026년 공고였다. 그래서 키워드 × 연도 × 어미
    조합으로 질의를 부채꼴로 펼쳐 커버리지를 확보한다.
  * 전송은 curl로만 된다. Python requests/urllib과 헤드리스 Chromium은 이 서버에서
    연결이 리셋된다(특정 TLS 클라이언트만 받는 것으로 보임). curl도 간헐적으로
    끊기므로 재시도가 필수다.

사용법:
    python3 scripts/collect_ntis.py                # 올해·내년 기준 수집
    python3 scripts/collect_ntis.py --years 2026 2027
    python3 scripts/collect_ntis.py --since 2026 --stdout
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
import time
import urllib.parse
from datetime import datetime, timedelta, timezone

ROOT = pathlib.Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "policy_items.json"
INBOX = ROOT / "data" / "inbox"
KST = timezone(timedelta(hours=9))

SEARCH_URL = "https://www.ntis.go.kr/ThSearchResultAnnouncementList.do"
DETAIL_URL = "https://www.ntis.go.kr/rndgate/eg/un/ra/view.do?roRndUid={uid}"

# 모빌리티 기술정책 대상 키워드. 연도와 조합해 질의를 만든다.
KEYWORDS = [
    "자율주행",
    "모빌리티",
    "자동차",
    "전기차",
    "이차전지",
    "배터리",
    "UAM",
    "도심항공교통",
    "차량용 반도체",
    "SDV",
    "수소차",
    "충전인프라",
    "미래차",
    "교통",
]

# 실측상 이 두 어미가 서로 다른 결과 집합을 준다. 세 번째('{y}년 {kw}')는
# 새 결과를 거의 주지 않아 질의 수만 늘려서 뺐다.
QUERY_FORMS = ["{y} {kw}", "{y}년도 {kw}"]

# 공고와 무관한 잡음 (지자체 물품구매, 단순 용역 등)을 걸러낸다.
NOISE = ["도서관", "장서", "청소", "급식", "경비용역", "임대차"]


def http_get(url: str, timeout: int = 40, retries: int = 6) -> str:
    """curl로 GET. Python HTTP 스택은 이 서버에서 리셋되므로 curl을 쓴다."""
    if not shutil.which("curl"):
        sys.exit("curl이 필요합니다. NTIS 서버가 Python HTTP 스택 연결을 거부합니다.")
    for attempt in range(1, retries + 1):
        r = subprocess.run(
            ["curl", "-sS", "-m", str(timeout), "-A", "Mozilla/5.0", url],
            capture_output=True, text=True,
        )
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout
        if attempt < retries:
            time.sleep(min(2 ** attempt, 16))
    return ""


def _text(fragment: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", fragment))).strip()


def parse_results(page: str) -> list[dict]:
    """검색 결과 HTML에서 공고 항목을 뽑는다."""
    rows = []
    for block in re.split(r'(?=<div class="result-list-inner">)', page)[1:]:
        uid = re.search(r"roRndUid=(\d+)", block)
        anchor = re.search(r'class="announce subject-txt"[^>]*>(.*?)</a>', block, re.S)
        if not (uid and anchor):
            continue
        info = [_text(x) for x in re.findall(r'<span class="txt">(.*?)</span>', block, re.S)]
        period = next((i for i in info if re.search(r"\d{4}\.\d{2}\.\d{2}", i)), "")
        years = re.findall(r"(20\d{2})\.", period)
        rows.append({
            "uid": uid.group(1),
            "title": _text(anchor.group(1)),
            "agency": info[0] if info else "",
            "status": next((i for i in info if i in ("마감", "진행중", "예정")), ""),
            "period": period,
            "year": max(years) if years else "",
            "url": DETAIL_URL.format(uid=uid.group(1)),
        })
    return rows


def is_noise(title: str) -> bool:
    return any(n in title for n in NOISE)


def title_key(title: str) -> str:
    """(공고)/(재공고)/(수정공고)/(연장공고) 같은 변형을 같은 공고로 접기 위한 키.

    NTIS는 같은 사업의 재공고·수정공고를 각각 다른 roRndUid로 올린다. 그대로 두면
    한 사업이 후보 목록을 네댓 건씩 차지한다.
    """
    t = re.sub(r"^\s*\([^)]*공[고모][^)]*\)\s*", "", title)  # 앞머리 (재공고)/(수정공모) 등
    t = re.sub(r"\([^)]*공[고모][^)]*\)", "", t)              # 본문 중 (공고-국-제14호)·(수정) 등
    t = re.sub(r"_\(?20\d{2}\)?.*$", "", t)                 # 꼬리표 _(2026)…
    t = re.sub(r"[\s\u00b7·,()\[\]「」]+", "", t)
    # 꼬리의 …시행공고 / …신규과제재공모 / …공모수정 을 모두 같은 키로
    t = re.sub(r"(수정|재|연장|변경)*공[고모](수정)?$", "", t)
    return t[:60]


def dedupe_variants(rows: list[dict]) -> list[dict]:
    """같은 사업의 공고 변형은 접수기간이 가장 늦은 1건만 남긴다."""
    best: dict[str, dict] = {}
    for r in rows:
        k = title_key(r["title"])
        cur = best.get(k)
        if cur is None or r.get("period", "") > cur.get("period", ""):
            if cur is not None:
                r["variants"] = cur.get("variants", 0) + 1
            best[k] = r
        else:
            cur["variants"] = cur.get("variants", 0) + 1
    return list(best.values())


def collect(years: list[str], since: str, verbose: bool = True) -> list[dict]:
    seen: dict[str, dict] = {}
    queries = [form.format(y=y, kw=kw) for y in years for kw in KEYWORDS for form in QUERY_FORMS]

    for i, q in enumerate(queries, 1):
        page = http_get(f"{SEARCH_URL}?searchWord={urllib.parse.quote(q)}")
        if not page:
            if verbose:
                print(f"  [{i}/{len(queries)}] {q}: 실패", file=sys.stderr)
            continue
        rows = parse_results(page)
        kept = 0
        for r in rows:
            if r["year"] and r["year"] < since:
                continue
            if is_noise(r["title"]):
                continue
            if r["uid"] not in seen:
                r["found_by"] = q
                seen[r["uid"]] = r
                kept += 1
        if verbose:
            print(f"  [{i}/{len(queries)}] {q}: {len(rows)}건 중 신규 {kept}건 (누적 {len(seen)})")
    return list(seen.values())


def known_urls() -> set[str]:
    """이미 승격됐거나 이미 후보로 잡아둔 공고는 다시 올리지 않는다."""
    urls: set[str] = set()
    if DB.exists():
        urls |= {i["url"] for i in json.loads(DB.read_text(encoding="utf-8"))["items"]}
    if INBOX.exists():
        for f in INBOX.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            urls |= {c.get("url", "") for c in data.get("candidates", [])}
    return urls


def main() -> None:
    now = datetime.now(KST)
    ap = argparse.ArgumentParser(description="NTIS 국가R&D통합공고 수집기")
    ap.add_argument("--years", nargs="+", default=[str(now.year)],
                    help="질의에 붙일 연도 (기본: 올해). 연말엔 내년도 함께 지정")
    ap.add_argument("--since", default=str(now.year),
                    help="이 연도보다 오래된 공고는 버린다 (기본: 올해)")
    ap.add_argument("--stdout", action="store_true", help="파일 대신 표준출력으로")
    args = ap.parse_args()

    print(f"NTIS 통합공고 수집 — 연도 {', '.join(args.years)} / 키워드 {len(KEYWORDS)}개")
    found = collect(args.years, args.since, verbose=not args.stdout)

    found = dedupe_variants(found)
    known = known_urls()
    fresh = [f for f in found if f["url"] not in known]
    fresh.sort(key=lambda r: (r.get("period", ""), r["title"]), reverse=True)

    payload = {
        "source": "NTIS 국가R&D통합공고",
        "collected_at": now.strftime("%Y-%m-%d"),
        "queried_years": args.years,
        "note": "수집 후보. Claude 세션이 검토·분석해 data/policy_items.json으로 승격한다.",
        "candidates": fresh,
    }
    blob = json.dumps(payload, ensure_ascii=False, indent=2)

    if args.stdout:
        print(blob)
        return

    INBOX.mkdir(parents=True, exist_ok=True)
    out = INBOX / f"ntis-{now.strftime('%Y-%m-%d')}.json"
    out.write_text(blob, encoding="utf-8")
    print(f"\n수집 {len(found)}건 · 기존 제외 후 신규 {len(fresh)}건 → {out.relative_to(ROOT)}")
    for c in fresh[:10]:
        print(f"  · [{c['agency']}] {c['title'][:64]}")
    if len(fresh) > 10:
        print(f"  … 외 {len(fresh)-10}건")


if __name__ == "__main__":
    main()
