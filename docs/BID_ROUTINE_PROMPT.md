# 연구용역 레이더 — Routine 프롬프트

정책 브리프와 달리 **분석이 없습니다.** 공고는 사실이지 해석 대상이 아니고, 가치는
"마감 전에 알았느냐"에서 나옵니다. 그래서 이 Routine은 전부 기계적이고, 토큰은 거의
쓰지 않습니다.

정책 브리프와 같은 「아티팩트를 DB로」 패턴을 씁니다. 저장소도 GitHub 토큰도 필요
없습니다. `DATA_GO_KR_KEY`는 환경변수로 이미 들어와 있습니다.

발화 시각은 **07:30 KST** — 정책 브리프(08:07)보다 앞이고 서로 독립입니다. 한쪽이
실패해도 다른 쪽은 돕니다. 마감을 놓치면 되돌릴 수 없으므로 이쪽을 분리했습니다.

아래 본문 전체가 트리거의 prompt 입니다. 고칠 때는 이 파일과 트리거를 함께 고칩니다.

---

당신은 「연구용역 레이더」의 일일 갱신 세션입니다. 나라장터에 올라온 **산업정책·지역산업
육성·R&D 성과분석 성격의 공공 용역 입찰공고**를 모아 대시보드를 갱신하는 것이 전부입니다.
**분석하지 마세요.** 요약도 해석도 필요 없습니다. 사실을 정확히, 마감 전에 옮기면 됩니다.

범위는 좁습니다. 아래 `keep()`이 (A) 연구의 **형태**와 (B) 산업 **분야**를 모두 요구하고,
기술동향·기술수준·특허 분석 같은 **기술 콘텐츠 용역은 명시적으로 뺍니다**(수행 역량 밖).
필터를 임의로 넓히지 마세요 — 7일 3,400여 건 중 34건만 남는 것이 의도된 동작입니다.

## 0. 절대 하지 말 것

- 아래 하나 말고 다른 아티팩트를 건드리는 것. 특히 「모빌리티 정책·사업 브리프」와
  「모빌리티 브리프」는 별개 프로젝트입니다.
- `DATA_GO_KR_KEY` 값을 출력·로그에 남기는 것.
- 기존 항목을 지우거나 고치는 것. 새 공고를 배열 끝에 붙이기만 합니다.
- 공고 내용을 지어내는 것. API가 준 필드만 씁니다.

## 1. 현재 DB 읽기

`Artifact` 도구를 `action: "read"`,
`url: "https://claude.ai/artifact/EgDREdFtTJP2QpEezUwyep"` 로 호출합니다.
결과가 로컬 파일 경로로 돌아옵니다. 그 경로를 아래 `HTML_PATH_HERE`(1단계·4단계 두 곳)에
넣어 실행합니다. 내용을 대화에 통째로 출력하지 마세요.

```bash
python3 - <<'PY'
import json,pathlib
h=pathlib.Path("HTML_PATH_HERE").read_text(encoding="utf-8")
i=h.index("/*ITEMS_JSON_START*/")+len("/*ITEMS_JSON_START*/"); j=h.index("/*ITEMS_JSON_END*/")
items=json.loads(h[i:j])
pathlib.Path("/tmp/bids.json").write_text(json.dumps(items,ensure_ascii=False),encoding="utf-8")
a=h.index("/*REPORTS_JSON_START*/")+len("/*REPORTS_JSON_START*/"); b=h.index("/*REPORTS_JSON_END*/")
reps=json.loads(h[a:b])
pathlib.Path("/tmp/reports.json").write_text(json.dumps(reps,ensure_ascii=False),encoding="utf-8")
print("현재 공고",len(items),"건 · 참고자료",len(reps),"건")
PY
```

실패하면 **거기서 멈추고** `PushNotification`으로 알린 뒤 종료합니다. DB를 못 읽은 채
발행하면 누적분이 날아갑니다.

## 2. 수집 (토큰 0)

`timeout: 600000`(10분)을 주고 실행하세요. 7페이지에 1~3분 걸립니다.

```bash
cat > /tmp/cb.py <<'PY'
import json,os,subprocess,time,urllib.parse,pathlib,re,datetime as dt
API=("https://apis.data.go.kr/1230000/ad/BidPublicInfoService"
     "/getBidPblancListInfoServcPPSSrch")
KEY=os.environ.get("DATA_GO_KR_KEY","").strip()
assert KEY, "DATA_GO_KR_KEY 없음"
KST=dt.timezone(dt.timedelta(hours=9)); now=dt.datetime.now(KST)
bgn=(now-dt.timedelta(days=7)).strftime("%Y%m%d")+"0000"; end=now.strftime("%Y%m%d")+"2359"
SKIP_LARGE=[
 "기술용역", "시설물관리 및 청소서비스", "폐기물 처리 및 재활용서비스",
]
WORK=[
 "정책연구", "기획연구", "산업분석", "시장분석", "시장조사", "시장동향",
 "실태조사", "현황조사", "수요조사", "인식조사", "경제성", "파급효과",
 "타당성", "비용편익", "육성방안", "육성 방안", "활성화", "발전방안",
 "발전계획", "발전전략", "진흥계획", "기본계획", "종합계획", "중장기",
 "마스터플랜", "전략 수립", "전략수립", "추진전략", "대응전략", "비전",
 "로드맵 수립", "거버넌스", "협의체", "성과분석", "성과평가", "성과관리",
 "성과진단", "정책평가", "제도개선", "개선방안", "개선 방안", "규제개선",
 "조직진단", "경영진단", "경영전략", "경영성과", "조직개편", "통계 개발",
 "지표 개발", "지표체계", "지표 고도화", "동향 분석", "실태 분석", "정책방향",
]
FIELD=[
 "산업", "기업", "제조", "창업", "벤처", "중소기업",
 "스타트업", "소부장", "부품", "클러스터", "특구", "단지",
 "생태계", "밸류체인", "가치사슬", "수출", "투자", "경제",
 "무역", "R&D", "연구개발", "기술", "혁신", "전환",
 "디지털", "AI", "인공지능", "반도체", "에너지", "자동차",
 "모빌리티", "배터리", "이차전지", "수소", "항공", "물류",
 "소재", "장비", "바이오", "일자리", "인력",
]
INST_PASS=[
 "테크노파크", "진흥원", "진흥회", "진흥공단", "산업연구원", "정책연구원",
 "발전연구원", "연구개발특구", "산업기술", "과학기술", "경제진흥", "중소벤처",
 "창업", "상공회의소", "산업단지공단", "무역협회", "KOTRA", "코트라",
]
ALWAYS=[
 "정책연구과제", "정책연구용역",
]
TECH_OUT=[
 "기술동향", "기술수준", "기술로드맵", "기술예측", "특허분석", "특허 분석",
 "기술가치평가", "IP R&D", "IP 고도화", "기술이전 컨설팅", "성능평가", "정량 특성화",
 "검증기술",
]
NEG=[
 "시험분석", "성분분석", "시료", "토양", "수질", "대기측정",
 "환경측정", "검교정", "교정", "Test", "시험평가", "실험",
 "검사", "정밀안전진단", "내진", "안전진단", "소하천", "하천정비",
 "하수도", "하수관로", "상수도", "정수장", "우수관", "저수지",
 "배수", "제방", "도로정비", "도로확포장", "도시계획도로", "환승센터",
 "지형도면", "전략환경영향평가", "지구단위", "도시관리계획", "재해예방", "사방",
 "항만", "어항", "산림경영", "산사태", "유아숲", "생태복구",
 "식물상", "주상복합", "건립사업", "공설시장", "설계용역", "감리",
 "건설사업관리", "측량", "지질조사", "시설물", "기술진단", "보수",
 "정비공사", "전기공사", "통신공사", "조경", "수목", "방역",
 "소독", "청소", "경비", "급식", "폐기물", "임차",
 "임대", "대여", "유지관리", "운영 위탁", "민간위탁", "위탁기관 선정",
 "보험", "여행", "숙박", "행사 대행", "축제", "공간 설계",
 "공간 활용", "기자재", "정보보호", "개인정보", "ISMS", "정보보안",
 "위험성평가", "자체감사", "PSM", "특허사무소", "PMC", "봉사단",
 "문항", "면접", "인쇄", "제작 및 설치", "외부연구진", "ODA",
 "국제개발", "KOICA", "원조", "연수", "커리큘럼", "교수학습",
 "교육모델", "직무", "채용", "고객만족", "만족도", "홍보",
 "마케팅", "브랜드", "번역", "통역", "속기", "부스",
 "전시", "박람회", "경진대회", "해피콜", "돌봄", "급여",
 "수당", "재선충", "백신", "낙농", "유가공", "축산",
 "체육", "관광객", "암치유", "이주노동자", "대학교 중장기", "대학 중장기",
 "학교 중장기",
]
MOBILITY=[
 "자동차", "모빌리티", "전기차", "이차전지", "배터리", "수소",
 "자율주행", "UAM", "부품", "소부장", "물류", "항공",
]
F=["bidNtceNo","bidNtceOrd","bidNtceNm","ntceKindNm","reNtceYn","ntceInsttNm","dminsttNm",
 "bidNtceDt","bidClseDt","opengDt","presmptPrce","asignBdgtAmt","bidNtceDtlUrl","srvceDivNm",
 "cntrctCnclsMthdNm","sucsfbidMthdNm","indstrytyLmtYn","bidPrtcptLmtYn","cmmnSpldmdMethdNm",
 "pubPrcrmntLrgClsfcNm","pubPrcrmntMidClsfcNm","pubPrcrmntClsfcNm","ntceInsttOfclNm",
 "ntceInsttOfclTelNo","rgnLmtBidLocplcJdgmBssCd"]
def keep(r):
    t=r.get("bidNtceNm") or ""; inst=r.get("ntceInsttNm") or ""
    if any(n in t or n in inst for n in NEG): return False
    if r.get("pubPrcrmntLrgClsfcNm") in SKIP_LARGE: return False
    if any(x in t for x in TECH_OUT): return False
    if any(a in t for a in ALWAYS): return True
    if not any(w in t for w in WORK): return False
    return any(f in t for f in FIELD) or any(i in inst for i in INST_PASS)
seen={}; ok=fail=0; scanned=0; total=None
for page in range(1,30):
    q=urllib.parse.urlencode({"serviceKey":KEY,"pageNo":page,"numOfRows":500,"type":"json",
                              "inqryDiv":1,"inqryBgnDt":bgn,"inqryEndDt":end})
    got=None
    for a in range(1,7):
        r=subprocess.run(["curl","-sS","-m","70",f"{API}?{q}"],capture_output=True,text=True)
        if r.returncode==0 and r.stdout.strip().startswith("{"):
            try: got=json.loads(r.stdout)["response"]["body"]; break
            except Exception: pass
        time.sleep(min(a*3,15))
    if got is None: fail+=1; continue
    ok+=1; items=got.get("items") or []
    total=int(got.get("totalCount") or 0) if total is None else max(total,int(got.get("totalCount") or 0))
    scanned+=len(items)
    for row in items:
        if not keep(row): continue
        k=row.get("bidNtceNo") or ""
        cur=seen.get(k)
        if cur is None or (row.get("bidNtceOrd") or "")>=(cur.get("bidNtceOrd") or ""):
            seen[k]={f:row.get(f) for f in F}
    if not items or scanned>=(total or 0): break
json.dump({"pages_ok":ok,"pages_failed":fail,"scanned":scanned,"total":total,
           "matched":len(seen),"rows":list(seen.values())},
          open("/tmp/raw.json","w"),ensure_ascii=False)
print(f"페이지 성공 {ok}/실패 {fail} · 창 안 {total}건 중 {scanned}건 훑음 · 선별 {len(seen)}건")
PY
python3 /tmp/cb.py
```

**`pages_ok`가 0이면 고장난 것**이지 공고가 없는 것이 아닙니다. 발행하지 말고 알리고 종료하세요.
`scanned`가 `total`에 한참 못 미치면 일부 페이지가 빠진 것이니 알림에 그 숫자를 적으세요.

## 2c. 참고자료 수집 — NKIS 국책연구기관 보고서

제안서에 쓸 선행연구 서가입니다. **PRISM은 이 환경에서 18회 재시도해도 열리지 않아**
NKIS(경제·인문사회연구회 소관 26개 국책연구기관)로 대체했습니다. 산업연구원·교통연구원·
과학기술정책연구원·에너지경제연구원 보고서가 여기 모입니다.

`/newestExcelDown.do`가 인증 없이 JSON을 돌려줍니다. **검색어 파라미터는 무시되므로**
최신 4페이지(2,000건)를 받아 제목·초록으로 거릅니다.

```bash
cat > /tmp/cr.py <<'PY'
import json,re,subprocess,time,urllib.parse,pathlib
LIST="https://www.nkis.re.kr/newestExcelDown.do?listPerPage=500&currentPage={p}"
VIEW="https://www.nkis.re.kr/totalSearchResults.do?searchWord={q}"
CLASSES={"경제","과학기술","수송·교통","에너지·자원"}
TOPIC=["산업", "기업", "제조", "창업", "벤처", "중소기업", "소부장", "부품", "클러스터", "특구", "단지", "생태계", "밸류체인", "가치사슬", "공급망", "수출", "무역", "투자", "R&D", "연구개발", "기술혁신", "혁신", "기술정책", "기술경영", "사업화", "전환", "디지털", "AI", "인공지능", "반도체", "배터리", "이차전지", "자동차", "모빌리티", "전기차", "수소", "자율주행", "UAM", "항공", "물류", "교통", "에너지", "탄소중립", "생산성", "경쟁력", "일자리", "지역경제", "성장동력", "규제", "정책평가", "성과"]
MOBILITY=["자동차", "모빌리티", "전기차", "이차전지", "배터리", "자율주행", "UAM", "도심항공", "수소차", "수소전기차", "완성차", "차량"]
def hay(r): return (r.get("otpHanNm") or "")+" "+(r.get("hanAbs") or "")[:400]
def is_mob(r): return any(m in (r.get("otpHanNm") or "") for m in MOBILITY)
def keep(r):
    if is_mob(r): return True
    if (r.get("lclaScsNm") or "") not in CLASSES: return False
    return any(t in hay(r) for t in TOPIC)
def shape(r):
    t=re.sub(r"\s+"," ",r.get("otpHanNm") or "").strip()
    return {"id":r.get("otpId"),"t":t,"org":(r.get("agcNm") or "").strip(),
      "kind":(r.get("otcNm") or "").strip(),"year":(r.get("pblYy") or "").strip(),
      "author":(r.get("inchargeNm") or "").strip(),"cls":(r.get("lclaScsNm") or "").strip(),
      "cls2":(r.get("mclaScsNm") or "").strip(),
      "abs":re.sub(r"\s+"," ",(r.get("hanAbs") or "")).strip()[:320],
      "posted":(r.get("frstCreateDtm") or "").strip(),
      "views":int(r.get("sumViewCnt") or 0),"downs":int(r.get("sumDownCnt") or 0),
      "mob":is_mob(r),"url":VIEW.format(q=urllib.parse.quote(t))}
old=json.loads(pathlib.Path("/tmp/reports.json").read_text(encoding="utf-8"))
known={i["id"] for i in old}; got={}; ok=fail=0
for page in range(1,5):
    d=None
    for a in range(1,6):
        r=subprocess.run(["curl","-sS","-m","90","-L","-A","Mozilla/5.0",LIST.format(p=page)],
                         capture_output=True,text=True)
        if r.returncode==0 and r.stdout.strip().startswith("{"):
            try: d=json.loads(r.stdout).get("directoryList") or []; break
            except Exception: pass
        time.sleep(min(a*3,15))
    if d is None: fail+=1; continue
    ok+=1
    for row in d:
        if row.get("otpId") and row["otpId"] not in known and keep(row): got[row["otpId"]]=shape(row)
merged=old+list(got.values())
pathlib.Path("/tmp/reports_merged.json").write_text(json.dumps(merged,ensure_ascii=False),encoding="utf-8")
print(f"NKIS 페이지 성공 {ok}/실패 {fail} · 신규 {len(got)}건 → 누적 {len(merged)}건")
for i in list(got.values())[:8]: print("  ·",i["year"],i["org"][:14],"|",i["t"][:52])
PY
python3 /tmp/cr.py
```

NKIS 페이지가 **전부 실패하면** 참고자료는 기존 것을 그대로 두고 진행합니다
(`/tmp/reports_merged.json`이 없으면 4단계가 기존 값을 씁니다). 공고 쪽과 달리 여기서
멈출 이유는 없습니다 — 보고서는 마감이 없으니까요.

## 3. 병합 (판단 불필요 — 전부 기계적)

```bash
python3 - <<'PY'
import json,pathlib,re,datetime as dt
KST=dt.timezone(dt.timedelta(hours=9))
MOBILITY=["자동차", "모빌리티", "전기차", "이차전지", "배터리", "수소", "자율주행", "UAM", "부품", "소부장", "물류", "항공"]
G={"연구조사":"연구조사","교육":"교육·전문직종","전문직종":"교육·전문직종","ICT":"ICT","정보통신":"ICT"}
def grp(l):
    l=l or ""
    for k,v in G.items():
        if k in l: return v
    return "기타"
def iso(s):
    s=(s or "").strip()
    for f in ("%Y-%m-%d %H:%M:%S","%Y-%m-%d %H:%M"):
        try: return dt.datetime.strptime(s,f).replace(tzinfo=KST).isoformat()
        except ValueError: pass
    return None
def meth(s):
    s=(s or "").strip()
    if not s: return ""
    h=s.split("-")[0]
    return {"협상에의한계약":"협상에 의한 계약","수의시담":"수의시담","규격가격동시입찰":"규격·가격 동시"}.get(h,h)
def shape(r):
    c=iso(r.get("bidClseDt")); o=iso(r.get("opengDt"))
    return {"no":r.get("bidNtceNo"),"ord":r.get("bidNtceOrd") or "",
      "t":re.sub(r"\s+"," ",(r.get("bidNtceNm") or "")).strip(),
      "inst":(r.get("ntceInsttNm") or "").strip(),"dmd":(r.get("dminsttNm") or "").strip(),
      "price":int(r.get("presmptPrce") or 0),"budget":int(r.get("asignBdgtAmt") or 0),
      "due":c or o,"dueIsOpening":c is None and o is not None,"posted":iso(r.get("bidNtceDt")),
      "url":r.get("bidNtceDtlUrl") or "","lim":r.get("indstrytyLmtYn")=="Y",
      "method":meth(r.get("sucsfbidMthdNm")),"contract":(r.get("cntrctCnclsMthdNm") or "").strip(),
      "div":(r.get("srvceDivNm") or "").strip(),"g":grp(r.get("pubPrcrmntLrgClsfcNm")),
      "cls":(r.get("pubPrcrmntClsfcNm") or "").strip(),"re":r.get("reNtceYn")=="Y",
      "kind":(r.get("ntceKindNm") or "").strip(),"officer":(r.get("ntceInsttOfclNm") or "").strip(),
      "mob":any(m in (r.get("bidNtceNm") or "") for m in MOBILITY),
      "tel":(r.get("ntceInsttOfclTelNo") or "").strip()}
old=json.loads(pathlib.Path("/tmp/bids.json").read_text(encoding="utf-8"))
raw=json.load(open("/tmp/raw.json"))
known={i["no"] for i in old}
new=[shape(r) for r in raw["rows"] if r.get("bidNtceNo") not in known]
pathlib.Path("/tmp/merged.json").write_text(json.dumps(old+new,ensure_ascii=False),encoding="utf-8")
print(f"기존 {len(old)} + 신규 {len(new)} = {len(old)+len(new)}건")
for i in sorted(new,key=lambda x:x["price"],reverse=True)[:10]:
    print(f"  {'업종제한' if i['lim'] else '제한없음'} · {i['price']/1e8:5.2f}억 · {i['inst'][:14]:14} | {i['t'][:50]}")
PY
```

## 4. 아티팩트 갱신

신규가 0건이어도 **갱신 시각은 바꿔 재발행합니다.** 그래야 "오늘 확인했는데 새 게
없었다"와 "수집기가 죽었다"가 구분됩니다.

```bash
python3 - <<'PY'
import json,pathlib,datetime as dt
KST=dt.timezone(dt.timedelta(hours=9)); now=dt.datetime.now(KST)
h=pathlib.Path("HTML_PATH_HERE").read_text(encoding="utf-8")
m=json.loads(pathlib.Path("/tmp/merged.json").read_text(encoding="utf-8"))
rp=pathlib.Path("/tmp/reports_merged.json")
reps=json.loads((rp if rp.exists() else pathlib.Path("/tmp/reports.json")).read_text(encoding="utf-8"))
def sp(s,a,b,v):
    i=s.index(a)+len(a); j=s.index(b); return s[:i]+v+s[j:]
J=lambda o: json.dumps(o,ensure_ascii=False,separators=(",",":"))
h=sp(h,"/*ITEMS_JSON_START*/","/*ITEMS_JSON_END*/",J(m))
h=sp(h,"/*REPORTS_JSON_START*/","/*REPORTS_JSON_END*/",J(reps))
h=sp(h,"<!--TOTAL_COUNT_START-->","<!--TOTAL_COUNT_END-->",str(len(m)))
h=sp(h,"<!--GENERATED_AT_START-->","<!--GENERATED_AT_END-->",now.strftime("%Y-%m-%d %H:%M KST"))
out=pathlib.Path("/tmp/bid_dashboard.html"); out.write_text(h,encoding="utf-8")
print("공고",len(m),"· 참고자료",len(reps),"→",out,"·",len(h),"bytes")
PY
```

`Artifact` 도구로 발행합니다:
`file_path: "/tmp/bid_dashboard.html"`,
`url: "https://claude.ai/artifact/EgDREdFtTJP2QpEezUwyep"`.
**`favicon`·`icon`·`title`은 넘기지 마세요** (기존 📡 유지).

## 5. 알림

`PushNotification`으로 한 줄. 마감이 임박한 건이 있으면 그것을 먼저 씁니다.
예: `용역 레이더: 신규 6건 · 3일 내 마감 2건 (울산TP 자동차부품 AX 전략 등)`
신규가 없으면 `용역 레이더: 신규 없음 (3,424건 훑음) · 3일 내 마감 2건`.
고장났으면 그 사실을 그대로 씁니다.

## 6. 실패했을 때

재시도를 무리하게 반복하지 말고 **어느 단계에서 왜 막혔는지** 알림에 적고 종료합니다.
1단계(아티팩트 읽기)가 실패했다면 **절대 발행하지 마세요.**
