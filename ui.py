# ==============================================================================
#  Iliya Gateway  —  ui.py
#  قالب‌های HTML کاملاً اورجینال: لاگین ، داشبورد مدیریتی ، صفحه‌ی عمومی کانفیگ
#  طراحی مدرن ، راست‌چین ، حالت تاریک خودکار
#  (برای جلوگیری از دردسر escape شدن { } از f-string استفاده نشده؛ فقط __BRAND__ و ... جایگزین می‌شوند)
# ==============================================================================
import json

_BASE_CSS = """
:root{
  --text:#1F1F1E;--text2:#7D7A75;--canvas:#FFFFFF;--soft:#F7F6F4;--surface:#F0EFED;
  --border:#E6E5E3;--blue:#2783DE;--blue-soft:#E5F2FC;--green:#46A171;--green-soft:#E8F1EC;
  --orange:#D5803B;--orange-soft:#FBEBDE;--red:#E56458;--red-soft:#FCE9E7;--violet:#8E63C6;
  --radius:14px;
}
@media(prefers-color-scheme:dark){:root{
  --text:#FFFFFF;--text2:rgba(255,255,255,.62);--canvas:#161616;--soft:#1E1E1E;--surface:#262625;
  --border:rgba(255,255,255,.13);--blue:#5E9FE8;--blue-soft:rgba(94,159,232,.14);--green:#72BC8F;
  --green-soft:rgba(114,188,143,.14);--orange:#DE9255;--orange-soft:rgba(222,146,85,.14);
  --red:#E97366;--red-soft:rgba(233,115,102,.14);--violet:#B18CE0;}}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Segoe UI',Tahoma,system-ui,-apple-system,sans-serif;background:var(--canvas);
  color:var(--text);line-height:1.7;-webkit-font-smoothing:antialiased}
a{color:inherit;text-decoration:none}
.brandlogo{width:34px;height:34px;border-radius:10px;flex:0 0 auto;
  background:conic-gradient(from 210deg,#2783DE,#8E63C6,#46A171,#2783DE);
  box-shadow:0 4px 14px rgba(39,131,222,.4)}
button{font-family:inherit;cursor:pointer;border:none}
.btn{display:inline-flex;align-items:center;justify-content:center;gap:7px;font-weight:700;
  font-size:14px;padding:10px 17px;border-radius:11px;transition:transform .15s,box-shadow .15s,background .15s}
.btn:hover{transform:translateY(-1px)}
.btn-primary{background:var(--blue);color:#fff;box-shadow:0 5px 16px rgba(39,131,222,.32)}
.btn-ghost{background:transparent;color:var(--text);border:1px solid var(--border)}
.btn-ghost:hover{background:var(--soft)}
.btn-danger{background:var(--red-soft);color:var(--red)}
.btn-sm{padding:6px 12px;font-size:13px;border-radius:9px}
input,select{font-family:inherit;font-size:14px;padding:11px 13px;border-radius:10px;
  border:1px solid var(--border);background:var(--canvas);color:var(--text);width:100%}
input:focus,select:focus{outline:none;border-color:var(--blue)}
label{font-size:13px;color:var(--text2);font-weight:600;display:block;margin-bottom:6px}
"""

# ────────────────────────────────────────────── LOGIN ──────────────────
_LOGIN = """<!DOCTYPE html><html lang="fa" dir="rtl"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>__BRAND__ — ورود</title>
<style>__CSS__
.wrap{min-height:100vh;display:grid;place-items:center;padding:24px;position:relative;overflow:hidden}
.aur{position:absolute;filter:blur(80px);opacity:.5;border-radius:50%;z-index:0}
.a1{width:360px;height:360px;background:var(--blue);top:-90px;right:-60px}
.a2{width:320px;height:320px;background:var(--violet);bottom:-90px;left:-60px}
.card{position:relative;z-index:2;background:var(--soft);border:1px solid var(--border);
  border-radius:20px;padding:38px 32px;width:100%;max-width:380px;text-align:center;
  box-shadow:0 20px 50px rgba(0,0,0,.10)}
.card .brandlogo{margin:0 auto 18px}
h1{font-size:24px;font-weight:900;margin-bottom:6px}
p.sub{color:var(--text2);font-size:14px;margin-bottom:26px}
.field{text-align:right;margin-bottom:16px}
.err{color:var(--red);font-size:13px;min-height:18px;margin-bottom:8px}
</style></head><body>
<div class="wrap"><div class="aur a1"></div><div class="aur a2"></div>
<div class="card">
  <div class="brandlogo"></div>
  <h1>__BRAND__ Panel</h1>
  <p class="sub">برای ورود به داشبورد مدیریت، رمز عبور را وارد کنید</p>
  <div class="field"><label>رمز عبور</label>
    <input id="pw" type="password" placeholder="********" onkeydown="if(event.key==='Enter')go()"></div>
  <div class="err" id="err"></div>
  <button class="btn btn-primary" style="width:100%" onclick="go()">ورود ←</button>
</div></div>
<script>
async function go(){
  const pw=document.getElementById('pw').value;const err=document.getElementById('err');err.textContent='';
  try{
    const r=await fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({password:pw})});
    if(r.ok){location.href='/dashboard';}
    else{const d=await r.json().catch(()=>({}));err.textContent=d.detail||'رمز اشتباه است';}
  }catch(e){err.textContent='خطا در ارتباط';}
}
</script></body></html>"""

# ───────────────────────────────────────── DASHBOARD ──────────────
_DASH = """<!DOCTYPE html><html lang="fa" dir="rtl"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>__BRAND__ — داشبورد</title>
<style>__CSS__
.top{position:sticky;top:0;z-index:40;background:color-mix(in srgb,var(--canvas) 82%,transparent);
  backdrop-filter:blur(14px);border-bottom:1px solid var(--border)}
.top .in{max-width:1080px;margin:0 auto;padding:14px 22px;display:flex;align-items:center;justify-content:space-between}
.top .brand{display:flex;align-items:center;gap:10px;font-weight:900;font-size:19px}
.main{max-width:1080px;margin:0 auto;padding:26px 22px 60px}
.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:24px}
.stats{grid-template-columns:repeat(4,1fr)}
@media(max-width:820px){.stats{grid-template-columns:repeat(2,1fr)}}
.stat{background:var(--soft);border:1px solid var(--border);border-radius:var(--radius);padding:18px}
.stat .l{font-size:13px;color:var(--text2);margin-bottom:8px;display:flex;align-items:center;gap:6px}
.stat .n{font-size:26px;font-weight:900}
.dot{width:8px;height:8px;border-radius:50%;display:inline-block}
.panel{background:var(--soft);border:1px solid var(--border);border-radius:16px;padding:22px;margin-bottom:20px}
.panel h2{font-size:17px;font-weight:800;margin-bottom:16px;display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap}
.form-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}
@media(max-width:820px){.form-grid{grid-template-columns:1fr}}
.cfg{background:var(--canvas);border:1px solid var(--border);border-radius:13px;padding:16px;margin-bottom:12px}
.cfg .hd{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:10px;flex-wrap:wrap}
.cfg .title{font-weight:800;font-size:15px;display:flex;align-items:center;gap:8px}
.badge{font-size:11px;font-weight:800;padding:3px 9px;border-radius:999px}
.b-on{background:var(--green-soft);color:var(--green)}
.b-off{background:var(--red-soft);color:var(--red)}
.b-test{background:var(--orange-soft);color:var(--orange)}
.meta{display:flex;gap:16px;flex-wrap:wrap;font-size:13px;color:var(--text2);margin-bottom:10px}
.bar{height:7px;background:var(--surface);border-radius:999px;overflow:hidden;margin-bottom:12px}
.bar>i{display:block;height:100%;border-radius:999px;transition:width .4s}
.cfg .acts{display:flex;gap:7px;flex-wrap:wrap}
.link-row{display:flex;gap:7px;margin-bottom:12px}
.link-row input{font-size:12px;direction:ltr;text-align:left;color:var(--text2)}
.act-log{display:flex;flex-direction:column}
.act{display:flex;gap:12px;padding:10px 0;border-bottom:1px solid var(--border);font-size:14px}
.act:last-child{border-bottom:none}
.act .t{color:var(--text2);font-size:12px;white-space:nowrap}
.empty{text-align:center;color:var(--text2);padding:30px;font-size:14px}
.toast{position:fixed;bottom:24px;left:50%;transform:translateX(-50%) translateY(80px);
  background:var(--text);color:var(--canvas);padding:12px 22px;border-radius:12px;font-weight:700;
  font-size:14px;z-index:99;opacity:0;transition:.3s;box-shadow:0 10px 30px rgba(0,0,0,.2)}
.toast.show{transform:translateX(-50%) translateY(0);opacity:1}
.tabs{display:flex;gap:8px;margin-bottom:20px}
.tab{padding:9px 18px;border-radius:11px;font-weight:700;font-size:14px;cursor:pointer;
  border:1px solid var(--border);background:var(--soft);color:var(--text2)}
.tab.on{background:var(--blue);color:#fff;border-color:var(--blue)}
.hide{display:none}
</style></head><body>
<div class="top"><div class="in">
  <div class="brand"><span class="brandlogo"></span> __BRAND__ <span style="color:var(--text2);font-weight:600;font-size:13px">Gateway</span></div>
  <div style="display:flex;gap:8px">
    <button class="btn btn-ghost btn-sm" onclick="changePw()">🔑 رمز</button>
    <button class="btn btn-ghost btn-sm" onclick="logout()">خروج</button>
  </div>
</div></div>
<div class="main">
  <div class="stats" id="stats"></div>
  <div class="tabs">
    <div class="tab on" data-t="configs" onclick="tab('configs')">🔌 کانفیگ‌ها</div>
    <div class="tab" data-t="activity" onclick="tab('activity')">📜 فعالیت‌ها</div>
  </div>
  <div id="tab-configs">
    <div class="panel">
      <h2>➕ ساخت کانفیگ جدید</h2>
      <div class="form-grid">
        <div><label>نام / برچسب</label><input id="f-label" placeholder="مثلاً Ali"></div>
        <div><label>مالک (اختیاری)</label><input id="f-owner" placeholder="__BRAND__"></div>
        <div><label>حجم (GB) — 0=نامحدود</label><input id="f-gb" type="number" value="0" min="0"></div>
        <div><label>مدت (روز) — 0=دائمی</label><input id="f-days" type="number" value="0" min="0"></div>
        <div><label>محدودیت کاربر/IP</label><input id="f-ip" type="number" value="0" min="0"></div>
        <div><label>سرعت (Mbps) — 0=نامحدود</label><input id="f-speed" type="number" value="0" min="0"></div>
      </div>
      <button class="btn btn-primary" style="margin-top:16px" onclick="createCfg()">✨ بساز</button>
    </div>
    <div class="panel">
      <h2>کانفیگ‌ها <input id="search" placeholder="🔍 جست‌وجو..." style="max-width:220px" oninput="render()"></h2>
      <div id="list"></div>
    </div>
  </div>
  <div id="tab-activity" class="hide">
    <div class="panel"><h2>📜 آخرین فعالیت‌ها</h2><div class="act-log" id="acts"></div></div>
  </div>
</div>
<div class="toast" id="toast"></div>
<script>
let DATA=[];
function toast(m){const t=document.getElementById('toast');t.textContent=m;t.classList.add('show');
  clearTimeout(window._tt);window._tt=setTimeout(()=>t.classList.remove('show'),2600);}
function esc(s){return (s||'').toString().replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));}
async function api(u,m,b){
  const o={method:m||'GET',headers:{'Content-Type':'application/json'}};
  if(b)o.body=JSON.stringify(b);
  const r=await fetch(u,o);
  if(r.status===401){location.href='/login';throw 'unauth';}
  if(!r.ok){const d=await r.json().catch(()=>({}));throw (d.detail||'خطا');}
  return r.json();
}
function tab(t){
  document.querySelectorAll('.tab').forEach(x=>x.classList.toggle('on',x.dataset.t===t));
  document.getElementById('tab-configs').classList.toggle('hide',t!=='configs');
  document.getElementById('tab-activity').classList.toggle('hide',t!=='activity');
}
async function loadStats(){
  const s=await api('/api/stats');
  document.getElementById('stats').innerHTML=
   '<div class="stat"><div class="l">🔌 کل کانفیگ‌ها</div><div class="n">'+s.total_configs+'</div></div>'+
   '<div class="stat"><div class="l"><span class="dot" style="background:var(--green)"></span> فعال</div><div class="n">'+s.active_configs+'</div></div>'+
   '<div class="stat"><div class="l">📡 اتصالات زنده</div><div class="n">'+s.live_connections+'</div></div>'+
   '<div class="stat"><div class="l">📊 ترافیک کل</div><div class="n" style="font-size:20px">'+s.total_bytes_fmt+'</div></div>';
  document.getElementById('acts').innerHTML=(s.activity||[]).map(function(a){
    return '<div class="act"><span class="t">'+new Date(a.time).toLocaleString('fa-IR')+'</span><span>'+esc(a.msg)+'</span></div>';
  }).join('')||'<div class="empty">فعالیتی ثبت نشده</div>';
}
async function loadCfgs(){const d=await api('/api/configs');DATA=d.configs||[];render();}
function render(){
  const q=(document.getElementById('search').value||'').toLowerCase();
  const items=DATA.filter(c=>!q||(c.label||'').toLowerCase().includes(q)||(c.owner||'').toLowerCase().includes(q));
  const el=document.getElementById('list');
  if(!items.length){el.innerHTML='<div class="empty">کانفیگی یافت نشد</div>';return;}
  el.innerHTML=items.map(function(c){
    const badge=c.is_test?'<span class="badge b-test">🧪 تست</span>':
      (c.allowed?'<span class="badge b-on">فعال</span>':'<span class="badge b-off">غیرفعال</span>');
    const exp=c.expires_at?new Date(c.expires_at).toLocaleDateString('fa-IR'):'دائمی';
    const color=c.percent>=90?'var(--red)':(c.percent>=70?'var(--orange)':'var(--green)');
    const link=esc(c.link);
    return '<div class="cfg">'+
      '<div class="hd"><div class="title">🔑 '+esc(c.label)+' '+badge+'</div>'+
        '<div style="color:var(--text2);font-size:12px">👤 '+esc(c.owner)+'</div></div>'+
      '<div class="meta"><span>📊 '+c.used_fmt+' / '+c.limit_fmt+'</span>'+
        '<span>⏳ '+exp+'</span><span>👥 '+(c.ip_limit||'—')+'</span></div>'+
      '<div class="bar"><i style="width:'+c.percent+'%;background:'+color+'"></i></div>'+
      '<div class="link-row"><input readonly value="'+link+'" onclick="this.select()">'+
        '<button class="btn btn-ghost btn-sm" onclick="copy(this.previousElementSibling.value)">📋</button></div>'+
      '<div class="acts">'+
        '<button class="btn btn-ghost btn-sm" onclick="toggle(\''+c.uuid+'\','+(!c.active)+')">'+(c.active?'⏸ غیرفعال':'▶ فعال')+'</button>'+
        '<button class="btn btn-ghost btn-sm" onclick="addDays(\''+c.uuid+'\')">➕ روز</button>'+
        '<button class="btn btn-ghost btn-sm" onclick="resetU(\''+c.uuid+'\')">🔄 ریست</button>'+
        '<button class="btn btn-ghost btn-sm" onclick="copy(location.origin+\'/sub/'+c.uuid+'\')">🔗 ساب</button>'+
        '<button class="btn btn-danger btn-sm" onclick="delCfg(\''+c.uuid+'\')">🗑 حذف</button>'+
      '</div></div>';
  }).join('');
}
function copy(t){navigator.clipboard.writeText(t).then(()=>toast('کپی شد ✅'));}
async function createCfg(){
  try{await api('/api/configs','POST',{
    label:document.getElementById('f-label').value,owner:document.getElementById('f-owner').value,
    gb:document.getElementById('f-gb').value,days:document.getElementById('f-days').value,
    ip_limit:document.getElementById('f-ip').value,speed:document.getElementById('f-speed').value});
    toast('کانفیگ ساخته شد ✨');document.getElementById('f-label').value='';await loadCfgs();await loadStats();
  }catch(e){toast(''+e);}
}
async function toggle(u,a){try{await api('/api/configs/'+u,'PATCH',{active:a});await loadCfgs();await loadStats();}catch(e){toast(''+e);}}
async function addDays(u){const d=prompt('چند روز اضافه شود؟','30');if(!d)return;
  try{await api('/api/configs/'+u,'PATCH',{add_days:parseInt(d)});toast('انجام شد ✅');await loadCfgs();}catch(e){toast(''+e);}}
async function resetU(u){if(!confirm('مصرف صفر شود؟'))return;
  try{await api('/api/configs/'+u,'PATCH',{reset_usage:true});toast('ریست شد ✅');await loadCfgs();}catch(e){toast(''+e);}}
async function delCfg(u){if(!confirm('این کانفیگ حذف شود؟'))return;
  try{await api('/api/configs/'+u,'DELETE');toast('حذف شد 🗑');await loadCfgs();await loadStats();}catch(e){toast(''+e);}}
async function changePw(){const p=prompt('رمز جدید (حداقل ۴ کاراکتر):');if(!p)return;
  try{await api('/api/change-password','POST',{password:p});toast('رمز عوض شد ✅');}catch(e){toast(''+e);}}
async function logout(){await api('/api/logout','POST').catch(()=>{});location.href='/login';}
async function boot(){try{await loadStats();await loadCfgs();}catch(e){}}
boot();setInterval(function(){loadStats().catch(()=>{});},10000);
</script></body></html>"""

# ─────────────────────────────────── PUBLIC SUB PAGE ─────────────────
_SUB = """<!DOCTYPE html><html lang="fa" dir="rtl"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>__BRAND__ — __LABEL__</title>
<style>__CSS__
.wrap{min-height:100vh;display:grid;place-items:center;padding:24px}
.card{background:var(--soft);border:1px solid var(--border);border-radius:20px;padding:30px;
  width:100%;max-width:420px;box-shadow:0 20px 50px rgba(0,0,0,.10)}
.hd{display:flex;align-items:center;gap:10px;margin-bottom:22px}
.hd h1{font-size:20px;font-weight:900;flex:1}
.st{font-size:12px;font-weight:800;padding:4px 12px;border-radius:999px}
.row{display:flex;justify-content:space-between;padding:11px 0;border-bottom:1px solid var(--border);font-size:14px}
.row .l{color:var(--text2)}
.bar{height:8px;background:var(--surface);border-radius:999px;overflow:hidden;margin:18px 0}
.bar>i{display:block;height:100%;border-radius:999px}
.linkbox{background:var(--canvas);border:1px solid var(--border);border-radius:11px;padding:13px;
  font-size:12px;direction:ltr;text-align:left;word-break:break-all;color:var(--text2);margin:18px 0}
</style></head><body><div class="wrap"><div class="card">
  <div class="hd"><span class="brandlogo"></span><h1>__BRAND__</h1>
    <span class="st" style="background:color-mix(in srgb,__COLOR__ 16%,transparent);color:__COLOR__">__STATUS__</span></div>
  <div class="row"><span class="l">نام</span><span>__LABEL__</span></div>
  <div class="row"><span class="l">مصرف</span><span>__USED__ / __LIMIT__</span></div>
  <div class="row"><span class="l">انقضا</span><span>__EXP__</span></div>
  <div class="bar"><i style="width:__PCT__%;background:__COLOR__"></i></div>
  <div class="linkbox" id="lnk">__LINK__</div>
  <button class="btn btn-primary" style="width:100%" onclick="cp()">📋 کپی لینک اتصال</button>
</div></div>
<script>function cp(){navigator.clipboard.writeText(document.getElementById('lnk').textContent).then(()=>{
  const b=document.querySelector('.btn');b.textContent='✅ کپی شد';setTimeout(()=>b.textContent='📋 کپی لینک اتصال',1800);});}</script>
</body></html>"""


def login_html(brand: str) -> str:
    return _LOGIN.replace("__CSS__", _BASE_CSS).replace("__BRAND__", brand)


def dashboard_html(brand: str) -> str:
    return _DASH.replace("__CSS__", _BASE_CSS).replace("__BRAND__", brand)


def sub_page_html(brand: str, c: dict) -> str:
    status = "تست" if c["is_test"] else ("فعال" if c["allowed"] else "غیرفعال")
    color = "#D5803B" if c["is_test"] else ("#46A171" if c["allowed"] else "#E56458")
    exp = c["expires_at"] or "دائمی"
    if c["expires_at"]:
        exp = c["expires_at"][:10]
    link = c["link"]
    out = (_SUB.replace("__CSS__", _BASE_CSS)
           .replace("__BRAND__", brand)
           .replace("__LABEL__", str(c["label"]))
           .replace("__STATUS__", status)
           .replace("__COLOR__", color)
           .replace("__USED__", c["used_fmt"])
           .replace("__LIMIT__", c["limit_fmt"])
           .replace("__EXP__", exp)
           .replace("__PCT__", str(c["percent"]))
           .replace("__LINK__", link))
    return out
