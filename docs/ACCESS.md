# Putting the dashboard behind a sign-in

The dashboard is a static site, so the lock has to sit in front of it rather than inside it. The arrangement below
uses **Cloudflare Pages** to host the files and **Cloudflare Access** as the door: only email addresses you list can
get in, and each visitor proves who they are with a one-time code sent to that address (or a Google / Microsoft login
if you prefer). Free for up to 50 users. Nothing changes in the pipeline; the refresh, QA pull request and repair
issue all keep working exactly as before.

Think of it as moving the exhibition from a shop window to a gallery with a guest list.

## One-off setup (about 30 minutes)

### 1. Create a Cloudflare account and a Pages project (5 min)
1. Sign up at https://dash.cloudflare.com/sign-up (free plan). Verify your email.
2. In the left menu open **Workers & Pages → Create → Pages → Upload assets**.
   Project name: `super-insights` (exactly). Upload any single file to finish the wizard — the real content arrives
   from GitHub in step 3. Your site address will be `https://super-insights.pages.dev`.

### 2. Give GitHub permission to publish to it (5 min)
1. Cloudflare: click your profile icon (top right) → **My Profile → API Tokens → Create Token → Custom token**.
   Name: `github-super-insights`. Permissions: **Account · Cloudflare Pages · Edit**. Account resources: your account.
   Click **Continue to summary → Create Token**. Copy the token — it is shown once.
2. Cloudflare: **Workers & Pages → Overview** — the **Account ID** is in the right-hand column. Copy it.
3. GitHub: your repository → **Settings → Secrets and variables → Actions → New repository secret**, twice:
   * `CLOUDFLARE_API_TOKEN` = the token
   * `CLOUDFLARE_ACCOUNT_ID` = the account id
   (You paste these yourself; nobody else should ever see the token.)

### 3. Publish (2 min)
GitHub → **Actions → Deploy dashboard → Run workflow**. The workflow sees the two secrets and deploys to Cloudflare
instead of GitHub Pages. When it is green, open https://super-insights.pages.dev — the dashboard, still open to all.

### 4. Lock the door with Cloudflare Access (10 min)
1. Cloudflare left menu → **Zero Trust** (first time: choose a team name, e.g. `super-insights`, and the **Free** plan).
2. **Access → Applications → Add an application → Self-hosted**.
   * Application name: `Super Insights`
   * Session duration: `1 week` (visitors sign in once a week)
   * Public hostname: subdomain `super-insights`, domain `pages.dev` → this protects `super-insights.pages.dev`.
     Click **Add public hostname** again and add subdomain `*.super-insights` domain `pages.dev` so preview
     deployments are covered too.
3. **Add policies → Add a policy**:
   * Policy name: `Guest list` · Action: **Allow**
   * Include → Selector **Emails** → paste the allowed addresses, one per line (start with your own).
     (Alternative: selector **Emails ending in** with `@yourfirm.com` to allow a whole domain.)
4. Login methods: leave **One-time PIN** ticked (it is on by default). Optional: **Settings → Authentication → Add new →
   Google** if you want people to use their Google account instead.
5. Save. Open https://super-insights.pages.dev in a private window: you should see the Cloudflare sign-in page, get a
   code by email, and then the dashboard.

### 5. Close the shop window (2 min)
Until now the old address on GitHub Pages still works. Once Cloudflare is confirmed:
1. GitHub → **Settings → Pages → Unpublish site** (three dots next to the live URL).
2. GitHub → **Settings → General → Danger Zone → Change repository visibility → Private**.
   The refresh workflows keep running (private repositories get 2,000 free Actions minutes a month; the six-monthly
   refresh uses about 70).

## Day to day
* **Add or remove a person**: Zero Trust → Access → Applications → Super Insights → Policies → Guest list → edit the
  email list → Save. Takes effect immediately; removed people are cut off at their next page load.
* **See who has been signing in**: Zero Trust → Logs → Access.
* **The link to give people**: https://super-insights.pages.dev — they enter their email, receive a six-digit code,
  and are in. No passwords to manage.
* **Custom address later** (e.g. `insights.yourdomain.com`): add the domain to Cloudflare, then Pages project →
  Custom domains, and add the same hostname to the Access application.

## What this does and does not protect
* It protects the dashboard pages and every data file under `/data/` — Access sits in front of the whole hostname.
* It does **not** stop an allowed person downloading data and sharing it; the guest list is the control.
* The underlying source material (funds' Portfolio Holdings Disclosures, APRA statistics) is public by law; what you
  are protecting is the assembled, cleaned dataset and the analysis.
