#!/usr/bin/env python3
"""data/policy_items.json -> artifact/dashboard.html

모빌리티 기술정책·신규사업 모니터 대시보드 생성기.

자동화 세션은 이 스크립트를 실행하지 않고 HTML 안의 마커 3곳만 문자열 치환한다
(docs/POLICY_BRIEFING_PLAYBOOK.md 참고). 이 스크립트는 사람이 로컬에서 구조까지
다시 만들 때 사용한다.
"""
import json
import pathlib
from datetime import datetime, timedelta, timezone

ROOT = pathlib.Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "policy_items.json"
OUT = ROOT / "artifact" / "dashboard.html"
KST = timezone(timedelta(hours=9))

CATEGORIES = [
    "자율주행",
    "SDV·차량반도체",
    "전기차·배터리",
    "UAM·미래항공",
    "모빌리티서비스·물류",
    "인프라·표준·규제",
    "미래차전환·총괄",
]
STAGES = ["구상·계획", "예타·예산확정", "공고", "수행중"]
TYPES = ["정책·계획", "예타·예산", "기술수요조사", "신규사업공고", "법·제도"]

TEMPLATE = r"""<title>모빌리티 정책·사업 브리프</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans+KR:wght@300;400;500;600&family=Noto+Serif+KR:wght@500;700&display=swap">
<style>
  :root{
    --paper:#eef1f4;
    --surface:#fbfcfd;
    --surface-2:#f2f5f8;
    --ink:#16202b;
    --ink-2:#3d4c5a;
    --muted:#6b7d8d;
    --line:#d9e0e7;
    --line-strong:#c2ccd6;
    --accent:#1f6f7a;
    --accent-soft:#1f6f7a1a;
    --signal:#b5622f;
    --signal-soft:#b5622f1a;
    --good:#3f7d54;
    --shadow:0 1px 2px rgba(22,32,43,.06), 0 8px 24px -16px rgba(22,32,43,.28);
    --radius:10px;
  }
  @media (prefers-color-scheme: dark){
    :root:not([data-theme="light"]){
      --paper:#0e151b;
      --surface:#151e26;
      --surface-2:#1b262f;
      --ink:#e6edf3;
      --ink-2:#b9c6d1;
      --muted:#8698a6;
      --line:#26333d;
      --line-strong:#35454f;
      --accent:#57b3bd;
      --accent-soft:#57b3bd1f;
      --signal:#dd9358;
      --signal-soft:#dd93581f;
      --good:#6cba86;
      --shadow:0 1px 2px rgba(0,0,0,.4), 0 8px 24px -16px rgba(0,0,0,.7);
    }
  }
  :root[data-theme="dark"]{
    --paper:#0e151b;
    --surface:#151e26;
    --surface-2:#1b262f;
    --ink:#e6edf3;
    --ink-2:#b9c6d1;
    --muted:#8698a6;
    --line:#26333d;
    --line-strong:#35454f;
    --accent:#57b3bd;
    --accent-soft:#57b3bd1f;
    --signal:#dd9358;
    --signal-soft:#dd93581f;
    --good:#6cba86;
    --shadow:0 1px 2px rgba(0,0,0,.4), 0 8px 24px -16px rgba(0,0,0,.7);
  }

  *{box-sizing:border-box}
  body{
    margin:0; background:var(--paper); color:var(--ink);
    font-family:"IBM Plex Sans KR",-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
    font-weight:400; line-height:1.62; -webkit-font-smoothing:antialiased;
  }
  .wrap{max-width:1120px; margin:0 auto; padding:36px 24px 72px;}
  h1,h2,h3{font-family:"Noto Serif KR",Georgia,serif; font-weight:700; margin:0; text-wrap:balance; letter-spacing:-.01em;}
  .num{font-family:"IBM Plex Mono",ui-monospace,monospace; font-variant-numeric:tabular-nums;}

  /* ---- masthead ---- */
  .masthead{
    display:flex; flex-wrap:wrap; gap:20px; align-items:flex-end; justify-content:space-between;
    padding-bottom:20px; border-bottom:2px solid var(--ink); margin-bottom:8px;
  }
  .eyebrow{
    font-size:11px; letter-spacing:.14em; text-transform:uppercase; color:var(--accent);
    font-weight:600; margin-bottom:6px;
  }
  h1{font-size:31px; line-height:1.25;}
  .tagline{color:var(--muted); font-size:13.5px; margin-top:7px; max-width:56ch;}
  .masthead-meta{text-align:right; font-size:12.5px; color:var(--muted); line-height:1.85;}
  .masthead-meta .big{color:var(--ink); font-size:15px;}

  /* ---- deadline strip ---- */
  .alert{
    display:flex; gap:12px; align-items:baseline; flex-wrap:wrap;
    margin:18px 0 0; padding:11px 15px;
    background:var(--signal-soft); border-left:3px solid var(--signal); border-radius:0 6px 6px 0;
    font-size:13px; color:var(--ink-2);
  }
  .alert b{color:var(--signal); font-weight:600;}
  .alert .a-item{color:var(--ink);}

  /* ---- stat tiles ---- */
  .stats{display:grid; grid-template-columns:repeat(4,1fr); gap:1px; background:var(--line);
    border:1px solid var(--line); border-radius:var(--radius); overflow:hidden; margin:26px 0 30px;}
  .stat{background:var(--surface); padding:16px 18px 15px;}
  .stat .label{font-size:11px; letter-spacing:.06em; color:var(--muted); font-weight:500;}
  .stat .value{font-size:27px; font-weight:500; margin-top:5px; line-height:1.15; color:var(--ink);}
  .stat .value .unit{font-size:13px; color:var(--muted); margin-left:3px; font-family:"IBM Plex Sans KR",sans-serif;}
  .stat .sub{font-size:11.5px; color:var(--muted); margin-top:3px;}
  .stat.hi .value{color:var(--signal);}

  /* ---- pipeline ---- */
  .pipeline{margin-bottom:30px;}
  .sec-head{display:flex; align-items:baseline; justify-content:space-between; gap:16px; margin-bottom:12px; flex-wrap:wrap;}
  .sec-head h2{font-size:16px;}
  .sec-head .desc{font-size:12px; color:var(--muted);}
  .stages{display:grid; grid-template-columns:repeat(4,1fr); gap:9px;}
  .stage{
    background:var(--surface); border:1px solid var(--line); border-radius:var(--radius);
    padding:14px 16px; position:relative; cursor:pointer; text-align:left; width:100%;
    font-family:inherit; color:inherit; transition:border-color .15s, background .15s;
  }
  .stage:hover{border-color:var(--line-strong);}
  .stage[aria-pressed="true"]{border-color:var(--accent); background:var(--accent-soft);}
  .stage .st-i{font-size:10.5px; color:var(--muted); font-family:"IBM Plex Mono",monospace; letter-spacing:.08em;}
  .stage .st-n{font-size:13.5px; font-weight:600; margin-top:3px; color:var(--ink);}
  .stage .st-c{font-size:22px; font-weight:500; margin-top:5px; color:var(--accent);}
  .stage .st-d{font-size:11px; color:var(--muted); margin-top:2px; line-height:1.5;}
  .stage-track{height:3px; background:var(--line); border-radius:2px; margin-top:10px; overflow:hidden;}
  .stage-track i{display:block; height:100%; background:var(--accent); border-radius:2px;}

  /* ---- panels ---- */
  .grid-2{display:grid; grid-template-columns:1.5fr 1fr; gap:18px; margin-bottom:30px;}
  .panel{background:var(--surface); border:1px solid var(--line); border-radius:var(--radius); padding:18px 20px 16px;}
  .chart-wrap{overflow-x:auto;}
  svg.chart{width:100%; min-width:420px; height:212px; display:block; margin-top:6px;}
  svg.chart text{font-family:"IBM Plex Mono",monospace; font-size:9.5px; fill:var(--muted);}
  svg.chart .gridline{stroke:var(--line); stroke-width:1;}
  .legend{display:flex; flex-wrap:wrap; gap:5px 14px; margin-top:10px; font-size:11px; color:var(--ink-2);}
  .legend .it{display:inline-flex; align-items:center; gap:5px;}
  .sw{width:9px; height:9px; border-radius:2px; display:inline-block; flex:none;}
  .cat-rows{display:flex; flex-direction:column; gap:9px; margin-top:4px;}
  .cat-row{display:grid; grid-template-columns:1fr auto; gap:3px 10px; font-size:12px;}
  .cat-row .cn{color:var(--ink-2);}
  .cat-row .cv{color:var(--muted); font-size:11.5px;}
  .cat-bar{grid-column:1/-1; height:5px; background:var(--surface-2); border-radius:3px; overflow:hidden;}
  .cat-bar i{display:block; height:100%; border-radius:3px;}

  /* ---- controls ---- */
  .controls{display:flex; flex-wrap:wrap; gap:10px; align-items:center; margin:14px 0 4px;}
  .search{
    flex:1 1 240px; min-width:200px; padding:9px 12px; font:inherit; font-size:13px;
    background:var(--surface); color:var(--ink);
    border:1px solid var(--line); border-radius:7px;
  }
  .search::placeholder{color:var(--muted);}
  .search:focus{outline:2px solid var(--accent); outline-offset:1px; border-color:transparent;}
  .seg{display:inline-flex; background:var(--surface-2); border:1px solid var(--line); border-radius:7px; padding:2px; gap:2px;}
  .seg button{
    font:inherit; font-size:12px; padding:5px 11px; border:0; border-radius:5px;
    background:transparent; color:var(--muted); cursor:pointer;
  }
  .seg button:hover{color:var(--ink);}
  .seg button.on{background:var(--surface); color:var(--ink); font-weight:500; box-shadow:0 1px 2px rgba(22,32,43,.08);}
  .chips{display:flex; flex-wrap:wrap; gap:6px; margin:10px 0 2px;}
  .chip{
    font:inherit; font-size:11.5px; padding:4px 10px; border-radius:20px; cursor:pointer;
    border:1px solid var(--line); background:var(--surface); color:var(--muted);
    display:inline-flex; align-items:center; gap:6px;
  }
  .chip:hover{border-color:var(--line-strong); color:var(--ink-2);}
  .chip.on{color:var(--ink); border-color:currentColor; font-weight:500;}
  .chip .cc{font-family:"IBM Plex Mono",monospace; opacity:.65;}
  .count-line{font-size:11.5px; color:var(--muted); margin:14px 0 8px; font-family:"IBM Plex Mono",monospace;}

  /* ---- item list ---- */
  .items{list-style:none; margin:0; padding:0; display:flex; flex-direction:column; gap:9px;}
  .item{background:var(--surface); border:1px solid var(--line); border-radius:var(--radius); overflow:hidden;}
  .item.open{border-color:var(--line-strong); box-shadow:var(--shadow);}
  .item-head{
    width:100%; text-align:left; font:inherit; color:inherit; background:transparent;
    border:0; cursor:pointer; padding:15px 18px; display:grid;
    grid-template-columns:auto 1fr auto; gap:4px 14px; align-items:start;
  }
  .item-head:focus-visible{outline:2px solid var(--accent); outline-offset:-2px;}
  .rail{width:3px; align-self:stretch; border-radius:2px; min-height:38px;}
  .ihead-main{min-width:0;}
  .meta-top{display:flex; flex-wrap:wrap; gap:7px; align-items:center; font-size:11px; margin-bottom:5px;}
  .tag{padding:2px 7px; border-radius:4px; font-size:10.5px; font-weight:500; letter-spacing:.01em; white-space:nowrap;}
  .tag.cat{background:var(--tagbg); color:var(--tagfg);}
  .tag.type{background:var(--surface-2); color:var(--ink-2); border:1px solid var(--line);}
  .date{font-family:"IBM Plex Mono",monospace; color:var(--muted); font-size:11px;}
  .est{color:var(--muted); font-size:10px; border:1px solid var(--line); border-radius:3px; padding:0 4px;}
  .item-title{font-size:14.5px; font-weight:500; line-height:1.5; color:var(--ink);}
  .meta-bot{display:flex; flex-wrap:wrap; gap:4px 12px; font-size:11.5px; color:var(--muted); margin-top:6px;}
  .meta-bot .k{color:var(--muted);}
  .meta-bot .v{color:var(--ink-2); font-family:"IBM Plex Mono",monospace;}
  .ddl{color:var(--signal); font-weight:500;}
  .chev{color:var(--muted); font-size:11px; padding-top:2px; transition:transform .18s;}
  .item.open .chev{transform:rotate(180deg);}

  .body{display:none; padding:0 18px 18px 35px; border-top:1px solid var(--line); margin-top:-1px;}
  .item.open .body{display:block;}
  .summary{font-size:13.5px; color:var(--ink-2); line-height:1.75; padding:15px 0 4px; max-width:72ch;}
  .analysis{display:grid; grid-template-columns:1fr 1fr; gap:14px 22px; margin-top:16px;
    padding-top:16px; border-top:1px dashed var(--line);}
  .af{min-width:0;}
  .af .k{
    font-size:10.5px; letter-spacing:.1em; text-transform:uppercase; color:var(--accent);
    font-weight:600; display:flex; align-items:center; gap:6px; margin-bottom:5px;
  }
  .af .k::before{content:""; width:14px; height:1.5px; background:var(--accent); flex:none;}
  .af .t{font-size:12.8px; line-height:1.72; color:var(--ink-2);}
  .foot{display:flex; flex-wrap:wrap; gap:10px 16px; align-items:center; margin-top:16px;
    padding-top:12px; border-top:1px solid var(--line); font-size:11.5px; color:var(--muted);}
  .kw{display:flex; flex-wrap:wrap; gap:5px;}
  .kw span{font-family:"IBM Plex Mono",monospace; font-size:10.5px; color:var(--muted);
    background:var(--surface-2); border-radius:3px; padding:1px 6px;}
  a.src{color:var(--accent); text-decoration:none; font-weight:500; margin-left:auto;}
  a.src:hover{text-decoration:underline;}
  a.src:focus-visible{outline:2px solid var(--accent); outline-offset:2px; border-radius:3px;}

  .empty{padding:36px; text-align:center; color:var(--muted); font-size:13px;
    background:var(--surface); border:1px dashed var(--line); border-radius:var(--radius);}
  .pagefoot{margin-top:34px; padding-top:16px; border-top:1px solid var(--line);
    font-size:11.5px; color:var(--muted); line-height:1.85;}
  .pagefoot code{font-family:"IBM Plex Mono",monospace; font-size:11px; background:var(--surface-2); padding:1px 5px; border-radius:3px;}

  @media (max-width:860px){
    .stats{grid-template-columns:repeat(2,1fr);}
    .stages{grid-template-columns:repeat(2,1fr);}
    .grid-2{grid-template-columns:1fr;}
    .analysis{grid-template-columns:1fr;}
  }
  @media (max-width:560px){
    .wrap{padding:26px 16px 56px;}
    h1{font-size:25px;}
    .masthead-meta{text-align:left;}
    .body{padding-left:18px;}
  }
  @media (prefers-reduced-motion: reduce){
    *{transition:none !important; animation:none !important;}
  }
</style>

<div class="wrap">
  <header class="masthead">
    <div>
      <div class="eyebrow">Korea Mobility Technology Policy Monitor</div>
      <h1>모빌리티 정책·사업 브리프</h1>
      <p class="tagline">자동차·모빌리티 기술정책과 정부 신규사업을 추적하고, 각 사업이 <em>왜 지금</em> 기획되었는지를 분석해 누적합니다.</p>
    </div>
    <div class="masthead-meta">
      <div>마지막 갱신 · <span class="num"><!--GENERATED_AT_START-->__GENERATED_AT__<!--GENERATED_AT_END--></span></div>
      <div class="big">누적 <span class="num"><!--TOTAL_COUNT_START-->__TOTAL_COUNT__<!--TOTAL_COUNT_END--></span>건</div>
    </div>
  </header>

  <div id="alert-slot"></div>
  <div class="stats" id="stats"></div>

  <section class="pipeline">
    <div class="sec-head">
      <div>
        <h2>정책에서 사업까지</h2>
        <div class="desc">정부 R&amp;D는 구상 → 예타 → 공고 순으로 흐릅니다. 앞단을 볼수록 대응이 빨라집니다. 단계를 눌러 필터링하세요.</div>
      </div>
    </div>
    <div class="stages" id="stages"></div>
  </section>

  <div class="grid-2">
    <div class="panel">
      <div class="sec-head"><div><h2>월별 수집 동향</h2><div class="desc">발표·공고일 기준, 분야별 누적</div></div></div>
      <div class="chart-wrap"><svg class="chart" id="chart" viewBox="0 0 660 212" preserveAspectRatio="xMidYMid meet" role="img" aria-label="월별 분야별 항목 수 막대그래프"></svg></div>
      <div class="legend" id="legend"></div>
    </div>
    <div class="panel">
      <div class="sec-head"><div><h2>분야별 비중</h2><div class="desc">현재 필터 기준</div></div></div>
      <div class="cat-rows" id="cat-rows"></div>
    </div>
  </div>

  <section>
    <div class="sec-head">
      <div><h2>분석 카드</h2><div class="desc">항목을 눌러 배경 분석을 펼칩니다</div></div>
      <div class="seg" id="type-seg"></div>
    </div>
    <div class="controls">
      <input class="search" id="q" type="text" placeholder="제목·요약·분석·키워드 검색…" aria-label="검색">
    </div>
    <div class="chips" id="chips"></div>
    <div class="count-line" id="count"></div>
    <ul class="items" id="list"></ul>
    <div class="empty" id="empty" hidden>조건에 맞는 항목이 없습니다.</div>
  </section>

  <footer class="pagefoot">
    데이터 <code>data/policy_items.json</code> · 분석 필드는 공개 자료를 근거로 한 해석이며 정부의 공식 입장이 아닙니다.
    금액 단위는 억원입니다. 원문 링크로 반드시 교차 확인하세요.
  </footer>
</div>

<script>
const ITEMS = /*ITEMS_JSON_START*/__ITEMS_JSON__/*ITEMS_JSON_END*/;
const CATS = __CATS__;
const STAGES = __STAGES__;
const TYPES = __TYPES__;
const CAT_COLOR = __CAT_COLOR__;
const STAGE_DESC = {
  "구상·계획": "업무계획·로드맵·수요조사",
  "예타·예산확정": "예타 통과 / 예산 배정",
  "공고": "신규과제 모집 중",
  "수행중": "집행·실증 진행"
};
const TODAY = new Date(__TODAY_JSON__);

const $ = (s) => document.querySelector(s);
const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const color = (c) => CAT_COLOR[c] || "#78889a";
const fmtNum = (n) => n.toLocaleString("ko-KR");

const state = { q:"", cats:new Set(), type:"all", stage:null };

function daysUntil(d){
  if(!d) return null;
  const t = new Date(d + "T00:00:00+09:00");
  return Math.ceil((t - TODAY) / 86400000);
}

function passes(it){
  if(state.type !== "all" && it.type !== state.type) return false;
  if(state.stage && it.stage !== state.stage) return false;
  if(state.cats.size && !state.cats.has(it.category)) return false;
  if(state.q){
    const a = it.analysis || {};
    const hay = [it.title, it.summary, it.agency, it.exec_agency, it.doc_no, it.source,
                 a.why_now, a.lineage, a.tech, a.implication, (it.keywords||[]).join(" ")]
                .join(" ").toLowerCase();
    if(!hay.includes(state.q.toLowerCase())) return false;
  }
  return true;
}

/* ---------- alert strip: 마감 임박 공고 ---------- */
function renderAlert(){
  const soon = ITEMS
    .map(it => ({it, d: daysUntil(it.deadline)}))
    .filter(x => x.d !== null && x.d >= 0 && x.d <= 30)
    .sort((a,b) => a.d - b.d);
  const slot = $("#alert-slot");
  if(!soon.length){ slot.innerHTML = ""; return; }
  slot.innerHTML = `<div class="alert"><b>접수 마감 임박</b>` +
    soon.slice(0,3).map(x =>
      `<span class="a-item">${esc(x.it.title)} <span class="num">D-${x.d}</span> (${esc(x.it.deadline)})</span>`
    ).join("") + `</div>`;
}

/* ---------- stat tiles ---------- */
function renderStats(){
  const open = ITEMS.filter(it => it.stage === "공고").length;
  const budget = ITEMS.reduce((s,it) => s + (typeof it.budget_total === "number" ? it.budget_total : 0), 0);
  const withBudget = ITEMS.filter(it => typeof it.budget_total === "number").length;
  const cutoff = new Date(TODAY.getTime() - 90*86400000);
  const recent = ITEMS.filter(it => new Date(it.date + "T00:00:00+09:00") >= cutoff).length;
  const upstream = ITEMS.filter(it => it.stage === "구상·계획").length;

  const tiles = [
    {label:"추적 중인 정책·사업", value:fmtNum(ITEMS.length), unit:"건", sub:`분야 ${new Set(ITEMS.map(i=>i.category)).size}개 · 부처 ${new Set(ITEMS.map(i=>i.agency)).size}곳`},
    {label:"모집 중인 신규사업", value:fmtNum(open), unit:"건", sub:"stage = 공고", hi:open>0},
    {label:"확인된 사업비", value:fmtNum(budget), unit:"억원", sub:`${withBudget}건 단순합 · 사업기간·성격 상이`},
    {label:"최근 90일 신규", value:fmtNum(recent), unit:"건", sub:`선행 신호(구상·계획) ${upstream}건 포함`}
  ];
  $("#stats").innerHTML = tiles.map(t => `
    <div class="stat${t.hi ? " hi" : ""}">
      <div class="label">${esc(t.label)}</div>
      <div class="value num">${t.value}<span class="unit">${esc(t.unit)}</span></div>
      <div class="sub">${esc(t.sub)}</div>
    </div>`).join("");
}

/* ---------- pipeline ---------- */
function renderStages(){
  const counts = STAGES.map(s => ITEMS.filter(i => i.stage === s).length);
  const max = Math.max(1, ...counts);
  $("#stages").innerHTML = STAGES.map((s,i) => `
    <button class="stage" data-stage="${esc(s)}" aria-pressed="${state.stage === s}">
      <div class="st-i">STEP ${i+1}</div>
      <div class="st-n">${esc(s)}</div>
      <div class="st-c num">${counts[i]}</div>
      <div class="st-d">${esc(STAGE_DESC[s] || "")}</div>
      <div class="stage-track"><i style="width:${(counts[i]/max*100).toFixed(1)}%"></i></div>
    </button>`).join("");
  $("#stages").querySelectorAll(".stage").forEach(b => {
    b.addEventListener("click", () => {
      const s = b.dataset.stage;
      state.stage = (state.stage === s) ? null : s;
      renderStages(); render();
    });
  });
}

/* ---------- monthly stacked chart ---------- */
function renderChart(rows){
  const svg = $("#chart");
  const W = 660, H = 212, padL = 26, padR = 8, padB = 22, padT = 10;
  if(!rows.length){ svg.innerHTML = `<text x="${W/2}" y="${H/2}" text-anchor="middle">데이터 없음</text>`; return; }

  const seen = [...new Set(rows.map(r => r.date.slice(0,7)))].sort();
  let months = seen;
  if(seen.length > 1){
    const span = [];
    let [y,m] = seen[0].split("-").map(Number);
    const [ey,em] = seen[seen.length-1].split("-").map(Number);
    while((y < ey || (y === ey && m <= em)) && span.length < 24){
      span.push(`${y}-${String(m).padStart(2,"0")}`);
      if(++m > 12){ m = 1; y++; }
    }
    if(span.length < 24) months = span;   // 24개월 넘으면 데이터 있는 달만
  }
  const byMonth = {};
  months.forEach(m => { byMonth[m] = {}; CATS.forEach(c => byMonth[m][c] = 0); });
  rows.forEach(r => { byMonth[r.date.slice(0,7)][r.category] += 1; });

  const totals = months.map(m => CATS.reduce((s,c) => s + byMonth[m][c], 0));
  const maxV = Math.max(1, ...totals);
  const niceMax = maxV <= 4 ? maxV : Math.ceil(maxV/2)*2;
  const plotW = W - padL - padR, plotH = H - padT - padB;
  const step = plotW / months.length;
  const barW = Math.min(38, step * 0.6);
  const y = v => padT + plotH - (v / niceMax) * plotH;

  let s = "";
  const ticks = niceMax <= 4 ? niceMax : 4;
  for(let i=0; i<=ticks; i++){
    const v = Math.round(niceMax * i / ticks);
    s += `<line class="gridline" x1="${padL}" x2="${W-padR}" y1="${y(v)}" y2="${y(v)}"/>`;
    s += `<text x="${padL-6}" y="${y(v)+3.2}" text-anchor="end">${v}</text>`;
  }
  months.forEach((m,i) => {
    const cx = padL + step*i + step/2;
    let cursor = 0;
    CATS.forEach(c => {
      const v = byMonth[m][c];
      if(!v) return;
      const h = (v / niceMax) * plotH;
      const yy = y(cursor + v);
      s += `<rect x="${(cx - barW/2).toFixed(1)}" y="${yy.toFixed(1)}" width="${barW.toFixed(1)}" height="${Math.max(h-1.2,1).toFixed(1)}" rx="2" fill="${color(c)}"><title>${esc(m)} · ${esc(c)} — ${v}건</title></rect>`;
      cursor += v;
    });
    s += `<text x="${cx}" y="${H-6}" text-anchor="middle">${m.slice(2).replace("-","/")}</text>`;
  });
  svg.innerHTML = s;

  const usedCats = CATS.filter(c => months.some(m => byMonth[m][c] > 0));
  $("#legend").innerHTML = usedCats.map(c =>
    `<span class="it"><span class="sw" style="background:${color(c)}"></span>${esc(c)}</span>`).join("");
}

/* ---------- category shares ---------- */
function renderCats(rows){
  const counts = CATS.map(c => rows.filter(r => r.category === c).length);
  const max = Math.max(1, ...counts);
  const total = rows.length || 1;
  const html = CATS.map((c,i) => counts[i] === 0 ? "" : `
    <div class="cat-row">
      <span class="cn">${esc(c)}</span>
      <span class="cv num">${counts[i]}건 · ${Math.round(counts[i]/total*100)}%</span>
      <span class="cat-bar"><i style="width:${(counts[i]/max*100).toFixed(1)}%; background:${color(c)}"></i></span>
    </div>`).join("");
  $("#cat-rows").innerHTML = html || `<div class="cv" style="color:var(--muted);font-size:12px">데이터 없음</div>`;
}

/* ---------- controls ---------- */
function renderControls(){
  $("#type-seg").innerHTML = [{v:"all",l:"전체"}].concat(TYPES.map(t => ({v:t,l:t})))
    .map(o => `<button data-type="${esc(o.v)}" class="${state.type===o.v?"on":""}">${esc(o.l)}</button>`).join("");
  $("#type-seg").querySelectorAll("button").forEach(b => b.addEventListener("click", () => {
    state.type = b.dataset.type; renderControls(); render();
  }));

  $("#chips").innerHTML = CATS.map(c => {
    const n = ITEMS.filter(i => i.category === c).length;
    if(!n) return "";
    const on = state.cats.has(c);
    return `<button class="chip${on?" on":""}" data-cat="${esc(c)}" style="${on?`color:${color(c)};background:${color(c)}14`:""}">
      <span class="sw" style="background:${color(c)}"></span>${esc(c)}<span class="cc">${n}</span></button>`;
  }).join("");
  $("#chips").querySelectorAll(".chip").forEach(b => b.addEventListener("click", () => {
    const c = b.dataset.cat;
    state.cats.has(c) ? state.cats.delete(c) : state.cats.add(c);
    renderControls(); render();
  }));
}

/* ---------- list ---------- */
function itemHTML(it, open){
  const a = it.analysis || {};
  const d = daysUntil(it.deadline);
  const meta = [];
  if(it.agency) meta.push(`<span><span class="k">소관</span> <span class="v">${esc(it.agency)}</span></span>`);
  if(it.exec_agency) meta.push(`<span><span class="k">전담</span> <span class="v">${esc(it.exec_agency)}</span></span>`);
  if(typeof it.budget_total === "number") meta.push(`<span><span class="k">사업비</span> <span class="v">${fmtNum(it.budget_total)}억원</span></span>`);
  if(it.period) meta.push(`<span><span class="k">기간</span> <span class="v">${esc(it.period)}</span></span>`);
  if(it.doc_no) meta.push(`<span><span class="v">${esc(it.doc_no)}</span></span>`);
  if(it.deadline) meta.push(`<span class="ddl">마감 ${esc(it.deadline)}${d !== null && d >= 0 ? ` · D-${d}` : ""}</span>`);

  const fields = [["왜 지금", a.why_now], ["정책 계보", a.lineage], ["기술 쟁점", a.tech], ["시사점", a.implication]];

  return `<li class="item${open?" open":""}" data-id="${esc(it.id)}">
    <button class="item-head" aria-expanded="${open}">
      <span class="rail" style="background:${color(it.category)}"></span>
      <span class="ihead-main">
        <span class="meta-top">
          <span class="tag cat" style="--tagbg:${color(it.category)}1a; --tagfg:${color(it.category)}">${esc(it.category)}</span>
          <span class="tag type">${esc(it.type)}</span>
          <span class="date">${esc(it.date)}</span>
          ${it.date_estimated ? `<span class="est">추정</span>` : ""}
        </span>
        <span class="item-title">${esc(it.title)}</span>
        <span class="meta-bot">${meta.join("")}</span>
      </span>
      <span class="chev">▼</span>
    </button>
    <div class="body">
      <p class="summary">${esc(it.summary)}</p>
      <div class="analysis">
        ${fields.map(([k,v]) => `<div class="af"><div class="k">${esc(k)}</div><div class="t">${esc(v || "—")}</div></div>`).join("")}
      </div>
      <div class="foot">
        <span class="kw">${(it.keywords||[]).map(k => `<span>${esc(k)}</span>`).join("")}</span>
        <a class="src" href="${esc(it.url)}" target="_blank" rel="noopener noreferrer">원문 · ${esc(it.source)} ↗</a>
      </div>
    </div>
  </li>`;
}

const opened = new Set();

function render(){
  const rows = ITEMS.filter(passes).sort((a,b) => b.date.localeCompare(a.date) || a.id.localeCompare(b.id));
  if(opened.size === 0 && rows.length) opened.add(rows[0].id);

  $("#count").textContent = `${rows.length}건 표시 / 전체 ${ITEMS.length}건` +
    (state.stage ? ` · 단계: ${state.stage}` : "") +
    (state.cats.size ? ` · 분야: ${[...state.cats].join(", ")}` : "");

  $("#list").innerHTML = rows.map(it => itemHTML(it, opened.has(it.id))).join("");
  $("#empty").hidden = rows.length > 0;

  $("#list").querySelectorAll(".item").forEach(li => {
    li.querySelector(".item-head").addEventListener("click", () => {
      const id = li.dataset.id;
      opened.has(id) ? opened.delete(id) : opened.add(id);
      li.classList.toggle("open");
      li.querySelector(".item-head").setAttribute("aria-expanded", String(opened.has(id)));
    });
  });

  renderChart(rows);
  renderCats(rows);
}

$("#q").addEventListener("input", (e) => { state.q = e.target.value.trim(); render(); });

renderAlert();
renderStats();
renderStages();
renderControls();
render();
</script>
"""

CAT_COLOR = {
    "자율주행": "#2a8b96",
    "SDV·차량반도체": "#8b6bc0",
    "전기차·배터리": "#4e9647",
    "UAM·미래항공": "#5a76d0",
    "모빌리티서비스·물류": "#c8923f",
    "인프라·표준·규제": "#78889a",
    "미래차전환·총괄": "#c1554f",
}


def build(db: dict, now: datetime) -> str:
    items = db["items"]
    j = lambda o: json.dumps(o, ensure_ascii=False, separators=(",", ":"))
    return (
        TEMPLATE
        .replace("__GENERATED_AT__", now.strftime("%Y-%m-%d %H:%M KST"))
        .replace("__TOTAL_COUNT__", str(len(items)))
        .replace("__ITEMS_JSON__", j(items))
        .replace("__CATS__", j(CATEGORIES))
        .replace("__STAGES__", j(STAGES))
        .replace("__TYPES__", j(TYPES))
        .replace("__CAT_COLOR__", j(CAT_COLOR))
        .replace("__TODAY_JSON__", j(now.strftime("%Y-%m-%dT00:00:00+09:00")))
    )


def main() -> None:
    db = json.loads(DB.read_text(encoding="utf-8"))
    html = build(db, datetime.now(KST))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html, encoding="utf-8")
    print(f"wrote {OUT} ({len(html):,} bytes, {len(db['items'])} items)")


if __name__ == "__main__":
    main()
