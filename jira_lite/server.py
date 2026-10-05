#!/usr/bin/env python3
"""
ESS Tracker (Jira-lite) - a tiny ticket platform for the ESS AI workflow demo.

  * Live Kanban board : http://127.0.0.1:5055
  * REST API          : GET   /api/tickets
                        POST  /api/tickets                 {"title": "...", "type": "Bug", ...}   (create)
                        GET   /api/tickets/<id>
                        PATCH /api/tickets/<id>            {"status": "...", "assignee": "...", "changes": {...}}
                        POST  /api/tickets/<id>/comments   {"author": "...", "body": "..."}

Standard library only - nothing to install.
"""
import json
import re
import shutil
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "tickets.json"
SEED = HERE / "seed_tickets.json"
HOST, PORT = "127.0.0.1", 5055
STATUSES = ["To Do", "In Progress", "In Review", "Done"]
TYPES = ["Bug", "Story"]
PRIORITIES = ["Highest", "High", "Medium", "Low"]
LOCK = threading.Lock()


def load():
    if not DATA.exists():
        shutil.copyfile(SEED, DATA)
    return json.loads(DATA.read_text(encoding="utf-8"))


def save(data):
    DATA.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def find(data, ticket_id):
    for t in data["tickets"]:
        if t["id"].lower() == ticket_id.lower():
            return t
    return None


def lines(value):
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    return [x.strip() for x in str(value or "").splitlines() if x.strip()]


PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>ESS Tracker</title>
<style>
:root{--n:#10183A;--c:#00A7D8;--line:#DCE4EF;--bg:#F5F7FB;--mut:#64748B}
*{box-sizing:border-box}
body{margin:0;font:14px/1.5 "Segoe UI",Inter,Arial,sans-serif;background:var(--bg);color:#17233D}
header{background:var(--n);color:#fff;padding:14px 26px;display:flex;align-items:center;gap:14px}
header b{letter-spacing:.14em;font-size:15px} header i{font-style:normal;color:#7FE0F5}
header small{margin-left:auto;color:#9FB6D4}
header button{background:var(--c);color:#fff;border:0;border-radius:8px;padding:7px 14px;font:inherit;font-weight:700;cursor:pointer}
.live{display:inline-block;width:9px;height:9px;border-radius:50%;background:#1FA463;margin-right:6px;animation:p 1.4s infinite}
@keyframes p{50%{opacity:.25}}
.board{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;padding:20px 26px}
.col{background:#E7EDF6;border-radius:12px;padding:10px;min-height:70vh;min-width:0}
.col h3{margin:6px 8px 12px;font-size:11px;letter-spacing:.14em;color:#52637A;text-transform:uppercase;display:flex;justify-content:space-between}
.card{background:#fff;border:1px solid var(--line);border-radius:10px;padding:12px 13px;margin-bottom:10px;cursor:pointer;box-shadow:0 4px 12px #19345c14;transition:.25s}
.card:hover{transform:translateY(-1px)}
.card.flash{animation:f 1.6s}
@keyframes f{0%{box-shadow:0 0 0 3px #00A7D8}100%{box-shadow:0 4px 12px #19345c14}}
.id{font-weight:800;color:#1769AA;font-size:12px}
.title{font-weight:600;margin:3px 0 8px}
.tag{display:inline-block;font-size:10px;font-weight:800;letter-spacing:.06em;padding:2px 8px;border-radius:20px;margin-right:5px;text-transform:uppercase}
.Bug{background:#FDE8E8;color:#B42318}.Story{background:#E6F4EA;color:#1E7B3C}
.High,.Highest{background:#FFF1DB;color:#B25E09}.Medium{background:#E8F0FE;color:#1B5FC1}.Low{background:#EEF1F5;color:#52637A}
.assignee{float:right;font-size:11px;color:var(--mut)}
.bot{background:#10183A;color:#7FE0F5}
.detail{display:none;margin-top:10px;padding-top:10px;border-top:1px dashed var(--line);font-size:13px}
.card.open .detail{display:block}
.detail h4{margin:10px 0 3px;font-size:10px;letter-spacing:.12em;color:#007C91;text-transform:uppercase}
.detail ul{margin:0;padding-left:18px}
.cmt{background:#F5F7FB;border-radius:8px;padding:8px 10px;margin:6px 0;white-space:pre-wrap}
.cmt b{font-size:12px}.cmt small{color:var(--mut);margin-left:6px}
.kv{font-size:12px;margin:2px 0}
.diff{font:12px/1.45 Consolas,"Courier New",monospace;background:#0F172A;color:#CBD5E1;border-radius:8px;padding:8px 10px;overflow:auto;max-height:280px;white-space:pre;margin-top:6px}
.diff .a{color:#6EE7A8}.diff .d{color:#FCA5A5}.diff .h{color:#7FE0F5}
.act{display:flex;gap:8px;margin-top:12px}
.act button{border:0;border-radius:8px;padding:7px 12px;font:inherit;font-weight:700;cursor:pointer;background:#1FA463;color:#fff}
.act button.sec{background:#fff;color:#B42318;border:1px solid #F1B5B0}
.modal{position:fixed;inset:0;background:#0F172A88;display:none;align-items:center;justify-content:center;z-index:10}
.modal.show{display:flex}
.dlg{background:#fff;border-radius:14px;padding:20px 24px;width:min(520px,94vw);max-height:92vh;overflow:auto}
.dlg h3{margin:0 0 6px}
.dlg label{display:block;font-size:12px;font-weight:700;color:#52637A;margin:10px 0 3px}
.dlg input,.dlg select,.dlg textarea{width:100%;padding:8px 10px;border:1px solid var(--line);border-radius:8px;font:inherit}
.dlg textarea{min-height:56px;resize:vertical}
.two{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.row{display:flex;justify-content:flex-end;gap:8px;margin-top:16px}
.row .p{background:var(--c);color:#fff;border:0;border-radius:8px;padding:8px 18px;font:inherit;font-weight:700;cursor:pointer}
.row .s{background:#fff;border:1px solid var(--line);border-radius:8px;padding:8px 16px;font:inherit;cursor:pointer}
</style></head><body>
<header><b>ESS <i>TRACKER</i></b><span style="color:#9FB6D4">Project ESS · User Management app</span>
<small><span class="live"></span>live board</small><button onclick="openNew()">+ New ticket</button></header>
<div class="board" id="board"></div>

<div class="modal" id="modal"><div class="dlg">
  <h3>Create ticket</h3>
  <label>Title</label><input id="n-title">
  <div class="two"><div><label>Type</label><select id="n-type"><option>Bug</option><option>Story</option></select></div>
  <div><label>Priority</label><select id="n-prio"><option>Highest</option><option selected>High</option><option>Medium</option><option>Low</option></select></div></div>
  <label>Description</label><textarea id="n-desc"></textarea>
  <label>Steps to reproduce (one per line)</label><textarea id="n-steps"></textarea>
  <label>Expected</label><input id="n-exp">
  <label>Actual</label><input id="n-act">
  <label>Acceptance criteria (one per line)</label><textarea id="n-ac"></textarea>
  <div class="row"><button class="s" onclick="closeNew()">Cancel</button><button class="p" onclick="createTicket()">Create</button></div>
</div></div>

<script>
const STATUSES=["To Do","In Progress","In Review","Done"];
let last="",open=new Set(),prev={};
const $=id=>document.getElementById(id);
const esc=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
function chg(c){
  if(!c)return "";
  const d=(c.diff||"").split("\n").map(l=>{
    const k=l.startsWith("+++")||l.startsWith("---")?"":l.startsWith("+")?"a":l.startsWith("-")?"d":(l.startsWith("@@")||l.startsWith("diff "))?"h":"";
    return `<span class="${k}">${esc(l)}</span>`;}).join("\n");
  return `<h4>What the agent changed</h4>
   <div class="kv">Branch <b>${esc(c.branch)}</b> · Commit <b>${esc(c.commit)}</b></div>
   <div class="kv">Tests: <b>${esc(c.tests)}</b></div>
   <div class="kv">Files: ${esc((c.files||[]).join(", "))}</div>
   <div class="diff">${d}</div>`;
}
function card(t){
  const bot=t.assignee&&t.assignee.startsWith("ESS AI");
  const li=a=>a&&a.length?`<ul>${a.map(x=>`<li>${esc(x)}</li>`).join("")}</ul>`:"<i>-</i>";
  const cm=(t.comments||[]).map(c=>`<div class="cmt"><b>${esc(c.author)}</b><small>${esc(c.time)}</small><br>${esc(c.body)}</div>`).join("")||"<i>No comments</i>";
  const act=t.status==="In Review"?`<div class="act"><button onclick="mv(event,'${t.id}','Done')">✔ Approve &amp; mark Done</button><button class="sec" onclick="mv(event,'${t.id}','To Do')">↩ Reject</button></div>`:"";
  return `<div class="card ${open.has(t.id)?"open":""} ${prev[t.id]&&prev[t.id]!==t.status+"|"+(t.comments||[]).length?"flash":""}" onclick="tg('${t.id}')">
   <div class="id">${esc(t.id)}<span class="assignee ${bot?"tag bot":""}">${esc(t.assignee)}</span></div>
   <div class="title">${esc(t.title)}</div>
   <span class="tag ${esc(t.type)}">${esc(t.type)}</span><span class="tag ${esc(t.priority)}">${esc(t.priority)}</span>
   <span style="font-size:11px;color:#64748B">💬 ${(t.comments||[]).length}</span>
   <div class="detail">
    ${chg(t.changes)}
    <h4>Description</h4>${esc(t.description)}
    <h4>Steps to reproduce</h4>${li(t.steps)}
    <h4>Expected</h4>${esc(t.expected)}
    <h4>Actual</h4>${esc(t.actual)}
    <h4>Acceptance criteria</h4>${li(t.acceptance_criteria)}
    <h4>Comments</h4>${cm}
    ${act}
   </div></div>`;
}
function render(tickets){
  $("board").innerHTML=STATUSES.map(s=>{
    const items=tickets.filter(t=>t.status===s);
    return `<div class="col"><h3><span>${s}</span><span>${items.length}</span></h3>${items.map(card).join("")}</div>`;
  }).join("");
  prev={};tickets.forEach(t=>prev[t.id]=t.status+"|"+(t.comments||[]).length);
}
function tg(id){open.has(id)?open.delete(id):open.add(id);render(window._t||[]);}
async function send(method,url,body){
  await fetch(url,{method,headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});poll();
}
function mv(ev,id,status){
  ev.stopPropagation();
  const ok=status==="Done";
  send("PATCH","/api/tickets/"+id,{status}).then(()=>send("POST","/api/tickets/"+id+"/comments",
   {author:"Reviewer",body:ok?"Reviewed the diff and tests. Approved - merge the branch and release.":"Changes rejected - back to To Do."}));
}
function openNew(){$("modal").classList.add("show");$("n-title").focus();}
function closeNew(){$("modal").classList.remove("show");}
async function createTicket(){
  const title=$("n-title").value.trim();if(!title){$("n-title").focus();return;}
  const body={title,type:$("n-type").value,priority:$("n-prio").value,description:$("n-desc").value,
    steps:$("n-steps").value,expected:$("n-exp").value,actual:$("n-act").value,acceptance_criteria:$("n-ac").value,reporter:"You"};
  const r=await fetch("/api/tickets",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
  if(r.ok){["n-title","n-desc","n-steps","n-exp","n-act","n-ac"].forEach(i=>$(i).value="");closeNew();poll();}
}
async function poll(){
  try{
    const r=await fetch("/api/tickets",{cache:"no-store"});const txt=await r.text();
    if(txt!==last){last=txt;window._t=JSON.parse(txt);render(window._t);}
  }catch(e){}
}
poll();setInterval(poll,1200);
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    server_version = "ESSTracker/1.1"

    def log_message(self, fmt, *args):  # keep the console clean for the demo
        pass

    def _send(self, code, payload, ctype="application/json; charset=utf-8"):
        body = payload if isinstance(payload, bytes) else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}")

    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ("/", "/index.html"):
            return self._send(200, PAGE.encode("utf-8"), "text/html; charset=utf-8")
        if path == "/api/tickets":
            with LOCK:
                return self._send(200, load()["tickets"])
        m = re.fullmatch(r"/api/tickets/([A-Za-z0-9-]+)", path)
        if m:
            with LOCK:
                t = find(load(), m.group(1))
            return self._send(200, t) if t else self._send(404, {"error": "ticket not found"})
        self._send(404, {"error": "not found"})

    def do_PATCH(self):
        m = re.fullmatch(r"/api/tickets/([A-Za-z0-9-]+)", self.path.split("?")[0])
        if not m:
            return self._send(404, {"error": "not found"})
        body = self._body()
        with LOCK:
            data = load()
            t = find(data, m.group(1))
            if not t:
                return self._send(404, {"error": "ticket not found"})
            if "status" in body:
                if body["status"] not in STATUSES:
                    return self._send(400, {"error": f"status must be one of {STATUSES}"})
                t["status"] = body["status"]
            if "assignee" in body:
                t["assignee"] = body["assignee"]
            if "changes" in body:  # what the AI agent changed: branch, commit, tests, files, diff
                t["changes"] = body["changes"]
            save(data)
        self._send(200, t)

    def do_POST(self):
        path = self.path.split("?")[0]
        if path == "/api/tickets":  # create a ticket
            body = self._body()
            title = str(body.get("title", "")).strip()
            if not title:
                return self._send(400, {"error": "title is required"})
            with LOCK:
                data = load()
                nums = [int(re.sub(r"\D", "", t["id"]) or 0) for t in data["tickets"]]
                t = {
                    "id": f"ESS-{max(nums + [200]) + 1}",
                    "title": title,
                    "type": body.get("type") if body.get("type") in TYPES else "Bug",
                    "priority": body.get("priority") if body.get("priority") in PRIORITIES else "Medium",
                    "status": "To Do",
                    "reporter": body.get("reporter", "You"),
                    "assignee": "Unassigned",
                    "component": body.get("component", "User Management"),
                    "description": body.get("description", ""),
                    "steps": lines(body.get("steps")),
                    "expected": body.get("expected", ""),
                    "actual": body.get("actual", ""),
                    "acceptance_criteria": lines(body.get("acceptance_criteria")),
                    "comments": [],
                }
                data["tickets"].append(t)
                save(data)
            return self._send(201, t)
        m = re.fullmatch(r"/api/tickets/([A-Za-z0-9-]+)/comments", path)
        if not m:
            return self._send(404, {"error": "not found"})
        body = self._body()
        with LOCK:
            data = load()
            t = find(data, m.group(1))
            if not t:
                return self._send(404, {"error": "ticket not found"})
            t.setdefault("comments", []).append({
                "author": body.get("author", "anonymous"),
                "time": datetime.now().strftime("%H:%M:%S"),
                "body": body.get("body", ""),
            })
            save(data)
        self._send(201, t)


if __name__ == "__main__":
    load()  # make sure tickets.json exists
    srv = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"ESS Tracker running  ->  http://{HOST}:{PORT}   (Ctrl+C to stop)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
