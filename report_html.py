"""
דוח HTML אינטראקטיבי של התוצאות הסופיות: קובץ אחד עצמאי (CSS, JavaScript וגרפים ב-SVG מוטמעים), שנפתח בכל דפדפן
גם בלי אינטרנט. אין כאן תלות ב-Streamlit: collect_report_data אוסף את הנתונים למבנה JSON פשוט, ו-build_html_report
מטמיע אותו בתבנית.
"""
import ast
import datetime
import html
import json

from ism_core import compute_ism_levels, ism_cycle_members

SYMBOLS = ['V', 'A', 'X', 'O']
CLASS_KEYS = (('Driving', 'driving'), ('Linkage', 'linkage'), ('Dependent', 'dependent'), ('Autonomous', 'autonomous'))


def _class_key(label):
    for prefix, key in CLASS_KEYS:
        if str(label).startswith(prefix):
            return key
    return 'autonomous'


def _matrix(df):
    return None if df is None else [[str(v) for v in row] for row in df.values.tolist()]


def _parse_votes(text):
    try:
        votes = ast.literal_eval(text) if isinstance(text, str) else dict(text)
        return {str(k): int(v) for k, v in votes.items()}
    except (ValueError, SyntaxError, TypeError, AttributeError):
        return {}


def collect_report_data(factors, expert_data, results, ssim_init=None, ssim_final=None, ai_log=None,
                        justifications=None, topic="", question=""):
    """ממיר את מצב הניתוח למבנה JSON שהדוח צורך. results הוא המילון של build_analysis_results."""
    factors = list(factors)
    n = len(factors)
    irm, frm = results['irm'], results['frm']
    levels = compute_ism_levels(frm)
    cycles = ism_cycle_members(frm)

    experts = []
    for exp_id, info in expert_data.items():
        counts = dict.fromkeys(SYMBOLS, 0)
        for i in range(n):
            for j in range(i + 1, n):
                sym = info['responses'].get(factors[i], {}).get(factors[j], 'O')
                counts[sym if sym in counts else 'O'] += 1
        experts.append({'name': info.get('name', exp_id), 'role': info.get('role', ''),
                        'type': 'ai' if str(exp_id).startswith('Synth_') else 'human', 'counts': counts})

    def method(key, label, unit, note, threshold=None):
        df = results[key]
        thr_dp = float(threshold if threshold is not None else df['DP'].mean())
        thr_dep = float(threshold if threshold is not None else df['DEP'].mean())
        rows = [{'f': f, 'dp': float(df.loc[f, 'DP']), 'dep': float(df.loc[f, 'DEP']),
                 'cls': _class_key(df.loc[f, 'Classification'])} for f in df.index]
        return {'label': label, 'unit': unit, 'note': note, 'thr': [thr_dp, thr_dep], 'rows': rows}

    micmac = {
        'classic': method('micmac', 'קלאסי (סף ממוצע)', '',
                          'סכומי השורות והעמודות של ה-FRM. הסף לכל ציר הוא הממוצע בפועל.'),
        'classic_mid': method('micmac_midpoint', f'קלאסי (סף n/2 = {n / 2:g})', '',
                              'סכומי ה-FRM, עם סף באמצע הסולם כמקובל ברוב מאמרי ה-ISM.', threshold=n / 2),
        'godet': method('micmac_godet', f'עקיף, Godet (חזקה {results["godet_power"]})', '%',
                        'אחוז מסך ההשפעה במערכת, מחזקות מטריצת ההשפעה הישירה עד להתייצבות הדירוג.'),
        'katz': method('micmac_katz', f'עקיף מצטבר, Katz (α = {results["katz_alpha"]:.3g})', '%',
                       'אחוז מסך ההשפעה, מסכום כל המסלולים עם דעיכה. יציב גם כשיש מעגל השפעה קצר.'),
    }

    justifications = justifications or {}
    conflicts = []
    for entry in ai_log or []:
        pair = str(entry.get('זוג גורמים', ''))
        fi, _, fj = pair.partition(' ↔ ')
        conflicts.append({
            'pair': [fi, fj],
            'votes': _parse_votes(entry.get('הצבעות', '')),
            'decision': str(entry.get('הכרעת AI', '')),
            'rationale': str(entry.get('נימוק ה-AI', '')),
            'justs': [{'expert': str(j.get('expert', '')), 'symbol': str(j.get('symbol', '')), 'text': str(j.get('text', ''))}
                      for j in justifications.get((fi, fj), [])],
        })

    pairs = n * (n - 1) // 2
    related = 0
    if ssim_final is not None:
        related = sum(1 for i in range(n) for j in range(i + 1, n) if str(ssim_final.iloc[i, j]) in ('V', 'A', 'X'))

    return {
        'topic': topic or '',
        'question': question or '',
        'generated': datetime.datetime.now().strftime('%d/%m/%Y %H:%M'),
        'factors': factors,
        'experts': experts,
        'ssim_init': _matrix(ssim_init),
        'ssim_final': _matrix(ssim_final),
        'irm': [[int(v) for v in row] for row in irm.values.tolist()],
        'frm': [[int(v) for v in row] for row in frm.values.tolist()],
        'levels': [list(lvl) for lvl in levels],
        'cycles': sorted(cycles),
        'micmac': micmac,
        'default_method': 'katz' if results['classic_degenerate'] else 'classic',
        'conflicts': conflicts,
        'stats': {
            'saturation': float(results['saturation']),
            'degenerate': bool(results['classic_degenerate']),
            'pairs': pairs,
            'related': related,
        },
    }


def build_html_report(data):
    """מחזיר מחרוזת HTML מלאה. ה-JSON מוטמע כך ש-'</script>' בתוך טקסט חופשי לא יסגור את התגית."""
    payload = json.dumps(data, ensure_ascii=False).replace('</', '<\\/')
    title = html.escape(data.get('topic') or 'ניתוח ISM-MICMAC')
    return _TEMPLATE.replace('__TITLE__', title).replace('__DATA__', payload)


_TEMPLATE = r"""<!doctype html>
<html lang="he" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>דוח ISM-MICMAC: __TITLE__</title>
<style>
:root {
  color-scheme: light;
  --page: #f9f9f7; --surface: #fcfcfb; --surface-2: #f3f2ee; --ink: #0b0b0b; --ink-2: #52514e; --muted: #898781;
  --grid: #e1e0d9; --axis: #c3c2b7; --border: rgba(11,11,11,0.10); --shadow: 0 1px 2px rgba(11,11,11,.05), 0 4px 16px rgba(11,11,11,.04);
  --accent: #2a78d6; --accent-ink: #ffffff; --accent-soft: #e8f1fc;
  --c-driving: #2a78d6; --c-linkage: #eb6834; --c-dependent: #1baf7a; --c-autonomous: #a3a19b;
  --s-V: #2a78d6; --s-A: #eb6834; --s-X: #1baf7a; --s-O: #d6d4cc;
  --t-V: #e3eefb; --t-A: #fde9e0; --t-X: #dcf3ea; --t-O: transparent; --t-C: #fbe1e1;
  --seq-direct: #2a78d6; --seq-indirect: #b7d3f6; --diag: #ecebe6;
  --good: #0ca30c; --warning: #fab219; --critical: #d03b3b; --good-ink: #006300;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    color-scheme: dark;
    --page: #0d0d0d; --surface: #1a1a19; --surface-2: #232321; --ink: #f0efec; --ink-2: #c3c2b7; --muted: #898781;
    --grid: #2c2c2a; --axis: #383835; --border: rgba(255,255,255,0.10); --shadow: none;
    --accent: #3987e5; --accent-ink: #ffffff; --accent-soft: #1d2a3a;
    --c-driving: #3987e5; --c-linkage: #d95926; --c-dependent: #199e70; --c-autonomous: #6f6d68;
    --s-V: #3987e5; --s-A: #d95926; --s-X: #199e70; --s-O: #4a4945;
    --t-V: #1d2a3a; --t-A: #3a2219; --t-X: #15302a; --t-C: #3d1c1c;
    --seq-direct: #3987e5; --seq-indirect: #1c5cab; --diag: #262624; --good-ink: #0ca30c;
  }
}
:root[data-theme="dark"] {
  color-scheme: dark;
  --page: #0d0d0d; --surface: #1a1a19; --surface-2: #232321; --ink: #f0efec; --ink-2: #c3c2b7; --muted: #898781;
  --grid: #2c2c2a; --axis: #383835; --border: rgba(255,255,255,0.10); --shadow: none;
  --accent: #3987e5; --accent-ink: #ffffff; --accent-soft: #1d2a3a;
  --c-driving: #3987e5; --c-linkage: #d95926; --c-dependent: #199e70; --c-autonomous: #6f6d68;
  --s-V: #3987e5; --s-A: #d95926; --s-X: #199e70; --s-O: #4a4945;
  --t-V: #1d2a3a; --t-A: #3a2219; --t-X: #15302a; --t-C: #3d1c1c;
  --seq-direct: #3987e5; --seq-indirect: #1c5cab; --diag: #262624; --good-ink: #0ca30c;
}
* { box-sizing: border-box; }
html, body { margin: 0; }
body { background: var(--page); color: var(--ink); font: 15px/1.55 system-ui, -apple-system, "Segoe UI", Arial, sans-serif; }
.wrap { max-width: 1180px; margin: 0 auto; padding: 0 16px 48px; }
header.top { padding: 28px 0 8px; display: flex; gap: 16px; align-items: flex-start; justify-content: space-between; flex-wrap: wrap; }
.eyebrow { font-size: 12px; letter-spacing: .08em; color: var(--muted); font-weight: 600; direction: ltr; text-align: right; }
h1 { font-size: 26px; line-height: 1.25; margin: 4px 0 6px; font-weight: 700; }
.sub { color: var(--ink-2); margin: 0; max-width: 760px; }
.tools { display: flex; gap: 8px; }
button.ghost { font: inherit; font-size: 13px; color: var(--ink-2); background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 7px 12px; cursor: pointer; }
button.ghost:hover { color: var(--ink); background: var(--surface-2); }
nav.tabs { position: sticky; top: 0; z-index: 5; background: var(--page); display: flex; gap: 4px; overflow-x: auto; border-bottom: 1px solid var(--grid); margin: 16px 0 24px; scrollbar-width: none; }
nav.tabs button { font: inherit; font-weight: 600; font-size: 14px; color: var(--ink-2); background: none; border: 0; border-bottom: 2px solid transparent; padding: 12px 14px 10px; cursor: pointer; white-space: nowrap; }
nav.tabs button:hover { color: var(--ink); }
nav.tabs button[aria-selected="true"] { color: var(--ink); border-bottom-color: var(--accent); }
nav.tabs .count { font-weight: 500; color: var(--muted); font-size: 12px; margin-inline-start: 4px; }
section.panel { display: none; }
section.panel.active { display: block; animation: fade .18s ease; }
@keyframes fade { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: none; } }
h2 { font-size: 19px; margin: 0 0 4px; }
h3 { font-size: 15px; margin: 0 0 10px; }
.lead { color: var(--ink-2); margin: 0 0 18px; }
.card { background: var(--surface); border: 1px solid var(--border); border-radius: 14px; padding: 20px; box-shadow: var(--shadow); }
.grid { display: grid; gap: 16px; }
.g-tiles { grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); }
.g-2 { grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); }
.tile .k { color: var(--ink-2); font-size: 13px; }
.tile .v { font-size: 30px; font-weight: 700; line-height: 1.15; margin-top: 4px; }
.tile .h { color: var(--muted); font-size: 12px; margin-top: 2px; }
.stack { display: flex; flex-direction: column; gap: 16px; }
.chips { display: flex; flex-wrap: wrap; gap: 8px; }
.chip { display: inline-flex; align-items: center; gap: 6px; border: 1px solid var(--border); background: var(--surface-2); border-radius: 999px; padding: 4px 11px; font-size: 13.5px; }
.dot { width: 9px; height: 9px; border-radius: 50%; flex: none; }
.note { display: flex; gap: 10px; align-items: flex-start; border-radius: 10px; padding: 12px 14px; background: var(--surface-2); color: var(--ink-2); font-size: 14px; }
.note b { color: var(--ink); }
.note .ic { font-weight: 700; flex: none; width: 22px; height: 22px; border-radius: 50%; display: grid; place-items: center; font-size: 13px; color: #0b0b0b; }
.note.warn .ic { background: var(--warning); }
.note.info .ic { background: var(--accent); color: #fff; }
.quad { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; direction: ltr; }
.quad div { border-radius: 10px; padding: 12px; background: var(--surface-2); direction: rtl; }
.quad .n { font-size: 24px; font-weight: 700; }
.quad .l { font-size: 13px; color: var(--ink-2); display: flex; align-items: center; gap: 6px; }
.seg { display: inline-flex; flex-wrap: wrap; background: var(--surface-2); border-radius: 10px; padding: 3px; gap: 2px; margin-bottom: 14px; }
.seg button { font: inherit; font-size: 13px; color: var(--ink-2); background: none; border: 0; border-radius: 8px; padding: 6px 12px; cursor: pointer; }
.seg button[aria-pressed="true"] { background: var(--surface); color: var(--ink); font-weight: 600; box-shadow: 0 0 0 1px var(--border); }
.legend { display: flex; flex-wrap: wrap; gap: 14px; font-size: 13px; color: var(--ink-2); margin: 0 0 10px; }
.legend span { display: inline-flex; align-items: center; gap: 6px; }
.sw { width: 12px; height: 12px; border-radius: 3px; display: inline-block; }
svg text { fill: var(--ink-2); font-family: inherit; }
.chart-wrap { width: 100%; }
.chart-wrap svg { width: 100%; height: auto; display: block; }
.pt { cursor: pointer; }
.pt .mk { stroke: var(--surface); stroke-width: 2; }
.pt.dim { opacity: .18; }
.pt text { font-size: 12px; fill: var(--ink); paint-order: stroke; stroke: var(--surface); stroke-width: 3px; stroke-linejoin: round; }
table.data { width: 100%; border-collapse: collapse; font-size: 14px; }
table.data th { text-align: right; font-weight: 600; color: var(--ink-2); font-size: 12.5px; padding: 8px 10px; border-bottom: 1px solid var(--axis); cursor: pointer; white-space: nowrap; user-select: none; }
table.data th[data-sort]::after { content: " ↕"; color: var(--muted); font-weight: 400; }
table.data td { padding: 8px 10px; border-bottom: 1px solid var(--grid); }
table.data td.num { font-variant-numeric: tabular-nums; direction: ltr; text-align: right; }
table.data tr:hover td { background: var(--surface-2); }
.badge { display: inline-flex; align-items: center; gap: 6px; font-size: 12.5px; font-weight: 600; padding: 2px 9px; border-radius: 999px; background: var(--surface-2); color: var(--ink); white-space: nowrap; }
.scroll { overflow-x: auto; }
/* hierarchy */
.hier { position: relative; }
.hier svg.edges { position: absolute; inset: 0; width: 100%; height: 100%; pointer-events: none; overflow: visible; }
.hier svg.edges path { fill: none; stroke: var(--axis); stroke-width: 1.5; transition: opacity .15s, stroke .15s; }
.hier svg.edges path.on { stroke: var(--accent); stroke-width: 2; }
.hier svg.edges path.off { opacity: .1; }
.lvl { position: relative; display: grid; grid-template-columns: 92px 1fr; align-items: center; gap: 12px; padding: 22px 0; border-bottom: 1px dashed var(--grid); }
.lvl:last-child { border-bottom: 0; }
.lvl .lab { font-size: 12.5px; color: var(--muted); font-weight: 600; }
.lvl .lab b { display: block; font-size: 15px; color: var(--ink-2); }
.lvl .row { display: flex; flex-wrap: wrap; justify-content: center; gap: 14px 18px; }
.node { position: relative; z-index: 1; background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 9px 14px; font-size: 14px; font-weight: 600; display: inline-flex; align-items: center; gap: 8px; cursor: pointer; transition: opacity .15s, box-shadow .15s; box-shadow: var(--shadow); }
.node:hover, .node.focus { box-shadow: 0 0 0 2px var(--accent); }
.node.dim { opacity: .3; }
.node .cyc { font-size: 11px; font-weight: 600; color: var(--ink-2); background: var(--surface-2); border-radius: 999px; padding: 1px 7px; }
.side { font-size: 14px; }
.side .empty { color: var(--muted); }
/* matrices */
table.mx { border-collapse: separate; border-spacing: 2px; font-size: 13px; margin: 0 auto; }
table.mx th { font-weight: 600; color: var(--ink-2); font-size: 12px; padding: 4px 6px; white-space: nowrap; }
table.mx th.rh { text-align: right; position: sticky; right: 0; background: var(--surface); z-index: 1; }
table.mx td { width: 34px; min-width: 34px; height: 30px; text-align: center; border-radius: 5px; font-weight: 600; font-variant-numeric: tabular-nums; cursor: default; }
table.mx td.sum { background: none; color: var(--ink-2); font-weight: 600; }
table.mx td.diag { background: var(--diag); color: var(--muted); }
table.mx td.hl, table.mx th.hl { outline: 2px solid var(--accent); outline-offset: -1px; }
table.mx td.x { outline: 2px solid var(--ink); outline-offset: -1px; }
/* bars */
.bar { display: flex; height: 12px; border-radius: 4px; overflow: hidden; gap: 2px; min-width: 160px; }
.bar i { display: block; height: 100%; }
.conf { display: grid; gap: 10px; }
.conf .pair { font-weight: 700; font-size: 15px; }
.conf .arrow { color: var(--muted); padding: 0 6px; }
.conf .dec { display: inline-flex; align-items: center; gap: 8px; }
.sym { display: inline-grid; place-items: center; width: 26px; height: 26px; border-radius: 7px; font-weight: 700; font-size: 13px; color: #fff; }
.sym.O { color: var(--ink); }
details { font-size: 14px; color: var(--ink-2); }
details summary { cursor: pointer; color: var(--accent); font-weight: 600; }
details ul { margin: 8px 0 0; padding-inline-start: 20px; }
.tip { position: fixed; z-index: 50; pointer-events: none; background: var(--surface); color: var(--ink); border: 1px solid var(--border); border-radius: 10px; padding: 9px 12px; font-size: 13px; box-shadow: 0 8px 24px rgba(0,0,0,.14); max-width: 280px; opacity: 0; transition: opacity .1s; }
.tip.show { opacity: 1; }
.tip .t { font-weight: 700; margin-bottom: 3px; }
.tip .r { display: flex; justify-content: space-between; gap: 14px; color: var(--ink-2); }
.tip .r b { color: var(--ink); font-variant-numeric: tabular-nums; }
footer { margin-top: 40px; color: var(--muted); font-size: 12.5px; text-align: center; }
.empty-state { text-align: center; color: var(--ink-2); padding: 40px 16px; }
.empty-state .big { font-size: 34px; color: var(--good); }
@media (max-width: 640px) {
  h1 { font-size: 21px; }
  .lvl { grid-template-columns: 1fr; gap: 8px; padding: 16px 0; }
  .tile .v { font-size: 24px; }
}
@media print {
  nav.tabs, .tools, .seg { display: none !important; }
  section.panel { display: block !important; break-before: page; }
  section.panel:first-of-type { break-before: auto; }
  .card { box-shadow: none; break-inside: avoid; }
  body { background: #fff; }
}
@media (forced-colors: active) { .pt .mk, .sw, .bar i, .dot { forced-color-adjust: none; } }
</style>
</head>
<body>
<div class="wrap">
  <header class="top">
    <div>
      <div class="eyebrow">ISM-MICMAC REPORT</div>
      <h1 id="title"></h1>
      <p class="sub" id="subtitle"></p>
    </div>
    <div class="tools">
      <button class="ghost" id="themeBtn" type="button" aria-label="החלפת ערכת צבעים"></button>
      <button class="ghost" type="button" onclick="window.print()">הדפסה / PDF</button>
    </div>
  </header>
  <nav class="tabs" role="tablist" id="tabs"></nav>
  <main id="panels"></main>
  <footer id="foot"></footer>
</div>
<div class="tip" id="tip" role="tooltip"></div>
<script id="report-data" type="application/json">__DATA__</script>
<script>
(function () {
  "use strict";
  var D = JSON.parse(document.getElementById("report-data").textContent);
  var F = D.factors, N = F.length;
  var CLS = {
    driving: { he: "מניע", en: "Driving", desc: "השפעה גבוהה, תלות נמוכה" },
    linkage: { he: "קישור", en: "Linkage", desc: "השפעה ותלות גבוהות" },
    dependent: { he: "תלוי", en: "Dependent", desc: "השפעה נמוכה, תלות גבוהה" },
    autonomous: { he: "אוטונומי", en: "Autonomous", desc: "השפעה ותלות נמוכות" }
  };
  var SYM = { V: "משפיע על", A: "מושפע מ", X: "השפעה הדדית", O: "אין קשר ישיר", C: "קונפליקט" };
  var levelOf = {};
  D.levels.forEach(function (lvl, i) { lvl.forEach(function (f) { levelOf[f] = i + 1; }); });
  var inCycle = {};
  D.cycles.forEach(function (f) { inCycle[f] = true; });
  var method = D.default_method;

  function el(tag, attrs, kids) {
    var e = document.createElement(tag);
    if (attrs) Object.keys(attrs).forEach(function (k) {
      if (k === "text") e.textContent = attrs[k];
      else if (k === "html") e.innerHTML = attrs[k];
      else if (k === "class") e.className = attrs[k];
      else e.setAttribute(k, attrs[k]);
    });
    (kids || []).forEach(function (c) { if (c != null) e.appendChild(typeof c === "string" ? document.createTextNode(c) : c); });
    return e;
  }
  var SVGNS = "http://www.w3.org/2000/svg";
  function sv(tag, attrs, kids) {
    var e = document.createElementNS(SVGNS, tag);
    Object.keys(attrs || {}).forEach(function (k) { if (k === "text") e.textContent = attrs[k]; else e.setAttribute(k, attrs[k]); });
    (kids || []).forEach(function (c) { if (c) e.appendChild(c); });
    return e;
  }
  function fmt(v, unit) { var s = Math.abs(v - Math.round(v)) < 1e-9 ? String(Math.round(v)) : v.toFixed(1); return s + (unit || ""); }
  function pct(a, b) { return b ? Math.round(a / b * 100) : 0; }
  function cvar(name) { return "var(--" + name + ")"; }
  function dotEl(color) { var d = el("span", { class: "dot" }); d.style.background = color; return d; }
  function rows() { return D.micmac[method].rows; }
  function rowOf(f) { var r = rows(); for (var i = 0; i < r.length; i++) if (r[i].f === f) return r[i]; return null; }

  /* ---------- tooltip ---------- */
  var tip = document.getElementById("tip");
  function showTip(evt, title, pairs) {
    tip.innerHTML = "";
    tip.appendChild(el("div", { class: "t", text: title }));
    pairs.forEach(function (p) { tip.appendChild(el("div", { class: "r" }, [el("span", { text: p[0] }), el("b", { text: p[1] })])); });
    tip.classList.add("show");
    moveTip(evt);
  }
  function moveTip(evt) {
    var w = tip.offsetWidth, h = tip.offsetHeight, x = evt.clientX - w - 14, y = evt.clientY + 14;
    if (x < 8) x = evt.clientX + 14;
    if (x + w > window.innerWidth - 8) x = window.innerWidth - w - 8;
    if (y + h > window.innerHeight - 8) y = evt.clientY - h - 14;
    tip.style.left = x + "px"; tip.style.top = y + "px";
  }
  function hideTip() { tip.classList.remove("show"); }

  /* ---------- theme ---------- */
  var themeBtn = document.getElementById("themeBtn");
  var themes = ["auto", "light", "dark"], themeNames = { auto: "ערכה: אוטומטית", light: "ערכה: בהירה", dark: "ערכה: כהה" };
  function applyTheme(t) {
    if (t === "auto") document.documentElement.removeAttribute("data-theme");
    else document.documentElement.setAttribute("data-theme", t);
    themeBtn.textContent = themeNames[t];
    try { localStorage.setItem("ism-theme", t); } catch (e) {}
  }
  var savedTheme = "auto";
  try { savedTheme = localStorage.getItem("ism-theme") || "auto"; } catch (e) {}
  applyTheme(themes.indexOf(savedTheme) >= 0 ? savedTheme : "auto");
  themeBtn.addEventListener("click", function () {
    var cur = document.documentElement.getAttribute("data-theme") || "auto";
    applyTheme(themes[(themes.indexOf(cur) + 1) % 3]);
  });

  /* ---------- header ---------- */
  document.getElementById("title").textContent = D.topic || "ניתוח ISM-MICMAC";
  var nH = D.experts.filter(function (e) { return e.type === "human"; }).length, nA = D.experts.length - nH;
  document.getElementById("subtitle").textContent = N + " גורמים · " + D.experts.length + " משיבים (" + nH + " מומחים, " + nA + " סוכני AI) · הופק " + D.generated;
  document.getElementById("foot").textContent = "הדוח הופק במערכת ISM-MICMAC Pro · " + D.generated + " · קובץ עצמאי שעובד גם בלי חיבור לאינטרנט";

  /* ---------- tabs ---------- */
  var TABS = [
    ["summary", "סיכום"], ["hierarchy", "היררכיה"], ["micmac", "MICMAC"],
    ["matrices", "מטריצות"], ["conflicts", "קונפליקטים", D.conflicts.length], ["experts", "משיבים", D.experts.length]
  ];
  var nav = document.getElementById("tabs"), panels = document.getElementById("panels"), renderers = {}, rendered = {};
  TABS.forEach(function (t, i) {
    var b = el("button", { role: "tab", id: "tab-" + t[0], "aria-controls": "p-" + t[0], "aria-selected": i === 0 ? "true" : "false", type: "button" }, [t[1]]);
    if (t[2] != null) b.appendChild(el("span", { class: "count", text: "(" + t[2] + ")" }));
    b.addEventListener("click", function () { activate(t[0]); });
    nav.appendChild(b);
    panels.appendChild(el("section", { class: "panel" + (i === 0 ? " active" : ""), id: "p-" + t[0], role: "tabpanel", "aria-labelledby": "tab-" + t[0] }));
  });
  function activate(id) {
    TABS.forEach(function (t) {
      document.getElementById("tab-" + t[0]).setAttribute("aria-selected", t[0] === id ? "true" : "false");
      document.getElementById("p-" + t[0]).classList.toggle("active", t[0] === id);
    });
    if (!rendered[id]) { renderers[id](document.getElementById("p-" + id)); rendered[id] = true; }
    if (id === "hierarchy") drawEdges();
    try { history.replaceState(null, "", "#" + id); } catch (e) {}
  }
  nav.addEventListener("keydown", function (e) {
    if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
    var ids = TABS.map(function (t) { return t[0]; });
    var cur = ids.indexOf(document.querySelector('nav.tabs [aria-selected="true"]').id.slice(4));
    var next = ids[(cur + (e.key === "ArrowLeft" ? 1 : -1) + ids.length) % ids.length];
    activate(next); document.getElementById("tab-" + next).focus();
  });

  function head(p, title, lead) { p.appendChild(el("h2", { text: title })); if (lead) p.appendChild(el("p", { class: "lead", text: lead })); }
  function clsBadge(c) { return el("span", { class: "badge" }, [dotEl(cvar("c-" + c)), CLS[c].he + " · " + CLS[c].en]); }

  /* ---------- summary ---------- */
  renderers.summary = function (p) {
    var m = D.micmac[method], counts = { driving: 0, linkage: 0, dependent: 0, autonomous: 0 };
    m.rows.forEach(function (r) { counts[r.cls]++; });
    head(p, "תמונת מצב", "הממצאים המרכזיים של הניתוח. הסיווג לפי שיטת MICMAC: " + m.label + ".");
    var tiles = el("div", { class: "grid g-tiles" });
    [["גורמים", N, "בניתוח"], ["משיבים", D.experts.length, nH + " מומחים · " + nA + " סוכני AI"],
     ["רמות היררכיה", D.levels.length, "מ-ISM Level Partitioning"],
     ["קונפליקטים", D.conflicts.length, D.conflicts.length ? "הוכרעו על ידי AI" : "לא נדרשה הכרעה"],
     ["צפיפות קשרים", pct(D.stats.related, D.stats.pairs) + "%", D.stats.related + " מתוך " + D.stats.pairs + " זוגות"],
     ["רוויית FRM", Math.round(D.stats.saturation * 100) + "%", "תאים מחוץ לאלכסון שערכם 1"]
    ].forEach(function (t) {
      tiles.appendChild(el("div", { class: "card tile" }, [el("div", { class: "k", text: t[0] }), el("div", { class: "v", text: String(t[1]) }), el("div", { class: "h", text: t[2] })]));
    });
    p.appendChild(tiles);
    var st = el("div", { class: "stack", style: "margin-top:16px" });
    if (D.stats.degenerate) st.appendChild(el("div", { class: "note warn" }, [el("span", { class: "ic", text: "!" }), el("div", { html: "<b>מטריצת הנגישות רוויה.</b> כשמעגל השפעה עובר דרך רוב הגורמים, הסיווג הקלאסי לפי סכומי ה-FRM לא מבחין בין הגורמים. לכן הדוח מציג כברירת מחדל את MICMAC העקיף המצטבר (Katz)." })]));
    if (D.levels.length === 1 && N > 1) st.appendChild(el("div", { class: "note warn" }, [el("span", { class: "ic", text: "!" }), el("div", { html: "<b>כל הגורמים ברמה אחת.</b> כולם מגיעים זה לזה דרך מעגלי השפעה, ולכן אין היררכיה." })]));
    var g2 = el("div", { class: "grid g-2" });
    var drivers = m.rows.filter(function (r) { return r.cls === "driving"; }).sort(function (a, b) { return b.dp - a.dp; });
    var c1 = el("div", { class: "card" }, [el("h3", { text: "גורמי המפתח המניעים" }),
      el("p", { class: "lead", style: "margin-bottom:12px", text: "השקעה בגורמים אלה צפויה להשפיע על המערכת כולה." })]);
    var ch = el("div", { class: "chips" });
    (drivers.length ? drivers : []).forEach(function (r) { ch.appendChild(el("span", { class: "chip" }, [dotEl(cvar("c-driving")), r.f])); });
    if (!drivers.length) ch.appendChild(el("span", { class: "side empty", text: "אין גורמים ברביע המניע בשיטה זו." }));
    c1.appendChild(ch);
    var c2 = el("div", { class: "card" }, [el("h3", { text: "התפלגות הגורמים ברביעי MICMAC" })]);
    var q = el("div", { class: "quad" });
    ["driving", "linkage", "autonomous", "dependent"].forEach(function (k) {
      q.appendChild(el("div", null, [el("div", { class: "l" }, [dotEl(cvar("c-" + k)), CLS[k].he + " (" + CLS[k].en + ")"]), el("div", { class: "n", text: String(counts[k]) })]));
    });
    c2.appendChild(q);
    c2.appendChild(el("p", { class: "h", style: "color:var(--muted);font-size:12px;margin:8px 0 0", text: "מעלה: השפעה גבוהה · ימין בתרשים: תלות גבוהה" }));
    var top = D.levels[0] || [], base = D.levels[D.levels.length - 1] || [];
    var c3 = el("div", { class: "card" }, [el("h3", { text: "ראש ההיררכיה ובסיסה" })]);
    function chipRow(label, list) {
      var r = el("div", { style: "margin-bottom:12px" }, [el("div", { class: "k", style: "color:var(--ink-2);font-size:13px;margin-bottom:6px", text: label })]);
      var cc = el("div", { class: "chips" }); list.forEach(function (f) { cc.appendChild(el("span", { class: "chip", text: f })); }); r.appendChild(cc); return r;
    }
    c3.appendChild(chipRow("רמה 1, התוצאות (התלויות ביותר)", top));
    if (D.levels.length > 1) c3.appendChild(chipRow("רמה " + D.levels.length + ", השורשים (המניעים ביותר)", base));
    var c4 = el("div", { class: "card" }, [el("h3", { text: "שאלת הסקר" }), el("p", { class: "lead", style: "margin:0", text: D.question || "לא הוגדרה" })]);
    if (D.cycles.length) c4.appendChild(el("p", { class: "lead", style: "margin:12px 0 0", text: "גורמים במעגל השפעה הדדי: " + D.cycles.join(", ") + "." }));
    [c1, c2, c3, c4].forEach(function (c) { g2.appendChild(c); });
    st.appendChild(g2);
    p.appendChild(st);
  };

  /* ---------- hierarchy ---------- */
  var hierBox = null, edgeSvg = null, nodeEls = {}, sideBox = null;
  renderers.hierarchy = function (p) {
    head(p, "מבנה היררכי (ISM)", "רמה 1 למעלה היא התוצאה התלויה ביותר; הרמה התחתונה היא שורש המערכת. החיצים מראים השפעה ישירה מגורם ברמה נמוכה לגורם ברמה גבוהה יותר. העבר את העכבר על גורם, או הקש עליו, כדי לראות את קשריו.");
    var legend = el("div", { class: "legend" });
    Object.keys(CLS).forEach(function (k) { legend.appendChild(el("span", null, [dotEl(cvar("c-" + k)), CLS[k].he])); });
    legend.appendChild(el("span", { text: "↻ = מעגל השפעה הדדי" }));
    p.appendChild(legend);
    var g = el("div", { class: "grid", style: "grid-template-columns:minmax(0,1fr)" });
    var card = el("div", { class: "card" });
    hierBox = el("div", { class: "hier" });
    edgeSvg = sv("svg", { class: "edges", "aria-hidden": "true" });
    hierBox.appendChild(edgeSvg);
    D.levels.forEach(function (lvl, i) {
      var row = el("div", { class: "row" });
      lvl.forEach(function (f) {
        var r = rowOf(f), n = el("div", { class: "node", tabindex: "0", role: "button", "aria-label": f });
        n.appendChild(dotEl(cvar("c-" + (r ? r.cls : "autonomous"))));
        n.appendChild(document.createTextNode(f));
        if (inCycle[f]) n.appendChild(el("span", { class: "cyc", text: "↻" }));
        n.addEventListener("mouseenter", function () { focusNode(f); });
        n.addEventListener("mouseleave", function () { focusNode(null); });
        n.addEventListener("focus", function () { focusNode(f); });
        n.addEventListener("blur", function () { focusNode(null); });
        n.addEventListener("click", function () { focusNode(f, true); });
        nodeEls[f] = n; row.appendChild(n);
      });
      var label = i === 0 ? "התוצאות" : (i === D.levels.length - 1 ? "השורשים" : "");
      hierBox.appendChild(el("div", { class: "lvl" }, [el("div", { class: "lab" }, [el("b", { text: "רמה " + (i + 1) }), label]), row]));
    });
    card.appendChild(hierBox);
    sideBox = el("div", { class: "card side" }, [el("span", { class: "empty", text: "בחר גורם כדי לראות על מי הוא משפיע ומי משפיע עליו." })]);
    g.appendChild(card); g.appendChild(sideBox);
    p.appendChild(g);
    if (window.ResizeObserver) new ResizeObserver(function () { drawEdges(); }).observe(hierBox);
  };
  var edgeList = [];
  function drawEdges() {
    if (!hierBox || !hierBox.offsetParent) return;
    while (edgeSvg.firstChild) edgeSvg.removeChild(edgeSvg.firstChild);
    var defs = sv("defs", {}, [sv("marker", { id: "ah", viewBox: "0 0 10 10", refX: "9", refY: "5", markerWidth: "7", markerHeight: "7", orient: "auto-start-reverse" }, [sv("path", { d: "M0,0 L10,5 L0,10 z", style: "fill:var(--axis);stroke:none" })]),
      sv("marker", { id: "ahOn", viewBox: "0 0 10 10", refX: "9", refY: "5", markerWidth: "7", markerHeight: "7", orient: "auto-start-reverse" }, [sv("path", { d: "M0,0 L10,5 L0,10 z", style: "fill:var(--accent);stroke:none" })])]);
    edgeSvg.appendChild(defs);
    var box = hierBox.getBoundingClientRect();
    edgeList = [];
    for (var i = 0; i < N; i++) for (var j = 0; j < N; j++) {
      if (i === j || !D.irm[i][j]) continue;
      var a = F[i], b = F[j];
      if (!(levelOf[b] < levelOf[a])) continue;
      var ra = nodeEls[a].getBoundingClientRect(), rb = nodeEls[b].getBoundingClientRect();
      var x1 = ra.left + ra.width / 2 - box.left, y1 = ra.top - box.top, x2 = rb.left + rb.width / 2 - box.left, y2 = rb.bottom - box.top + 2;
      var my = (y1 + y2) / 2;
      var path = sv("path", { d: "M" + x1 + "," + y1 + " C" + x1 + "," + my + " " + x2 + "," + my + " " + x2 + "," + y2, "marker-end": "url(#ah)" });
      edgeSvg.appendChild(path);
      edgeList.push({ a: a, b: b, el: path });
    }
  }
  var pinned = null;
  function focusNode(f, toggle) {
    if (toggle) { pinned = pinned === f ? null : f; f = pinned; }
    else if (f === null) f = pinned;
    var out = [], inn = [];
    if (f) {
      var i = F.indexOf(f);
      for (var j = 0; j < N; j++) { if (j !== i && D.irm[i][j]) out.push(F[j]); if (j !== i && D.irm[j][i]) inn.push(F[j]); }
    }
    Object.keys(nodeEls).forEach(function (k) {
      nodeEls[k].classList.toggle("focus", k === f);
      nodeEls[k].classList.toggle("dim", !!f && k !== f && out.indexOf(k) < 0 && inn.indexOf(k) < 0);
    });
    edgeList.forEach(function (e) {
      var on = !!f && (e.a === f || e.b === f);
      e.el.classList.toggle("on", on); e.el.classList.toggle("off", !!f && !on);
      e.el.setAttribute("marker-end", on ? "url(#ahOn)" : "url(#ah)");
    });
    sideBox.innerHTML = "";
    if (!f) { sideBox.appendChild(el("span", { class: "empty", text: "בחר גורם כדי לראות על מי הוא משפיע ומי משפיע עליו." })); return; }
    var r = rowOf(f), m = D.micmac[method];
    sideBox.appendChild(el("h3", { text: f }));
    sideBox.appendChild(el("div", { class: "chips", style: "margin-bottom:12px" }, [el("span", { class: "badge", text: "רמה " + levelOf[f] }), r ? clsBadge(r.cls) : null,
      r ? el("span", { class: "badge", text: "DP " + fmt(r.dp, m.unit) + " · DEP " + fmt(r.dep, m.unit) }) : null, inCycle[f] ? el("span", { class: "badge", text: "↻ במעגל הדדי" }) : null]));
    function list(label, arr) {
      var d = el("div", { style: "margin-bottom:10px" }, [el("div", { style: "color:var(--ink-2);font-size:13px;margin-bottom:6px", text: label + " (" + arr.length + ")" })]);
      var c = el("div", { class: "chips" });
      if (!arr.length) c.appendChild(el("span", { class: "empty", text: "אין" }));
      arr.forEach(function (x) { c.appendChild(el("span", { class: "chip", text: x })); });
      d.appendChild(c); return d;
    }
    sideBox.appendChild(list("משפיע ישירות על", out));
    sideBox.appendChild(list("מושפע ישירות מ", inn));
  }

  /* ---------- MICMAC ---------- */
  var mxChart, mxTable, mxNote;
  renderers.micmac = function (p) {
    head(p, "מפת MICMAC", "כל גורם ממוקם לפי כוח התלות שלו (ציר אופקי) וכוח ההשפעה שלו (ציר אנכי). הקווים המקווקווים הם ספי הסיווג. אפשר להחליף שיטת חישוב.");
    var seg = el("div", { class: "seg", role: "group", "aria-label": "שיטת MICMAC" });
    Object.keys(D.micmac).forEach(function (k) {
      var b = el("button", { type: "button", "aria-pressed": k === method ? "true" : "false", text: D.micmac[k].label });
      b.addEventListener("click", function () {
        method = k;
        Array.prototype.forEach.call(seg.children, function (c) { c.setAttribute("aria-pressed", c === b ? "true" : "false"); });
        drawMicmac();
        rendered.summary = false; rendered.hierarchy = false;
        var sp = document.getElementById("p-summary"); sp.innerHTML = "";
        var hp = document.getElementById("p-hierarchy"); hp.innerHTML = ""; nodeEls = {}; hierBox = null; pinned = null;
      });
      seg.appendChild(b);
    });
    p.appendChild(seg);
    mxNote = el("div", { class: "note info", style: "margin-bottom:14px" });
    p.appendChild(mxNote);
    var legend = el("div", { class: "legend" });
    var shapes = { driving: "●", linkage: "◆", dependent: "■", autonomous: "▲" };
    Object.keys(CLS).forEach(function (k) {
      var s = el("span", null, [el("span", { text: shapes[k], style: "color:" + cvar("c-" + k) + ";font-size:14px" }), CLS[k].he + " · " + CLS[k].desc]);
      legend.appendChild(s);
    });
    var card = el("div", { class: "card" }, [legend]);
    mxChart = el("div", { class: "chart-wrap" });
    card.appendChild(mxChart);
    p.appendChild(card);
    var tcard = el("div", { class: "card", style: "margin-top:16px" }, [el("h3", { text: "טבלת הסיווג" })]);
    mxTable = el("div", { class: "scroll" });
    tcard.appendChild(mxTable);
    p.appendChild(tcard);
    drawMicmac();
    var lastW = mxChart.clientWidth;
    if (window.ResizeObserver) new ResizeObserver(function () { if (Math.abs(mxChart.clientWidth - lastW) > 40) { lastW = mxChart.clientWidth; drawMicmac(); } }).observe(mxChart);
  };
  function shapePath(cls, x, y, r) {
    if (cls === "linkage") return sv("path", { d: "M" + x + "," + (y - r - 1.5) + " L" + (x + r + 1.5) + "," + y + " L" + x + "," + (y + r + 1.5) + " L" + (x - r - 1.5) + "," + y + " z" });
    if (cls === "dependent") return sv("rect", { x: x - r + 0.5, y: y - r + 0.5, width: 2 * r - 1, height: 2 * r - 1, rx: 2 });
    if (cls === "autonomous") return sv("path", { d: "M" + x + "," + (y - r - 1) + " L" + (x + r + 1) + "," + (y + r) + " L" + (x - r - 1) + "," + (y + r) + " z" });
    return sv("circle", { cx: x, cy: y, r: r });
  }
  function niceStep(v) { if (v <= 0) return 1; var p = Math.pow(10, Math.floor(Math.log10(v))), m = v / p; return (m <= 1 ? 1 : m <= 2 ? 2 : m <= 2.5 ? 2.5 : m <= 5 ? 5 : 10) * p; }
  function axis(maxVal, integer) {
    var step = niceStep(maxVal / 5);
    if (integer) step = Math.max(1, Math.round(step));
    return { step: step, max: Math.max(step, Math.ceil(maxVal / step - 1e-9) * step) };
  }
  function drawMicmac() {
    var m = D.micmac[method], R = m.rows;
    mxNote.innerHTML = "";
    mxNote.appendChild(el("span", { class: "ic", text: "i" }));
    mxNote.appendChild(el("div", { text: m.note }));
    var cw = mxChart.clientWidth || 760, W = Math.max(340, Math.min(760, cw)), H = W < 560 ? Math.round(W * 1.1) : 520, L = 52, Rm = 16, T = 20, B = 52;
    var integer = !m.unit;
    // classic DP/DEP are counts of reachable factors, so the scale runs to n; Godet and Katz are shares of the total
    var ax = axis(integer ? N : Math.max.apply(null, R.map(function (r) { return r.dep; }).concat([m.thr[1]])) * 1.08, integer);
    var ay = axis(integer ? N : Math.max.apply(null, R.map(function (r) { return r.dp; }).concat([m.thr[0]])) * 1.08, integer);
    var maxX = ax.max, maxY = ay.max;
    function X(v) { return L + v / maxX * (W - L - Rm); }
    function Y(v) { return H - B - v / maxY * (H - T - B); }
    var s = sv("svg", { viewBox: "0 0 " + W + " " + H, role: "img", "aria-label": "מפת MICMAC: כוח השפעה מול כוח תלות" });
    s.setAttribute("direction", "ltr");
    var tx = X(m.thr[1]), ty = Y(m.thr[0]);
    [["driving", L, T, tx - L, ty - T, "start", L + 10, T + 18], ["linkage", tx, T, W - Rm - tx, ty - T, "end", W - Rm - 10, T + 18],
     ["autonomous", L, ty, tx - L, H - B - ty, "start", L + 10, H - B - 10], ["dependent", tx, ty, W - Rm - tx, H - B - ty, "end", W - Rm - 10, H - B - 10]
    ].forEach(function (q) {
      s.appendChild(sv("rect", { x: q[1], y: q[2], width: Math.max(0, q[3]), height: Math.max(0, q[4]), style: "fill:var(--c-" + q[0] + ");opacity:.06" }));
      s.appendChild(sv("text", { x: q[6], y: q[7], "text-anchor": q[5], style: "font-size:12px;font-weight:600;fill:var(--muted)", text: CLS[q[0]].he + " · " + CLS[q[0]].en }));
    });
    for (var vy = 0; vy <= maxY + 1e-9; vy += ay.step) {
      var gy = Y(vy);
      s.appendChild(sv("line", { x1: L, x2: W - Rm, y1: gy, y2: gy, style: "stroke:var(--grid);stroke-width:1" }));
      s.appendChild(sv("text", { x: L - 8, y: gy + 4, "text-anchor": "end", style: "font-size:11px;fill:var(--muted)", text: fmt(vy) }));
    }
    for (var vx = 0; vx <= maxX + 1e-9; vx += ax.step) {
      s.appendChild(sv("text", { x: X(vx), y: H - B + 18, "text-anchor": "middle", style: "font-size:11px;fill:var(--muted)", text: fmt(vx) }));
    }
    s.appendChild(sv("line", { x1: L, x2: W - Rm, y1: H - B, y2: H - B, style: "stroke:var(--axis)" }));
    s.appendChild(sv("line", { x1: L, x2: L, y1: T, y2: H - B, style: "stroke:var(--axis)" }));
    s.appendChild(sv("line", { x1: tx, x2: tx, y1: T, y2: H - B, style: "stroke:var(--ink-2);stroke-dasharray:5 4;opacity:.6" }));
    s.appendChild(sv("line", { x1: L, x2: W - Rm, y1: ty, y2: ty, style: "stroke:var(--ink-2);stroke-dasharray:5 4;opacity:.6" }));
    s.appendChild(sv("text", { x: (L + W - Rm) / 2, y: H - 10, "text-anchor": "middle", style: "font-size:12.5px;font-weight:600", text: "כוח תלות (Dependence)" + (m.unit ? " %" : "") }));
    s.appendChild(sv("text", { x: 16, y: (T + H - B) / 2, "text-anchor": "middle", transform: "rotate(-90 16 " + (T + H - B) / 2 + ")", style: "font-size:12.5px;font-weight:600", text: "כוח השפעה (Driving)" + (m.unit ? " %" : "") }));
    // overlapping points are spread on a small circle
    var groups = {};
    R.forEach(function (r) { var key = r.dep + "|" + r.dp; (groups[key] = groups[key] || []).push(r); });
    var pos = [];
    Object.keys(groups).forEach(function (key) {
      var g = groups[key];
      g.forEach(function (r, i) {
        var x = X(r.dep), y = Y(r.dp);
        if (g.length > 1) { var ang = 2 * Math.PI * i / g.length - Math.PI / 2, rad = 9 + g.length * 1.5; x += rad * Math.cos(ang); y += rad * Math.sin(ang); }
        pos.push({ r: r, x: x, y: y });
      });
    });
    // greedy label placement: try right, left, above, below and keep the first spot that does not collide
    var boxes = pos.map(function (p) { return [p.x - 8, p.y - 8, p.x + 8, p.y + 8]; });
    function hit(b) { for (var i = 0; i < boxes.length; i++) { var o = boxes[i]; if (b[0] < o[2] && b[2] > o[0] && b[1] < o[3] && b[3] > o[1]) return true; } return b[0] < L || b[2] > W - Rm || b[1] < T || b[3] > H - B; }
    var layer = sv("g", {}), lbls = [];
    pos.forEach(function (p) {
      var w = p.r.f.length * 6.6 + 4, h = 14, opts = [[p.x + 11, p.y + 4, "start", [p.x + 10, p.y - 8, p.x + 12 + w, p.y + 6]], [p.x - 11, p.y + 4, "end", [p.x - 12 - w, p.y - 8, p.x - 10, p.y + 6]],
        [p.x, p.y - 13, "middle", [p.x - w / 2, p.y - 25, p.x + w / 2, p.y - 11]], [p.x, p.y + 22, "middle", [p.x - w / 2, p.y + 10, p.x + w / 2, p.y + 24]]];
      opts.push([p.x + 11, p.y - 9, "start", [p.x + 10, p.y - 21, p.x + 12 + w, p.y - 7]], [p.x + 11, p.y + 17, "start", [p.x + 10, p.y + 5, p.x + 12 + w, p.y + 19]],
        [p.x - 11, p.y - 9, "end", [p.x - 12 - w, p.y - 21, p.x - 10, p.y - 7]], [p.x - 11, p.y + 17, "end", [p.x - 12 - w, p.y + 5, p.x - 10, p.y + 19]]);
      var pick = null;
      for (var i = 0; i < opts.length; i++) if (!hit(opts[i][3])) { pick = opts[i]; break; }
      if (!pick) pick = opts[0];  // every point keeps its name, even when the spot is crowded
      boxes.push(pick[3]);
      var g = sv("g", { class: "pt", tabindex: "0" });
      var mk = shapePath(p.r.cls, p.x, p.y, 7); mk.setAttribute("class", "mk"); mk.setAttribute("style", "fill:var(--c-" + p.r.cls + ")");
      g.appendChild(sv("circle", { cx: p.x, cy: p.y, r: 16, style: "fill:transparent" }));
      g.appendChild(mk);
      g.appendChild(sv("text", { x: pick[0], y: pick[1], "text-anchor": pick[2], text: p.r.f }));
      function enter(e) {
        Array.prototype.forEach.call(layer.children, function (c) { c.classList.toggle("dim", c !== g); });
        var ev = e.clientX != null ? e : (function () { var b = mk.getBoundingClientRect(); return { clientX: b.right, clientY: b.bottom }; })();
        showTip(ev, p.r.f, [["כוח השפעה (DP)", fmt(p.r.dp, m.unit)], ["כוח תלות (DEP)", fmt(p.r.dep, m.unit)], ["סיווג", CLS[p.r.cls].he], ["רמה", String(levelOf[p.r.f] || "")]]);
      }
      function leave() { Array.prototype.forEach.call(layer.children, function (c) { c.classList.remove("dim"); }); hideTip(); }
      g.addEventListener("mouseenter", enter); g.addEventListener("mousemove", moveTip); g.addEventListener("mouseleave", leave);
      g.addEventListener("focus", enter); g.addEventListener("blur", leave);
      layer.appendChild(g);
      lbls.push(g);
    });
    s.appendChild(layer);
    mxChart.innerHTML = ""; mxChart.appendChild(s);
    // table
    var cols = [["f", "גורם"], ["dp", "השפעה (DP)"], ["dep", "תלות (DEP)"], ["cls", "סיווג"], ["lvl", "רמה"]];
    var data = R.map(function (r) { return { f: r.f, dp: r.dp, dep: r.dep, cls: r.cls, lvl: levelOf[r.f] || 0 }; });
    sortableTable(mxTable, cols, data, "dp", function (r, k) {
      if (k === "cls") return clsBadge(r.cls);
      if (k === "dp" || k === "dep") return fmt(r[k], m.unit);
      return String(r[k]);
    }, ["dp", "dep", "lvl"]);
  }
  function sortableTable(host, cols, data, sortKey, cell, numeric) {
    var dir = -1;
    function render() {
      data.sort(function (a, b) { var x = a[sortKey], y = b[sortKey]; return (x < y ? -1 : x > y ? 1 : 0) * dir; });
      var t = el("table", { class: "data" }), tr = el("tr");
      cols.forEach(function (c) {
        var th = el("th", { "data-sort": c[0], scope: "col", text: c[1] });
        th.addEventListener("click", function () { if (sortKey === c[0]) dir = -dir; else { sortKey = c[0]; dir = numeric.indexOf(c[0]) >= 0 ? -1 : 1; } render(); });
        tr.appendChild(th);
      });
      t.appendChild(el("thead", null, [tr]));
      var tb = el("tbody");
      data.forEach(function (r) {
        var row = el("tr");
        cols.forEach(function (c) { var v = cell(r, c[0]); var td = el("td", { class: numeric.indexOf(c[0]) >= 0 ? "num" : "" }); td.appendChild(typeof v === "string" ? document.createTextNode(v) : v); row.appendChild(td); });
        tb.appendChild(row);
      });
      t.appendChild(tb);
      host.innerHTML = ""; host.appendChild(t);
    }
    render();
  }

  /* ---------- matrices ---------- */
  renderers.matrices = function (p) {
    head(p, "מטריצות", "שורה היא הגורם המשפיע, עמודה היא הגורם המושפע. העבר את העכבר על תא כדי לראות את הזוג.");
    var opts = [];
    if (D.ssim_final) opts.push(["ssim_final", "SSIM סופי"]);
    if (D.ssim_init) opts.push(["ssim_init", "SSIM לפני הכרעה"]);
    opts.push(["irm", "IRM: נגישות ראשונית"], ["frm", "FRM: נגישות סופית"]);
    var cur = opts[0][0];
    var seg = el("div", { class: "seg", role: "group", "aria-label": "בחירת מטריצה" });
    var legend = el("div", { class: "legend" }), host = el("div", { class: "scroll" });
    opts.forEach(function (o) {
      var b = el("button", { type: "button", "aria-pressed": o[0] === cur ? "true" : "false", text: o[1] });
      b.addEventListener("click", function () { cur = o[0]; Array.prototype.forEach.call(seg.children, function (c) { c.setAttribute("aria-pressed", c === b ? "true" : "false"); }); draw(); });
      seg.appendChild(b);
    });
    p.appendChild(seg);
    var card = el("div", { class: "card" }, [legend, host]);
    p.appendChild(card);
    function sw(bg, label, border) { var s = el("span", { class: "sw" }); s.style.background = bg; if (border) s.style.boxShadow = "inset 0 0 0 1px var(--axis)"; return el("span", null, [s, label]); }
    function draw() {
      var ssim = cur.indexOf("ssim") === 0, M = D[cur];
      legend.innerHTML = "";
      if (ssim) { ["V", "A", "X", "O"].concat(cur === "ssim_init" ? ["C"] : []).forEach(function (k) { legend.appendChild(sw(cvar("t-" + k), k + " = " + SYM[k], k === "O")); }); }
      else { legend.appendChild(sw(cvar("seq-direct"), "1: השפעה ישירה")); if (cur === "frm") legend.appendChild(sw(cvar("seq-indirect"), "1: השפעה עקיפה (טרנזיטיבית)")); legend.appendChild(sw("transparent", "0: אין השפעה", true)); }
      var t = el("table", { class: "mx" }), hr = el("tr", null, [el("th")]);
      F.forEach(function (f, j) { hr.appendChild(el("th", { text: String(j + 1), title: f, "data-c": j })); });
      if (!ssim) hr.appendChild(el("th", { text: "DP", title: "סכום שורה" }));
      t.appendChild(el("thead", null, [hr]));
      var tb = el("tbody"), colSum = F.map(function () { return 0; });
      F.forEach(function (fi, i) {
        var tr = el("tr", null, [el("th", { class: "rh", text: (i + 1) + ". " + fi, "data-r": i })]), rs = 0;
        F.forEach(function (fj, j) {
          var v = M[i][j], td = el("td", { "data-r": i, "data-c": j });
          if (i === j) { td.className = "diag"; td.textContent = ssim ? "" : String(v); }
          else if (ssim) { td.textContent = v; td.style.background = cvar("t-" + (SYM[v] ? v : "O")); }
          else if (+v) { var direct = cur === "irm" || D.irm[i][j]; td.style.background = cvar(direct ? "seq-direct" : "seq-indirect"); td.style.color = direct ? "#fff" : "var(--ink)"; td.textContent = "1"; }
          else { td.textContent = "0"; td.style.color = "var(--muted)"; td.style.boxShadow = "inset 0 0 0 1px var(--grid)"; }
          if (!ssim) { rs += +v; colSum[j] += +v; }
          td.addEventListener("mouseenter", function (e) {
            hl(i, j);
            var desc = ssim ? (SYM[v] || v) : (+v ? (cur === "frm" && !D.irm[i][j] && i !== j ? "השפעה עקיפה" : "השפעה ישירה") : "אין השפעה");
            showTip(e, fi + " ← " + fj, [["ערך", String(v)], ["משמעות", i === j ? "אלכסון" : desc]]);
          });
          td.addEventListener("mousemove", moveTip);
          td.addEventListener("mouseleave", function () { hl(-1, -1); hideTip(); });
          tr.appendChild(td);
        });
        if (!ssim) tr.appendChild(el("td", { class: "sum", text: String(rs) }));
        tb.appendChild(tr);
      });
      if (!ssim) {
        var sr = el("tr", null, [el("th", { class: "rh", text: "DEP (סכום עמודה)" })]);
        colSum.forEach(function (c) { sr.appendChild(el("td", { class: "sum", text: String(c) })); });
        sr.appendChild(el("td")); tb.appendChild(sr);
      }
      t.appendChild(tb);
      host.innerHTML = ""; host.appendChild(t);
      function hl(r, c) {
        Array.prototype.forEach.call(t.querySelectorAll("td[data-r],th[data-r],th[data-c]"), function (x) {
          var xr = x.getAttribute("data-r"), xc = x.getAttribute("data-c");
          x.classList.toggle("x", +xr === r && +xc === c);
          x.classList.toggle("hl", (xr !== null && xc === null && +xr === r) || (xc !== null && xr === null && +xc === c));
        });
      }
    }
    draw();
  };

  /* ---------- conflicts ---------- */
  function symBadge(s) { var b = el("span", { class: "sym " + s, text: s }); b.style.background = s === "O" ? cvar("s-O") : cvar("s-" + s); if (!SYM[s]) b.style.background = "var(--surface-2)"; return b; }
  function voteBar(votes) {
    var total = 0; Object.keys(votes).forEach(function (k) { total += votes[k]; });
    var bar = el("div", { class: "bar", role: "img", "aria-label": Object.keys(votes).map(function (k) { return k + ": " + votes[k]; }).join(", ") });
    ["V", "A", "X", "O"].forEach(function (k) { if (votes[k]) { var i = el("i", { title: k + ": " + votes[k] }); i.style.width = (votes[k] / total * 100) + "%"; i.style.background = cvar("s-" + k); bar.appendChild(i); } });
    return bar;
  }
  renderers.conflicts = function (p) {
    head(p, "קונפליקטים והכרעות AI", "זוגות שבהם לא היה רוב ברור בין המשיבים. לכל זוג מוצגים פילוח ההצבעות, ההכרעה והנימוק.");
    if (!D.conflicts.length) { p.appendChild(el("div", { class: "card empty-state" }, [el("div", { class: "big", text: "✓" }), el("div", { text: "לא היו קונפליקטים: בכל הזוגות היה רוב ברור." })])); return; }
    var legend = el("div", { class: "legend" });
    ["V", "A", "X", "O"].forEach(function (k) { var s = el("span", { class: "sw" }); s.style.background = cvar("s-" + k); legend.appendChild(el("span", null, [s, k + " = " + SYM[k]])); });
    p.appendChild(legend);
    var list = el("div", { class: "stack" });
    D.conflicts.forEach(function (c) {
      var votesTxt = ["V", "A", "X", "O"].filter(function (k) { return c.votes[k]; }).map(function (k) { return k + ": " + c.votes[k]; }).join(" · ");
      var card = el("div", { class: "card conf" }, [
        el("div", { class: "pair" }, [c.pair[0], el("span", { class: "arrow", text: "↔" }), c.pair[1]]),
        el("div", { style: "display:flex;align-items:center;gap:12px;flex-wrap:wrap" }, [voteBar(c.votes), el("span", { style: "color:var(--ink-2);font-size:13px", text: votesTxt })]),
        el("div", { class: "dec" }, [el("span", { style: "color:var(--ink-2);font-size:13px", text: "הכרעה:" }), symBadge(c.decision), el("span", { text: SYM[c.decision] || c.decision })]),
        c.rationale ? el("p", { style: "margin:0;color:var(--ink-2)", text: c.rationale }) : null
      ]);
      if (c.justs.length) {
        var ul = el("ul");
        c.justs.forEach(function (j) { ul.appendChild(el("li", null, [el("b", { text: j.expert + " (" + j.symbol + "): " }), j.text])); });
        card.appendChild(el("details", null, [el("summary", { text: "נימוקי המשיבים (" + c.justs.length + ")" }), ul]));
      }
      list.appendChild(card);
    });
    p.appendChild(list);
  };

  /* ---------- experts ---------- */
  renderers.experts = function (p) {
    head(p, "משיבים ופילוח תשובות", "התפלגות התשובות של כל משיב. ב-ISM רוב הזוגות צפויים להיות O; משיב שמסמן קשר כמעט בכל זוג עלול להביא למטריצה רוויה.");
    var legend = el("div", { class: "legend" });
    ["V", "A", "X", "O"].forEach(function (k) { var s = el("span", { class: "sw" }); s.style.background = cvar("s-" + k); legend.appendChild(el("span", null, [s, k + " = " + SYM[k]])); });
    var card = el("div", { class: "card" }, [legend]), host = el("div", { class: "scroll" });
    card.appendChild(host); p.appendChild(card);
    var data = D.experts.map(function (e) {
      var tot = e.counts.V + e.counts.A + e.counts.X + e.counts.O;
      return { name: e.name, role: e.role, type: e.type, counts: e.counts, rel: tot ? Math.round((tot - e.counts.O) / tot * 100) : 0 };
    });
    sortableTable(host, [["name", "משיב"], ["role", "תפקיד / תחום"], ["type", "סוג"], ["bar", "פילוח V / A / X / O"], ["rel", "זוגות עם קשר"]], data, "rel", function (r, k) {
      if (k === "type") return el("span", { class: "badge", text: r.type === "ai" ? "סוכן AI" : "מומחה אנושי" });
      if (k === "bar") return voteBar(r.counts);
      if (k === "rel") { var s = el("span", { text: r.rel + "%" }); if (r.rel > 70) { s = el("span", { class: "badge" }, [el("span", { class: "dot", style: "background:var(--warning)" }), r.rel + "% · חריג"]); } return s; }
      return r[k] || "";
    }, ["rel"]);
  };

  var start = (location.hash || "").slice(1);
  renderers.summary(document.getElementById("p-summary")); rendered.summary = true;
  if (start && start !== "summary" && renderers[start]) activate(start);
  window.addEventListener("beforeprint", function () { TABS.forEach(function (t) { if (!rendered[t[0]]) { renderers[t[0]](document.getElementById("p-" + t[0])); rendered[t[0]] = true; } }); });
})();
</script>
</body>
</html>
"""
