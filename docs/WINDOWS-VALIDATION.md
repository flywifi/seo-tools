# Windows validation runbook (local-only, in a scratch clone)

The ordered checklist for running Creator OS's Creator Books surfaces (P103: the Books tab, Inbox
receipts, photo receipts, price capture, mail triage) on a real Windows PC without touching an
external account, the PC's own clone, the real hub, or the real settings of Claude Desktop, Codex
or Antigravity. Install mechanics live in `docs/SETUP_WINDOWS.md`; where each install lands is in
`docs/INSTALL-SCOPE.md`. This file is the run-it-and-record-it companion, the Windows counterpart
of `docs/MAC-VALIDATION.md`.

## Ground rules for the run

- Work in a scratch clone under `%TEMP%`. The PC's main clone is left as it is, and git is not
  run there.
- The real hub folder is not used. The steps make a stand-in hub under `%TEMP%`.
- The wizard's Install buttons for Claude Desktop, Codex and Antigravity are not pressed: they
  write those apps' real settings files. Their writers are covered by the wizard's selftest
  (step W2), which uses stand-in paths.
- No sign-in, no posting, no credential. Of steps W1 to W8, W7 is the one meant to fetch a web
  page: the public product page you name. The scratch-clone setup below downloads the
  repository, the Python packages and Playwright's browser.
- Two things setup leaves outside the scratch clone, which Clean up does not remove: Playwright's
  browser under `%LOCALAPPDATA%\ms-playwright` (`docs/INSTALL-SCOPE.md`) and pip's download cache.
- Record outcomes. Machine measurements (timings, hardware figures) stay out of the log.

## Prerequisites (once)

Python 3.12 to 3.14 and Git for Windows, as in `docs/SETUP_WINDOWS.md` (Quick start step 1, and
Step 1 of the full setup).

## Scratch clone

Run every command in Command Prompt (cmd.exe), not PowerShell: the commands use `%TEMP%`,
`cd /d`, `rmdir /s /q` and `%ERRORLEVEL%`, which PowerShell reads differently. The wizard (W4, W5)
and the dashboard (W6, W7) each keep their window busy until Ctrl+C, so run the commands that
follow them in a new Command Prompt window, after `cd /d "%TEMP%\cos-accept"` there.

```
git clone --branch main https://github.com/flywifi/seo-tools.git "%TEMP%\cos-accept"
cd /d "%TEMP%\cos-accept"
py -3 tools\setup.py
py -3 tools\setup.py --install-deps
mkdir "%TEMP%\cos-hub\Inbox"
```

`--install-deps` builds the scratch clone's own `.venv`, including the photo reader set
(`requirements-photo.txt`). `tools\setup.py` creates `creator-os-config.local.json` beside
`creator-os-config.json` with every switch off. To turn the three switches on for this clone,
replace that file's contents with:

```
{"capabilities": {"finance_management": {"enabled": true}, "photo_receipts": {"enabled": true},
                  "price_capture": {"enabled": true}}}
```

Save this file, and the two JSON files in W6, as UTF-8 without a byte-order mark (in Notepad's
Save dialog: Encoding "UTF-8", not "UTF-8 with BOM"). A config file saved with the mark is not
read, and the switches then stay off without a message.

## Validation steps

Run each, compare against "expected", and record the outcome in the results log.

- **W1. Battery.** `py -3 tools\battery.py`
  - Expected: the closing line starts with `battery: PASS (15 of 15 gates)`. It runs for some
    tens of minutes.
- **W2. Wizard selftest (the Install screen's writers, stand-in paths).**
  `py -3 tools\wizard.py --selftest`
  - Expected: exit code 0 (`echo %ERRORLEVEL%` prints 0). This covers the Codex and Antigravity
    settings writers and the Inbox receipt screens without touching a real settings file.
- **W3. The photo reader.** `.venv\Scripts\python.exe tools\photo_text.py --engine-check`
  - Expected: JSON with `"ok": true` and an `engine` value. The reader's install on Windows was
    not run when it was built (ADR 0087), so if the output has `"ok": false`, copy its `gaps`
    text into the log as written.
- **W4. A text receipt, Inbox to books.** Save these seven lines as
  `%TEMP%\cos-hub\Inbox\receipt.txt`:

  ```
  Northstar Tools
  Order confirmation
  Date: 2026-05-02
  Sold by: Northstar Tools Co
  Brad nails 18ga 2in    2    $12.50
  Order total    $25.00
  Paid with card ending in 4242
  ```

  Run `py -3 tools\wizard.py`, open `/drive-hub` and give it the full path of `%TEMP%\cos-hub`
  (run `echo %TEMP%\cos-hub` to see it) as the hub folder. The path is saved in the scratch
  clone's `creator-os-config.local.json`. Then open `/inbox`, scan, tick
  "This is a receipt or payment notice" and approve. On the work order that opens (it is also
  reachable later at `/inbox-receipts` while the receipt is unrecorded), tick the entry and
  choose Confirm.
  - Expected: the file moves under `Inbox\Processed\`; the work order shows total 25.00, date
    2026-05-02, Northstar Tools Co and "Money I paid" ticked; after recording, the cost entry
    shows under Spending on the Books tab for tax year 2026 (step W6).
  - If the hub screen answers "Use a folder in your home folder", `%TEMP%` on this PC is outside
    the user folder: record BLOCKED with that sentence.
- **W5. A photo receipt.** Photograph a paper receipt, save it as a jpg or png into
  `%TEMP%\cos-hub\Inbox\`, and repeat W4's screen steps.
  - Expected: the photo is offered the receipt tick; the work order shows the fields at probable
    confidence at most, with the note "read from a photo; check each figure against the
    receipt". Record which fields were right. A HEIC photo is not offered the tick; that is the
    designed behaviour.
- **W6. The Books tab.** The receipts of W4 and W5 are money paid, which the tab lists under
  Spending; Confirm and Void act on ledger entries, so this step adds two. Save this as
  `%TEMP%\gift.json`:

  ```
  {"date": "2026-05-11", "payer": "Northstar Tools", "payer_type": "brand", "kind": "product",
   "source": "user_entry", "product": {"item": "Cordless brad nailer kit", "quantity": 1}}
  ```

  and this as `%TEMP%\cash.json`:

  ```
  {"date": "2026-05-12", "payer": "Northstar Tools", "payer_type": "brand", "kind": "cash",
   "amount": "10.00", "source": "user_entry"}
  ```

  Run `py -3 tools\books.py --add "%TEMP%\gift.json" --write` and
  `py -3 tools\books.py --add "%TEMP%\cash.json" --write`. Then, in a new Command Prompt window
  (after `cd /d "%TEMP%\cos-accept"`), run `py -3 tools\dashboard\server.py` and open the Books
  tab. If the dashboard page was open before the two entries were added, reload it: the tab
  reads the ledger when the page loads and after one of its own buttons is pressed. Press
  Confirm on the gift and Void on the cash entry.
  - Expected: each `--add` prints `"written": true`; the gift's entry carries the gap
    "retail_price: provide the brand or retailer page for this item, or state the price". Both
    entries show under "Awaiting your confirmation". Confirm moves the gift out of that list.
    Void, after its confirmation prompt, takes the cash entry out of the year's lists and
    totals. "Earlier year" is not offered at 2000 and "Later year" is not offered past next year.
  - The entries and the W4 receipt are dated 2026. If the tab opens on a later year, press
    "Earlier year" until it shows 2026.
- **W7. Price capture.** In a Command Prompt window in the scratch clone, run
  `py -3 tools\price_capture.py "<link to a public product page you choose>"`, keeping the link
  inside the double quotes (a link often holds `&`, which ends a command when unquoted). Then,
  on the Books tab, press "Record price" on the gift, enter the price, the source and the link,
  and record it.
  - Expected: the price command prints either a price with `source_ref` and `captured_at`, or a
    null price with a gap saying why (both are passes of the tool; record which). The tab then
    shows the gift valued, with its price source and page.
- **W8. Mail triage on stand-in messages.** `py -3 tools\mail_triage.py --selftest`
  - Expected: exit code 0. Live mail is not read in this run.

## Clean up

Stop the wizard and the dashboard (Ctrl+C in their windows), then:

```
cd /d "%TEMP%"
rmdir /s /q "%TEMP%\cos-accept"
rmdir /s /q "%TEMP%\cos-hub"
del "%TEMP%\gift.json"
del "%TEMP%\cash.json"
```

## Results log (copy per run; keep completed logs outside the repository)

```
Windows validation run. date: ____  operator: ____  Windows version: ____  Python: ____

W1 battery              : PASS / BLOCKED / NOT-RUN   notes: ____
W2 wizard selftest      : PASS / BLOCKED / NOT-RUN   notes: ____
W3 photo reader         : PASS / BLOCKED / NOT-RUN   engine: ____  notes: ____
W4 text receipt to books: PASS / BLOCKED / NOT-RUN   notes: ____
W5 photo receipt        : PASS / BLOCKED / NOT-RUN   fields right: ____  notes: ____
W6 Books tab            : PASS / BLOCKED / NOT-RUN   notes: ____
W7 price capture        : PASS / BLOCKED / NOT-RUN   price read or gap: ____  notes: ____
W8 mail triage selftest : PASS / BLOCKED / NOT-RUN   notes: ____

Not exercised (by design of this run): the Install buttons against real Claude Desktop, Codex
and Antigravity settings; a real hub; live mail; OAuth and publishing.
```
