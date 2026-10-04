"""Regression checks for persistence, restore, accessibility and precision."""
import functools
import http.server
import json
from pathlib import Path
import sys
import threading
from playwright.sync_api import sync_playwright

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
SERVER = http.server.ThreadingHTTPServer(("127.0.0.1", 8766), functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(ROOT)))
threading.Thread(target=SERVER.serve_forever, daemon=True).start()
URL = "http://127.0.0.1:8766/index.html"
checks = 0

def check(name, condition):
    global checks
    assert condition, name
    checks += 1
    print("PASS " + name)

try:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 390, "height": 844})
        page.route("**/fonts.g*/**", lambda r: r.abort())
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(URL)
        page.wait_for_function("ready.txns && ready.rules && ready.settings")
        E = page.evaluate
        def tab(name):
            page.click(f'#bottomNav [data-tab="{name}"]')

        page.click("#fab")
        page.fill("#fAmount", "250.75")
        page.fill("#fDesc", "Precision lunch")
        check("dialog makes background inert", E("document.querySelector('.app').inert"))
        page.focus("#submitBtn")
        page.keyboard.press("Tab")
        check("Tab stays inside dialog", E("document.querySelector('#scrim').contains(document.activeElement)"))
        page.focus("#closeSheet")
        page.keyboard.press("Shift+Tab")
        check("reverse Tab stays inside dialog", E("document.activeElement.id === 'submitBtn'"))
        E("()=>{window.originalSet=Storage.prototype.setItem;Storage.prototype.setItem=function(k,v){if(k==='kharcha-ledger-v2')throw new DOMException('Full','QuotaExceededError');return originalSet.call(this,k,v)}}")
        page.click("#submitBtn")
        page.wait_for_function("!entrySaving")
        check("failed save leaves form open", page.is_visible("#scrim"))
        check("failed save keeps input", page.input_value("#fAmount") == "250.75")
        check("failed save rolls ledger back", E("txns.length") == 0)
        check("failed save offers retry", "Not saved" in page.inner_text("#entrySaveStatus"))
        E("()=>{Storage.prototype.setItem=originalSet}")
        page.click("#submitBtn")
        page.locator("#scrim").wait_for(state="hidden")
        check("retry creates exactly one entry", E("txns.length") == 1)
        check("decimal spending displayed", page.inner_text("#hSpent") == "₹250.75")
        check("focus restored after dialog closes", E("document.activeElement.id === 'fab'"))

        tab("budgets")
        E("()=>{Storage.prototype.setItem=function(k,v){if(k==='kharcha-ledger-v2')throw new DOMException('Full','QuotaExceededError');return originalSet.call(this,k,v)}}")
        page.fill("#overallBudget", "1000")
        page.locator("#overallBudget").press("Tab")
        page.wait_for_function("document.querySelector('#budgetStatus').textContent.includes('Not saved')")
        check("failed budget save rolls back", E("settings.budget") == 0)
        E("()=>{Storage.prototype.setItem=originalSet}")
        page.fill("#overallBudget", "1000")
        page.locator("#overallBudget").press("Tab")
        page.wait_for_function("settings.budget === 1000")

        tab("profile")
        page.fill('#profileForm [name="name"]', "Test person")
        page.select_option('#profileForm [name="defaultPay"]', "Cash")
        page.click('#profileForm [type="submit"]')
        page.wait_for_function("settings.preferences?.defaultPay === 'Cash'")
        page.click("#fab")
        page.click("#entryOptions summary")
        check("payment preference used for new entries", page.input_value("#fPay") == "Cash")
        page.click("#closeSheet")

        # Include every entity in a round-trip fixture, with a real recurring split.
        E("""async()=>{
          txns[0].date=shiftM(todayISO().slice(0,7),-1)+'-01';
          people=[{id:'friend1',name:'Friend'}];groups=[{id:'group1',name:'Trip',members:['friend1']}];
          rules=[{id:'rule1',amount:100,desc:'Rent',cat:'Rent & housing',pay:'Cash',type:'expense',day:1,start:todayISO().slice(0,7),active:true,skip:[]}];
          txns.push({id:'split1',type:'expense',date:todayISO(),amount:5.01,cat:'Food & dining',pay:'Cash',desc:'Shared snack',split:{total:10.01,paidBy:'me',shares:{me:5.01,friend1:5},mode:'equal',vals:{},group:'group1'}});
          settings.catBudgets={'Food & dining':500};await store.commitLedger();renderProfile();
        }""")
        expected = E("ledgerData()")
        with page.expect_download() as event:
            page.click("#backupBtn")
        downloaded = event.value
        document = json.loads(Path(downloaded.path()).read_text(encoding="utf-8"))
        check("backup includes entire ledger", document["data"] == expected)
        E("async()=>{await store.replaceLedger({txns:[],rules:[],people:[],groups:[],settings:{budget:0,catBudgets:{}}});renderProfile()}")
        page.set_input_files("#restoreFile", {"name": "backup.json", "mimeType": "application/json", "buffer": json.dumps(document).encode()})
        page.locator("#confirmRestore").wait_for()
        check("restore preview does not modify data", E("txns.length") == 0)
        page.click("#confirmRestore")
        page.wait_for_function("txns.length === 2")
        check("restore round-trip preserves all entities", E("ledgerData()") == expected)
        check("restored ledger persisted", json.loads(E("localStorage.getItem('kharcha-ledger-v2')")) == expected)

        invalid = json.loads(json.dumps(document))
        invalid["data"]["txns"][0]["amount"] = -1
        page.set_input_files("#restoreFile", {"name": "invalid.json", "mimeType": "application/json", "buffer": json.dumps(invalid).encode()})
        page.wait_for_function("document.querySelector('#backupStatus').textContent.includes('not a valid')")
        check("invalid backup leaves ledger unchanged", E("ledgerData()") == expected)
        E("()=>{Storage.prototype.setItem=function(k,v){if(k==='kharcha-ledger-v2')throw new DOMException('Full','QuotaExceededError');return originalSet.call(this,k,v)}}")
        page.set_input_files("#restoreFile", {"name": "backup.json", "mimeType": "application/json", "buffer": json.dumps(document).encode()})
        page.click("#confirmRestore")
        page.wait_for_function("document.querySelector('#backupStatus').textContent.includes('Restore failed')")
        check("failed restore leaves ledger unchanged", E("ledgerData()") == expected)
        E("()=>{Storage.prototype.setItem=originalSet}")
        page.click("#cancelRestore")

        # A generated recurring write failure is visible and can be retried.
        E("window.saveTxnOriginal=store.saveTxn;store.saveTxn=async()=>{throw new Error('offline')};materialize()")
        page.wait_for_function("!recurringBusy")
        check("failed recurring entry is not treated as saved", E("txns.filter(t=>t.recurId).length") == 0)
        check("recurring failures show retry", "could not be saved" in E("document.querySelector('#recurringStatus').textContent"))
        E("store.saveTxn=saveTxnOriginal;materialize()")
        page.wait_for_function("!recurringBusy && txns.some(t=>t.recurId)")
        check("recurring retry adds one entry", E("txns.filter(t=>t.recurId).length") == 1)

        tab("transactions")
        page.locator('[data-panel="transactions"] .entry-options summary').click()
        page.fill("#filterFrom", "2020-01-01")
        page.fill("#filterTo", "2200-12-31")
        page.select_option("#entrySort", "largest")
        check("date range searches across months", page.locator("#list .tx").count() == 3)
        check("amount sorting works", page.locator("#list .tx").first.get_attribute("data-id") == expected["txns"][0]["id"])
        shots = ROOT / "tests" / "screenshots"
        shots.mkdir(exist_ok=True)
        for w,h,label in [(390,844,"phone"),(1280,900,"desktop")]:
            page.set_viewport_size({"width":w,"height":h})
            for section in ["overview","transactions","split","budgets","recurring","profile"]:
                E(f"go('{section}')")
                check(f"reflow {label}/{section}", E("document.documentElement.scrollWidth <= innerWidth"))
                if section in ["overview","profile"]:
                    page.screenshot(animations="disabled", path=str(shots / f"improved-{label}-{section}.png"), full_page=True)
            page.click("#fab" if label=="phone" else "#addBtnDesk")
            page.screenshot(animations="disabled", path=str(shots / f"improved-{label}-entry.png"))
            box=page.locator("#submitBtn").bounding_box()
            check(f"save visible without scrolling {label}", box is not None and box["y"]+box["height"] <= h)
            page.click("#closeSheet")
        check("no JavaScript errors", not errors)
        browser.close()
finally:
    SERVER.shutdown()
print(f"{checks} improvement checks passed")
