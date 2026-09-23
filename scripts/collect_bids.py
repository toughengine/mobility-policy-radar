#!/usr/bin/env python3
"""나라장터 용역 입찰공고 수집기 — 「연구용역 레이더」.

모빌리티 정책 브리프와 목적이 다르다. 저쪽은 '왜 지금 이 정책인가'를 공부하는 것이고,
이쪽은 **내가 수주할 수 있는 연구용역을 마감 전에 찾는 것**이다. 그래서 analysis 4필드가
없다. 대신 마감·추정가격·업종제한이 전부다.

설계 근거 (2026-09-23 실측, 7일치 3,410건 전수 분석):

  * 소스는 나라장터 하나로 충분하다. 공공기관은 일정 금액 이상 용역을 법적으로 여기
    공고해야 해서 부처·지자체·공공기관·출연연·테크노파크 발주가 전부 모인다.
    g2b.go.kr 웹은 이 환경에서 8회 재시도해도 안 열리지만 **apis.data.go.kr API는 열린다.**
  * 7일 3,410건 중 대상은 극소수다. 조달 대분류로 1차를 거른다:
      기술용역(토목·건축 설계·감리) 905 · 행사관리 332 · 폐기물 190 … 전부 대상 아님
      **연구조사서비스 273** (학술연구서비스 266)  ← 핵심
  * 대분류만으로는 부족하다. 「연구조사서비스」 안에도 GAP토양용수 안전성 분석,
    Round Robin Test, 토양조사 같은 **시험·분석 용역**이 섞여 있다. 제목 키워드로
    2차를 걸러야 한다.
  * 반대로 POS 키워드만 쓰면 '기본계획·종합계획'이 소하천정비·하수도정비 같은 토목
    계획을 대량으로 끌어온다. NEG가 그만큼 중요하다.
  * 조건을 'A(연구 형태) AND B(산업 분야)'로 걸어 35건/7일(하루 5건)로 수렴했다.
    형태만 보면 체육인·낙농·백신 실태조사와 도로 타당성조사가, 분야만 보면
    시험분석이 들어온다. 둘 다 걸어야 목록이 읽을 만해진다.

**업종제한으로 거르지 않는다.** `indstrytyLmtYn`은 표본에서 Y 605 / N 387로 39%가
제한 없음이다. 수집 단계에서 Y를 버리면 회사가 마침 그 업종을 가진 건까지 날아간다.
거르지 말고 화면에 배지로 띄워 사용자가 판단하게 한다.

사용법:
    export DATA_GO_KR_KEY='data.go.kr Decoding 인증키'
    python3 scripts/collect_bids.py              # 최근 7일
    python3 scripts/collect_bids.py --days 30    # 재고를 더 깊이
    python3 scripts/collect_bids.py --stdout     # 저장하지 않고 출력만
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import subprocess
import sys
import time
import urllib.parse
from datetime import datetime, timedelta, timezone

ROOT = pathlib.Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "bids.json"
KST = timezone(timedelta(hours=9))

API = ("https://apis.data.go.kr/1230000/ad/BidPublicInfoService"
       "/getBidPblancListInfoServcPPSSrch")

# 대분류 1차 — 이쪽은 아예 보지 않는다 (토목 설계·감리, 폐기물, 청소 등).
SKIP_LARGE = {"기술용역", "폐기물 처리 및 재활용서비스", "시설물관리 및 청소서비스"}

# (A) 어떤 '일'인가 — 산업·정책·경영 연구의 형태여야 한다.
WORK = [
    "정책연구", "기획연구", "산업분석", "시장분석", "시장조사", "시장동향",
    "실태조사", "현황조사", "수요조사", "인식조사",
    "경제성", "파급효과", "타당성", "비용편익",
    "육성방안", "육성 방안", "활성화", "발전방안", "발전계획", "발전전략", "진흥계획",
    "기본계획", "종합계획", "중장기", "마스터플랜", "전략 수립", "전략수립",
    "추진전략", "대응전략", "비전 수립", "비전수립", "로드맵 수립", "거버넌스", "협의체",
    "성과분석", "성과평가", "성과관리", "성과진단", "정책평가",
    "제도개선", "개선방안", "개선 방안", "규제개선",
    "조직진단", "경영진단", "경영전략", "경영성과", "조직개편",
    "통계 개발", "지표 개발", "지표체계", "지표 고도화", "동향 분석", "실태 분석", "정책방향",
]

# (B) 어떤 '분야'인가 — 산업·기술경영 맥락이어야 한다.
FIELD = [
    "산업", "기업", "제조", "창업", "벤처", "중소기업", "스타트업", "소부장", "부품",
    "클러스터", "특구", "단지", "생태계", "밸류체인", "가치사슬",
    "수출", "투자", "경제", "무역", "R&D", "연구개발", "기술", "혁신", "전환",
    "디지털", "AI", "인공지능", "반도체", "에너지",
    "자동차", "모빌리티", "배터리", "이차전지", "수소", "항공", "물류",
    "소재", "장비", "바이오", "일자리", "인력",
]

# 발주기관이 산업진흥·정책연구 계열이면 (B)를 면제한다 — 기관 자체가 분야를 말해준다.
# 실측: 전북TP「경영성과 진단」, 산업연구원「가격표시제 운영실태」처럼 제목에 산업 키워드가
# 없어도 명백히 대상인 건들이 이 면제로 살아난다.
INST_PASS = [
    "테크노파크", "진흥원", "진흥회", "진흥공단", "산업연구원", "정책연구원", "발전연구원",
    "연구개발특구", "산업기술", "과학기술", "경제진흥", "중소벤처", "창업",
    "상공회의소", "산업단지공단", "무역협회", "KOTRA", "코트라",
]

# 부처 정책연구과제 공모는 제목이 짧아 (A)(B)에 안 걸리는 경우가 있어 무조건 통과시킨다.
ALWAYS = ["정책연구과제", "정책연구용역"]

# **기술 자체를 분석하는 용역은 뺀다.** 기술동향·기술수준·특허 분석은 수행 역량 밖이다.
# 반면 기술사업화 '정책·성과' 연구는 기술경영이므로 남긴다 — 다른 것이다.
TECH_OUT = [
    "기술동향", "기술수준", "기술로드맵", "기술예측", "특허분석", "특허 분석",
    "기술가치평가", "IP R&D", "IP 고도화", "기술이전 컨설팅",
    "성능평가", "정량 특성화", "검증기술",
]

# 제목(또는 기관명)에 이 말이 있으면 버린다. 실측에서 실제로 섞여 들어온 것들만 넣었다.
NEG = [
    # 시험·측정·분석
    "시험분석", "성분분석", "시료", "토양", "수질", "대기측정", "환경측정", "검교정", "교정",
    "Test", "시험평가", "실험", "검사", "정밀안전진단", "내진", "안전진단",
    # 토목·건축·시설 — '기본계획/종합계획/타당성'이 이쪽을 대량으로 끌어온다
    "소하천", "하천정비", "하수도", "하수관로", "상수도", "정수장", "우수관", "저수지", "배수",
    "제방", "도로정비", "도로확포장", "도시계획도로", "환승센터", "지형도면",
    "전략환경영향평가", "지구단위", "도시관리계획", "재해예방", "사방", "항만", "어항",
    "산림경영", "산사태", "유아숲", "생태복구", "식물상", "주상복합", "건립사업", "공설시장",
    "설계용역", "감리", "건설사업관리", "측량", "지질조사", "시설물", "기술진단",
    "보수", "정비공사", "전기공사", "통신공사", "조경", "수목",
    # 운영·관리 위탁
    "방역", "소독", "청소", "경비", "급식", "폐기물", "임차", "임대", "대여", "유지관리",
    "운영 위탁", "민간위탁", "위탁기관 선정", "보험", "여행", "숙박", "행사 대행", "축제",
    "공간 설계", "공간 활용", "기자재",
    # 결이 다른 컨설팅·용역
    "정보보호", "개인정보", "ISMS", "정보보안", "위험성평가", "자체감사", "PSM",
    "특허사무소", "PMC", "봉사단", "문항", "면접", "인쇄", "제작 및 설치", "외부연구진",
    "ODA", "국제개발", "KOICA", "한국국제협력단", "원조", "연수", "항공보안", "커리큘럼", "교수학습", "교육모델",
    "직무", "채용", "고객만족", "만족도", "홍보", "마케팅", "브랜드", "번역", "통역", "속기",
    "부스", "전시", "박람회", "경진대회", "해피콜", "돌봄", "급여", "수당",
    "위탁제조", "위탁운영", "위탁 운영", "디지털화", "프로그램 운영", "평생교육",
    # 분야가 다른 조사
    "재선충", "백신", "낙농", "유가공", "축산", "체육", "관광객", "암치유", "이주노동자",
    # 대학 자체 발전계획
    "대학교 중장기", "대학 중장기", "학교 중장기",
]

# 자동차·모빌리티 관련이면 표시한다. 거르지는 않는다 — 한정할 필요는 없다고 했다.
MOBILITY = ["자동차", "모빌리티", "전기차", "이차전지", "배터리", "수소", "자율주행",
            "UAM", "부품", "소부장", "물류", "항공"]

KEEP_FIELDS = [
    "bidNtceNo", "bidNtceOrd", "bidNtceNm", "ntceKindNm", "reNtceYn",
    "ntceInsttNm", "dminsttNm", "bidNtceDt", "bidClseDt", "opengDt",
    "presmptPrce", "asignBdgtAmt", "bidNtceDtlUrl",
    "srvceDivNm", "cntrctCnclsMthdNm", "sucsfbidMthdNm",
    "indstrytyLmtYn", "bidPrtcptLmtYn", "cmmnSpldmdMethdNm",
    "pubPrcrmntLrgClsfcNm", "pubPrcrmntMidClsfcNm", "pubPrcrmntClsfcNm",
    "ntceInsttOfclNm", "ntceInsttOfclTelNo", "rgnLmtBidLocplcJdgmBssCd",
]


def keep(row: dict) -> bool:
    """(A) 산업·정책·경영 연구의 형태이고 (B) 산업 맥락일 것. 기술 분석은 뺀다."""
    title = row.get("bidNtceNm") or ""
    inst = row.get("ntceInsttNm") or ""
    if any(n in title or n in inst for n in NEG):
        return False
    if row.get("pubPrcrmntLrgClsfcNm") in SKIP_LARGE:
        return False
    if any(x in title for x in TECH_OUT):
        return False
    if any(a in title for a in ALWAYS):
        return True
    if not any(w in title for w in WORK):
        return False
    return any(f in title for f in FIELD) or any(i in inst for i in INST_PASS)


def fetch(page: int, bgn: str, end: str, rows: int, key: str) -> tuple[list, int]:
    """한 페이지를 받는다. 릴레이가 간헐적으로 끊기므로 재시도가 필수다(실측)."""
    q = urllib.parse.urlencode({
        "serviceKey": key, "pageNo": page, "numOfRows": rows, "type": "json",
        "inqryDiv": 1, "inqryBgnDt": bgn, "inqryEndDt": end,
    })
    for attempt in range(1, 7):
        r = subprocess.run(["curl", "-sS", "-m", "70", f"{API}?{q}"],
                           capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip().startswith("{"):
            try:
                body = json.loads(r.stdout)["response"]["body"]
            except (KeyError, json.JSONDecodeError):
                break
            return body.get("items") or [], int(body.get("totalCount") or 0)
        time.sleep(min(attempt * 3, 15))
    return [], -1     # -1 = 이 페이지는 실패했다 (0건과 구분한다)


def load_db() -> dict:
    if DB.exists():
        return json.loads(DB.read_text(encoding="utf-8"))
    return {"schema": "gov_service_bids.v1", "updated_at": None, "items": []}


def main() -> None:
    ap = argparse.ArgumentParser(description="나라장터 용역 입찰공고 수집기")
    ap.add_argument("--days", type=int, default=7, help="며칠치를 볼지 (기본 7)")
    ap.add_argument("--rows", type=int, default=500, help="페이지당 건수 (기본 500)")
    ap.add_argument("--stdout", action="store_true", help="저장하지 않고 출력만")
    args = ap.parse_args()

    key = os.environ.get("DATA_GO_KR_KEY", "").strip()
    if not key:
        sys.exit("DATA_GO_KR_KEY 환경변수가 없습니다. data.go.kr의 Decoding 인증키가 필요합니다.")

    now = datetime.now(KST)
    bgn = (now - timedelta(days=args.days)).strftime("%Y%m%d") + "0000"
    end = now.strftime("%Y%m%d") + "2359"

    seen: dict[str, dict] = {}
    scanned = pages_ok = pages_failed = 0
    total = None
    for page in range(1, 30):
        items, tot = fetch(page, bgn, end, args.rows, key)
        if tot == -1:
            pages_failed += 1
            if not args.stdout:
                print(f"  page{page}: 실패", file=sys.stderr)
            continue
        pages_ok += 1
        total = tot if total is None else max(total, tot)
        scanned += len(items)
        for row in items:
            if keep(row):
                # 같은 공고의 차수(bidNtceOrd) 변경분은 가장 나중 것만 남긴다
                k = row.get("bidNtceNo") or ""
                cur = seen.get(k)
                if cur is None or (row.get("bidNtceOrd") or "") >= (cur.get("bidNtceOrd") or ""):
                    seen[k] = {f: row.get(f) for f in KEEP_FIELDS}
        if not args.stdout:
            print(f"  page{page}: {len(items)}건 (누적 훑음 {scanned}/{total} · 선별 {len(seen)})")
        if not items or scanned >= (total or 0):
            break

    db = load_db()
    known = {i["bidNtceNo"] for i in db["items"]}
    fresh = [v for k, v in seen.items() if k not in known]
    for i in fresh:
        i["collected_at"] = now.strftime("%Y-%m-%d")

    payload = {
        "source": "나라장터 용역 입찰공고 (apis.data.go.kr)",
        "collected_at": now.strftime("%Y-%m-%d"),
        "window": f"{bgn}~{end}",
        # 0건이 '없어서'인지 '고장나서'인지 구분하려면 이 숫자들이 필요하다.
        "pages_ok": pages_ok, "pages_failed": pages_failed,
        "total_in_window": total, "scanned": scanned,
        "matched": len(seen), "already_known": len(seen) - len(fresh),
        "new": len(fresh), "items": fresh,
    }

    if args.stdout:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    # 누적 DB에 붙인다. 이 레이더는 분석이 필요 없으므로 승격 단계가 없다.
    db["items"] += fresh
    db["updated_at"] = now.isoformat(timespec="seconds")
    DB.parent.mkdir(parents=True, exist_ok=True)
    DB.write_text(json.dumps(db, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    inbox = ROOT / "data" / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    (inbox / f"bids-{now.strftime('%Y-%m-%d')}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n페이지 성공 {pages_ok} / 실패 {pages_failed} · 창 안 전체 {total}건 중 {scanned}건 훑음")
    print(f"선별 {len(seen)}건 · 기존 제외 후 신규 {len(fresh)}건 → 누적 {len(db['items'])}건")
    for i in sorted(fresh, key=lambda r: int(r.get("presmptPrce") or 0), reverse=True)[:15]:
        amt = int(i.get("presmptPrce") or 0) / 1e8
        lim = "업종제한" if i.get("indstrytyLmtYn") == "Y" else "제한없음"
        print(f"  · {lim} · {amt:6.2f}억 · {(i.get('ntceInsttNm') or '')[:14]:14} | {(i.get('bidNtceNm') or '')[:52]}")


if __name__ == "__main__":
    main()
