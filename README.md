# Galla

**Spend · Split · Settle**

Galla is a personal expense tracker with Splitwise-style bill splitting, built for India (₹). It uses static HTML with a premium light stylesheet (`premium.css`), with no build step or server required.

<img src="assets/galla-logo.svg" width="96" alt="Galla logo">

## Features

**Personal money**
- Log expenses and income with categories, payment method (UPI, card, cash, net banking, auto-debit) and date
- Monthly overview: what's left, income, spending and daily spend (leaves out rent, investments and recurring payments)
- Quick entry on the overview: amount, note and category, saved with today's date
- Category progress bars, day-by-day spending calendar, six-month income vs spending chart
- Insights: spending pace vs last month, biggest expense, next recurring payment
- Search and filter by text, type, category or day

**Budgets**
- Overall monthly budget with a progress meter and a "per day you can spend" figure
- Per-category limits with On track / Near limit / Over status

**Recurring entries**
- Rent, salary, SIPs, EMIs and subscriptions are added when you open the app after their due date (up to 12 months of catch-up)
- Pause, resume or delete; deleting one generated month doesn't bring it back

**Split with friends**
- Groups (trips, flatmates, office lunch) and individual friends
- Split equally, by exact amounts or by percentages; anyone can be the payer
- Only your share counts toward your personal spending
- Per-friend balances, "who owes whom" per group, one-tap settle-up
- Save a friend's UPI ID and copy a ready-to-send WhatsApp reminder

**Privacy and extras**
- Display name and default payment method, with optional personal details
- Full JSON backup and validated restore, including friends, groups, rules and settings
- CSV export for spreadsheet analysis
- Date range search across months and amount/date sorting
- Sample data to try it out, removable in one tap
- Works on phone, tablet and desktop

## Run it

Open `index.html` in a browser. That's it.

To host it, enable **GitHub Pages** for this repo (Settings → Pages → deploy from the `main` branch, root folder). The app will be live at `https://<your-username>.github.io/galla/`.

## Where data is stored

| Where Galla runs | Storage |
|---|---|
| Opened directly or on GitHub Pages | The browser's `localStorage` on that device. Clearing site data erases it, and it doesn't sync between devices. Use the full JSON backup in Profile to preserve all data; CSV is for analysis. |
| As a Claude artifact (claude.ai) | The signed-in user's private artifact storage, synced across devices. |

The app detects which one is available and picks automatically.

## Tests

End-to-end tests run the app in headless Chromium with a mocked account store:

```bash
pip install playwright
python -m playwright install chromium
python tests/run.py
python tests/improvements.py
```

The suite checks: adding, editing and deleting entries, income and balance maths, recurring back-fill and de-duplication, budgets, equal/exact/percent splits, settle-ups, balance consistency between friends and groups, group deletion, profile saving and reload persistence, sample data, filters, CSV export, the browser-only fallback, and no sideways scrolling at phone and desktop widths in light and dark system themes. Screenshots are saved to `tests/screenshots/`.

## Project layout

```
index.html           the whole app (HTML, base CSS, JS)
premium.css          the visual theme
assets/galla-logo.svg
tests/run.py         Playwright end-to-end suite
tests/mock.js        in-memory stand-in for the Claude artifact storage
```


## Full backup and restore

Open **Profile → Backup & restore** and download a full JSON backup. It contains your entries, friends, groups, recurring rules, budgets, profile and preferences. Keep it private. To move to another browser/device, open Galla there, choose the backup file, review the counts and confirm replacement. Existing browser data is replaced only after validation and a successful storage write. Download a backup of that data first. Restore currently supports browser storage; account-backed artifact storage can export a backup but cannot restore one.

Entry saves keep the form open on failure and allow retry. Browser writes restore the last saved state on failure. Budget save status and recurring retry controls make failures visible. Recurring entries are bookkeeping records; Galla does not send payments or run a background scheduler. It catches up due entries from the last twelve months when opened.

The additional improvement tests inject storage failures, exercise backup/restore and validation, check keyboard focus, paise precision and sorting, and verify phone/desktop layouts and the fixed save footer.
