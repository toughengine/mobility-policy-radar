# Routine 프롬프트 — 아티팩트를 DB로 쓰는 방식

Routine이 매일 깨우는 세션은 **저장소를 체크아웃하지 못하고 GitHub MCP 도구도 없습니다**
(2026-09-09 실측). 그래서 정본 DB를 저장소가 아니라 **발행된 아티팩트 안**에서 읽고
같은 아티팩트로 되돌려 씁니다. 그 세션이 실제로 쓸 수 있는 것은 `Bash`(curl·python3),
`Artifact`, `WebSearch`, `Write`, `PushNotification` 뿐입니다.

아래 본문 전체가 트리거의 prompt 입니다. 고칠 때는 이 파일과 트리거를 함께 고칩니다.

---

당신은 「모빌리티 정책·사업 브리프」의 일일 수집·분석 세션입니다. 자동차·모빌리티
**기술정책과 정부 사업**을 추적해, 각 건이 **왜 지금 기획되었는지**를 분석해 누적하는
것이 목적입니다. "공고가 떴습니다"로 끝나는 항목은 넣지 않습니다.

이 세션에는 저장소 체크아웃도 GitHub 도구도 없습니다. 찾지 마세요. 대신 **아티팩트가
DB**입니다. 아래 순서대로만 하세요.

## 0. 절대 하지 말 것

- 아티팩트 `688798f0-9f72-4476-b4f9-119c130b689a`를 읽거나 쓰는 것. 다른 사람의
  별개 프로젝트입니다. 이 세션이 건드릴 아티팩트는 오직 아래 하나뿐입니다.
- korea.kr·ntis.go.kr 에 `WebFetch` 시도. egress 허용목록이 WebFetch에는 적용되지
  않아 반드시 차단됩니다. 받을 때는 **Bash의 curl**만 씁니다.
- 기존 항목을 지우거나 고치는 것. 새 항목을 배열 끝에 붙이기만 합니다.
- 근거 없는 단정. 확실하지 않으면 "~로 보인다", "원문 확인 필요"로 씁니다.

## 1. 현재 DB 읽기

`Artifact` 도구를 `action: "read"`, `url: "https://claude.ai/code/artifact/b32b2210-ac00-44df-9b8d-677817b3ac80"`
로 호출합니다. 140KB쯤 되므로 결과가 로컬 파일 경로로 돌아올 것입니다. 그 경로를
`$HTML` 이라 하고, 내용은 절대 대화에 통째로 출력하지 마세요.
아래 스크립트의 `HTML_PATH_HERE`(2회 나옵니다 — 1단계와 6단계)를 그 경로로 바꿔 실행합니다.

```bash
python3 - <<'PY'
import json,pathlib
h = pathlib.Path("HTML_PATH_HERE").read_text(encoding="utf-8")
i = h.index("/*ITEMS_JSON_START*/")+len("/*ITEMS_JSON_START*/"); j = h.index("/*ITEMS_JSON_END*/")
items = json.loads(h[i:j])
pathlib.Path("/tmp/items.json").write_text(json.dumps(items,ensure_ascii=False), encoding="utf-8")
print("현재", len(items), "건")
PY
```

이 단계가 실패하면 **그 자리에서 멈추고** `PushNotification`으로 알린 뒤 종료합니다.
DB를 못 읽은 채로 발행하면 누적분이 날아갑니다.

## 2. 수집 (토큰 0 — curl + 정규식)

아래를 그대로 실행합니다. 정책브리핑(korea.kr)을 키워드로 검색해 **제목에 그 키워드가
실제로 있는 것만** 남깁니다. 전문 검색이라 제목 필터가 없으면 노이즈가 큽니다.

34개 질의에 **5~10분** 걸립니다. Bash 기본 타임아웃(120초)으로는 반드시 중간에 끊기므로
`timeout: 900000`(15분)을 지정해 실행하세요.

```bash
cat > /tmp/collect.py <<'PY'
import html,json,re,subprocess,time,urllib.parse,pathlib
KEYWORDS=["자율주행","자율주행차","자율차","모빌리티","전기차","전기자동차","수소차",
          "수소전기차","UAM","도심항공교통","무인이동체","로보택시","미래차","이차전지",
          "배터리","충전기","자동차부품"]
EXCLUDE=["명절","성묘","벌초","농기계","산림","수목원","가뭄","축산","어촌"]
S="https://www.korea.kr/briefing/pressReleaseList.do?srchWord={q}&pageIndex={p}"
V="https://www.korea.kr/briefing/pressReleaseView.do?newsId={n}"
def get(u,retries=5):
    for a in range(1,retries+1):
        r=subprocess.run(["curl","-sS","-m","30","-L","-A","Mozilla/5.0",u],capture_output=True,text=True)
        if r.returncode==0 and len(r.stdout)>5000: return r.stdout
        if a<retries: time.sleep(min(2**a,12))
    return ""
def txt(f): return re.sub(r"\s+"," ",html.unescape(re.sub(r"<[^>]+>","",f))).strip()
PAT=(r'pressReleaseView\.do\?newsId=(\d+)[^>]*>\s*<span class="text">\s*<strong>(.*?)</strong>\s*'
     r'(?:<span class="lead">(.*?)</span>)?')
DB=json.loads(pathlib.Path("/tmp/items.json").read_text(encoding="utf-8"))
known={m.group(1) for i in DB if (m:=re.search(r"newsId=(\d+)",i.get("url","")))}
# 정책브리핑은 같은 보도자료를 인접한 newsId로 중복 게시한다(실측: 156772711/156772713,
# 156713294/156713355). newsId만으로는 못 거르므로 제목을 정규화해 포함관계로 대조한다.
norm=lambda t: re.sub(r"[^0-9A-Za-z가-힣]+","",t)
kt=[(norm(i["title"]),i["id"]) for i in DB]
def dup_of(t):
    n=norm(t)
    if len(n)<10: return None
    return next((cid for kn,cid in kt if len(kn)>=10 and (n in kn or kn in n)), None)
seen={}; ok=fail=0; searched=0; dups=[]
for kw in KEYWORDS:
    for p in (1,2):
        pg=get(S.format(q=urllib.parse.quote(kw),p=p))
        if not pg: fail+=1; continue
        ok+=1
        for nid,title,lead in re.findall(PAT,pg,re.S):
            searched+=1; t=txt(title)
            if nid in seen or nid in known: continue
            if any(x in t for x in EXCLUDE) or kw not in t: continue
            d=dup_of(t)
            if d: dups.append((t,d)); known.add(nid); continue
            seen[nid]={"news_id":nid,"title":t,"lead":txt(lead or "")[:300],
                       "url":V.format(n=nid),"matched_by":kw}
print(json.dumps({"queries_ok":ok,"queries_failed":fail,"searched":searched,
                  "dup_dropped":[{"title":t,"same_as":d} for t,d in dups],
                  "new":len(seen),"candidates":list(seen.values())},ensure_ascii=False,indent=1))
PY
python3 /tmp/collect.py > /tmp/cand.json; python3 -c "
import json;d=json.load(open('/tmp/cand.json'))
print('질의 성공',d['queries_ok'],'실패',d['queries_failed'],'· 훑음',d['searched'],'· 재보도제외',len(d['dup_dropped']),'· 신규',d['new'])
for x in d['dup_dropped']: print(' = 재보도:',x['title'][:60],'->',x['same_as'])
for c in d['candidates']: print(' -',c['matched_by'],'|',c['title'][:70])"
```

고장과 "오늘은 없음"을 구분하는 신호는 두 개입니다:

- `queries_ok`가 0 → **네트워크가 막힌 것**입니다. 알림에 그대로 쓰고 발행 없이 종료합니다.
- `queries_ok`는 정상인데 `searched`가 0 → **정책브리핑 마크업이 바뀌어 정규식 파싱이
  깨진 것**입니다. 이 경우도 고장입니다. 조용히 0건으로 넘기지 말고 알림에 명시합니다.

둘 다 정상인데 `new`가 0인 것은 **정상**입니다. 실측상 흔한 날입니다.

## 3. 선별

후보 중 아래는 **버립니다** — 정책 내용이 없어 분석할 거리가 없습니다:
장·차관 동정, 박람회·엑스포·경진대회 개최, 인재양성 아카데미·부트캠프 홍보, 수상 소식,
기업 제품 출시, 해외 뉴스, 학술대회·컨퍼런스·쇼케이스 개최 안내.

재보도(이미 DB에 있는 건이 다른 newsId로 다시 올라온 것)는 수집 단계에서 제목 정규화로
이미 걸러져 `dup_dropped`에 들어갑니다. 그래도 제목이 많이 달라진 재보도는 빠져나올 수
있으니, 후보의 **발표일과 부처가 DB의 기존 항목과 겹치면** 원문을 열어 대조하세요.

남은 것이 0건이면 정상입니다. **억지로 채우지 마세요.** 다만 종료하지 말고 6단계로
가서 **타임스탬프만 갱신해 재발행**합니다(아래 참조).

## 4. 원문 확인 (제목·날짜)

선별한 건마다 상세 페이지를 받아 **원문 제목과 발표일**을 확인합니다. 목록 제목은
줄어 있을 수 있고, 날짜를 추측해 넣으면 안 됩니다.

```bash
for n in NEWSID1 NEWSID2; do
  curl -sS -m 30 -L -A "Mozilla/5.0" "https://www.korea.kr/briefing/pressReleaseView.do?newsId=$n" \
  | python3 -c "
import sys,re,html
h=sys.stdin.read()
t=re.search(r'<meta property=\"og:title\" content=\"(.*?)\"',h)
d=re.search(r'(20\d{2})[.\-](\d{2})[.\-](\d{2})',h)
print('$n', html.unescape(t.group(1)) if t else '?', '|', '-'.join(d.groups()) if d else '?')
print(re.sub(r'\s+',' ',re.sub(r'<[^>]+>','',h))[:1500])"
done
```

## 5. 분석 — 이 작업의 핵심

각 건마다 `analysis` 4필드를 씁니다. 이게 없으면 그 항목은 무가치합니다.

- `why_now` — 왜 **지금** 기획·발표되었나. 선행 사업 종료, 목표 연도에서의 역산,
  산업 구조 변화, 기술 병목 등 촉발 요인과 타이밍.
- `lineage` — 무엇의 후속인가. 상위 계획·선행 사업과의 계보. (20자 이상)
- `tech` — 무엇을 개발해야 하고 무엇이 어려운가. 기술적 병목.
- `implication` — 정책적 시사점, 참여자 관점의 함의.

항목 형식(열거값을 벗어나면 대시보드 색상·집계가 깨집니다):

```json
{"id":"YYYY-MM-DD-영문슬러그","date":"YYYY-MM-DD","date_estimated":false,
 "collected_at":"오늘YYYY-MM-DD","title":"원문 제목 그대로","type":"…","stage":"…",
 "category":"…","agency":"부처명","exec_agency":null,"doc_no":null,
 "budget_total":null,"budget_note":null,"period":null,"deadline":null,
 "url":"https://www.korea.kr/briefing/pressReleaseView.do?newsId=…","source":"정책브리핑",
 "summary":"2~4문장","analysis":{"why_now":"…","lineage":"…","tech":"…","implication":"…"},
 "keywords":["…"]}
```

- `type` ∈ 전략·계획 / 법·제도 / 규제·표준 / 예타·예산 / 실증·시범사업 / 신규사업공고 / 기술수요조사 / 통계·조사
- `stage` ∈ 구상·계획 / 예타·예산확정 / 제도화 / 공고·모집 / 수행중
- `category` ∈ 자율주행 / SDV·차량반도체 / 전기차·배터리 / UAM·미래항공 / 모빌리티서비스·물류 / 인프라·표준·규제 / 미래차전환·총괄
- `budget_total`은 **억원 단위 숫자**(모르면 null). `title`은 반드시 원문 표기.

작성한 배열을 `/tmp/new_items.json`에 저장합니다.

## 6. 아티팩트 갱신

**신규가 0건인 날에도 재발행합니다.** 항목은 그대로 두고 갱신 시각만 바꿉니다. 그래야
대시보드만 보고도 "오늘 점검했고 새 것이 없었다"와 "수집기가 죽었다"를 구분할 수 있습니다.
(수집이 고장난 날은 2단계에서 이미 종료했으므로 여기까지 오지 않습니다.)

```bash
python3 - <<'PY'
import json,pathlib,datetime as dt
KST=dt.timezone(dt.timedelta(hours=9)); now=dt.datetime.now(KST)
H=pathlib.Path("HTML_PATH_HERE"); h=H.read_text(encoding="utf-8")
items=json.loads(pathlib.Path("/tmp/items.json").read_text(encoding="utf-8"))
nf=pathlib.Path("/tmp/new_items.json")
new=json.loads(nf.read_text(encoding="utf-8")) if nf.exists() else []
ids={i["id"] for i in items}; urls={i["url"] for i in items}
new=[n for n in new if n["id"] not in ids and n["url"] not in urls]
merged=items+new   # 신규 0건이면 merged==items — 갱신 시각만 바뀐 채로 그대로 재발행한다
def splice(s,a,b,v):
    i=s.index(a)+len(a); j=s.index(b); return s[:i]+v+s[j:]
h=splice(h,"/*ITEMS_JSON_START*/","/*ITEMS_JSON_END*/",json.dumps(merged,ensure_ascii=False,separators=(",",":")))
h=splice(h,"<!--TOTAL_COUNT_START-->","<!--TOTAL_COUNT_END-->",str(len(merged)))
h=splice(h,"<!--GENERATED_AT_START-->","<!--GENERATED_AT_END-->",now.strftime("%Y-%m-%d %H:%M KST"))
out=pathlib.Path("/tmp/dashboard.html"); out.write_text(h,encoding="utf-8")
print("기존",len(items),"+ 신규",len(new),"=",len(merged),"→",out)
PY
```

그 다음 `Artifact` 도구로 발행합니다:
`file_path: "/tmp/dashboard.html"`, `url: "https://claude.ai/code/artifact/b32b2210-ac00-44df-9b8d-677817b3ac80"`.
**`favicon`은 넘기지 마세요** (기존 🏛️ 유지). 제목·아이콘도 건드리지 않습니다.

## 7. 알림

`PushNotification`으로 한 줄. 예: `정책 브리프: 3건 추가 (K-UAM 실증 예타 통과 등)`.
0건이면 `정책 브리프: 오늘 신규 없음 (질의 34/34 · 555건 훑음)` — 숫자를 넣어야
"점검했는데 없었다"가 전달됩니다.
수집이 고장났으면 그 사실을 그대로 씁니다. 실패를 성공처럼 쓰지 않습니다.

## 8. 실패했을 때

무리하게 재시도하지 말고 **어느 단계에서 왜 막혔는지** 알림에 적고 종료합니다.
특히 1단계(아티팩트 읽기)가 실패했다면 **절대 발행하지 마세요.**
