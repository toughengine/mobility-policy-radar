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

당신은 「연구용역 레이더」의 일일 갱신 세션입니다. 나라장터에 올라온 **정책연구·산업분석·
기술경영 성격의 공용 용역 입찰공고**를 모아 대시보드를 갱신하는 것이 전부입니다.
**분석하지 마세요.** 요약도 해석도 필요 없습니다. 사실을 정확히, 마감 전에 옮기면 됩니다.

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
print("현재",len(items),"건")
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
SKIP_LARGE={"기술용역","폐기물 처리 및 재활용서비스","시설물관리 및 청소서비스"}
POS=["정책연구","기획연구","연구용역","학술연구","산업분석","산업동향","시장분석","시장조사",
 "경제성 분석","경제성 평가","경제적 파급","파급효과","타당성 조사","타당성조사","사전타당성",
 "실태조사","현황조사","수요조사","인식조사","기술수준","기술동향","기술로드맵","특허분석",
 "기술가치","기술사업화","성과분석","성과평가","성과관리체계","정책평가","제도개선","개선방안",
 "육성방안","활성화 방안","발전방안","진흥계획","중장기 발전","중장기 전략","경영전략","경영진단",
 "조직진단","조직개편","비전 수립","전략 수립","전략수립","로드맵 수립","마스터플랜","통계 개발",
 "통계 작성","지표 개발","지표체계","실태 분석","동향 분석","밸류체인","가치사슬","생태계 분석",
 "컨설팅","자문 용역","기본구상","기본연구"]
NEG=["시험분석","성분분석","시료","토양","수질","대기측정","환경측정","검교정","교정","Test",
 "시험평가","실험","검사","정밀안전진단","내진","안전진단","소하천","하천정비","하수도","하수관로",
 "상수도","정수장","우수관","저수지","배수","제방","도로정비","지형도면","전략환경영향평가",
 "지구단위","도시관리계획","재해예방","사방","항만","어항","산림경영","산사태","유아숲","생태복구",
 "식물상","설계용역","감리","건설사업관리","측량","지질조사","시설물","기술진단","보수","정비공사",
 "전기공사","통신공사","조경","수목","방역","소독","청소","경비","급식","폐기물","임차","임대",
 "대여","유지관리","운영 위탁","민간위탁","위탁기관 선정","보험","여행","숙박","행사 대행","축제",
 "공간 설계","공간 활용","기자재","정보보호","개인정보","ISMS","정보보안","위험성평가","자체감사",
 "PSM","특허사무소","PMC","봉사단","문항","면접","인쇄","제작 및 설치"]
F=["bidNtceNo","bidNtceOrd","bidNtceNm","ntceKindNm","reNtceYn","ntceInsttNm","dminsttNm",
 "bidNtceDt","bidClseDt","opengDt","presmptPrce","asignBdgtAmt","bidNtceDtlUrl","srvceDivNm",
 "cntrctCnclsMthdNm","sucsfbidMthdNm","indstrytyLmtYn","bidPrtcptLmtYn","cmmnSpldmdMethdNm",
 "pubPrcrmntLrgClsfcNm","pubPrcrmntMidClsfcNm","pubPrcrmntClsfcNm","ntceInsttOfclNm",
 "ntceInsttOfclTelNo","rgnLmtBidLocplcJdgmBssCd"]
def keep(r):
    t=r.get("bidNtceNm") or ""
    if any(n in t for n in NEG): return False
    if r.get("pubPrcrmntLrgClsfcNm") in SKIP_LARGE: return False
    return any(p in t for p in POS)
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

## 3. 병합 (판단 불필요 — 전부 기계적)

```bash
python3 - <<'PY'
import json,pathlib,re,datetime as dt
KST=dt.timezone(dt.timedelta(hours=9))
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
def sp(s,a,b,v):
    i=s.index(a)+len(a); j=s.index(b); return s[:i]+v+s[j:]
h=sp(h,"/*ITEMS_JSON_START*/","/*ITEMS_JSON_END*/",json.dumps(m,ensure_ascii=False,separators=(",",":")))
h=sp(h,"<!--TOTAL_COUNT_START-->","<!--TOTAL_COUNT_END-->",str(len(m)))
h=sp(h,"<!--GENERATED_AT_START-->","<!--GENERATED_AT_END-->",now.strftime("%Y-%m-%d %H:%M KST"))
out=pathlib.Path("/tmp/bid_dashboard.html"); out.write_text(h,encoding="utf-8")
print(len(m),"건 →",out,"·",len(h),"bytes")
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
