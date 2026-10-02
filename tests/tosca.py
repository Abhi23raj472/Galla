"""End-to-end checks for tosca/ (Tosca Q Hub) with every source API mocked."""
import json, sys, threading, http.server, functools, os, time
from playwright.sync_api import sync_playwright

DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(DIR, "tests", "screenshots"); os.makedirs(OUT, exist_ok=True)
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 8766), functools.partial(type("Q", (http.server.SimpleHTTPRequestHandler,), {"log_message": lambda *a: None}), directory=DIR))
threading.Thread(target=srv.serve_forever, daemon=True).start()
URL = "http://127.0.0.1:8766/tosca/index.html"
now = int(time.time())

SO = {"items": [
    {"question_id": 1, "title": "How to handle dynamic IDs in Tosca XScan?", "link": "https://stackoverflow.com/q/1",
     "owner": {"display_name": "ana"}, "creation_date": now - 86400 * 3, "last_activity_date": now - 3600,
     "score": 5, "answer_count": 2, "is_answered": True, "tags": ["tosca", "xscan"], "body": "<p>My ids change &amp; break.</p>"},
    {"question_id": 2, "title": "Tosca buffer not resolving &quot;{B[x]}&quot;", "link": "https://stackoverflow.com/q/2",
     "owner": {"display_name": "raj"}, "creation_date": now - 86400 * 400, "last_activity_date": now - 86400 * 400,
     "score": 0, "answer_count": 0, "is_answered": False, "tags": ["tosca"], "body": "<p>buffer empty</p>"},
]}
SQA = {"items": [
    {"question_id": 9, "title": "Tosca vs Selenium for SAP", "link": "https://sqa.stackexchange.com/q/9",
     "owner": {"display_name": "lee"}, "creation_date": now - 86400 * 10, "last_activity_date": now - 86400 * 9,
     "score": 12, "answer_count": 4, "is_answered": True, "tags": ["tosca", "sap"], "body": "<p>which?</p>"},
]}
REDDIT = {"data": {"children": [
    {"data": {"id": "r1", "title": "How to handle dynamic IDs in Tosca XScan?", "permalink": "/r/QualityAssurance/comments/r1/x/",
              "author": "bob", "created_utc": now - 7200, "score": 3, "num_comments": 1, "selftext": "cross-post", "subreddit": "QualityAssurance"}},
    {"data": {"id": "r2", "title": "Tosca at the opera tonight", "permalink": "/r/opera/comments/r2/x/",
              "author": "fan", "created_utc": now - 100, "score": 99, "num_comments": 9, "selftext": "Puccini!", "subreddit": "opera"}},
    {"data": {"id": "r3", "title": "<img src=x onerror=alert(1)> Tosca DEX agent offline", "permalink": "/r/softwaretesting/comments/r3/x/",
              "author": "eve", "created_utc": now - 5000, "score": 1, "num_comments": 0, "selftext": "", "subreddit": "softwaretesting"}},
]}}
DEVTO = [{"id": 77, "title": "Getting started with Tosca API Scan", "url": "https://dev.to/a/77", "user": {"name": "Dee"},
          "published_at": "2025-01-01T00:00:00Z", "public_reactions_count": 8, "comments_count": 2,
          "description": "API testing in Tosca", "tag_list": ["tosca", "testing"]}]
HN = {"hits": [{"objectID": "55", "title": "Tricentis acquires something", "author": "pg", "created_at_i": now - 86400 * 50, "points": 40, "num_comments": 12}]}

def fulfill(route, body, status=200):
    route.fulfill(status=status, content_type="application/json", headers={"Access-Control-Allow-Origin": "*"}, body=json.dumps(body))

calls = []
def handler(route):
    u = route.request.url; calls.append(u)
    if "site=stackoverflow" in u: return fulfill(route, SO)
    if "site=sqa" in u: return fulfill(route, SQA)
    if "reddit.com" in u: return fulfill(route, REDDIT)
    if "api.github.com" in u: return fulfill(route, {"message": "API rate limit exceeded"}, 403)
    if "hn.algolia.com" in u: return fulfill(route, HN)
    if "dev.to/api" in u: return fulfill(route, DEVTO if "tag=tosca" in u else [])
    route.abort()

results = []
def check(name, cond, info=""):
    results.append(bool(cond)); print(("PASS " if cond else "FAIL ") + name + (f"  [{info}]" if info and not cond else ""))

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=os.environ.get("CHROMIUM_PATH") or None)
    for scheme in ("light", "dark"):
        for w, h in ((390, 844), (1280, 900)):
            ctx = b.new_context(viewport={"width": w, "height": h}, color_scheme=scheme)
            ctx.route(lambda u: not u.startswith("http://127.0.0.1"), handler)
            pg = ctx.new_page(); errs = []
            pg.on("pageerror", lambda e: errs.append(str(e)))
            pg.on("dialog", lambda d: (errs.append("dialog " + d.message), d.dismiss()))
            pg.goto(URL); pg.evaluate("localStorage.clear()"); pg.reload()
            pg.wait_for_function("document.querySelectorAll('#sourceChips .chip.loading').length === 0")
            tag = f"{scheme}-{w}"
            if scheme == "light" and w == 390:
                titles = pg.eval_on_selector_all("#feedList h3", "n => n.map(x => x.textContent)")
                check("renders merged questions", len(titles) == 6, titles)
                check("cross-post collapsed into one card", titles.count("How to handle dynamic IDs in Tosca XScan?") == 1)
                check("'also on' link shown for cross-post", pg.eval_on_selector_all(".also a", "n => n.map(x => x.textContent)") == ["Reddit"])
                check("opera noise filtered", not any("opera" in t for t in titles))
                check("HTML entities decoded", 'Tosca buffer not resolving "{B[x]}"' in titles)
                check("no script injection", not errs and pg.locator("#feedList img").count() == 0, errs)
                check("most recent first", titles[0].startswith("How to handle dynamic"), titles[0])
                gh = pg.locator('#sourceChips .chip', has_text="GitHub")
                check("failed source flagged", "error" in gh.get_attribute("class") and "unavailable" in pg.inner_text("#summary"))
                pg.check("#unanswered"); n = pg.locator("#feedList .card").count()
                check("unanswered filter", n == 2, n)  # SO q2 + reddit r3 (0 comments)
                pg.uncheck("#unanswered")
                pg.select_option("#range", "30"); n = pg.locator("#feedList .card").count()
                check("time range filter", n == 3, n)  # SO q1, SQA, reddit r3
                pg.select_option("#range", "0"); pg.select_option("#sort", "votes")
                check("sort by votes", pg.locator("#feedList h3").first.inner_text() == "Tricentis acquires something")
                pg.click('#sourceChips .chip:has-text("Hacker News")')
                check("source toggle hides items", pg.locator("#feedList .card").count() == 5)
                pg.locator("#feedList .save").first.click()
                check("save updates count", pg.inner_text("#savedCount") == "1")
                pg.click("#tab-saved"); check("saved tab lists item", pg.locator("#savedList .card").count() == 1)
                pg.click("#tab-prep")
                check("interview bank renders", pg.locator("#prepList details").count() >= 25)
                pg.fill("#prepQ", "buffer"); check("interview filter", 0 < pg.locator("#prepList details").count() < 10)
                pg.fill("#prepQ", ""); pg.click('#prepCats .chip:has-text("Execution")')
                check("interview category", pg.locator("#prepList details").count() == 5)
                pg.click("#tab-feed")
                before = len(calls); pg.fill("#q", "xscan"); pg.click("#searchForm .btn.primary")
                pg.wait_for_function("document.querySelectorAll('#sourceChips .chip.loading').length === 0")
                new = calls[before:]
                check("search sends query to sources", any("xscan" in c for c in new) and all("tosca" in c for c in new if "dev.to" not in c), new)
                check("query kept in URL", "q=xscan" in pg.url)
                check("dev.to filtered client-side", pg.locator('#feedList .card:has-text("API Scan")').count() == 0)
                before = len(calls); pg.reload(); pg.wait_for_function("document.querySelectorAll('#sourceChips .chip.loading').length === 0")
                check("cache avoids refetch", len([c for c in calls[before:] if "stackexchange" in c]) == 0, calls[before:])
                pg.click("#refreshBtn"); pg.wait_for_function("document.querySelectorAll('#sourceChips .chip.loading').length === 0")
                pg.fill("#q", ""); pg.click("#searchForm .btn.primary")
                pg.wait_for_function("document.querySelectorAll('#sourceChips .chip.loading').length === 0")
            sw = pg.evaluate("document.documentElement.scrollWidth"); cw = pg.evaluate("document.documentElement.clientWidth")
            wide = pg.evaluate("[...document.querySelectorAll('body *')].filter(e => { const r = e.getBoundingClientRect(); return r.right > document.documentElement.clientWidth + 1 || r.left < -1 || e.scrollWidth > e.clientWidth + 1 && getComputedStyle(e).overflowX === 'visible' && e.clientWidth > 0 }).slice(0,5).map(e => e.tagName + '.' + e.className + ' ' + Math.round(e.getBoundingClientRect().right))")
            check(f"no horizontal scroll {tag}", sw <= cw, f"{sw}>{cw} {wide}")
            pg.screenshot(path=os.path.join(OUT, f"tosca-{tag}.png"), full_page=False)
            pg.click("#tab-prep"); pg.locator("#prepList details").first.click()
            pg.screenshot(path=os.path.join(OUT, f"tosca-prep-{tag}.png"))
            check(f"no page errors {tag}", not errs, errs)
            ctx.close()
    b.close()
srv.shutdown()
print(f"\n{sum(results)}/{len(results)} passed")
sys.exit(0 if all(results) else 1)
