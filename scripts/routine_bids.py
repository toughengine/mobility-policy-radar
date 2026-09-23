#!/usr/bin/env python3
"""연구용역 레이더 — 자동화 세션이 실행하는 단일 진입점.

매일 07:30 KST Routine이 깨우는 세션에는 저장소 체크아웃이 없다. 그래서 이 스크립트를
`raw.githubusercontent.com`에서 형제 모듈과 함께 내려받아 실행한다. 수집 규칙과 화면
템플릿이 프롬프트가 아니라 **저장소에 한 벌만 존재**하게 만드는 것이 목적이다 —
필터를 고치면 자동화에도 그대로 반영되고, 프롬프트와 코드가 어긋날 일이 없다.

    python3 routine_bids.py <아티팩트에서 받은 HTML 경로>

하는 일:
  1. HTML의 마커에서 기존 공고·참고자료를 꺼낸다 (아티팩트가 DB다)
  2. 나라장터 API로 공고를, NKIS로 보고서를 새로 받는다
  3. 기존에 없던 것만 골라 붙인다
  4. 저장소의 템플릿으로 페이지를 다시 그려 /tmp/bid_dashboard.html 에 쓴다

종료 코드 2는 **발행하지 말라**는 뜻이다(공고 수집이 고장난 경우). 참고자료 수집만
실패한 경우는 기존 값을 유지하고 정상 종료한다 — 보고서에는 마감이 없기 때문이다.
"""
from __future__ import annotations

import json
import os
import pathlib
import sys
from datetime import datetime

import collect_bids as B
import collect_reports as R
import generate_bid_dashboard as G


def cut(html: str, a: str, b: str):
    return json.loads(html[html.index(a) + len(a):html.index(b)])


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit("사용법: routine_bids.py <아티팩트 HTML 경로>")
    src = pathlib.Path(sys.argv[1])
    html = src.read_text(encoding="utf-8")

    items = cut(html, "/*ITEMS_JSON_START*/", "/*ITEMS_JSON_END*/")
    reports = cut(html, "/*REPORTS_JSON_START*/", "/*REPORTS_JSON_END*/")
    print(f"현재 공고 {len(items)}건 · 참고자료 {len(reports)}건")

    # ---- 공고 ----
    if not os.environ.get("DATA_GO_KR_KEY", "").strip():
        print("DATA_GO_KR_KEY 환경변수가 없습니다.", file=sys.stderr)
        sys.exit(2)
    now = datetime.now(B.KST)
    bgn = (now - __import__("datetime").timedelta(days=7)).strftime("%Y%m%d") + "0000"
    end = now.strftime("%Y%m%d") + "2359"
    key = os.environ["DATA_GO_KR_KEY"].strip()

    known_no = {i["no"] for i in items}
    fresh_bids, ok, failed, scanned, total = {}, 0, 0, 0, None
    for page in range(1, 30):
        rows, tot = B.fetch(page, bgn, end, 500, key)
        if tot == -1:
            failed += 1
            continue
        ok += 1
        total = tot if total is None else max(total, tot)
        scanned += len(rows)
        for row in rows:
            if not B.keep(row):
                continue
            no = row.get("bidNtceNo") or ""
            if no in known_no or no in fresh_bids:
                continue
            fresh_bids[no] = G.shape(row)
        if not rows or scanned >= (total or 0):
            break
    print(f"나라장터 페이지 성공 {ok}/실패 {failed} · 창 안 {total}건 중 {scanned}건 훑음 "
          f"· 신규 {len(fresh_bids)}건")
    if ok == 0:
        print("나라장터 수집이 전부 실패했습니다 — 발행하지 마세요.", file=sys.stderr)
        sys.exit(2)

    # ---- 참고자료 (실패해도 멈추지 않는다) ----
    known_id = {r["id"] for r in reports}
    fresh_reports, rok, rfail = {}, 0, 0
    for page in range(1, 5):
        got = R.fetch(page, 500)
        if got is None:
            rfail += 1
            continue
        rok += 1
        for row in got:
            rid = row.get("otpId")
            if rid and rid not in known_id and rid not in fresh_reports and R.keep(row):
                fresh_reports[rid] = R.shape(row)
    print(f"NKIS 페이지 성공 {rok}/실패 {rfail} · 신규 {len(fresh_reports)}건"
          + ("  (참고자료는 기존 값 유지)" if rok == 0 else ""))

    merged_bids = items + list(fresh_bids.values())
    merged_reports = reports + list(fresh_reports.values())
    out = pathlib.Path("/tmp/bid_dashboard.html")
    out.write_text(G.render(merged_bids, merged_reports, now), encoding="utf-8")

    # 마감 임박 건수는 알림 문구에 쓰인다.
    soon = 0
    for i in merged_bids:
        d = i.get("due")
        if not d:
            continue
        try:
            left = (datetime.fromisoformat(d) - now).days
        except ValueError:
            continue
        if 0 <= left <= 3:
            soon += 1

    print(f"\n공고 {len(merged_bids)}건 · 참고자료 {len(merged_reports)}건 → {out}")
    print(f"SUMMARY: 공고신규={len(fresh_bids)} 참고자료신규={len(fresh_reports)} "
          f"3일내마감={soon} 훑음={scanned}")
    for i in sorted(fresh_bids.values(), key=lambda x: x["price"], reverse=True)[:8]:
        print(f"  · {'업종제한' if i['lim'] else '제한없음'} {i['price']/1e8:5.2f}억 "
              f"{i['inst'][:14]:14} | {i['t'][:50]}")


if __name__ == "__main__":
    main()
