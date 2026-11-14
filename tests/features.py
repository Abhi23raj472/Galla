"""Checks for the newer Galla features. Run: python tests/features.py
Covers the daily allowance with upcoming recurring payments, category limit alerts,
UPI payments, bank statement import, and two-device login/sync against a fake Supabase."""
import json, os, sys, threading, http.server, functools
from playwright.sync_api import sync_playwright
if hasattr(sys.stdout,"reconfigure"): sys.stdout.reconfigure(encoding="utf-8")
DIR=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIX=os.path.join(DIR,"tests","fixtures")
srv=http.server.ThreadingHTTPServer(("127.0.0.1",8771),functools.partial(http.server.SimpleHTTPRequestHandler,directory=DIR))
srv.RequestHandlerClass.log_message=lambda *a:None
threading.Thread(target=srv.serve_forever,daemon=True).start()
URL="http://127.0.0.1:8771/index.html"
NOW="2026-11-14T18:00:00+05:30"   # tests use a fixed "today" so date maths is stable
results=[]
def check(n,c,info=""):
    results.append(bool(c)); print(("PASS " if c else "FAIL ")+n+("" if c else f"  [{info}]"))

# ---- allowance, alerts and UPI
data={"txns":[
 {"id":"e1","amount":1900,"desc":"Dinners","cat":"Food & dining","pay":"UPI","type":"expense","date":"2026-11-08","created":1},
 {"id":"e2","amount":4200,"desc":"Shoes","cat":"Shopping","pay":"Card","type":"expense","date":"2026-11-09","created":2},
 {"id":"x1","amount":600,"desc":"Cab to airport","cat":"Transport","pay":"UPI","type":"expense","date":"2026-11-11","created":3,
  "split":{"group":None,"paidBy":"p1","total":1200,"shares":{"me":600,"p1":600},"mode":"equal","vals":{}}}],
 "rules":[{"id":"ru1","desc":"Netflix","amount":649,"cat":"Entertainment","pay":"Card","type":"expense","day":25,"start":"2026-10","active":True,"skip":[]},
          {"id":"ru2","desc":"Rent","amount":3000,"cat":"Rent & housing","pay":"Auto-debit","type":"expense","day":28,"start":"2026-10","active":True,"skip":[]}],
 "people":[{"id":"p1","name":"Rahul","upi":"rahul.k@okaxis","created":1}],"groups":[],
 "settings":{"budget":20000,"catBudgets":{"Food & dining":2000,"Shopping":4000,"Transport":5000},"profile":{"name":"Abhishek Kumar"},"preferences":{}}}
with sync_playwright() as p:
    b=p.chromium.launch(); pg=b.new_page(viewport={"width":1440,"height":1000}); pg.clock.set_fixed_time(NOW); errs=[]; pg.on("pageerror",lambda e:errs.append(str(e)))
    pg.goto(URL); pg.evaluate("d=>localStorage.setItem('kharcha-ledger-v2',JSON.stringify(d))",data); pg.reload(); pg.wait_for_function("ready.txns")
    note=pg.inner_text("#budgetText"); print("note:",note)
    spent=1900+4200+600; left=20000-spent; due=649+3000; rem=30-14+1
    check("allowance subtracts upcoming recurring", f"₹{(left-due)//rem:,}" in note and "₹3,649" in note, note)
    al=pg.inner_text("#catAlerts"); print("alerts:",al.replace("\n"," | "))
    check("food near/over alert", "Food & dining is at 95% of its ₹2,000 limit" in al, al)
    check("shopping over alert", "Shopping is ₹200 over its ₹4,000 limit" in al, al)
    check("transport not alerted", "Transport" not in al)
    pg.click('#topTabs [data-tab="split"]'); pg.click('#friends [data-p="p1"]'); pg.wait_for_timeout(300)
    href=pg.get_attribute("#dUpiPay","href"); print("href:",href)
    check("UPI link correct", href=="upi://pay?pa=rahul.k%40okaxis&pn=Rahul&am=600.00&cu=INR&tn=Galla%20settle-up", href)
    pg.evaluate("document.getElementById('dUpiPay').addEventListener('click',e=>e.preventDefault())")
    pg.click("#dUpiPay"); check("record button appears", pg.is_visible("#dUpiDone"))
    pg.click("#dUpiDone"); pg.wait_for_timeout(400)
    check("settled after recording", abs(pg.evaluate("balancesWithMe()['p1']||0"))<0.01, pg.evaluate("JSON.stringify(balancesWithMe())"))
    pg.fill("#dUpiEdit","not a upi"); pg.click("#dSaveUpi"); pg.wait_for_timeout(200)
    check("invalid UPI rejected", pg.evaluate("people[0].upi")=="rahul.k@okaxis")
    check("no JS errors", not errs, errs)

# ---- bank statement import
seed={"txns":[{"id":"e0","amount":2200,"desc":"Groceries","cat":"Groceries","pay":"UPI","type":"expense","date":"2026-11-10","created":1}],"rules":[],"people":[],"groups":[],"settings":{"budget":0,"catBudgets":{},"profile":{},"preferences":{}}}
with sync_playwright() as p:
    b=p.chromium.launch(); pg=b.new_page(viewport={"width":1440,"height":1000}); pg.clock.set_fixed_time(NOW); errs=[]; pg.on("pageerror",lambda e:errs.append(str(e)))
    pg.goto(URL); pg.evaluate("d=>localStorage.setItem('kharcha-ledger-v2',JSON.stringify(d))",seed); pg.reload(); pg.wait_for_function("ready.txns")
    pg.click('#topTabs [data-tab="transactions"]'); pg.click("#importBtn")
    pg.set_input_files("#impFile",os.path.join(FIX,"hdfc.csv")); pg.wait_for_selector(".imp-row")
    items=pg.evaluate("JSON.stringify(detailState.items.map(x=>[x.date,x.type,x.amount,x.desc,x.cat,x.pay,x.dup]))"); it=json.loads(items)
    for r in it: print("  ",r)
    check("hdfc: 5 rows, footer skipped", len(it)==5, len(it))
    check("hdfc: swiggy parsed", it[0]==["2026-11-01","expense",1240.5,"Swiggy","Food & dining","UPI",False], it[0])
    check("hdfc: salary is income", it[2][1]=="income" and it[2][4]=="Salary" and it[2][2]==85000, it[2])
    check("hdfc: amazon card shopping", it[3][4]=="Shopping" and it[3][5]=="Card", it[3])
    check("hdfc: duplicate groceries unticked", it[4][6] is True and pg.evaluate("detailState.items[4].on")==False)
    pg.click("#impSave"); pg.wait_for_timeout(500)
    check("hdfc: 4 entries added", pg.evaluate("txns.length")==5, pg.evaluate("txns.length"))
    pg.reload(); pg.wait_for_function("ready.txns"); check("persisted after reload", pg.evaluate("txns.length")==5)
    pg.click('#topTabs [data-tab="transactions"]'); pg.click("#importBtn"); pg.set_input_files("#impFile",os.path.join(FIX,"sbi.csv")); pg.wait_for_selector(".imp-row")
    it=json.loads(pg.evaluate("JSON.stringify(detailState.items.map(x=>[x.date,x.type,x.amount,x.desc,x.cat,x.pay]))"))
    for r in it: print("  ",r)
    check("sbi: uber transport", it[0][:2]==["2026-11-02","expense"] and it[0][4]=="Transport" and it[0][3]=="Uber India", it[0])
    check("sbi: credit income", it[1][1]=="income" and it[1][2]==600, it[1])
    check("sbi: atm cash", it[2][5]=="Cash" and it[2][2]==2000, it[2])
    pg.click("#impBack"); pg.set_input_files("#impFile",os.path.join(FIX,"icici.csv")); pg.wait_for_selector(".imp-row")
    it=json.loads(pg.evaluate("JSON.stringify(detailState.items.map(x=>[x.date,x.type,x.amount,x.desc,x.cat,x.pay]))"))
    for r in it: print("  ",r)
    check("icici: netflix expense auto-debit", it[0][1]=="expense" and it[0][4]=="Entertainment" and it[0][5]=="Auto-debit", it[0])
    check("icici: interest income", it[1][1]=="income" and it[1][4]=="Interest", it[1])
    pg.click('.imp-type[data-type="0"]'); check("type toggle", pg.evaluate("detailState.items[0].type")=="income")
    pg.set_viewport_size({"width":390,"height":844}); pg.wait_for_timeout(200)
    check("no sideways scroll on phone", pg.evaluate("document.documentElement.scrollWidth<=innerWidth"))
    check("no JS errors", not errs, errs)

# ---- login and sync
TABLE={}; CALLS=[]
def db(op,payload):
    p=json.loads(payload); CALLS.append(op)
    uid=p.get("user_id")
    if op=="select":
        r=TABLE.get(uid); return json.dumps({"data":(None if not r else {k:r[k] for k in p["cols"]}),"error":None})
    if op=="insert":
        if uid in TABLE: return json.dumps({"error":{"code":"23505"}})
        TABLE[uid]={"data":json.loads(json.dumps(p["row"]["data"],sort_keys=True)),"version":p["row"]["version"]}; return json.dumps({"error":None})
    if op=="update":
        r=TABLE.get(uid)
        if not r or r["version"]!=p["version"]: return json.dumps({"data":[],"error":None})
        r["data"]=json.loads(json.dumps(p["row"]["data"],sort_keys=True)); r["version"]=p["row"]["version"]
        return json.dumps({"data":[{"version":r["version"]}],"error":None})
FAKE="""
(()=>{let session=null,cbs=[];
const user=e=>({id:'u-'+e,email:e});
function from(){const st={f:{}};const b={
  select(c){if(!st.op)st.op='select';st.cols=c.split(',');return b},
  insert(row){st.op='insert';st.row=row;return b},
  update(row){st.op='update';st.row=row;return b},
  eq(k,v){st.f[k]=v;return b},
  async run(){const r=JSON.parse(await window.fakeDb(st.op,JSON.stringify({user_id:st.f.user_id||(st.row&&st.row.user_id),version:st.f.version,cols:st.cols,row:st.row})));return r},
  maybeSingle(){return b.run()},
  then(a,c){return b.run().then(a,c)}};return b}
window.supabase={createClient:()=>({
  auth:{getSession:async()=>({data:{session}}),onAuthStateChange:cb=>{cbs.push(cb);return {data:{subscription:{unsubscribe(){}}}}},
        signInWithOtp:async({email})=>({error:null}),signOut:async()=>{session=null;cbs.forEach(c=>c('SIGNED_OUT',null));return {error:null}}},
  from})};
window.__fakeLogin=e=>{session={user:user(e)};cbs.forEach(c=>c('SIGNED_IN',session))};
})();"""
seed={"txns":[{"id":"e1","amount":250,"desc":"Lunch","cat":"Food & dining","pay":"UPI","type":"expense","date":"2026-11-03","created":1},
              {"id":"e2","amount":900,"desc":"Auto","cat":"Transport","pay":"UPI","type":"expense","date":"2026-11-04","created":2}],
      "rules":[],"people":[],"groups":[],"settings":{"budget":10000,"catBudgets":{},"profile":{"name":"Abhishek"},"preferences":{}}}
def device(b):
    ctx=b.new_context(viewport={"width":1280,"height":900})
    ctx.expose_function("fakeDb",db); ctx.add_init_script(FAKE)
    ctx.route("**/config.js",lambda r:r.fulfill(content_type="application/javascript",body='window.GALLA_CONFIG={supabaseUrl:"https://fake.supabase.co",supabaseAnonKey:"anon"};'))
    pg=ctx.new_page(); pg.clock.set_fixed_time(NOW); pg.errs=[]; pg.on("pageerror",lambda e:pg.errs.append(str(e))); return pg
def ids(pg): return sorted(pg.evaluate("txns.map(t=>t.id)"))
def wait_synced(pg): pg.wait_for_function("cloud.state==='synced'&&!cloud.busy",timeout=8000)
with sync_playwright() as p:
    b=p.chromium.launch()
    A=device(b); A.goto(URL); A.evaluate("d=>localStorage.setItem('kharcha-ledger-v2',JSON.stringify(d))",seed); A.reload(); A.wait_for_function("ready.txns")
    A.click('#topTabs [data-tab="profile"]'); check("signed-out card shows email form", A.is_visible("#acctEmail"))
    A.fill("#acctEmail","abhi@example.com"); A.click("#acctSend"); A.wait_for_timeout(200)
    check("link-sent message", "emailed a sign-in link" in A.inner_text("#accountCard"))
    A.evaluate("__fakeLogin('abhi@example.com')"); wait_synced(A)
    check("A uploaded ledger", TABLE["u-abhi@example.com"]["version"]==1 and len(TABLE["u-abhi@example.com"]["data"]["txns"])==2)
    check("A shows signed in", "Signed in as" in A.inner_text("#accountCard") and A.inner_text("#sideSync")=="Synced")
    B=device(b); B.goto(URL); B.wait_for_function("ready.txns"); B.evaluate("__fakeLogin('abhi@example.com')"); wait_synced(B)
    check("B pulled A's entries", ids(B)==["e1","e2"], ids(B))
    check("B got settings", B.evaluate("settings.budget")==10000)
    B.fill("#qAmount","120"); B.fill("#qDesc","Chai"); B.click("#qSave"); B.wait_for_timeout(900); wait_synced(B)
    check("B pushed new entry (v2)", TABLE["u-abhi@example.com"]["version"]==2 and len(TABLE["u-abhi@example.com"]["data"]["txns"])==3)
    A.evaluate("checkRemote()"); A.wait_for_timeout(500); wait_synced(A)
    check("A received B's entry", len(ids(A))==3, ids(A))
    # concurrent edits: A deletes e1 offline while B adds an entry
    A.evaluate("cloud.busy=true; txns=txns.filter(t=>t.id!=='e1'); store.commitLedger()")
    B.fill("#qAmount","60"); B.fill("#qDesc","Bus"); B.click("#qSave"); B.wait_for_timeout(900); wait_synced(B)
    A.evaluate("cloud.busy=false; syncNow()"); A.wait_for_timeout(600); wait_synced(A)
    a_ids=ids(A); remote_ids=sorted(t["id"] for t in TABLE["u-abhi@example.com"]["data"]["txns"])
    check("merge: e1 deleted, B's two entries kept", "e1" not in a_ids and len(a_ids)==3 and a_ids==remote_ids, (a_ids,remote_ids))
    B.evaluate("checkRemote()"); B.wait_for_timeout(500); wait_synced(B)
    check("B converges to same ledger", ids(B)==remote_ids, (ids(B),remote_ids))
    check("version advanced to 4", TABLE["u-abhi@example.com"]["version"]==4, TABLE["u-abhi@example.com"]["version"])
    # reload keeps session-less state but data stays; sign out + remove
    A.click('#topTabs [data-tab="profile"]'); A.click("#acctWipe"); A.click("#acctWipe"); A.wait_for_timeout(400)
    check("sign out and remove clears device", A.evaluate("txns.length")==0 and A.is_visible("#acctEmail"))
    check("account data untouched", len(TABLE["u-abhi@example.com"]["data"]["txns"])==3)
    check("no JS errors", not A.errs and not B.errs, A.errs+B.errs)

print(f"\n{sum(results)}/{len(results)} feature checks passed")
sys.exit(0 if all(results) else 1)
