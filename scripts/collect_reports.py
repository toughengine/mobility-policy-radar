#!/usr/bin/env python3
"""NKIS 국가정책연구포털 연구보고서 수집기 — 「참고자료」 축.

입찰공고(collect_bids.py)가 '앞으로 할 일'이라면 이쪽은 '남이 이미 한 일'이다.
제안서를 쓸 때 선행연구로 인용하거나 목차를 참고할 보고서 서가를 만든다.

왜 PRISM이 아니라 NKIS인가 (2026-09-23 실측):
  * `prism.go.kr`은 이 환경에서 **18회 재시도해도 열리지 않는다**(세션 3회에 걸쳐 확인).
    `www.data.go.kr` 포털도 같다. 열리는 것은 API 게이트웨이 `apis.data.go.kr`뿐이다.
  * NKIS(`www.nkis.re.kr`)는 열린다. 경제·인문사회연구회 소관 **26개 국책연구기관**
    (산업연구원·과학기술정책연구원·교통연구원·에너지경제연구원·국토연구원·KDI 등)의
    연구보고서가 모인 곳이라, 정책연구용역 '결과물'을 찾는 목적에는 오히려 더 맞다.
  * PRISM이 담는 '부처 정책연구용역 과제'와 완전히 겹치지는 않는다. 국책연구기관이
    수탁연구보고서로 올린 것은 잡히지만, 민간 수행 용역 결과물은 빠질 수 있다.
    이 한계를 알고 쓴다.

엔드포인트 (실측):
  * `/newestExcelDown.do?listPerPage=500&currentPage=N` 이 **JSON을 그대로 돌려준다.**
    화면용 AJAX가 아니라 엑셀 내려받기용이라 인증 없이 열린다.
  * `listPerPage`·`currentPage`는 먹지만 **검색어 파라미터는 무시된다.** 그래서
    최신 N페이지를 통째로 받아 제목·초록으로 거른다 (korea.kr과 같은 구조).
  * 상세 페이지 `/newest_view.do`는 GET으로 열리지 않는다(내부 시퀀스 필요). 대신
    `/totalSearchResults.do?searchWord=<제목>`이 확실히 동작하는 것을 확인해 링크로 쓴다.

사용법:
    python3 scripts/collect_reports.py              # 최신 4페이지(2,000건)
    python3 scripts/collect_reports.py --pages 8    # 서가를 더 깊이
    python3 scripts/collect_reports.py --stdout
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import subprocess
import sys
import time
import urllib.parse
from datetime import datetime, timedelta, timezone

ROOT = pathlib.Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "reports.json"
KST = timezone(timedelta(hours=9))

LIST = "https://www.nkis.re.kr/newestExcelDown.do?listPerPage={n}&currentPage={p}"
VIEW = "https://www.nkis.re.kr/totalSearchResults.do?searchWord={q}"

# NKIS 표준분류 대분류. 이 넷이 산업·기술경영 연구가 모이는 곳이다
# (실측 2,000건 기준: 경제 333 · 국토개발 165 · 수송·교통 122 · 에너지·자원 93 · 과학기술 87).
CLASSES = {"경제", "과학기술", "수송·교통", "에너지·자원"}

TOPIC = [
    "산업", "기업", "제조", "창업", "벤처", "중소기업", "소부장", "부품",
    "클러스터", "특구", "단지", "생태계", "밸류체인", "가치사슬", "공급망",
    "수출", "무역", "투자", "R&D", "연구개발", "기술혁신", "혁신",
    "기술정책", "기술경영", "사업화", "전환", "디지털", "AI", "인공지능",
    "반도체", "배터리", "이차전지", "자동차", "모빌리티", "전기차", "수소",
    "자율주행", "UAM", "항공", "물류", "교통", "에너지", "탄소중립",
    "생산성", "경쟁력", "일자리", "지역경제", "성장동력", "규제", "정책평가", "성과",
]

# 배지는 **제목에만** 건다. 초록까지 보면 '수소공급 믹스', '탄소중립도시 공간계획'처럼
# 본문에 교통·수소가 스치기만 한 보고서에 자동차 배지가 붙는다(실측 오탐).
MOBILITY = ["자동차", "모빌리티", "전기차", "이차전지", "배터리", "자율주행",
            "UAM", "도심항공", "수소차", "수소전기차", "완성차", "차량"]

ABSTRACT_CHARS = 320   # 초록은 관련성 판단용이라 앞부분만 있으면 충분하다


def haystack(row: dict) -> str:
    return (row.get("otpHanNm") or "") + " " + (row.get("hanAbs") or "")[:400]


def is_mobility(row: dict) -> bool:
    return any(m in (row.get("otpHanNm") or "") for m in MOBILITY)


def keep(row: dict) -> bool:
    text = haystack(row)
    # 모빌리티는 분류와 무관하게 담는다 — 교통·환경·국토 어디에 분류돼 있어도 볼 가치가 있다.
    if is_mobility(row):
        return True
    if (row.get("lclaScsNm") or "") not in CLASSES:
        return False
    return any(t in text for t in TOPIC)


def fetch(page: int, rows: int) -> list | None:
    url = LIST.format(n=rows, p=page)
    for attempt in range(1, 6):
        r = subprocess.run(["curl", "-sS", "-m", "90", "-L", "-A", "Mozilla/5.0", url],
                           capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip().startswith("{"):
            try:
                return json.loads(r.stdout).get("directoryList") or []
            except json.JSONDecodeError:
                pass
        time.sleep(min(attempt * 3, 15))
    return None


def shape(row: dict) -> dict:
    title = re.sub(r"\s+", " ", row.get("otpHanNm") or "").strip()
    return {
        "id": row.get("otpId"),
        "t": title,
        "org": (row.get("agcNm") or "").strip(),
        "kind": (row.get("otcNm") or "").strip(),
        "year": (row.get("pblYy") or "").strip(),
        "author": (row.get("inchargeNm") or "").strip(),
        "cls": (row.get("lclaScsNm") or "").strip(),
        "cls2": (row.get("mclaScsNm") or "").strip(),
        "abs": re.sub(r"\s+", " ", (row.get("hanAbs") or "")).strip()[:ABSTRACT_CHARS],
        "posted": (row.get("frstCreateDtm") or "").strip(),
        "views": int(row.get("sumViewCnt") or 0),
        "downs": int(row.get("sumDownCnt") or 0),
        "mob": is_mobility(row),
        "url": VIEW.format(q=urllib.parse.quote(title)),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="NKIS 연구보고서 수집기")
    ap.add_argument("--pages", type=int, default=4, help="받을 페이지 수 (500건/페이지, 기본 4)")
    ap.add_argument("--rows", type=int, default=500)
    ap.add_argument("--stdout", action="store_true")
    args = ap.parse_args()

    now = datetime.now(KST)
    seen: dict[str, dict] = {}
    ok = failed = scanned = 0
    for page in range(1, args.pages + 1):
        got = fetch(page, args.rows)
        if got is None:
            failed += 1
            if not args.stdout:
                print(f"  page{page}: 실패", file=sys.stderr)
            continue
        ok += 1
        scanned += len(got)
        for row in got:
            if row.get("otpId") and keep(row):
                seen[row["otpId"]] = shape(row)
        if not args.stdout:
            print(f"  page{page}: {len(got)}건 (누적 훑음 {scanned} · 선별 {len(seen)})")
        if not got:
            break

    if ok == 0:
        sys.exit("모든 페이지가 실패했습니다 — NKIS 접속이나 응답 형식을 확인하세요.")

    db = json.loads(DB.read_text(encoding="utf-8")) if DB.exists() else \
        {"schema": "nkis_reports.v1", "updated_at": None, "items": []}
    known = {i["id"] for i in db["items"]}
    fresh = [v for k, v in seen.items() if k not in known]
    db["items"] += fresh
    db["updated_at"] = now.isoformat(timespec="seconds")

    if args.stdout:
        print(json.dumps({"pages_ok": ok, "pages_failed": failed, "scanned": scanned,
                          "matched": len(seen), "new": len(fresh), "items": fresh},
                         ensure_ascii=False, indent=2))
        return

    DB.parent.mkdir(parents=True, exist_ok=True)
    DB.write_text(json.dumps(db, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\n페이지 성공 {ok} / 실패 {failed} · {scanned}건 훑음")
    print(f"선별 {len(seen)}건 · 신규 {len(fresh)}건 → 누적 {len(db['items'])}건 "
          f"(자동차·모빌리티 {sum(1 for i in db['items'] if i['mob'])}건)")
    for i in fresh[:10]:
        print(f"  · {i['year']} {i['org'][:14]:14} | {i['t'][:54]}")


if __name__ == "__main__":
    main()
