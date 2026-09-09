# Setting up Super Insights — the checklist

You do not need to write code. You need a free GitHub account, about 45 minutes, and this list. Each step says
exactly what to click. Once it is done, the system refreshes itself every April and October.

Think of it as opening a bank account for data: you set it up once, the standing orders (the six-monthly refresh)
run on their own, and you review the statement (the QA report) when it arrives.

---

## Part A — Put the code on GitHub (15 minutes)

1. **Create a GitHub account** at https://github.com/signup if you do not have one. Use your work email.
   Turn on two-factor authentication when prompted.
2. **Create a new repository.** Click the **+** (top right) → **New repository**.
   * Repository name: `super-insights`
   * Visibility: **Public** (GitHub Pages hosting is free only for public repositories; everything here is built from
     public disclosures, so nothing confidential is exposed)
   * Leave "Add a README" **unticked**. Click **Create repository**.
3. **Upload the code.** On the empty repository page click **uploading an existing file**.
   Unzip `super-insights.zip` on your Mac, open the unzipped folder, select **everything inside it** (including the
   hidden `.github` folder — press `Cmd+Shift+.` in Finder to show hidden files) and drag it into the browser window.
   Wait for the upload bar to finish, type `Initial import` in the commit box, click **Commit changes**.
   *If the drag-and-drop refuses the `.github` folder, install GitHub Desktop (https://desktop.github.com), choose
   File → Add local repository → pick the unzipped folder → Publish repository. Either route works.*
4. **Check it arrived.** The repository page should show folders `config`, `pipeline`, `site`, `tests`, `docs`, `.github`.

## Part B — Switch on the dashboard (5 minutes)

5. Click **Settings** (repository tab) → **Pages** (left menu).
   Under **Build and deployment → Source** choose **GitHub Actions**. Nothing else to change.
6. Click the **Actions** tab. If it asks you to enable workflows, click **I understand my workflows, go ahead and enable them**.
7. In **Actions**, click **Deploy dashboard** (left list) → **Run workflow** → **Run workflow**.
   After ~2 minutes it goes green. Go back to **Settings → Pages**; the page shows your dashboard address, something like
   `https://<your-username>.github.io/super-insights/`. Open it. You will see the dashboard populated with three
   **synthetic example funds** — proof the plumbing works before any real data.

## Part C — Load real data for the first time (20 minutes)

You have two ways to get real data in. Do both: the first gives you content today, the second is the real thing.

8. **Seed with the reference dataset (Graeme's).** Nothing to do: the refresh workflow downloads
   `super_holdings_dec2025.json` and `apra_saa_dec2025.json` from `fund-scope-pro.lovable.app` into `seed/` on its
   first run and imports them as snapshot `2025-12-31`, tagged as reference-imported so they are never confused with
   primary data. If that site ever disappears, save the two files by hand and upload them to the `seed/` folder.
9. **Run the first real harvest.** **Actions → Six-monthly refresh → Run workflow**. Leave both boxes empty and click
   **Run workflow**. This downloads every fund's latest Portfolio Holdings Disclosure and the APRA statistics, parses,
   validates and builds. It takes 20–60 minutes.
10. **Read the result.** When it finishes you will find:
    * a **Pull request** titled `data: snapshot <date>` — its description is the QA report: which options loaded,
      which were quarantined and why. Click **Merge pull request** to publish; the dashboard redeploys itself.
    * possibly an **Issue** titled `repair: <date> — N fund(s) need attention`. That is the list of funds whose
      website moved or whose file layout defeated the parser. Expect several on the very first run: the registry of
      fund web pages in `config/sources.csv` has not been verified against the live sites yet.

## Part D — Let an agent do the repairs (10 minutes, optional but recommended)

11. **Get an Anthropic API key** at https://console.anthropic.com → API Keys → Create key. Copy it.
12. In GitHub: **Settings → Secrets and variables → Actions → New repository secret**.
    Name: `ANTHROPIC_API_KEY`. Value: paste the key. Save.
    From now on, whenever a refresh has failures, a Claude agent reads the repair report, fixes the fund registry or
    writes a parser adapter with tests, and opens a pull request for you to review and merge. You stay in control:
    nothing reaches the dashboard until you click Merge.
13. Optional: an **OpenFIGI** key (free, https://www.openfigi.com/api) as secret `OPENFIGI_API_KEY` speeds up the
    security master from ~10 to 100 identifiers per request.
14. For working on your Mac with Claude Code: install it (https://docs.claude.com/en/docs/claude-code), open a terminal
    in the repository folder and say, for example, "run make test, then import seed/super_holdings_dec2025.json as
    snapshot 2025-12-31 and rebuild the site". `docs/ARCHITECTURE.md` tells the agent how everything fits.

## Part E — The six-monthly rhythm (what happens without you)

| When | What |
|---|---|
| 28 September / 31 March | Trustees' deadline to publish 30 June / 31 December holdings |
| 5 October / 5 April, 06:00 AEST | The refresh runs by itself, opens the data pull request and, if needed, the repair issue |
| Same day, if the API key is set | The repair agent works through the issue and opens fix pull requests |
| When you have 15 minutes | Read the QA report, merge; the dashboard updates. From the second snapshot the Time Series page fills in |

You can run the refresh by hand at any time (Actions → Six-monthly refresh → Run workflow), and limit it to one fund
by typing its `fund_id` (from `config/sources.csv`) in the "only" box.

## If something goes wrong

* **Workflow red at "Harvest"** — usually a fund website blocking automated downloads. The repair issue names it; a
  human (or the agent) downloads the file by hand and drops it into `raw/<snapshot>/<fund_id>/`, then re-runs the
  workflow with that fund in the "only" box.
* **APRA step failed** — APRA renamed a sheet or column. Fix `COLUMN_HINTS` in `pipeline/apra.py` (the agent does this).
* **Dashboard shows old data** — the pull request has not been merged yet.
* **Everything else** — open the repository in Claude Code and describe the symptom; `reports/` holds the evidence.

## Brand note

Publish this under the Qblue Balanced identity or a neutral research brand. It is an institutional research asset.
