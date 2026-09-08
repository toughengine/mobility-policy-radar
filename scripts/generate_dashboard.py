#!/usr/bin/env python3
"""모빌리티 브리프 대시보드 생성기.

data/mobility_news.json 을 읽어 artifact/dashboard.html (Claude Artifact로 발행할
정적 HTML)을 만든다. 외부 의존성 없이 표준 라이브러리만 사용한다.

사용법:
    python3 scripts/generate_dashboard.py
"""
import json
import pathlib
import sys
from datetime import datetime, timezone, timedelta

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA_PATH = ROOT / "data" / "mobility_news.json"
OUT_PATH = ROOT / "artifact" / "dashboard.html"

KST = timezone(timedelta(hours=9))


def load_data():
    with DATA_PATH.open(encoding="utf-8") as f:
        payload = json.load(f)
    articles = payload.get("articles", [])
    # 중복 URL 검사 (경고만, 생성은 계속)
    seen = {}
    for a in articles:
        if a["url"] in seen:
            print(f"[경고] 중복 URL 발견: {a['url']} ({seen[a['url']]} / {a['id']})",
                  file=sys.stderr)
        seen[a["url"]] = a["id"]
        for field in ("id", "date", "title", "summary", "url", "source", "category", "region"):
            if field not in a:
                raise ValueError(f"필수 필드 누락: {field} in {a}")
    return payload, articles


def build_html(payload, articles):
    now_kst = datetime.now(KST).strftime("%Y-%m-%d %H:%M KST")
    data_json = json.dumps(articles, ensure_ascii=False)
    html = TEMPLATE
    html = html.replace("__ARTICLES_JSON__", data_json)
    html = html.replace("__GENERATED_AT__", now_kst)
    html = html.replace("__TOTAL_COUNT__", str(len(articles)))
    return html


TEMPLATE = r"""<title>모빌리티 브리프</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Gothic+A1:wght@500;700;800&family=IBM+Plex+Sans+KR:wght@400;500;600;700&family=IBM+Plex+Mono:wght@500;600&display=swap" rel="stylesheet">
<style>
  :root {
    --page: #eef1f3;
    --surface: #ffffff;
    --surface-2: #f6f8f9;
    --ink: #0b0f14;
    --ink-2: #4b5560;
    --ink-3: #868d94;
    --grid: #e1e6e9;
    --border: rgba(11,15,20,0.10);
    --accent: #2a78d6;
    --accent-ink: #ffffff;
    --warn: #b8790f;
    --warn-bg: #fdf1dc;

    --c1: #2a78d6; /* 자율주행 */
    --c2: #d0591f; /* UAM */
    --c3: #17976a; /* 전기차·배터리 */
    --c4: #c2820a; /* 모빌리티 서비스 */
    --c5: #c15c85; /* 정책·규제 */
    --c6: #4a3aa7; /* 기타 */
  }
  @media (prefers-color-scheme: dark) {
    :root:not([data-theme="light"]) {
      --page: #0d1013;
      --surface: #161a1e;
      --surface-2: #1c2126;
      --ink: #f3f5f6;
      --ink-2: #c7cbd0;
      --ink-3: #8b9299;
      --grid: #262c31;
      --border: rgba(255,255,255,0.10);
      --accent: #3987e5;
      --accent-ink: #ffffff;
      --warn: #f0b23c;
      --warn-bg: #3a2f11;

      --c1: #3987e5;
      --c2: #e07a3f;
      --c3: #2bb684;
      --c4: #dba22c;
      --c5: #d9799e;
      --c6: #9085e9;
    }
  }
  :root[data-theme="dark"] {
    --page: #0d1013;
    --surface: #161a1e;
    --surface-2: #1c2126;
    --ink: #f3f5f6;
    --ink-2: #c7cbd0;
    --ink-3: #8b9299;
    --grid: #262c31;
    --border: rgba(255,255,255,0.10);
    --accent: #3987e5;
    --accent-ink: #ffffff;
    --warn: #f0b23c;
    --warn-bg: #3a2f11;

    --c1: #3987e5;
    --c2: #e07a3f;
    --c3: #2bb684;
    --c4: #dba22c;
    --c5: #d9799e;
    --c6: #9085e9;
  }

  * { box-sizing: border-box; }
  html, body { margin: 0; padding: 0; }
  body {
    background: var(--page);
    color: var(--ink);
    font-family: "IBM Plex Sans KR", "Noto Sans KR", system-ui, sans-serif;
    font-size: 15px;
    line-height: 1.55;
  }
  .num { font-family: "IBM Plex Mono", ui-monospace, monospace; font-variant-numeric: tabular-nums; }
  h1, h2, h3 { font-family: "Gothic A1", "IBM Plex Sans KR", sans-serif; text-wrap: balance; margin: 0; }
  a { color: inherit; }

  .wrap { max-width: 1180px; margin: 0 auto; padding: 28px 20px 80px; }

  /* ---- Hero ---- */
  .hero {
    display: flex; justify-content: space-between; align-items: flex-end; gap: 24px;
    flex-wrap: wrap; padding-bottom: 22px; margin-bottom: 22px; border-bottom: 1px solid var(--border);
  }
  .hero .eyebrow {
    font-size: 12px; letter-spacing: 0.08em; text-transform: uppercase; color: var(--accent);
    font-weight: 700; margin-bottom: 8px;
  }
  .hero h1 { font-size: 30px; font-weight: 800; letter-spacing: -0.01em; }
  .hero p { color: var(--ink-2); margin-top: 6px; font-size: 14px; max-width: 46ch; }
  .hero-meta { text-align: right; color: var(--ink-3); font-size: 12.5px; }
  .hero-meta .updated { color: var(--ink-2); font-weight: 500; }

  /* ---- KPI strip ---- */
  .kpis { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 22px; }
  .kpi {
    background: var(--surface); border: 1px solid var(--border); border-radius: 10px;
    padding: 16px 18px;
  }
  .kpi .label { font-size: 12px; color: var(--ink-3); font-weight: 500; }
  .kpi .value { font-size: 28px; font-weight: 600; margin-top: 6px; }
  .kpi .value .unit { font-size: 13px; color: var(--ink-3); font-weight: 500; margin-left: 2px; }
  .kpi .sub { font-size: 12px; color: var(--ink-3); margin-top: 4px; }

  /* ---- Panels ---- */
  .grid-2 { display: grid; grid-template-columns: 1.65fr 1fr; gap: 14px; margin-bottom: 14px; }
  @media (max-width: 860px) { .grid-2 { grid-template-columns: 1fr; } }
  .panel {
    background: var(--surface); border: 1px solid var(--border); border-radius: 12px;
    padding: 18px 20px 20px;
  }
  .panel-head { display: flex; justify-content: space-between; align-items: center; gap: 10px; margin-bottom: 14px; flex-wrap: wrap; }
  .panel-head h2 { font-size: 15px; font-weight: 700; }
  .panel-head .desc { font-size: 12px; color: var(--ink-3); margin-top: 2px; }

  .seg { display: inline-flex; background: var(--surface-2); border: 1px solid var(--border); border-radius: 8px; padding: 2px; gap: 2px; }
  .seg button {
    appearance: none; border: none; background: transparent; color: var(--ink-2);
    font: inherit; font-size: 12.5px; font-weight: 500; padding: 5px 10px; border-radius: 6px; cursor: pointer;
  }
  .seg button.active { background: var(--surface); color: var(--ink); box-shadow: 0 1px 2px var(--border); font-weight: 700; }
  .seg button:hover:not(.active) { color: var(--ink); }

  /* ---- Trend chart ---- */
  .chart-svg { width: 100%; height: 260px; display: block; overflow: visible; }
  .bar-seg { cursor: pointer; }
  .bar-seg:hover { filter: brightness(1.08); }
  .axis-label { font-size: 10.5px; fill: var(--ink-3); font-family: "IBM Plex Mono", monospace; }
  .gridline { stroke: var(--grid); stroke-width: 1; }

  .legend { display: flex; flex-wrap: wrap; gap: 10px 16px; margin-top: 14px; font-size: 12px; color: var(--ink-2); }
  .legend .item { display: inline-flex; align-items: center; gap: 6px; }
  .legend .swatch { width: 9px; height: 9px; border-radius: 2px; display: inline-block; }

  .tooltip {
    position: fixed; pointer-events: none; z-index: 50; background: var(--ink); color: var(--page);
    font-size: 12px; padding: 8px 10px; border-radius: 8px; max-width: 240px; line-height: 1.5;
    opacity: 0; transform: translateY(4px); transition: opacity .1s ease;
  }
  .tooltip.show { opacity: 1; }
  .tooltip b { display: block; margin-bottom: 2px; }
  .tooltip .row { display: flex; justify-content: space-between; gap: 10px; }

  /* ---- Category bars ---- */
  .cat-bars { display: flex; flex-direction: column; gap: 10px; }
  .cat-bar-row { display: grid; grid-template-columns: 92px 1fr 34px; align-items: center; gap: 8px; font-size: 12.5px; }
  .cat-bar-row .name { color: var(--ink-2); font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .cat-bar-track { background: var(--surface-2); border-radius: 5px; height: 10px; overflow: hidden; }
  .cat-bar-fill { height: 100%; border-radius: 5px; }
  .cat-bar-row .count { text-align: right; color: var(--ink-3); }

  /* ---- List ---- */
  .list-panel { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 18px 20px 8px; }
  .list-controls { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; margin-bottom: 14px; }
  .search {
    flex: 1 1 220px; background: var(--surface-2); border: 1px solid var(--border); border-radius: 8px;
    padding: 9px 12px; font: inherit; font-size: 13px; color: var(--ink);
  }
  .search:focus { outline: 2px solid var(--accent); outline-offset: -1px; }
  .chip-row { display: flex; gap: 6px; flex-wrap: wrap; }
  .chip {
    appearance: none; border: 1px solid var(--border); background: var(--surface-2); color: var(--ink-2);
    font: inherit; font-size: 12px; font-weight: 500; padding: 6px 11px; border-radius: 999px; cursor: pointer;
    display: inline-flex; align-items: center; gap: 6px;
  }
  .chip .dot { width: 7px; height: 7px; border-radius: 50%; }
  .chip.active { background: var(--ink); color: var(--page); border-color: var(--ink); }
  .chip.active .dot { filter: none; }

  .count-line { font-size: 12px; color: var(--ink-3); margin-bottom: 6px; }

  .article-list { list-style: none; margin: 0; padding: 0; }
  .article {
    display: grid; grid-template-columns: 3px 1fr auto; gap: 14px; padding: 14px 0;
    border-top: 1px solid var(--border);
  }
  .article:first-child { border-top: none; }
  .article .bar { border-radius: 2px; align-self: stretch; }
  .article .title-row { display: flex; align-items: baseline; gap: 8px; flex-wrap: wrap; }
  .article a.title { font-weight: 700; font-size: 14.5px; text-decoration: none; }
  .article a.title:hover { text-decoration: underline; }
  .article .summary { color: var(--ink-2); font-size: 13px; margin-top: 4px; max-width: 74ch; }
  .article .meta { display: flex; gap: 8px; margin-top: 8px; flex-wrap: wrap; align-items: center; }
  .tag {
    font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 999px;
    background: var(--surface-2); color: var(--ink-2); border: 1px solid var(--border);
  }
  .tag.estimated { background: var(--warn-bg); color: var(--warn); border-color: transparent; }
  .article .right { text-align: right; white-space: nowrap; }
  .article .date { font-size: 12.5px; color: var(--ink-3); }
  .article .source { font-size: 12px; color: var(--ink-3); margin-top: 3px; }

  .empty-state { padding: 40px 0; text-align: center; color: var(--ink-3); font-size: 13.5px; }

  footer { margin-top: 28px; text-align: center; color: var(--ink-3); font-size: 12px; }
</style>

<div class="wrap">
  <div class="hero">
    <div>
      <div class="eyebrow">Mobility Trend Briefing</div>
      <h1>모빌리티 브리프</h1>
      <p>국내·글로벌 모빌리티 산업 뉴스를 매일 자동 수집해 누적하는 트렌드 데이터베이스입니다.</p>
    </div>
    <div class="hero-meta">
      <div class="updated">마지막 갱신 · <!--GENERATED_AT_START-->__GENERATED_AT__<!--GENERATED_AT_END--></div>
      <div>누적 기사 <span class="num"><!--TOTAL_COUNT_START-->__TOTAL_COUNT__<!--TOTAL_COUNT_END--></span>건 · 매일 08:00 KST 자동 갱신</div>
    </div>
  </div>

  <div class="kpis" id="kpis"></div>

  <div class="grid-2">
    <div class="panel">
      <div class="panel-head">
        <div>
          <h2>기간별 동향</h2>
          <div class="desc">카테고리별 기사 건수 추이</div>
        </div>
        <div class="seg" id="bucket-seg">
          <button data-bucket="month" class="active">월간</button>
          <button data-bucket="quarter">분기별</button>
          <button data-bucket="half">반기별</button>
        </div>
      </div>
      <svg class="chart-svg" id="trend-chart" viewBox="0 0 640 260" preserveAspectRatio="none"></svg>
      <div class="legend" id="trend-legend"></div>
    </div>

    <div class="panel">
      <div class="panel-head">
        <div>
          <h2>카테고리 비중</h2>
          <div class="desc">현재 필터 기준 전체 누적</div>
        </div>
      </div>
      <div class="cat-bars" id="cat-bars"></div>
    </div>
  </div>

  <div class="list-panel">
    <div class="panel-head">
      <div>
        <h2>누적 리스트</h2>
        <div class="desc">지금까지 수집된 모든 기사 (최근 수집순)</div>
      </div>
      <div class="seg" id="region-seg">
        <button data-region="all" class="active">전체</button>
        <button data-region="국내">국내</button>
        <button data-region="글로벌">글로벌</button>
      </div>
    </div>
    <div class="list-controls">
      <input class="search" id="search" type="text" placeholder="제목·요약 키워드 검색…">
      <div class="chip-row" id="cat-chips"></div>
    </div>
    <div class="count-line" id="count-line"></div>
    <ul class="article-list" id="article-list"></ul>
    <div class="empty-state" id="empty-state" style="display:none;">검색·필터 조건에 맞는 기사가 없습니다.</div>
  </div>

  <footer>모빌리티 브리프 · 매일 자동 수집·요약되는 개인용 트렌드 아카이브</footer>
</div>

<div class="tooltip" id="tooltip"></div>

<script>
  const ARTICLES = /*ARTICLES_JSON_START*/__ARTICLES_JSON__/*ARTICLES_JSON_END*/;

  const CATS = ["자율주행", "UAM", "전기차·배터리", "모빌리티 서비스", "정책·규제", "기타"];
  const CAT_VARS = { "자율주행": "--c1", "UAM": "--c2", "전기차·배터리": "--c3", "모빌리티 서비스": "--c4", "정책·규제": "--c5", "기타": "--c6" };
  const root = document.documentElement;
  const cssVar = (name) => getComputedStyle(root).getPropertyValue(name).trim();
  const catColor = (cat) => cssVar(CAT_VARS[cat] || "--c6");

  const state = { bucket: "month", region: "all", cats: new Set(), query: "" };

  // ---------- date helpers ----------
  function parseDate(s) { const [y,m,d] = s.split("-").map(Number); return new Date(Date.UTC(y, m-1, d)); }
  function bucketKey(dateStr, bucket) {
    const d = parseDate(dateStr);
    const y = d.getUTCFullYear(), m = d.getUTCMonth();
    if (bucket === "month") return `${y}-${String(m+1).padStart(2,"0")}`;
    if (bucket === "quarter") return `${y}-Q${Math.floor(m/3)+1}`;
    return `${y}-${m < 6 ? "상반기" : "하반기"}`;
  }
  function bucketLabel(key, bucket) {
    if (bucket === "month") { const [y,m] = key.split("-"); return `${y.slice(2)}.${m}`; }
    return key.replace(/^(\d{4})-/, (_, y) => y.slice(2) + " ");
  }

  // ---------- KPIs ----------
  function renderKPIs() {
    const now = new Date();
    const thisMonthKey = `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,"0")}`;
    const weekAgo = new Date(now); weekAgo.setDate(now.getDate() - 7);
    const total = ARTICLES.length;
    const thisMonth = ARTICLES.filter(a => bucketKey(a.collected_at, "month") === thisMonthKey).length;
    const thisWeek = ARTICLES.filter(a => parseDate(a.collected_at) >= weekAgo).length;
    const cats = new Set(ARTICLES.map(a => a.category)).size;
    const tiles = [
      ["누적 기사", total, "건", "서비스 시작 이후 총계"],
      ["이번 달 신규", thisMonth, "건", "이번 달 수집분"],
      ["최근 7일", thisWeek, "건", "지난 7일간 신규"],
      ["추적 카테고리", cats, "종", "자율주행 · UAM · 배터리 등"],
    ];
    document.getElementById("kpis").innerHTML = tiles.map(([label, value, unit, sub]) => `
      <div class="kpi">
        <div class="label">${label}</div>
        <div class="value num">${value}<span class="unit">${unit}</span></div>
        <div class="sub">${sub}</div>
      </div>`).join("");
  }

  // ---------- trend chart (stacked bars) ----------
  function renderTrend() {
    const buckets = {};
    for (const a of ARTICLES) {
      const key = bucketKey(a.date, state.bucket);
      buckets[key] = buckets[key] || {};
      buckets[key][a.category] = (buckets[key][a.category] || 0) + 1;
    }
    const keys = Object.keys(buckets).sort();
    const W = 640, H = 260, padL = 28, padB = 24, padT = 10;
    const plotW = W - padL - 8, plotH = H - padB - padT;
    const maxTotal = Math.max(1, ...keys.map(k => CATS.reduce((s,c) => s + (buckets[k][c]||0), 0)));
    const niceMax = Math.ceil(maxTotal / 4) * 4 || 4;
    const barW = Math.min(46, plotW / Math.max(keys.length, 1) * 0.6);
    const step = plotW / Math.max(keys.length, 1);

    let svg = "";
    // gridlines + axis labels
    const ticks = 4;
    for (let i = 0; i <= ticks; i++) {
      const v = Math.round(niceMax * i / ticks);
      const y = padT + plotH - (v/niceMax)*plotH;
      svg += `<line class="gridline" x1="${padL}" x2="${W}" y1="${y}" y2="${y}"/>`;
      svg += `<text class="axis-label" x="0" y="${y+3}">${v}</text>`;
    }
    keys.forEach((k, i) => {
      const x = padL + step*i + step/2 - barW/2;
      let yCursor = padT + plotH;
      const total = CATS.reduce((s,c) => s + (buckets[k][c]||0), 0);
      CATS.forEach(cat => {
        const v = buckets[k][cat] || 0;
        if (!v) return;
        const h = (v/niceMax)*plotH;
        yCursor -= h;
        svg += `<rect class="bar-seg" x="${x}" y="${yCursor}" width="${barW}" height="${Math.max(h-1.5,0)}" rx="2" fill="${catColor(cat)}" data-bucket="${k}" data-cat="${cat}" data-v="${v}"/>`;
      });
      svg += `<text class="axis-label" x="${padL + step*i + step/2}" y="${H-4}" text-anchor="middle">${bucketLabel(k, state.bucket)}</text>`;
    });

    const svgEl = document.getElementById("trend-chart");
    svgEl.setAttribute("viewBox", `0 0 ${W} ${H}`);
    svgEl.innerHTML = svg;

    const tooltip = document.getElementById("tooltip");
    svgEl.querySelectorAll(".bar-seg").forEach(el => {
      el.addEventListener("mousemove", (e) => {
        const cat = el.getAttribute("data-cat"), k = el.getAttribute("data-bucket"), v = el.getAttribute("data-v");
        tooltip.innerHTML = `<b>${bucketLabel(k, state.bucket)} · ${cat}</b><div class="row"><span>기사 수</span><span class="num">${v}건</span></div>`;
        tooltip.style.left = (e.clientX + 14) + "px";
        tooltip.style.top = (e.clientY + 14) + "px";
        tooltip.classList.add("show");
      });
      el.addEventListener("mouseleave", () => tooltip.classList.remove("show"));
    });

    document.getElementById("trend-legend").innerHTML = CATS.map(c => `
      <span class="item"><span class="swatch" style="background:${catColor(c)}"></span>${c}</span>`).join("");
  }

  // ---------- category bars ----------
  function renderCatBars() {
    const counts = {};
    CATS.forEach(c => counts[c] = 0);
    ARTICLES.forEach(a => counts[a.category] = (counts[a.category]||0) + 1);
    const max = Math.max(1, ...Object.values(counts));
    document.getElementById("cat-bars").innerHTML = CATS.map(c => `
      <div class="cat-bar-row">
        <div class="name">${c}</div>
        <div class="cat-bar-track"><div class="cat-bar-fill" style="width:${(counts[c]/max*100).toFixed(1)}%; background:${catColor(c)}"></div></div>
        <div class="count num">${counts[c]}</div>
      </div>`).join("");
  }

  // ---------- filter chips ----------
  function renderChips() {
    document.getElementById("cat-chips").innerHTML = CATS.map(c => `
      <button class="chip" data-cat="${c}"><span class="dot" style="background:${catColor(c)}"></span>${c}</button>`).join("");
    document.querySelectorAll(".chip").forEach(btn => {
      btn.addEventListener("click", () => {
        const c = btn.getAttribute("data-cat");
        if (state.cats.has(c)) { state.cats.delete(c); btn.classList.remove("active"); }
        else { state.cats.add(c); btn.classList.add("active"); }
        renderList();
      });
    });
  }

  // ---------- article list ----------
  function renderList() {
    let items = ARTICLES.slice().sort((a,b) =>
      b.collected_at.localeCompare(a.collected_at) || b.date.localeCompare(a.date));
    if (state.region !== "all") items = items.filter(a => a.region === state.region);
    if (state.cats.size) items = items.filter(a => state.cats.has(a.category));
    if (state.query) {
      const q = state.query.toLowerCase();
      items = items.filter(a => a.title.toLowerCase().includes(q) || a.summary.toLowerCase().includes(q));
    }
    document.getElementById("count-line").textContent = `${items.length}건 표시 중 (전체 ${ARTICLES.length}건)`;
    document.getElementById("empty-state").style.display = items.length ? "none" : "block";
    document.getElementById("article-list").innerHTML = items.map(a => `
      <li class="article">
        <div class="bar" style="background:${catColor(a.category)}"></div>
        <div>
          <div class="title-row">
            <a class="title" href="${a.url}" target="_blank" rel="noopener">${escapeHtml(a.title)}</a>
          </div>
          <div class="summary">${escapeHtml(a.summary)}</div>
          <div class="meta">
            <span class="tag" style="color:${catColor(a.category)}">${a.category}</span>
            <span class="tag">${a.region}</span>
            ${a.date_estimated ? '<span class="tag estimated">추정</span>' : ''}
          </div>
        </div>
        <div class="right">
          <div class="date num">${a.date}</div>
          <div class="source">${escapeHtml(a.source)}</div>
          ${a.collected_at !== a.date ? `<div class="source">수집 ${a.collected_at}</div>` : ''}
        </div>
      </li>`).join("");
  }

  function escapeHtml(s) {
    return s.replace(/[&<>"']/g, ch => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[ch]));
  }

  // ---------- wiring ----------
  document.getElementById("bucket-seg").addEventListener("click", (e) => {
    const btn = e.target.closest("button"); if (!btn) return;
    document.querySelectorAll("#bucket-seg button").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    state.bucket = btn.getAttribute("data-bucket");
    renderTrend();
  });
  document.getElementById("region-seg").addEventListener("click", (e) => {
    const btn = e.target.closest("button"); if (!btn) return;
    document.querySelectorAll("#region-seg button").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    state.region = btn.getAttribute("data-region");
    renderList();
  });
  document.getElementById("search").addEventListener("input", (e) => {
    state.query = e.target.value.trim();
    renderList();
  });

  renderKPIs();
  renderTrend();
  renderCatBars();
  renderChips();
  renderList();
</script>
"""


def main():
    payload, articles = load_data()
    html = build_html(payload, articles)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(html, encoding="utf-8")
    print(f"생성 완료: {OUT_PATH} ({len(articles)}건)")


if __name__ == "__main__":
    main()
