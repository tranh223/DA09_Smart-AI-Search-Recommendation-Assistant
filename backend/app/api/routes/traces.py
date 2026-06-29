"""
Traces API — xem lại input/output của từng node trong mỗi request.

Endpoints:
  GET  /traces/ui                    — HTML viewer (tương tác, fetch thật từ API)
  GET  /traces                       — danh sách traces (header only, no spans)
  GET  /traces/{request_id}          — full trace với tất cả spans + input/output
  GET  /traces/{request_id}/nodes/{node} — chi tiết một node cụ thể
  GET  /traces/{request_id}/summary  — summary latency không kèm data chi tiết
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/traces", tags=["traces"])

_NODE_NAMES = frozenset({
    "session", "intent", "slot_check", "clarify", "rewrite",
    "rag", "recommend", "rerank", "response_builder",
    "explain", "format_response", "analytics",
})

_VIEWER_HTML = """\
<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>OTA AI — Trace Viewer</title>
<style>
  :root { --bg:#0d1117; --bg2:#161b22; --bg3:#21262d; --border:#30363d;
          --text:#e6edf3; --muted:#8b949e; --accent:#58a6ff; --green:#3fb950;
          --yellow:#d29922; --red:#f85149; --purple:#bc8cff; --orange:#db6d28; }
  * { box-sizing:border-box; margin:0; padding:0; }
  body { background:var(--bg); color:var(--text); font:13px/1.5 "SF Mono","Fira Code",monospace;
         display:flex; flex-direction:column; height:100vh; overflow:hidden; }
  /* ── Header ── */
  #header { background:var(--bg2); border-bottom:1px solid var(--border);
             padding:10px 16px; display:flex; align-items:center; gap:12px; flex-shrink:0; }
  #header h1 { font-size:14px; font-weight:600; color:var(--text); }
  #header .badge { font-size:11px; background:var(--bg3); border:1px solid var(--border);
                   border-radius:4px; padding:2px 7px; color:var(--muted); }
  /* ── Layout ── */
  #main { display:flex; flex:1; overflow:hidden; }
  /* ── Sidebar ── */
  #sidebar { width:340px; border-right:1px solid var(--border); display:flex; flex-direction:column; flex-shrink:0; }
  #sidebar-toolbar { padding:8px 10px; border-bottom:1px solid var(--border); display:flex; gap:6px; }
  #sidebar-toolbar input { flex:1; background:var(--bg3); border:1px solid var(--border);
                           border-radius:4px; color:var(--text); padding:4px 8px; font:inherit; font-size:12px; }
  #trace-list { overflow-y:auto; flex:1; }
  .trace-item { padding:10px 12px; border-bottom:1px solid var(--border); cursor:pointer;
                transition:background 0.1s; }
  .trace-item:hover { background:var(--bg3); }
  .trace-item.active { background:var(--bg3); border-left:2px solid var(--accent); }
  .trace-item .query { font-size:12px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  .trace-item .meta { margin-top:3px; display:flex; gap:8px; font-size:11px; color:var(--muted); }
  .trace-item .intent { color:var(--accent); }
  .trace-item .latency { color:var(--green); }
  .trace-item .clarify { color:var(--yellow); }
  /* ── Detail panel ── */
  #detail { flex:1; display:flex; flex-direction:column; overflow:hidden; }
  #detail-header { padding:10px 14px; border-bottom:1px solid var(--border);
                   background:var(--bg2); flex-shrink:0; }
  #detail-header .dq { font-size:13px; font-weight:600; color:var(--text); }
  #detail-header .dm { margin-top:4px; display:flex; gap:12px; flex-wrap:wrap; font-size:11px; color:var(--muted); }
  #detail-header .dm span { color:var(--text); }
  /* ── Pipeline flow ── */
  #pipeline { padding:12px 14px; border-bottom:1px solid var(--border); flex-shrink:0; overflow-x:auto; }
  #pipeline .flow { display:flex; align-items:center; gap:4px; }
  .node-pill { display:flex; flex-direction:column; align-items:center; gap:2px; cursor:pointer; }
  .node-pill .nb { border:1px solid var(--border); border-radius:6px; padding:5px 10px;
                   font-size:11px; white-space:nowrap; transition:all 0.15s; min-width:72px; text-align:center; }
  .node-pill.active .nb { border-color:var(--accent); background:rgba(88,166,255,.12); color:var(--accent); }
  .node-pill.ok .nb { border-color:var(--border); }
  .node-pill.error .nb { border-color:var(--red); color:var(--red); }
  .node-pill.skipped .nb { opacity:0.35; }
  .node-pill .nms { font-size:10px; color:var(--green); }
  .flow-arrow { color:var(--muted); font-size:12px; flex-shrink:0; }
  .flow-branch { display:flex; flex-direction:column; gap:4px; }
  /* ── Node detail ── */
  #node-detail { flex:1; overflow-y:auto; padding:14px; }
  .nd-section { margin-bottom:14px; }
  .nd-section h3 { font-size:11px; font-weight:600; text-transform:uppercase; letter-spacing:.06em;
                   color:var(--muted); margin-bottom:6px; }
  .nd-section pre { background:var(--bg3); border:1px solid var(--border); border-radius:6px;
                    padding:10px 12px; font:12px/1.6 "SF Mono","Fira Code",monospace;
                    overflow-x:auto; white-space:pre-wrap; word-break:break-word; }
  .nd-kv { display:flex; flex-direction:column; gap:4px; }
  .nd-kv .kv { display:flex; gap:8px; font-size:12px; }
  .nd-kv .kv .k { color:var(--muted); min-width:140px; flex-shrink:0; }
  .nd-kv .kv .v { color:var(--text); word-break:break-all; }
  .nd-kv .kv .v.ok { color:var(--green); }
  .nd-kv .kv .v.err { color:var(--red); }
  .nd-kv .kv .v.acc { color:var(--accent); }
  .nd-kv .kv .v.yel { color:var(--yellow); }
  /* ── Empty / loading ── */
  .empty { color:var(--muted); font-size:12px; padding:20px; text-align:center; }
  .loader { animation:spin 1s linear infinite; }
  @keyframes spin { from{transform:rotate(0deg)} to{transform:rotate(360deg)} }
  /* ── Scroll ── */
  ::-webkit-scrollbar { width:6px; height:6px; }
  ::-webkit-scrollbar-track { background:transparent; }
  ::-webkit-scrollbar-thumb { background:var(--border); border-radius:3px; }
</style>
</head>
<body>
<div id="header">
  <h1>OTA AI — Trace Viewer</h1>
  <span class="badge">Pipeline Input / Output Inspector</span>
  <span id="hstatus" class="badge" style="margin-left:auto;"></span>
</div>
<div id="main">
  <div id="sidebar">
    <div id="sidebar-toolbar">
      <input id="search" placeholder="Filter by query / user / intent…" oninput="filterList()">
    </div>
    <div id="trace-list"><div class="empty">Loading traces…</div></div>
  </div>
  <div id="detail">
    <div id="detail-header"><div class="empty" style="padding:0">Select a trace to inspect</div></div>
    <div id="pipeline" style="display:none"></div>
    <div id="node-detail"></div>
  </div>
</div>
<script>
const BASE = window.location.origin;
let allTraces = [], selectedTrace = null, selectedNode = null;

const NODE_ORDER = ["session","intent","slot_check","rewrite","rag","recommend","rerank",
                    "response_builder","explain","format_response","analytics","clarify"];
const NODE_LABEL = {session:"Session",intent:"Intent",slot_check:"Slot Check",clarify:"Clarify",
  rewrite:"Rewrite",rag:"RAG",recommend:"Recommend",rerank:"Rerank",
  response_builder:"Response Builder",explain:"Explain",format_response:"Format",analytics:"Analytics"};

async function loadTraces() {
  try {
    const r = await fetch(BASE + "/traces?limit=50");
    const d = await r.json();
    allTraces = d.items || [];
    document.getElementById("hstatus").textContent = allTraces.length + " traces loaded";
    renderList(allTraces);
  } catch(e) {
    document.getElementById("trace-list").innerHTML = '<div class="empty">Error loading traces: ' + e.message + '</div>';
  }
}

function renderList(items) {
  const el = document.getElementById("trace-list");
  if (!items.length) { el.innerHTML = '<div class="empty">No traces found</div>'; return; }
  el.innerHTML = items.map(t => {
    const spans = t.spans || [];
    const latency = spans.reduce((a,s) => ({...a, [s.name]: s.elapsed_ms}), {});
    const totalMs = t.total_ms ? Math.round(t.total_ms) : "?";
    const clarify = t.needs_clarification;
    return `<div class="trace-item" onclick="selectTrace('${t.request_id}')">
      <div class="query">${esc(t.query || "(no query)")}</div>
      <div class="meta">
        <span class="intent">${t.intent || "?"}</span>
        <span class="${clarify ? "clarify" : "latency"}">${clarify ? "clarify" : (totalMs + "ms")}</span>
        <span>${t.user_id || ""}</span>
        <span>${(t.started_at || "").slice(0,16).replace("T"," ")}</span>
      </div>
    </div>`;
  }).join("");
}

function filterList() {
  const q = document.getElementById("search").value.toLowerCase();
  renderList(allTraces.filter(t =>
    (t.query||"").toLowerCase().includes(q) ||
    (t.user_id||"").toLowerCase().includes(q) ||
    (t.intent||"").toLowerCase().includes(q)
  ));
}

async function selectTrace(rid) {
  selectedNode = null;
  document.querySelectorAll(".trace-item").forEach(el => el.classList.remove("active"));
  const items = document.querySelectorAll(".trace-item");
  // mark active
  document.getElementById("detail-header").innerHTML = "<div class='empty'>Loading…</div>";
  document.getElementById("pipeline").style.display = "none";
  document.getElementById("node-detail").innerHTML = "";
  try {
    const r = await fetch(BASE + "/traces/" + rid);
    selectedTrace = await r.json();
    renderDetailHeader(selectedTrace);
    renderPipeline(selectedTrace);
  } catch(e) {
    document.getElementById("detail-header").innerHTML = "<div class='empty'>Error: " + e.message + "</div>";
  }
}

function renderDetailHeader(t) {
  const el = document.getElementById("detail-header");
  const clarify = t.needs_clarification ? '<span style="color:var(--yellow)">clarification</span>' : '<span style="color:var(--green)">' + t.n_recs + ' recs</span>';
  el.innerHTML = `<div class="dq">${esc(t.query || "")}</div>
    <div class="dm">
      <span>request_id: <span style="color:var(--accent)">${(t.request_id||"").slice(0,16)}…</span></span>
      <span>user: <span>${esc(t.user_id||"?")}</span></span>
      <span>session: <span>${esc((t.session_id||"?").slice(0,12))}…</span></span>
      <span>intent: <span style="color:var(--accent)">${t.intent||"?"}</span></span>
      <span>total: <span style="color:var(--green)">${Math.round(t.total_ms||0)}ms</span></span>
      <span>result: ${clarify}</span>
      <span>${(t.started_at||"").slice(0,19).replace("T"," ")}</span>
    </div>`;
}

function renderPipeline(t) {
  const pEl = document.getElementById("pipeline");
  pEl.style.display = "block";
  const spans = t.spans || [];
  const spanMap = {};
  spans.forEach(s => spanMap[s.name] = s);
  const exec = new Set(t.executed_nodes || []);
  const route = t.route_taken || "complete";

  // Build flow array based on route taken
  let flow;
  if (route === "clarify") {
    flow = [["session"],["intent"],["slot_check"],["clarify"],["analytics"]];
  } else {
    flow = [
      ["session"],["intent"],["slot_check"],["rewrite"],
      ["rag","recommend"],["rerank"],["response_builder"],
      ["explain"],["format_response"],["analytics"]
    ];
  }

  let html = '<div class="flow">';
  flow.forEach((group, gi) => {
    if (gi > 0) html += '<span class="flow-arrow">→</span>';
    if (group.length === 1) {
      html += nodeHtml(group[0], spanMap, exec);
    } else {
      html += '<div class="flow-branch">';
      group.forEach(n => html += nodeHtml(n, spanMap, exec));
      html += '</div>';
    }
  });
  html += '</div>';
  pEl.innerHTML = html;
}

function nodeHtml(name, spanMap, exec) {
  const span = spanMap[name];
  const ran = exec.has(name);
  const status = span ? (span.status || "ok") : (ran ? "ok" : "skipped");
  const ms = span ? Math.round(span.elapsed_ms || 0) : "";
  const cls = (selectedNode === name ? " active" : "") + " " + (ran ? status : "skipped");
  return `<div class="node-pill ${cls}" onclick="selectNode('${name}')">
    <div class="nb">${NODE_LABEL[name]||name}</div>
    ${ms ? '<div class="nms">' + ms + 'ms</div>' : ''}
  </div>`;
}

function selectNode(name) {
  if (!selectedTrace) return;
  selectedNode = name;
  renderPipeline(selectedTrace);  // re-render to update active highlight
  const spans = selectedTrace.spans || [];
  const span = spans.find(s => s.name === name);
  const el = document.getElementById("node-detail");
  if (!span) {
    el.innerHTML = '<div class="empty">Node "' + name + '" was not executed in this request.</div>';
    return;
  }
  let html = "";
  // Status row
  html += `<div class="nd-section"><div class="nd-kv">
    <div class="kv"><span class="k">Node</span><span class="v acc">${name}</span></div>
    <div class="kv"><span class="k">Status</span><span class="v ${span.status==="error"?"err":"ok"}">${span.status}</span></div>
    <div class="kv"><span class="k">Latency</span><span class="v ok">${Math.round(span.elapsed_ms||0)} ms</span></div>
    ${span.error ? '<div class="kv"><span class="k">Error</span><span class="v err">' + esc(span.error) + '</span></div>' : ""}
  </div></div>`;
  // Input
  if (span.input && Object.keys(span.input).length) {
    html += `<div class="nd-section"><h3>Input — State Before</h3>
      <pre>${esc(JSON.stringify(span.input, null, 2))}</pre></div>`;
  }
  // Output
  if (span.output && Object.keys(span.output).length) {
    html += `<div class="nd-section"><h3>Output — State Delta</h3>
      <pre>${esc(JSON.stringify(span.output, null, 2))}</pre></div>`;
  }
  // Context / sub_spans
  if (span.context && Object.keys(span.context).length) {
    html += `<div class="nd-section"><h3>Context Summary</h3>
      <pre>${esc(JSON.stringify(span.context, null, 2))}</pre></div>`;
  }
  if (span.sub_spans && span.sub_spans.length) {
    html += `<div class="nd-section"><h3>Sub-spans (${span.sub_spans.length})</h3>
      <pre>${esc(JSON.stringify(span.sub_spans, null, 2))}</pre></div>`;
  }
  el.innerHTML = html;
}

function esc(s) {
  return String(s||"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
}

loadTraces();
// auto-refresh list every 30s
setInterval(loadTraces, 30000);
</script>
</body>
</html>
"""


# ── HTML UI ───────────────────────────────────────────────────────────────────

@router.get(
    "/ui",
    response_class=HTMLResponse,
    include_in_schema=False,
    summary="Trace Viewer UI",
)
def trace_viewer_ui():
    """Giao diện HTML tương tác — tự fetch /traces API, click node xem input/output."""
    return HTMLResponse(content=_VIEWER_HTML, status_code=200)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_store():
    from app.db.trace_store import (  # noqa: PLC0415
        count_traces,
        get_node_trace,
        get_trace,
        list_traces,
    )
    return get_trace, list_traces, get_node_trace, count_traces


def _build_latency_map(spans: list[dict[str, Any]]) -> dict[str, float]:
    return {s["name"]: s.get("elapsed_ms", 0.0) for s in spans}


def _build_graph_edges() -> list[dict[str, str]]:
    """Trả về cạnh đồ thị LangGraph để UI render DAG."""
    return [
        {"from": "START", "to": "session"},
        {"from": "session", "to": "intent"},
        {"from": "intent", "to": "slot_check"},
        {"from": "slot_check", "to": "clarify", "condition": "incomplete"},
        {"from": "slot_check", "to": "rewrite", "condition": "complete"},
        {"from": "clarify", "to": "analytics"},
        {"from": "rewrite", "to": "rag"},
        {"from": "rewrite", "to": "recommend"},
        {"from": "recommend", "to": "rerank"},
        {"from": "rag", "to": "response_builder"},
        {"from": "rerank", "to": "response_builder"},
        {"from": "response_builder", "to": "explain"},
        {"from": "explain", "to": "format_response"},
        {"from": "format_response", "to": "analytics"},
        {"from": "analytics", "to": "END"},
    ]


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get(
    "",
    summary="Danh sách traces gần đây",
    description=(
        "Trả về danh sách traces (header only — không bao gồm spans đầy đủ). "
        "Có thể filter theo user_id, session_id, intent."
    ),
)
def list_trace_runs(
    user_id: str | None = Query(None, description="Filter theo user_id"),
    session_id: str | None = Query(None, description="Filter theo session_id"),
    intent: str | None = Query(None, description="Filter theo intent phân loại"),
    needs_clarification: bool | None = Query(None, description="Filter theo needs_clarification"),
    limit: int = Query(20, ge=1, le=100, description="Số trace tối đa trả về"),
    offset: int = Query(0, ge=0, description="Skip N trace đầu"),
):
    get_trace, list_traces, get_node_trace, count_traces = _get_store()
    items = list_traces(
        user_id=user_id,
        session_id=session_id,
        limit=limit,
        offset=offset,
        intent=intent,
        needs_clarification=needs_clarification,
    )
    total = count_traces(user_id=user_id, session_id=session_id)
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": items,
    }


@router.get(
    "/{request_id}",
    summary="Full trace của một request",
    description=(
        "Trả về toàn bộ trace: metadata request + tất cả spans với "
        "input/output của mỗi node + cấu trúc DAG."
    ),
)
def get_trace_run(request_id: str):
    get_trace, list_traces, get_node_trace, count_traces = _get_store()
    doc = get_trace(request_id)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Trace '{request_id}' not found.")

    spans = doc.get("spans") or []

    # Xây latency map cho từng node
    latency = _build_latency_map(spans)

    # Xác định các node nào thực sự đã chạy
    executed_nodes = [s["name"] for s in spans]

    # Xác định route được chọn (complete vs clarify)
    slot_check_span = next((s for s in spans if s.get("name") == "slot_check"), None)
    route_taken = "clarify" if "clarify" in executed_nodes else "complete"

    return {
        "request_id": doc.get("request_id"),
        "user_id": doc.get("user_id"),
        "session_id": doc.get("session_id"),
        "query": doc.get("query"),
        "started_at": doc.get("started_at"),
        "total_ms": doc.get("total_ms"),
        "intent": doc.get("intent"),
        "n_recs": doc.get("n_recs"),
        "needs_clarification": doc.get("needs_clarification"),
        "route_taken": route_taken,
        "executed_nodes": executed_nodes,
        "latency_per_node_ms": latency,
        "graph": {
            "nodes": list(_NODE_NAMES),
            "edges": _build_graph_edges(),
        },
        "spans": spans,
    }


@router.get(
    "/{request_id}/nodes/{node_name}",
    summary="Input/Output của một node cụ thể",
    description=(
        "Trả về span chi tiết của một node: "
        "input (state trước khi chạy), output (state delta trả về), "
        "context summary và latency."
    ),
)
def get_node_detail(request_id: str, node_name: str):
    if node_name not in _NODE_NAMES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown node '{node_name}'. Valid nodes: {sorted(_NODE_NAMES)}",
        )
    get_trace, list_traces, get_node_trace, count_traces = _get_store()
    span = get_node_trace(request_id, node_name)
    if span is None:
        raise HTTPException(
            status_code=404,
            detail=f"Node '{node_name}' not found in trace '{request_id}' "
                   "(node may have been skipped).",
        )
    return {
        "request_id": request_id,
        "node": node_name,
        "elapsed_ms": span.get("elapsed_ms"),
        "status": span.get("status"),
        "error": span.get("error"),
        "input": span.get("input") or {},
        "output": span.get("output") or {},
        "context": span.get("context") or {},
        "sub_spans": span.get("sub_spans") or [],
    }


@router.get(
    "/{request_id}/summary",
    summary="Latency summary của một request",
    description="Tóm tắt latency từng bước, bottleneck stage, không kèm data chi tiết.",
)
def get_trace_summary(request_id: str):
    get_trace, list_traces, get_node_trace, count_traces = _get_store()
    doc = get_trace(request_id)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Trace '{request_id}' not found.")

    spans = doc.get("spans") or []
    latency = _build_latency_map(spans)
    errors = [
        {"node": s["name"], "error": s.get("error")}
        for s in spans
        if s.get("status") == "error"
    ]
    bottleneck = max(latency, key=latency.__getitem__) if latency else None

    return {
        "request_id": request_id,
        "query": doc.get("query"),
        "total_ms": doc.get("total_ms"),
        "intent": doc.get("intent"),
        "n_recs": doc.get("n_recs"),
        "needs_clarification": doc.get("needs_clarification"),
        "bottleneck_node": bottleneck,
        "bottleneck_ms": latency.get(bottleneck) if bottleneck else None,
        "latency_per_node_ms": latency,
        "executed_nodes": [s["name"] for s in spans],
        "errors": errors,
    }
