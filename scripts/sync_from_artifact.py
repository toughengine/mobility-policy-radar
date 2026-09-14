#!/usr/bin/env python3
"""발행된 대시보드(아티팩트)의 항목을 저장소 DB로 되가져온다.

왜 필요한가:
  Routine이 깨우는 세션은 저장소를 체크아웃하지 못한다(실측). 그래서 일일 자동화는
  저장소가 아니라 **발행된 대시보드 HTML 안의 마커**를 DB로 쓴다. 그 결과 정본이
  아티팩트 쪽에 쌓이고 `data/policy_items.json`은 그 시점부터 뒤처진다.

  이 스크립트가 그 간격을 메운다. 사람이 있는 세션에서 아티팩트를 내려받아
  이 스크립트에 물리면 저장소 DB가 아티팩트와 같아진다. git 이력이 있어야
  "언제 무엇이 늘었는지"를 되짚을 수 있으므로 이 되돌림은 버릴 수 없다.

사용법:
    # Artifact 도구의 read_file / read 로 index.html 을 받아둔 뒤
    python3 scripts/sync_from_artifact.py <내려받은 index.html>
    python3 scripts/sync_from_artifact.py <파일> --check   # 쓰지 않고 차이만 본다

안전장치: 아티팩트 쪽 항목이 저장소보다 **적으면** 쓰지 않고 멈춘다. 자동화가
항목을 잃은 채 발행한 사고라면 그것을 저장소에까지 덮어쓰면 안 된다.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
from datetime import datetime, timedelta, timezone

ROOT = pathlib.Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "policy_items.json"
KST = timezone(timedelta(hours=9))


def extract(html: str) -> list[dict]:
    a, b = "/*ITEMS_JSON_START*/", "/*ITEMS_JSON_END*/"
    if a not in html or b not in html:
        sys.exit("마커를 찾지 못했습니다 — 대시보드 HTML이 맞는지 확인하세요.")
    return json.loads(html[html.index(a) + len(a):html.index(b)])


def main() -> None:
    ap = argparse.ArgumentParser(description="아티팩트 → 저장소 DB 동기화")
    ap.add_argument("html", help="내려받은 대시보드 index.html")
    ap.add_argument("--check", action="store_true", help="쓰지 않고 차이만 보고")
    args = ap.parse_args()

    live = extract(pathlib.Path(args.html).read_text(encoding="utf-8"))
    db = json.loads(DB.read_text(encoding="utf-8"))
    repo = db["items"]

    repo_ids = {i["id"] for i in repo}
    live_ids = {i["id"] for i in live}
    added = [i for i in live if i["id"] not in repo_ids]
    lost = [i for i in repo if i["id"] not in live_ids]

    print(f"저장소 {len(repo)}건 · 아티팩트 {len(live)}건")
    for i in added:
        print(f"  + {i['date']} {i['title'][:60]}")
    for i in lost:
        print(f"  - {i['date']} {i['title'][:60]}  ← 아티팩트에서 사라짐")

    if lost:
        sys.exit("\n아티팩트에 없는 항목이 있습니다. 자동화가 데이터를 잃었을 수 있으니 "
                 "덮어쓰지 않고 멈춥니다. 원인을 먼저 확인하세요.")
    if not added:
        print("차이 없음 — 할 일이 없습니다.")
        return
    if args.check:
        print(f"\n--check 모드 — 쓰지 않았습니다 ({len(added)}건 추가 예정)")
        return

    db["items"] = live
    db["updated_at"] = datetime.now(KST).isoformat(timespec="seconds")
    DB.write_text(json.dumps(db, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\n{len(added)}건 반영 → {DB.relative_to(ROOT)}")
    print("이제 `python3 scripts/generate_dashboard.py` 로 저장소 쪽 HTML도 맞추고 커밋하세요.")


if __name__ == "__main__":
    main()
