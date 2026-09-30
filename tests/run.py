import json, sys, threading, http.server, functools, os
from playwright.sync_api import sync_playwright

DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(DIR, "tests", "screenshots"); os.makedirs(OUT, exist_ok=True)
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 8765), functools.partial(http.server.SimpleHTTPRequestHandler, directory=DIR))
threading.Thread(target=srv.serve_forever, daemon=True).start()
URL = "http://127.0.0.1:8765/index.html"
MOCK = open(os.path.join(DIR, "tests", "mock.js")).read()
results = []
def check(name, cond, info=""):
    results.append((bool(cond), name, info))
    print(("PASS " if cond else "FAIL ") + name + (f"  [{info}]" if info and not cond else ""))

with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2)
    ctx.route("**/fonts.g*/**", lambda r: r.abort())
    ctx.add_init_script(MOCK)
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("console", lambda m: m.type == "error" and "fonts" not in m.text and "ERR_FAILED" not in m.text and errs.append(m.text))
    E = pg.evaluate
    def fresh():
        pg.goto(URL); E("localStorage.clear()"); pg.reload(); pg.wait_for_function("ready.txns && ready.rules && ready.settings")
    def tab(t):
        pg.click(f'#bottomNav [data-tab="{t}"]')
    def add(amount, desc, cat=None, typ=None, date=None, repeat=False):
        pg.click("#fab")
        if typ == "income": pg.click('#formType [data-type="income"]')
        pg.fill("#fAmount", str(amount)); pg.fill("#fDesc", desc)
        if cat: pg.click(f'#catGrid label:has-text("{cat}")')
        if date: pg.fill("#fDate", date)
        if repeat: pg.check("#fRepeat")
        pg.click("#submitBtn"); pg.wait_for_timeout(120)
    def db(prefix): return E(f"Object.keys(JSON.parse(localStorage.getItem('mockdb')||'{{}}')).filter(k=>k.includes({json.dumps(prefix)}))")

    # ---- load
    fresh()
    check("loads with account storage", "Saved to your account" in pg.inner_text("#status"))
    check("welcome card on empty ledger", pg.is_visible("#welcome"))

    # ---- add / edit / delete expense
    add(250, "Lunch", "Food & dining")
    check("expense added to state", E("txns.length") == 1)
    check("expense saved to account", len(db("/ledger/expenses/")) == 1)
    check("hero shows spent ₹250", pg.inner_text("#hSpent") == "₹250", pg.inner_text("#hSpent"))
    check("welcome hidden after first entry", not pg.is_visible("#welcome"))
    pg.click("#recent .tx"); pg.fill("#fAmount", "300"); pg.click("#submitBtn"); pg.wait_for_timeout(120)
    check("edit keeps one entry", E("txns.length") == 1)
    check("edit updates amount", E("txns[0].amount") == 300)
    add(50000, "Salary", "Salary", typ="income")
    check("income recorded", E("sum(inMonth(cur),'income')") == 50000)
    check("balance = income - spent", pg.inner_text("#balance") == "₹49,700", pg.inner_text("#balance"))
    check("per-day spend shown", pg.inner_text("#hDaily").startswith("₹"), pg.inner_text("#hDaily"))
    pg.click("#fab"); pg.fill("#fAmount", "0"); pg.fill("#fDesc", "zero"); pg.click("#submitBtn"); pg.wait_for_timeout(100)
    check("rejects ₹0 amount", E("txns.length") == 2)
    pg.click("#closeSheet")
    pg.click('#recent .tx:has-text("Lunch")'); pg.click("#deleteBtn")
    check("delete needs confirmation", E("txns.length") == 2)
    pg.click("#deleteBtn"); pg.wait_for_timeout(120)
    check("delete removes entry", E("txns.length") == 1 and len(db("/ledger/expenses/")) == 1)

    # ---- reload persistence
    pg.reload(); pg.wait_for_function("ready.txns && ready.rules && ready.settings"); pg.wait_for_timeout(150)
    check("entries survive reload", E("txns.length") == 1)

    # ---- PIN lock
    check("lock hidden when no PIN", not pg.is_visible("#lock"))
    pg.click("#acctBtn"); pg.fill("#aPin1","1234"); pg.fill("#aPin2","1243"); pg.click('#aPinForm button[type="submit"]'); pg.wait_for_timeout(100)
    check("mismatched PIN rejected", "don't match" in pg.inner_text("#aErr") and not E("hasPin()"))
    pg.fill("#aPin1","1234"); pg.fill("#aPin2","1234"); pg.click('#aPinForm button[type="submit"]'); pg.wait_for_timeout(200)
    check("PIN turned on + saved", E("hasPin()") and "pinHash" in pg.evaluate("localStorage.getItem('mockdb')"))
    check("PIN not stored in plain text", '"1234"' not in pg.evaluate("localStorage.getItem('mockdb')"))
    pg.reload(); pg.wait_for_function("ready.settings"); pg.wait_for_timeout(150)
    check("app locked after reload", pg.is_visible("#lock") and "Enter your PIN" in pg.inner_text("#lock"))
    for k in "1111": pg.click(f'#lock [data-k="{k}"]')
    pg.wait_for_timeout(150)
    check("wrong PIN keeps it locked", pg.is_visible("#lock") and "Wrong PIN" in pg.inner_text("#lkMsg"))
    for _ in range(4):
        for k in "9999": pg.click(f'#lock [data-k="{k}"]')
        pg.wait_for_timeout(80)
    check("5 wrong tries -> cooldown", "Try again in" in pg.inner_text("#lkMsg"), pg.inner_text("#lkMsg"))
    E("lockState.until=0; renderLock()")
    pg.keyboard.type("1234"); pg.wait_for_timeout(200)
    check("correct PIN (keyboard) unlocks", not pg.is_visible("#lock"))
    pg.click("#acctBtn"); pg.click("#aChange"); pg.fill("#aCur","0000"); pg.fill("#aPin1","5678"); pg.fill("#aPin2","5678"); pg.click('#aPinForm button[type="submit"]'); pg.wait_for_timeout(150)
    check("change PIN needs current PIN", "wrong" in pg.inner_text("#aErr"))
    pg.fill("#aCur","1234"); pg.click('#aPinForm button[type="submit"]'); pg.wait_for_timeout(200)
    pg.click("#aLockNow"); pg.wait_for_timeout(100)
    check("lock now works", pg.is_visible("#lock"))
    for k in "5678": pg.click(f'#lock [data-k="{k}"]')
    pg.wait_for_timeout(200)
    check("new PIN unlocks", not pg.is_visible("#lock"))
    pg.click("#acctBtn"); pg.click("#aRemove"); pg.fill("#aOffPin","5678"); pg.click('#aOffForm button[type="submit"]'); pg.wait_for_timeout(200)
    check("PIN turned off", not E("hasPin()"))
    # forgot PIN path
    E("(async()=>{const s='sx';settings={...settings,pinSalt:s,pinHash:await hashPin('4321',s)};await store.saveSettings(settings)})()"); pg.wait_for_timeout(150)
    pg.reload(); pg.wait_for_function("ready.settings"); pg.wait_for_timeout(150)
    pg.click("#lkForgot"); pg.click("#lkReset"); pg.wait_for_timeout(200)
    check("forgot PIN removes lock, keeps entries", not pg.is_visible("#lock") and not E("hasPin()") and E("txns.length")==1)

    # ---- recurring backfill
    start = E("shiftM(todayISO().slice(0,7),-3)+'-05'")
    add(18000, "Rent", "Rent & housing", date=start, repeat=True)
    exp = E("new Date().getDate()>=5 ? 4 : 3")
    pg.wait_for_timeout(200)
    got = E("txns.filter(t=>t.recurId).length")
    check("recurring backfills past months", got == exp, f"got {got} want {exp}")
    check("recurring rule saved", len(db("/ledger/recurring/")) == 1)
    pg.reload(); pg.wait_for_function("ready.txns && ready.rules && ready.settings"); pg.wait_for_timeout(250)
    check("reload does not duplicate recurring", E("txns.filter(t=>t.recurId).length") == exp)
    # delete one generated entry -> must not come back
    rid = E("txns.find(t=>t.recurId && mKey(t.date)===todayISO().slice(0,7))?.id || txns.find(t=>t.recurId).id")
    E(f"openSheet(txns.find(t=>t.id==={json.dumps(rid)}))"); pg.click("#deleteBtn"); pg.click("#deleteBtn"); pg.wait_for_timeout(200)
    pg.reload(); pg.wait_for_function("ready.txns && ready.rules && ready.settings"); pg.wait_for_timeout(250)
    check("deleted recurring entry stays deleted", E(f"!txns.some(t=>t.id==={json.dumps(rid)})"))
    tab("recurring"); pg.click('#rules [data-act="toggle"]'); pg.wait_for_timeout(120)
    check("pause recurring", E("rules[0].active") is False)
    check("month bar visible on Recurring", pg.is_visible("#monthBar"))

    # ---- budgets
    tab("budgets"); pg.fill("#overallBudget", "40000"); pg.press("#overallBudget", "Tab"); pg.wait_for_timeout(120)
    check("overall budget saved", E("settings.budget") == 40000)
    add(900, "Dinner", "Food & dining")
    tab("budgets")
    pg.fill('#budList input[data-cat="Food & dining"]', "500"); pg.press('#budList input[data-cat="Food & dining"]', "Tab"); pg.wait_for_timeout(150)
    check("category limit saved", E("settings.catBudgets['Food & dining']") == 500)
    check("over-limit status shown", "Over" in pg.inner_text("#budList .bud:first-child"), pg.inner_text("#budList .bud:first-child")[:80])
    pg.fill('#budList input[data-cat="Food & dining"]', ""); pg.press('#budList input[data-cat="Food & dining"]', "Tab"); pg.wait_for_timeout(120)
    check("clearing a limit removes it", E("!('Food & dining' in settings.catBudgets)"))

    # ---- split: friends & groups
    fresh()
    tab("split")
    check("month bar hidden on Split", not pg.is_visible("#monthBar"))
    pg.click("#newFriend"); pg.fill("#dName", "Rahul"); pg.fill("#dUpi", "rahul@okaxis"); pg.click('#dForm button[type="submit"]'); pg.wait_for_timeout(120)
    check("friend created + saved", E("people.length") == 1 and len(db("/ledger/people/")) == 1)
    pg.click("[data-close]")
    pg.click("#newGroup"); pg.fill("#dName", "Goa trip")
    pg.click('#dMembers label'); pg.fill("#dNew", "Aman"); pg.press("#dNew", "Enter"); pg.wait_for_timeout(120)
    check("group form keeps name after adding member", pg.input_value("#dName") == "Goa trip", pg.input_value("#dName"))
    pg.click('#dForm button[type="submit"]'); pg.wait_for_timeout(150)
    check("group created with 2 members", E("groups.length===1 && groups[0].members.length===2"), E("JSON.stringify(groups)"))
    # add group expense from group sheet: 900 equally, paid by me
    pg.click("#gAdd"); pg.fill("#fAmount", "900"); pg.fill("#fDesc", "Villa"); pg.wait_for_timeout(50)
    check("split preselects group members", E("sf.parts.size") == 3)
    check("equal share preview", "₹300" in pg.inner_text("#shares"), pg.inner_text("#shares"))
    pg.click("#submitBtn"); pg.wait_for_timeout(150)
    t = E("JSON.stringify(txns[0])")
    check("personal amount = my share", E("txns[0].amount") == 300, t)
    check("split total stored", E("txns[0].split.total") == 900)
    bal = E("balancesWithMe()")
    check("each friend owes me 300", sorted(bal.values()) == [300, 300], bal)
    check("overview counts only my share", E("sum(inMonth(cur),'expense')") == 300)
    # friend pays 600 split equally with me only
    rahul = E("people.find(p=>p.name==='Rahul').id")
    pg.click("#fab"); pg.fill("#fAmount", "600"); pg.fill("#fDesc", "Cab"); pg.check("#fSplit")
    pg.select_option("#fGroup", ""); pg.wait_for_timeout(50)
    E("sf.parts=new Set(['me',%s]);renderSplitForm()" % json.dumps(rahul))
    pg.select_option("#fPaidBy", rahul); pg.click("#submitBtn"); pg.wait_for_timeout(150)
    check("friend-paid: I owe share", E(f"balancesWithMe()[{json.dumps(rahul)}]") == 0, E("JSON.stringify(balancesWithMe())"))
    # uneven: exact mode mismatch rejected
    n0 = E("txns.length")
    pg.click("#fab"); pg.fill("#fAmount", "1000"); pg.fill("#fDesc", "Tickets"); pg.check("#fSplit")
    pg.select_option("#fGroup", E("groups[0].id")); pg.click('#splitMode [data-m="exact"]')
    ins = pg.query_selector_all("#shares input"); ins[0].fill("500"); ins[1].fill("200"); ins[2].fill("200")
    check("exact mismatch message", "still to assign" in pg.inner_text("#remain"), pg.inner_text("#remain"))
    pg.click("#submitBtn"); pg.wait_for_timeout(100)
    check("exact mismatch not saved", E("txns.length") == n0)
    ins[2].fill("300"); pg.click("#submitBtn"); pg.wait_for_timeout(150)
    check("exact split saved", E("txns.length") == n0 + 1)
    # percent mode redistributes when a person is removed
    pg.click("#fab"); pg.fill("#fAmount", "1000"); pg.fill("#fDesc", "Boat"); pg.check("#fSplit")
    pg.select_option("#fGroup", E("groups[0].id")); pg.click('#splitMode [data-m="pct"]')
    pg.click("#pChips label >> nth=2"); pg.wait_for_timeout(50)
    check("percent resets to 100% after removing someone", "Your share" in pg.inner_text("#remain"), pg.inner_text("#remain"))
    pg.click("#submitBtn"); pg.wait_for_timeout(150)
    boat = E("JSON.stringify(txns.find(t=>t.desc==='Boat').split.shares)")
    check("percent split = 500/500", E("Object.values(txns.find(t=>t.desc==='Boat').split.shares).sort().join()") == "500,500", boat)
    # consistency: friend balances == group pairs involving me
    g = E("groups[0].id")
    cons = E("""(()=>{const pr=groupPairs(groups[0]);const b=balancesWithMe();const nong=txns.filter(t=>t.split&&!t.split.group);
      const direct={};for(const t of nong){const s=t.split;if(s.paidBy==='me'){for(const[k,v]of Object.entries(s.shares))if(k!=='me')direct[k]=(direct[k]||0)+v}else direct[s.paidBy]=(direct[s.paidBy]||0)-(s.shares.me||0)}
      return people.every(p=>{const fromPairs=pr.filter(x=>x.from===p.id&&x.to==='me').reduce((s,x)=>s+x.amount,0)-pr.filter(x=>x.from==='me'&&x.to===p.id).reduce((s,x)=>s+x.amount,0);return Math.abs(fromPairs+(direct[p.id]||0)-(b[p.id]||0))<0.01})})()""")
    check("friend balances match group view", cons)
    # settle up with a friend from group suggestion involving me
    E(f"openDetail({{kind:'group',id:{json.dumps(g)}}})")
    pairs = E("groupPairs(groups[0]).filter(x=>x.from==='me'||x.to==='me').length")
    before = E("JSON.stringify(balancesWithMe())")
    pg.click('#detail [data-sug="0"]'); pg.wait_for_timeout(150)
    check("mark-paid records settlement", E("txns.some(t=>t.type==='settle')"), before)
    check("settled pair disappears", E("groupPairs(groups[0]).filter(x=>x.from==='me'||x.to==='me').length") == pairs - 1)
    # friend detail settle-up to zero
    pg.click("[data-close]")
    aman = E("people.find(p=>p.name==='Aman').id")
    E(f"openDetail({{kind:'friend',id:{json.dumps(aman)}}})")
    amt = E(f"balancesWithMe()[{json.dumps(aman)}]||0")
    if abs(amt) > 0.009:
        pg.click('#dSettle button[type="submit"]'); pg.wait_for_timeout(150)
    check("friend settle-up clears balance", abs(E(f"balancesWithMe()[{json.dumps(aman)}]||0")) < 0.01, str(amt))
    # clipboard fallback (headless clipboard is denied)
    E(f"txns.push({{id:'x1',type:'expense',amount:100,desc:'Snacks',cat:'Other',pay:'UPI',date:todayISO(),created:1,split:{{group:null,paidBy:'me',total:600,shares:{{me:100,{json.dumps(rahul)}:500}},mode:'equal',vals:{{}}}}}});store.saveTxn(txns[txns.length-1]);render()")
    E(f"openDetail({{kind:'friend',id:{json.dumps(rahul)}}})")
    pg.click("#dRemind"); pg.wait_for_timeout(200)
    has_ta = pg.is_visible("textarea.fallback")
    ta = pg.input_value("textarea.fallback") if has_ta else ""
    check("reminder shows or copies text", has_ta or "copied" in pg.inner_text("#toast"))
    check("reminder text names amount", (not has_ta) or "₹200" in ta, ta)
    pg.click("[data-close]")
    # delete group keeps balances
    pg.wait_for_timeout(150); b1 = E("balancesWithMe()")
    E(f"openDetail({{kind:'editGroup',id:{json.dumps(g)}}})"); pg.click("#dDel"); pg.click("#dDel"); pg.wait_for_timeout(200)
    check("group deleted", E("groups.length") == 0)
    b2=E("balancesWithMe()"); check("balances unchanged after group delete", b2 == b1, f"{b1} -> {b2}")
    check("no orphan group ids left", E("!txns.some(t=>t.split?.group||t.group)"))
    # edit split -> normal expense
    vid = E("txns.find(t=>t.desc==='Villa').id")
    E(f"openSheet(txns.find(t=>t.id==={json.dumps(vid)}))")
    check("edit prefills split total", pg.input_value("#fAmount") == "900")
    pg.uncheck("#fSplit"); pg.click("#submitBtn"); pg.wait_for_timeout(150)
    check("unsplit keeps full amount, no split", E(f"(t=>t.amount===900&&!t.split)(txns.find(t=>t.id==={json.dumps(vid)}))"))
    # settle rows hidden from Entries
    tab("transactions")
    check("settle-ups not in Entries list", "paid You" not in pg.inner_text("#list") and "paid Rahul" not in pg.inner_text("#list"))

    # ---- sample data
    fresh(); pg.click('#welcome [data-sample]'); pg.wait_for_timeout(400)
    check("sample adds entries, friends, group", E("txns.length>5 && people.length===3 && groups.length===1"))
    tab("split")
    check("sample split tab renders balances", "Goa trip" in pg.inner_text("#groups") and "₹" in pg.inner_text("#friends"))
    tab("transactions"); pg.click("#removeSamples"); pg.wait_for_timeout(400)
    check("remove samples clears everything", E("txns.length===0&&people.length===0&&groups.length===0"), E("[txns.length,people.length,groups.length].join()"))
    check("remove samples clears storage", len(db("/ledger/")) == 0, str(db("/ledger/")))

    # ---- calendar + filters + month nav
    add(120, "Tea", "Food & dining"); add(80, "Bus", "Transport")
    tab("overview"); pg.click(f'#cal [data-day="{E("todayISO()")}"]')
    check("calendar day opens filtered Entries", E("tab") == "transactions" and E("filt.day") == E("todayISO()"))
    pg.click("#clearDay"); pg.fill("#search", "bus")
    check("search filters", pg.inner_text("#list").count("Bus") == 1 and "Tea" not in pg.inner_text("#list"))
    pg.fill("#search", ""); pg.click('#typeSeg [data-type="income"]')
    check("type filter", "No matches" in pg.inner_text("#list"))
    pg.click('#typeSeg [data-type=""]'); pg.click("#prevM")
    check("previous month is empty", "Nothing logged" in pg.inner_text("#list"))
    pg.click("#thisMonth")
    check("back to this month", E("cur===todayISO().slice(0,7)"))

    # ---- CSV
    pg.click("#exportBtn"); pg.wait_for_timeout(150)
    dl = E("window.__dl[0]")
    check("CSV export produced", dl and dl["filename"].endswith(".csv") and dl["data"].startswith('"Date","Type"'), str(dl)[:120])

    # ---- browser-only fallback (no account)
    pg.goto(URL); E("localStorage.clear();localStorage.setItem('mockmode','off')"); pg.reload(); pg.wait_for_timeout(11500)
    check("works without account (browser storage)", "this browser only" in pg.inner_text("#status"), pg.inner_text("#status"))
    add(99, "Offline test", "Other")
    pg.reload(); pg.wait_for_timeout(11500)
    check("browser storage persists", E("txns.length") == 1)
    E("localStorage.clear()")

    # ---- layout: phone + desktop, light + dark, every tab
    shots = []
    fresh(); pg.click('#welcome [data-sample]'); pg.wait_for_timeout(400)
    for w, h, name in [(390, 844, "phone"), (1280, 900, "desktop")]:
        pg.set_viewport_size({"width": w, "height": h})
        for scheme in ["light", "dark"]:
            pg.emulate_media(color_scheme=scheme)
            for t in ["overview", "transactions", "split", "budgets", "recurring"]:
                E(f"go('{t}')"); pg.wait_for_timeout(60)
                ov = E("document.documentElement.scrollWidth - innerWidth")
                check(f"no sideways scroll: {name}/{scheme}/{t}", ov <= 0, str(ov))
                if scheme == "light" or t in ("overview", "split"):
                    f = f"shot-{name}-{scheme}-{t}.png"; pg.screenshot(path=os.path.join(OUT, f), full_page=True); shots.append(f)
    pg.set_viewport_size({"width": 390, "height": 844}); pg.emulate_media(color_scheme="light")
    E("go('split')"); E("openDetail({kind:'group',id:groups[0].id})"); pg.wait_for_timeout(100)
    pg.screenshot(path=os.path.join(OUT, "shot-phone-group-sheet.png"))
    pg.click("[data-close]"); pg.click("#addShared"); pg.wait_for_timeout(100)
    pg.select_option("#fGroup", E("groups[0].id")); pg.wait_for_timeout(50)
    pg.screenshot(path=os.path.join(OUT, "shot-phone-add-split.png"), full_page=False)
    sheet_ov = E("(()=>{const s=document.querySelector('#scrim .sheet');return s.scrollWidth-s.clientWidth})()")
    check("add sheet has no sideways scroll", sheet_ov <= 0, str(sheet_ov))

    check("no JavaScript errors", not errs, " | ".join(errs[:5]))
    b.close()

fails = [r for r in results if not r[0]]
srv.shutdown()
print(f"\n{len(results)-len(fails)}/{len(results)} passed")
for f in fails: print("FAIL:", f[1], f[2])
sys.exit(1 if fails else 0)
