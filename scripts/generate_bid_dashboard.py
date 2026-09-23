#!/usr/bin/env python3
"""data/bids.json → artifact/bid_dashboard.html 생성기 — 「연구용역 레이더」.

모빌리티 정책 대시보드와 의도적으로 다르게 만들었다. 저쪽은 읽는 문서라 분석 카드를
펼치는 구조지만, 이쪽은 **훑고 판단하는 작업판**이다. 그래서:

  * 기본 정렬이 마감 임박순이다. 금액도 분야도 그 다음이다.
  * D-day를 **서버에서 굳히지 않고 브라우저에서 계산한다.** 재발행이 하루 늦어도
    화면의 남은 일수는 정확해야 한다.
  * 업종제한 여부가 배지로 항상 보인다. 회사가 그 업종을 등록했는지에 따라 입찰
    가능 여부가 갈리는데, 실측상 39%는 제한이 아예 없다.
  * 카드를 쌓지 않고 좌측 심각도 레일을 가진 띠로 놓는다. 126건을 둥근 카드로 깔면
    위계가 뭉개진다.

마커(ITEMS_JSON / TOTAL_COUNT / GENERATED_AT)는 정책 대시보드와 같은 규약이다.
자동화 세션이 저장소 없이 마커만 치환해 재발행할 수 있게 하기 위한 것이다.
"""
from __future__ import annotations

import json
import pathlib
import re
from datetime import datetime, timedelta, timezone

ROOT = pathlib.Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "bids.json"
OUT = ROOT / "artifact" / "bid_dashboard.html"
KST = timezone(timedelta(hours=9))

GROUPS = ["연구조사", "교육·전문직종", "ICT", "기타"]
GROUP_COLOR = {
    "연구조사": "#3c6e8f",
    "교육·전문직종": "#7a5ea8",
    "ICT": "#2f7d6b",
    "기타": "#8a7a5e",
}


def to_iso(s: str | None) -> str | None:
    s = (s or "").strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=KST).isoformat()
        except ValueError:
            continue
    return None


def group_of(large: str | None) -> str:
    large = large or ""
    if "연구조사" in large:
        return "연구조사"
    if "교육" in large or "전문직종" in large:
        return "교육·전문직종"
    if "ICT" in large or "정보통신" in large:
        return "ICT"
    return "기타"


def short_method(s: str | None) -> str:
    s = (s or "").strip()
    if not s:
        return ""
    head = s.split("-")[0]
    return {"협상에의한계약": "협상에 의한 계약", "수의시담": "수의시담",
            "규격가격동시입찰": "규격·가격 동시"}.get(head, head)


def clean_title(s: str | None) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()


def shape(row: dict) -> dict:
    close = to_iso(row.get("bidClseDt"))
    opening = to_iso(row.get("opengDt"))
    return {
        "no": row.get("bidNtceNo"),
        "ord": row.get("bidNtceOrd") or "",
        "t": clean_title(row.get("bidNtceNm")),
        "inst": (row.get("ntceInsttNm") or "").strip(),
        "dmd": (row.get("dminsttNm") or "").strip(),
        "price": int(row.get("presmptPrce") or 0),
        "budget": int(row.get("asignBdgtAmt") or 0),
        # 입찰마감이 비어 있는 공고(우편/상시 등)는 개찰일시를 대신 쓴다.
        "due": close or opening,
        "dueIsOpening": close is None and opening is not None,
        "posted": to_iso(row.get("bidNtceDt")),
        "url": row.get("bidNtceDtlUrl") or "",
        "lim": row.get("indstrytyLmtYn") == "Y",
        "method": short_method(row.get("sucsfbidMthdNm")),
        "contract": (row.get("cntrctCnclsMthdNm") or "").strip(),
        "div": (row.get("srvceDivNm") or "").strip(),
        "g": group_of(row.get("pubPrcrmntLrgClsfcNm")),
        "cls": (row.get("pubPrcrmntClsfcNm") or "").strip(),
        "re": row.get("reNtceYn") == "Y",
        "kind": (row.get("ntceKindNm") or "").strip(),
        "officer": (row.get("ntceInsttOfclNm") or "").strip(),
        "tel": (row.get("ntceInsttOfclTelNo") or "").strip(),
    }


TEMPLATE = """<title>연구용역 레이더</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Gothic+A1:wght@300;400;500;700&family=Hahmlet:wght@500;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap">
<style>
  :root{
    color-scheme: light;
    --paper:#e9ecef;
    --surface:#fdfdfe;
    --surface-2:#f1f4f7;
    --ink:#161a1f;
    --ink-2:#3b454f;
    --muted:#6d7985;
    --line:#d7dde3;
    --line-2:#bcc6cf;
    --accent:#33556b;
    --accent-soft:#33556b14;
    --crit:#a8362c;
    --crit-soft:#a8362c16;
    --warn:#9c6414;
    --warn-soft:#9c641416;
    --ok:#3a6b4c;
    --ok-soft:#3a6b4c16;
    --shadow:0 1px 2px rgba(22,26,31,.05), 0 10px 26px -18px rgba(22,26,31,.35);
    --r:9px;
  }
  @media (prefers-color-scheme: dark){
    :root:not([data-theme="light"]){
      color-scheme: dark;
      --paper:#0f1317;
      --surface:#171d23;
      --surface-2:#1e262d;
      --ink:#e8edf2;
      --ink-2:#bcc7d1;
      --muted:#87949f;
      --line:#28323b;
      --line-2:#3a4650;
      --accent:#7bb0cf;
      --accent-soft:#7bb0cf1c;
      --crit:#e8776b;
      --crit-soft:#e8776b1e;
      --warn:#dfa64f;
      --warn-soft:#dfa64f1e;
      --ok:#6fb587;
      --ok-soft:#6fb5871e;
      --shadow:0 1px 2px rgba(0,0,0,.45), 0 10px 26px -18px rgba(0,0,0,.8);
    }
  }
  :root[data-theme="dark"]{
    color-scheme: dark;
    --paper:#0f1317;
    --surface:#171d23;
    --surface-2:#1e262d;
    --ink:#e8edf2;
    --ink-2:#bcc7d1;
    --muted:#87949f;
    --line:#28323b;
    --line-2:#3a4650;
    --accent:#7bb0cf;
    --accent-soft:#7bb0cf1c;
    --crit:#e8776b;
    --crit-soft:#e8776b1e;
    --warn:#dfa64f;
    --warn-soft:#dfa64f1e;
    --ok:#6fb587;
    --ok-soft:#6fb5871e;
    --shadow:0 1px 2px rgba(0,0,0,.45), 0 10px 26px -18px rgba(0,0,0,.8);
  }

  *{box-sizing:border-box}
  body{
    margin:0; background:var(--paper); color:var(--ink);
    font-family:"Gothic A1",-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
    font-weight:400; line-height:1.6; -webkit-font-smoothing:antialiased;
  }
  .wrap{max-width:1060px; margin:0 auto; padding-block:34px 72px; padding-left:20px; padding-right:20px;}
  h1,h2{font-family:"Hahmlet",Georgia,serif; font-weight:700; margin:0; text-wrap:balance; letter-spacing:-.015em;}
  .n{font-family:"IBM Plex Mono",ui-monospace,monospace; font-variant-numeric:tabular-nums;}

  /* masthead */
  .top{display:flex; flex-wrap:wrap; gap:18px; align-items:flex-end; justify-content:space-between;
       border-bottom:2px solid var(--ink); padding-bottom:16px;}
  .eyebrow{font-size:10.5px; letter-spacing:.16em; text-transform:uppercase; color:var(--accent); font-weight:700;}
  h1{font-size:29px; line-height:1.22; margin-top:5px;}
  .sub{color:var(--muted); font-size:13px; margin-top:6px; max-width:60ch;}
  .top-meta{text-align:right; font-size:12px; color:var(--muted); line-height:1.8;}

  /* urgent strip */
  .urgent{margin-top:16px; border:1px solid var(--crit); border-left-width:3px; border-radius:0 var(--r) var(--r) 0;
          background:var(--crit-soft); padding:12px 15px;}
  .urgent h2{font-size:12px; letter-spacing:.06em; color:var(--crit); font-family:"Gothic A1",sans-serif; font-weight:700;}
  .urgent ul{list-style:none; margin:8px 0 0; padding:0; display:flex; flex-direction:column; gap:6px;}
  .urgent li{display:flex; gap:10px; align-items:baseline; font-size:12.5px; flex-wrap:wrap;}
  .urgent a{color:var(--ink); text-decoration:none; border-bottom:1px solid var(--line-2);}
  .urgent a:hover{border-bottom-color:var(--crit);}

  /* stats */
  .stats{display:grid; grid-template-columns:repeat(4,1fr); gap:1px; background:var(--line);
         border:1px solid var(--line); border-radius:var(--r); overflow:hidden; margin:22px 0 24px;}
  .stat{background:var(--surface); padding:14px 16px 13px;}
  .stat .k{font-size:10.5px; letter-spacing:.05em; color:var(--muted); font-weight:500;}
  .stat .v{font-size:25px; font-weight:500; margin-top:4px; line-height:1.15;}
  .stat .v .u{font-size:12px; color:var(--muted); margin-left:3px; font-family:"Gothic A1",sans-serif;}
  .stat .d{font-size:11px; color:var(--muted); margin-top:2px;}
  .stat.hot .v{color:var(--crit);}

  /* controls */
  .ctl{display:flex; flex-wrap:wrap; gap:9px; align-items:center;}
  .search{flex:1 1 230px; min-width:190px; padding:9px 12px; font:inherit; font-size:13px;
          background:var(--surface); color:var(--ink); border:1px solid var(--line); border-radius:7px;}
  .search::placeholder{color:var(--muted);}
  .search:focus-visible{outline:2px solid var(--accent); outline-offset:1px;}
  .seg{display:inline-flex; background:var(--surface-2); border:1px solid var(--line); border-radius:7px; padding:2px; gap:2px;}
  .seg button{font:inherit; font-size:12px; padding:5px 10px; border:0; border-radius:5px;
              background:transparent; color:var(--muted); cursor:pointer;}
  .seg button:hover{color:var(--ink);}
  .seg button[aria-pressed="true"]{background:var(--surface); color:var(--ink); font-weight:600; box-shadow:0 1px 2px rgba(22,26,31,.09);}
  .chips{display:flex; flex-wrap:wrap; gap:6px; margin-top:10px;}
  .chip{font:inherit; font-size:11.5px; padding:4px 10px; border-radius:20px; cursor:pointer;
        border:1px solid var(--line); background:var(--surface); color:var(--muted);
        display:inline-flex; align-items:center; gap:6px;}
  .chip:hover{border-color:var(--line-2); color:var(--ink-2);}
  .chip[aria-pressed="true"]{color:var(--ink); border-color:currentColor; font-weight:600;}
  .chip .c{font-family:"IBM Plex Mono",monospace; opacity:.6;}
  .count{font-size:11.5px; color:var(--muted); margin:16px 0 9px; font-family:"IBM Plex Mono",monospace;}

  /* list */
  .rows{list-style:none; margin:0; padding:0; border:1px solid var(--line);
        border-radius:var(--r); overflow:hidden; background:var(--surface);}
  .row{border-top:1px solid var(--line);}
  .row:first-child{border-top:0;}
  .row.open{background:var(--surface-2);}
  .rhead{width:100%; text-align:left; font:inherit; color:inherit; background:transparent; border:0;
         cursor:pointer; padding:13px 16px 13px 0; display:grid;
         grid-template-columns:3px 62px 1fr auto; gap:3px 13px; align-items:start;}
  .rhead:focus-visible{outline:2px solid var(--accent); outline-offset:-2px;}
  .rail{align-self:stretch; min-height:40px; background:var(--line-2);}
  .row.c0 .rail{background:var(--crit);} .row.c1 .rail{background:var(--warn);}
  .row.c2 .rail{background:var(--accent);} .row.c3 .rail{background:var(--line-2);}
  .dd{font-family:"IBM Plex Mono",monospace; font-size:15px; font-weight:600; text-align:right; padding-top:1px;}
  .row.c0 .dd{color:var(--crit);} .row.c1 .dd{color:var(--warn);}
  .row.c2 .dd{color:var(--ink-2);} .row.c3 .dd{color:var(--muted);}
  .dd small{display:block; font-size:9.5px; font-weight:400; letter-spacing:.02em; color:var(--muted); margin-top:1px;}
  .main{min-width:0;}
  .tt{font-size:14px; font-weight:500; line-height:1.48; color:var(--ink);}
  .meta{display:flex; flex-wrap:wrap; gap:3px 11px; font-size:11.5px; color:var(--muted); margin-top:5px; align-items:center;}
  .badge{font-size:10px; font-weight:600; padding:1.5px 6px; border-radius:3px; white-space:nowrap;}
  .b-open{background:var(--ok-soft); color:var(--ok);}
  .b-lim{background:var(--surface-2); color:var(--ink-2); border:1px solid var(--line-2);}
  .b-g{background:var(--gb); color:var(--gf); font-weight:500;}
  .amt{font-family:"IBM Plex Mono",monospace; font-size:13px; color:var(--ink-2); text-align:right;
       padding-top:1px; white-space:nowrap;}
  .amt small{display:block; font-size:10px; color:var(--muted); font-family:"Gothic A1",sans-serif;}

  .detail{display:none; padding:2px 16px 16px 78px; border-top:1px dashed var(--line);}
  .row.open .detail{display:block;}
  .dl{display:grid; grid-template-columns:auto 1fr; gap:6px 16px; font-size:12.5px; margin-top:12px;}
  .dl dt{color:var(--muted); white-space:nowrap;}
  .dl dd{margin:0; color:var(--ink-2);}
  .go{display:inline-block; margin-top:14px; font-size:12.5px; font-weight:600; color:var(--accent);
      text-decoration:none; border-bottom:1.5px solid var(--accent); padding-bottom:1px;}
  .go:focus-visible{outline:2px solid var(--accent); outline-offset:3px;}

  .empty{padding:34px; text-align:center; color:var(--muted); font-size:13px;}
  .foot{margin-top:28px; padding-top:15px; border-top:1px solid var(--line);
        font-size:11.5px; color:var(--muted); line-height:1.8;}
  .foot code{font-family:"IBM Plex Mono",monospace; font-size:11px; background:var(--surface-2); padding:1px 5px; border-radius:3px;}

  @media (max-width:820px){
    .stats{grid-template-columns:repeat(2,1fr);}
    .rhead{grid-template-columns:3px 54px 1fr; padding-right:14px;}
    .amt{grid-column:3; text-align:left; padding-top:6px;}
    .amt small{display:inline; margin-left:6px;}
    .detail{padding-left:16px;}
    .top-meta{text-align:left;}
  }
  @media (max-width:440px){
    .wrap{padding-block:24px 56px; padding-left:16px; padding-right:16px;}
    h1{font-size:23px;}
    .dl{grid-template-columns:1fr; gap:2px 0;}
    .dl dt{margin-top:8px;}
  }
  @media (prefers-reduced-motion: reduce){*{transition:none!important; animation:none!important;}}
</style>

<div class="wrap">
  <header class="top">
    <div>
      <div class="eyebrow">Public R&amp;D Service Tenders · 나라장터</div>
      <h1>연구용역 레이더</h1>
      <p class="sub">정책연구·산업분석·기술경영 성격의 공공 용역 입찰공고를 마감 임박순으로 모읍니다.
        추정가격은 부가세 별도이며, 입찰 전 반드시 나라장터 원문으로 교차 확인하세요.</p>
    </div>
    <div class="top-meta">
      <div>마지막 갱신 · <span class="n"><!--GENERATED_AT_START-->__GENERATED_AT__<!--GENERATED_AT_END--></span></div>
      <div>누적 <span class="n"><!--TOTAL_COUNT_START-->__TOTAL_COUNT__<!--TOTAL_COUNT_END--></span>건 수집</div>
    </div>
  </header>

  <div id="urgent-slot"></div>
  <div class="stats" id="stats"></div>

  <div class="ctl">
    <input class="search" id="q" type="text" placeholder="공고명·발주기관 검색…" aria-label="검색">
    <div class="seg" id="sort" role="group" aria-label="정렬">
      <button type="button" data-s="due" aria-pressed="true">마감순</button>
      <button type="button" data-s="price" aria-pressed="false">금액순</button>
      <button type="button" data-s="posted" aria-pressed="false">공고순</button>
    </div>
  </div>
  <div class="chips" id="chips"></div>
  <div class="count" id="count"></div>
  <ul class="rows" id="list"></ul>
  <div class="empty" id="empty" hidden>조건에 맞는 공고가 없습니다.</div>

  <footer class="foot">
    데이터 <code>data/bids.json</code> · 출처 나라장터 입찰공고정보(조달청) OpenAPI ·
    <b>업종제한</b>은 <code>indstrytyLmtYn</code> 필드 그대로이며, 제한이 있는 건은 해당 업종 등록업체만 입찰할 수 있습니다.
    남은 일수는 이 페이지를 여는 시점 기준으로 계산됩니다.
  </footer>
</div>

<script>
const ITEMS = /*ITEMS_JSON_START*/__ITEMS_JSON__/*ITEMS_JSON_END*/;
const GROUPS = __GROUPS__, GCOLOR = __GCOLOR__;

// 마감은 한국 시각 기준이다. 보는 사람이 어디에 있든 공고의 시각으로 읽혀야 하므로
// 표시·날짜계산 모두 Asia/Seoul에 고정한다.
const TZ = "Asia/Seoul";
const seoulParts = (d) => {
  const p = new Intl.DateTimeFormat("en-CA", {timeZone:TZ, year:"numeric", month:"2-digit",
    day:"2-digit", hour:"2-digit", minute:"2-digit", hour12:false}).formatToParts(d);
  const g = t => p.find(x => x.type === t).value;
  return {y:+g("year"), m:+g("month"), d:+g("day"), hh:g("hour"), mm:g("minute")};
};
const isPast = (iso) => iso ? new Date(iso).getTime() < Date.now() : false;
// D-day는 시분 차가 아니라 **달력 날짜 차**다. ceil((마감-지금)/하루)를 쓰면 23시간 전에
// 끝난 공고가 D-0으로, 1시간 뒤 마감인 공고가 D-1로 나온다(실측 버그).
const dday = (iso) => {
  if (!iso) return null;
  const a = seoulParts(new Date(iso)), b = seoulParts(new Date());
  return Math.round((Date.UTC(a.y,a.m-1,a.d) - Date.UTC(b.y,b.m-1,b.d)) / 86400000);
};
// 금액은 한 줄로 훑는 열이라 단위를 섞지 않는다. 전부 억원.
const won = (v) => v ? {t:(v/1e8).toFixed(v >= 1e10 ? 0 : 2), s:"억원"} : {t:"—", s:""};
const fmt = (iso) => { if(!iso) return "—"; const p = seoulParts(new Date(iso));
  return `${p.m}/${String(p.d).padStart(2,"0")} ${p.hh}:${p.mm}`; };
const fmtFull = (iso) => { if(!iso) return "—"; const p = seoulParts(new Date(iso));
  return `${p.y}. ${p.m}. ${p.d}. ${p.hh}:${p.mm} KST`; };
const esc = (s) => String(s??"").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));

const state = {q:"", sort:"due", openOnly:true, noLimit:false, groups:new Set(), open:new Set()};

function severity(d, past){ if(past || d===null) return 3; if(d<=1) return 0; if(d<=7) return 1; return 2; }

function passes(it){
  if (state.openOnly && (!it.due || isPast(it.due))) return false;
  if (state.noLimit && it.lim) return false;
  if (state.groups.size && !state.groups.has(it.g)) return false;
  if (state.q){
    const hay = (it.t+" "+it.inst+" "+it.dmd+" "+it.cls+" "+it.method).toLowerCase();
    if (!hay.includes(state.q.toLowerCase())) return false;
  }
  return true;
}

function sortRows(rows){
  const s = state.sort;
  return rows.slice().sort((a,b)=>{
    if (s==="price") return (b.price||0)-(a.price||0);
    if (s==="posted") return String(b.posted||"").localeCompare(String(a.posted||""));
    const da = a.due ? new Date(a.due).getTime() : Infinity;
    const db = b.due ? new Date(b.due).getTime() : Infinity;
    return da-db || (b.price||0)-(a.price||0);
  });
}

function renderStats(){
  const open = ITEMS.filter(i => i.due && !isPast(i.due));
  const wk = open.filter(i => dday(i.due) <= 7);
  const free = open.filter(i => !i.lim);
  const sum = open.reduce((a,i)=>a+(i.price||0),0);
  const s = won(sum);
  document.getElementById("stats").innerHTML = [
    ["접수 중인 공고", open.length, "건", `전체 수집 ${ITEMS.length}건 중`, false],
    ["7일 내 마감", wk.length, "건", "제안서 준비가 급한 구간", wk.length>0],
    ["업종제한 없음", free.length, "건", `접수 중의 ${open.length?Math.round(free.length/open.length*100):0}%`, false],
    ["접수 중 추정가 합", s.t, s.s, "부가세 별도", false],
  ].map(([k,v,u,d,hot]) =>
    `<div class="stat${hot?" hot":""}"><div class="k">${k}</div>
     <div class="v n">${v}<span class="u">${u}</span></div><div class="d">${d}</div></div>`).join("");
}

function renderUrgent(){
  const soon = sortRows(ITEMS.filter(i => i.due && !isPast(i.due) && dday(i.due) <= 3)).slice(0,4);
  const el = document.getElementById("urgent-slot");
  if (!soon.length){ el.innerHTML=""; return; }
  el.innerHTML = `<div class="urgent"><h2>마감 임박 — 3일 이내</h2><ul>${soon.map(i=>{
    const d = dday(i.due);
    return `<li><b class="n">${d===0?"오늘":"D-"+d}</b><span class="n">${fmt(i.due)}</span>
      <a href="${esc(i.url)}" target="_blank" rel="noopener">${esc(i.t)}</a>
      <span style="color:var(--muted)">${esc(i.inst)}</span></li>`;
  }).join("")}</ul></div>`;
}

function renderChips(){
  const counts = {};
  GROUPS.forEach(g => counts[g] = ITEMS.filter(i => i.g===g && passesExceptGroup(i)).length);
  const el = document.getElementById("chips");
  el.innerHTML =
    `<button type="button" class="chip" id="ch-open" aria-pressed="${state.openOnly}">접수 중만</button>` +
    `<button type="button" class="chip" id="ch-lim" aria-pressed="${state.noLimit}">업종제한 없음만</button>` +
    GROUPS.map(g => `<button type="button" class="chip" data-g="${esc(g)}" aria-pressed="${state.groups.has(g)}"
       style="${state.groups.has(g)?`color:${GCOLOR[g]}`:""}">${esc(g)} <span class="c">${counts[g]}</span></button>`).join("");
  document.getElementById("ch-open").onclick = () => { state.openOnly=!state.openOnly; render(); };
  document.getElementById("ch-lim").onclick  = () => { state.noLimit=!state.noLimit; render(); };
  el.querySelectorAll("[data-g]").forEach(b => b.onclick = () => {
    const g=b.dataset.g; state.groups.has(g) ? state.groups.delete(g) : state.groups.add(g); render();
  });
}
function passesExceptGroup(it){
  const saved = state.groups; state.groups = new Set();
  const r = passes(it); state.groups = saved; return r;
}

function renderList(){
  const rows = sortRows(ITEMS.filter(passes));
  document.getElementById("count").textContent =
    `${rows.length}건 표시 · 전체 ${ITEMS.length}건`;
  const list = document.getElementById("list");
  document.getElementById("empty").hidden = rows.length > 0;
  list.hidden = rows.length === 0;
  list.innerHTML = rows.map(i => {
    const past = isPast(i.due), d = dday(i.due), sev = severity(d, past);
    const a = won(i.price);
    const ddText = d === null ? "—" : (past ? "마감" : (d === 0 ? "오늘" : `D-${d}`));
    const openId = i.no + i.ord;
    return `<li class="row c${sev}${state.open.has(openId)?" open":""}" data-id="${esc(openId)}">
      <button type="button" class="rhead" aria-expanded="${state.open.has(openId)}">
        <span class="rail"></span>
        <span class="dd">${ddText}<small>${i.due?fmt(i.due):""}</small></span>
        <span class="main">
          <span class="tt">${esc(i.t)}</span>
          <span class="meta">
            <span class="badge b-g" style="--gb:${GCOLOR[i.g]}1c;--gf:${GCOLOR[i.g]}">${esc(i.g)}</span>
            ${i.lim ? '<span class="badge b-lim">업종제한</span>' : '<span class="badge b-open">업종제한 없음</span>'}
            ${i.re ? '<span class="badge b-lim">재공고</span>' : ""}
            <span>${esc(i.inst)}</span>
            ${i.method ? `<span>${esc(i.method)}</span>` : ""}
          </span>
        </span>
        <span class="amt">${a.t}<small>${a.s}</small></span>
      </button>
      <div class="detail">
        <dl class="dl">
          <dt>수요기관</dt><dd>${esc(i.dmd||"—")}</dd>
          <dt>${i.dueIsOpening?"개찰일시":"입찰마감"}</dt><dd class="n">${fmtFull(i.due)}${i.dueIsOpening?" <span style=\\"color:var(--muted)\\">(입찰마감일시가 공고에 없어 개찰일시로 표시)</span>":""}</dd>
          <dt>계약·낙찰</dt><dd>${esc(i.contract||"—")}${i.method?` · ${esc(i.method)}`:""}</dd>
          <dt>추정가격</dt><dd class="n">${i.price?i.price.toLocaleString("ko-KR")+"원":"—"}${i.budget?` <span style="color:var(--muted)">(배정예산 ${i.budget.toLocaleString("ko-KR")}원)</span>`:""}</dd>
          <dt>조달분류</dt><dd>${esc(i.cls||"—")}</dd>
          <dt>공고구분</dt><dd>${esc(i.div||"—")}${i.kind?` · ${esc(i.kind)}`:""}${i.ord&&i.ord!=="000"?` · ${esc(i.ord)}차`:""}</dd>
          <dt>담당</dt><dd>${esc(i.officer||"—")}${i.tel?` · <span class="n">${esc(i.tel)}</span>`:""}</dd>
        </dl>
        <a class="go" href="${esc(i.url)}" target="_blank" rel="noopener">나라장터 공고 원문 열기 →</a>
      </div>
    </li>`;
  }).join("");
  list.querySelectorAll(".row").forEach(row => {
    row.querySelector(".rhead").onclick = () => {
      const id = row.dataset.id;
      state.open.has(id) ? state.open.delete(id) : state.open.add(id);
      row.classList.toggle("open");
      row.querySelector(".rhead").setAttribute("aria-expanded", state.open.has(id));
    };
  });
}

function render(){ renderStats(); renderUrgent(); renderChips(); renderList(); }

document.getElementById("q").addEventListener("input", e => { state.q = e.target.value.trim(); render(); });
document.getElementById("sort").querySelectorAll("button").forEach(b => b.onclick = () => {
  state.sort = b.dataset.s;
  document.getElementById("sort").querySelectorAll("button")
    .forEach(x => x.setAttribute("aria-pressed", String(x === b)));
  render();
});
render();
</script>
"""


def build(db: dict, now: datetime) -> str:
    items = [shape(r) for r in db["items"]]
    j = lambda o: json.dumps(o, ensure_ascii=False, separators=(",", ":"))
    return (TEMPLATE
            .replace("__GENERATED_AT__", now.strftime("%Y-%m-%d %H:%M KST"))
            .replace("__TOTAL_COUNT__", str(len(items)))
            .replace("__ITEMS_JSON__", j(items))
            .replace("__GROUPS__", j(GROUPS))
            .replace("__GCOLOR__", j(GROUP_COLOR)))


def main() -> None:
    db = json.loads(DB.read_text(encoding="utf-8"))
    html = build(db, datetime.now(KST))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html, encoding="utf-8")
    print(f"wrote {OUT} ({len(html):,} bytes, {len(db['items'])} items)")


if __name__ == "__main__":
    main()
