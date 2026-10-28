"""Interaktywny wykres trudnosci pytan (HTML, bez zewnetrznych bibliotek) na podstawie dziennika odpowiedzi (review_log).
Os X = ID pytania, os Y = wskaznik trudnosci (wygladzony odsetek bledow, patrz opis w pliku). Baza tylko do odczytu.
Uzycie: python stats_chart.py [baza.db] [wynik.html]"""
import json
import sqlite3
import sys
from pathlib import Path

DB = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.home() / "Documents" / "memonic_app.db"
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else Path.home() / "Desktop" / "Statystyki_pytan.html"
CAT = {"Kapitan żeglugi wielkiej": "Master", "Dział pokładowy": "Pokład", "Angielski": "Angielski"}

con = sqlite3.connect(f"file:{DB.as_posix()}?mode=ro", uri=True)
rows = con.execute("""
    SELECT q.id, q.kategoria, q.dup_group, l.n, l.w, q.pytanie,
           CASE q.poprawna_odpowiedz WHEN 'A' THEN q.odp_a WHEN 'B' THEN q.odp_b WHEN 'C' THEN q.odp_c WHEN 'D' THEN q.odp_d END
    FROM (SELECT question_id, COUNT(*) n, SUM(correct = 0) w FROM review_log GROUP BY question_id) l
    JOIN questions q ON q.id = l.question_id ORDER BY q.id""").fetchall()
data = [dict(id=r[0], c=CAT.get(r[1], r[1]), g=r[2], a=r[3], w=r[4] or 0, q=(r[5] or "")[:400], k=(r[6] or "")[:200]) for r in rows]
total = con.execute("SELECT COUNT(*), SUM(correct=0) FROM review_log").fetchone()

HTML = r"""<!doctype html>
<html lang="pl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Statystyki pytań</title>
<style>
:root{--bg:#fff;--fg:#1c1b1f;--mut:#6b6b73;--card:#f4f4f8;--grid:#dcdce4;--m:#2f6fed;--p:#e8860c;--e:#1a9e6b}
@media (prefers-color-scheme:dark){:root{--bg:#121217;--fg:#e6e6ec;--mut:#9a9aa6;--card:#1d1d25;--grid:#33333f;--m:#6b9bff;--p:#ffb066;--e:#4fd6a0}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.45 system-ui,Segoe UI,sans-serif;padding:16px}
h1{font-size:20px;margin:0 0 4px}.sub{color:var(--mut);margin-bottom:12px}
.bar{display:flex;flex-wrap:wrap;gap:14px 22px;align-items:center;background:var(--card);padding:10px 14px;border-radius:10px;margin-bottom:12px}
.bar label{display:flex;gap:6px;align-items:center;cursor:pointer}.dot{width:11px;height:11px;border-radius:50%;display:inline-block}
#wrap{position:relative;background:var(--card);border-radius:10px;padding:6px}canvas{width:100%;height:520px;display:block;cursor:crosshair}
#tip{position:fixed;pointer-events:none;background:var(--bg);color:var(--fg);border:1px solid var(--grid);border-radius:8px;padding:8px 10px;max-width:420px;font-size:13px;box-shadow:0 4px 18px #0004;display:none;z-index:5}
.mut{color:var(--mut)}button{background:var(--card);color:var(--fg);border:1px solid var(--grid);border-radius:8px;padding:5px 10px;cursor:pointer}
table{border-collapse:collapse;width:100%;margin-top:10px}th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--grid);vertical-align:top}
th{color:var(--mut);font-weight:600;position:sticky;top:0;background:var(--bg)}tr.row{cursor:pointer}tr.row:hover{background:var(--card)}
details{margin-top:14px;color:var(--mut)}input[type=range]{width:140px}
</style></head><body>
<h1>Statystyki pytań — trudność wg ID</h1>
<div class="sub">Odpowiedzi w dzienniku: __TOTAL__ (błędnych: __WRONG__). Kółko = pytanie; im wyżej, tym trudniejsze; większe kółko = więcej odpowiedzi. Kółka z tej samej grupy powtórzeń są domyślnie scalone.</div>
<div class="bar">
 <label><input type="checkbox" class="cat" value="Master" checked><span class="dot" style="background:var(--m)"></span>Master</label>
 <label><input type="checkbox" class="cat" value="Angielski" checked><span class="dot" style="background:var(--e)"></span>Angielski</label>
 <label><input type="checkbox" class="cat" value="Pokład" checked><span class="dot" style="background:var(--p)"></span>Pokład</label>
 <label>Min. odpowiedzi: <input id="mina" type="range" min="1" max="10" value="1"><b id="minav">1</b></label>
 <label>Min. trudność: <input id="mind" type="range" min="0" max="95" value="0"><b id="mindv">0.00</b></label>
 <label><input type="checkbox" id="merge" checked>Scal powtórzenia</label>
 <button id="reset">Reset powiększenia</button>
 <span class="mut" id="cnt"></span>
</div>
<div id="wrap"><canvas id="cv"></canvas></div>
<div class="mut" style="margin:6px 2px">Kółkiem myszy powiększasz oś ID, przeciągnięciem przesuwasz. Najechanie = szczegóły, kliknięcie = zaznaczenie na liście.</div>
<h3>Najtrudniejsze (wg bieżących filtrów)</h3>
<table><thead><tr><th>ID</th><th>Dział</th><th>Odp.</th><th>Błędy</th><th>Trudność</th><th>Pytanie → poprawna odpowiedź</th></tr></thead><tbody id="tb"></tbody></table>
<details><summary>Jak liczona jest trudność (oś Y)</summary>
<p>Trudność = (błędy + 0,5) / (odpowiedzi + 1) — wygładzony odsetek błędów (prior Jeffreysa). Mała liczba odpowiedzi jest ściągana ku środkowi, ale błąd w jedynej odpowiedzi nadal daje wysoko:</p>
<ul><li>1 odpowiedź, 1 błąd → <b>0,75</b> &nbsp; (10/10 błędnych → 0,95; 3/3 → 0,88)</li>
<li>1 odpowiedź, 0 błędów → 0,25 &nbsp; (0/10 → 0,05)</li>
<li>10 odpowiedzi, 1 błąd (9 dobrych) → <b>0,14</b> &nbsp; (2/10 → 0,24; 5/10 → 0,50)</li></ul>
<p>Pytanie z jedną błędną odpowiedzią jest więc wysoko, a rosnąca liczba poprawnych odpowiedzi je obniża. Do dziennika trafia każda odpowiedź w nauce oraz błędne w TEŚCIE (poprawne w TEŚCIE nie są zapisywane).</p></details>
<div id="tip"></div>
<script>
const RAW=__DATA__;
const COL={Master:'--m',Angielski:'--e','Pokład':'--p'};
const cv=document.getElementById('cv'),ctx=cv.getContext('2d'),tip=document.getElementById('tip');
let pts=[],view={x0:0,x1:1},pinned=null,dragging=null,hover=null,dpr=1,W=0,H=0;
const M={l:46,r:14,t:12,b:34};
const css=n=>getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const score=(w,a)=>(w+0.5)/(a+1);
function build(){
 const merge=document.getElementById('merge').checked,cats=[...document.querySelectorAll('.cat')].filter(c=>c.checked).map(c=>c.value);
 const mina=+document.getElementById('mina').value,mind=+document.getElementById('mind').value/100;
 const map=new Map();
 for(const r of RAW){const key=merge&&r.g?'g'+r.g:'i'+r.id;let o=map.get(key);
  if(!o){o={id:r.id,ids:[],c:r.c,a:0,w:0,q:r.q,k:r.k};map.set(key,o)}
  o.a+=r.a;o.w+=r.w;o.ids.push(r.id);if(r.id<o.id){o.id=r.id;o.q=r.q;o.k=r.k;o.c=r.c}}
 pts=[...map.values()].filter(o=>cats.includes(o.c)&&o.a>=mina).map(o=>({...o,s:score(o.w,o.a)})).filter(o=>o.s>=mind);
 const all=RAW.map(r=>r.id);const lo=Math.min(...all),hi=Math.max(...all);
 if(view.x1<=view.x0||view.fresh!==false){view.x0=lo-20;view.x1=hi+20;view.min=view.x0;view.max=view.x1;view.fresh=false}
 document.getElementById('cnt').textContent=pts.length+' pytań na wykresie';
 table();draw();
}
function sx(x){return M.l+(x-view.x0)/(view.x1-view.x0)*(W-M.l-M.r)}
function sy(y){return M.t+(1-y)*(H-M.t-M.b)}
function rad(a){return Math.min(3+Math.sqrt(a)*1.1,12)}
function draw(){
 dpr=window.devicePixelRatio||1;const r=cv.getBoundingClientRect();W=r.width;H=r.height;cv.width=W*dpr;cv.height=H*dpr;ctx.setTransform(dpr,0,0,dpr,0,0);
 ctx.clearRect(0,0,W,H);ctx.font='12px system-ui';ctx.fillStyle=css('--mut');ctx.strokeStyle=css('--grid');ctx.lineWidth=1;
 for(let i=0;i<=10;i++){const y=sy(i/10);ctx.beginPath();ctx.moveTo(M.l,y);ctx.lineTo(W-M.r,y);ctx.stroke();ctx.textAlign='right';ctx.fillText((i/10).toFixed(1),M.l-6,y+4)}
 const span=view.x1-view.x0,step=Math.pow(10,Math.floor(Math.log10(span/6)))*([1,2,5].find(m=>span/(Math.pow(10,Math.floor(Math.log10(span/6)))*m)<=8)||10);
 ctx.textAlign='center';for(let x=Math.ceil(view.x0/step)*step;x<=view.x1;x+=step){const X=sx(x);ctx.beginPath();ctx.moveTo(X,M.t);ctx.lineTo(X,H-M.b);ctx.stroke();ctx.fillText(Math.round(x),X,H-M.b+16)}
 ctx.save();ctx.beginPath();ctx.rect(M.l,M.t,W-M.l-M.r,H-M.t-M.b);ctx.clip();
 for(const p of pts){const X=sx(p.id);if(X<M.l-12||X>W)continue;p._x=X;p._y=sy(p.s);p._r=rad(p.a);
  ctx.globalAlpha=.72;ctx.fillStyle=css(COL[p.c]||'--m');ctx.beginPath();ctx.arc(X,p._y,p._r,0,7);ctx.fill();
  if(p===pinned||p===hover){ctx.globalAlpha=1;ctx.lineWidth=2;ctx.strokeStyle=css('--fg');ctx.stroke();ctx.lineWidth=1;ctx.strokeStyle=css('--grid')}}
 ctx.restore();ctx.globalAlpha=1;ctx.fillStyle=css('--mut');ctx.textAlign='center';ctx.fillText('ID pytania',(M.l+W-M.r)/2,H-4);
 ctx.save();ctx.translate(12,(H)/2);ctx.rotate(-Math.PI/2);ctx.fillText('trudność',0,0);ctx.restore();
}
function nearest(mx,my){let best=null,bd=1e9;for(const p of pts){if(p._x==null)continue;const d=Math.hypot(p._x-mx,p._y-my);if(d<=p._r+4&&d<bd){bd=d;best=p}}return best}
function info(p){return `<b>ID ${p.ids.length>1?p.ids.sort((a,b)=>a-b).join(', '):p.id}</b> · ${p.c}<br>odpowiedzi: <b>${p.a}</b>, błędnych: <b>${p.w}</b> · trudność <b>${p.s.toFixed(2)}</b><br><span class="mut">${esc(p.q)}</span><br>→ <b>${esc(p.k)}</b>`}
const esc=s=>(s||'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
cv.addEventListener('mousemove',e=>{const r=cv.getBoundingClientRect(),mx=e.clientX-r.left,my=e.clientY-r.top;
 if(dragging){const dx=(mx-dragging.mx)/(W-M.l-M.r)*(view.x1-view.x0);view.x0=dragging.x0-dx;view.x1=dragging.x1-dx;clampView();draw();return}
 const p=nearest(mx,my);if(p!==hover){hover=p;draw()}
 if(p){tip.innerHTML=info(p);tip.style.display='block';const tw=tip.offsetWidth;tip.style.left=Math.min(e.clientX+14,innerWidth-tw-8)+'px';tip.style.top=Math.min(e.clientY+14,innerHeight-tip.offsetHeight-8)+'px'}else tip.style.display='none'});
cv.addEventListener('mouseleave',()=>{tip.style.display='none';hover=null;dragging=null;draw()});
cv.addEventListener('mousedown',e=>{const r=cv.getBoundingClientRect();dragging={mx:e.clientX-r.left,x0:view.x0,x1:view.x1,moved:0}});
addEventListener('mouseup',e=>{if(dragging){dragging=null}});
cv.addEventListener('click',e=>{const r=cv.getBoundingClientRect(),p=nearest(e.clientX-r.left,e.clientY-r.top);pinned=p;draw();if(p){const tr=document.querySelector('tr[data-id="'+p.id+'"]');if(tr){tr.scrollIntoView({block:'center'});tr.style.outline='2px solid '+css('--fg')}}});
function clampView(){const span=view.x1-view.x0,full=view.max-view.min;if(span>full){view.x0=view.min;view.x1=view.max;return}if(view.x0<view.min){view.x1+=view.min-view.x0;view.x0=view.min}if(view.x1>view.max){view.x0-=view.x1-view.max;view.x1=view.max}}
cv.addEventListener('wheel',e=>{e.preventDefault();const r=cv.getBoundingClientRect(),mx=e.clientX-r.left,f=(mx-M.l)/(W-M.l-M.r),c=view.x0+f*(view.x1-view.x0),k=e.deltaY<0?0.8:1.25;
 view.x0=c-(c-view.x0)*k;view.x1=c+(view.x1-c)*k;if(view.x1-view.x0<15){view.x0=c-7.5;view.x1=c+7.5}clampView();draw()},{passive:false});
function table(){const top=[...pts].sort((a,b)=>b.s-a.s||b.a-a.a||a.id-b.id).slice(0,150);
 document.getElementById('tb').innerHTML=top.map(p=>`<tr class="row" data-id="${p.id}"><td>${p.id}</td><td>${p.c}</td><td>${p.a}</td><td>${p.w}</td><td>${p.s.toFixed(2)}</td><td>${esc(p.q)}<br><b>→ ${esc(p.k)}</b></td></tr>`).join('');
 document.querySelectorAll('tr.row').forEach(tr=>tr.onclick=()=>{pinned=pts.find(p=>p.id==tr.dataset.id)||null;if(pinned){const c=pinned.id,sp=view.x1-view.x0;if(c<view.x0||c>view.x1){view.x0=c-sp/2;view.x1=c+sp/2;clampView()}}draw()})}
document.querySelectorAll('.cat,#merge').forEach(el=>el.onchange=build);
document.getElementById('mina').oninput=e=>{document.getElementById('minav').textContent=e.target.value;build()};
document.getElementById('mind').oninput=e=>{document.getElementById('mindv').textContent=(e.target.value/100).toFixed(2);build()};
document.getElementById('reset').onclick=()=>{view.x0=view.min;view.x1=view.max;draw()};
addEventListener('resize',draw);matchMedia('(prefers-color-scheme:dark)').onchange=draw;build();
</script></body></html>"""

OUT.write_text(HTML.replace("__DATA__", json.dumps(data, ensure_ascii=False, separators=(",", ":")))
               .replace("__TOTAL__", str(total[0])).replace("__WRONG__", str(total[1] or 0)), encoding="utf-8")
print("zapisano", OUT, "| pytań z odpowiedziami:", len(data), "| rozmiar KB:", OUT.stat().st_size // 1024)
