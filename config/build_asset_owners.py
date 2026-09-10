"""Asset-owner registry beyond superannuation: Commonwealth and state sovereign / public investment funds, state
insurers and compensation schemes, New Zealand Crown investors, and life insurers / friendly societies with
investment products.

None of these publish holdings under the superannuation Portfolio Holdings Disclosure regime, so the dashboard
records what each one DOES publish (size, mandate, allocation, manager list, holdings list) and where. Run
`python config/build_asset_owners.py` to regenerate site/data/asset_owners.json. Every figure carries a source and
an as-at date; "to confirm" means the figure was not verifiable from a primary source at the time of writing.
"""
import json
from pathlib import Path

GROUPS = [
    "Commonwealth & state investment funds",
    "State insurers & compensation schemes",
    "New Zealand Crown investors",
    "Life insurers & friendly societies (investment products)",
]

E = []  # entities

def add(**kw):
    kw.setdefault("confidence", "sourced")
    kw.setdefault("allocation", {})
    kw.setdefault("notes", "")
    E.append(kw)

# ---------------------------------------------------------------- Commonwealth & state investment funds
add(id="future_fund", name="Future Fund (Board of Guardians)", group=GROUPS[0], jurisdiction="Commonwealth", run_by="Future Fund Management Agency (in-house asset allocation; ~all assets externally managed)",
    aum_bn=335.3, currency="A$", aum_asof="31 Dec 2025",
    mandate="Sovereign wealth fund family: Future Fund $267.4bn plus Medical Research Future Fund $25.3bn, DisabilityCare Australia Fund $18.1bn, Housing Australia Future Fund $11.4bn, Future Drought Fund $5.5bn, Disaster Ready Fund $5.2bn, ATSI Land & Sea Future Fund $2.5bn. Mandate CPI+4–5% pa; 2025 return 12.4%.",
    allocation={"Global equities (developed)": 29.3, "Alternatives": 15.1, "Private equity": 12.5, "Australian equities": 10.7, "Infrastructure & timberland": 10.5, "Credit": 8.5, "Cash": 4.7, "Property": 4.3},
    managers_published="full", managers_url="https://www.futurefund.gov.au/investment/how-we-invest/investment-managers", managers_note="Names every external manager by asset class (~150 across equities, PE, property, infrastructure, credit, alternatives, overlays), as at 31 Dec 2025.",
    holdings_published="none", holdings_url="", cadence="Quarterly portfolio update; annual report (Oct); manager list refreshed each half-year",
    sources=["https://www.futurefund.gov.au/-/media/80E64D906DF040ED81D6999F3608A500.ashx", "https://www.futurefund.gov.au/investment/how-we-invest/investment-managers"])

add(id="tcorp", name="TCorp — NSW Treasury Corporation (incl. NSW Generations Fund)", group=GROUPS[0], jurisdiction="New South Wales", run_by="TCorp (in-house total-portfolio management; external managers not named)",
    aum_bn=118.6, currency="A$", aum_asof="30 Jun 2025",
    mandate="Investment manager for the NSW public sector: NSW Generations (Debt Retirement) Fund $19.0bn, NSW Infrastructure Future Fund $4.5bn, State Super (SAS Trustee) $30.2bn, icare Workers Compensation Insurance Fund $18.5bn, Lifetime Care & Support $12.2bn; OneFund pooled vehicle $64.5bn from Aug 2024.",
    allocation={"United States": 49, "Australia": 24, "Europe incl. UK": 15, "Other developed": 7, "Emerging markets": 5},
    managers_published="none", managers_url="https://tcorp.nsw.gov.au/tcorp/about-tcorp/annual-report-2025/", managers_note="Annual report refers to external managers generically; no names. Geographic and sector splits of listed equities are published instead.",
    holdings_published="none", holdings_url="", cadence="Annual report (Nov/Dec)",
    notes="Allocation shown is the geographic split of the investment portfolio, not an asset-class SAA.",
    sources=["https://tcorp.nsw.gov.au/wp-content/uploads/2025/12/TCorp_Annual_Report_2025.pdf"])

add(id="vfmc", name="VFMC — Victorian Funds Management Corporation (incl. Victorian Future Fund)", group=GROUPS[0], jurisdiction="Victoria", run_by="VFMC (in-house plus external managers, not named)",
    aum_bn=95.3, currency="A$", aum_asof="30 Jun 2025",
    mandate="Manages $95.3bn for 31 Victorian public authorities. Four 'Foundation' clients are ~84% of assets: WorkSafe Victoria, TAC, VMIA and ESSSuper; also the Victorian Future Fund and 26 smaller clients.",
    allocation={"International equities": 29.7, "Australian equities": 15.2, "Infrastructure": 11.0, "Property": 11.0, "Private credit": 10.0, "Hedge funds": 8.9},
    managers_published="none", managers_url="https://www.vfmc.vic.gov.au/wp-content/uploads/2025/10/VFMC-Annual-Report-2024-25.pdf", managers_note="Annual report states VFMC partners with external managers but does not list them.",
    holdings_published="none", holdings_url="", cadence="Annual report (Oct)",
    notes="Allocation is the Foundation CIM aggregate SAA at 30 Jun 2025 (remainder in bonds, EMD and cash).",
    sources=["https://www.vfmc.vic.gov.au/wp-content/uploads/2025/10/VFMC-Annual-Report-2024-25.pdf"])

add(id="qic", name="QIC — Queensland Investment Corporation (incl. Queensland Future Fund)", group=GROUPS[0], jurisdiction="Queensland", run_by="QIC (government-owned investment manager; also a third-party manager)",
    aum_bn=137.0, currency="A$", aum_asof="31 Mar 2026",
    mandate="Manages the State's Long Term Asset portfolio (~$37bn backing defined-benefit super liabilities) and the Queensland Future Fund — Debt Retirement Fund ($12.0bn at 30 Jun 2025, +$2.2bn in FY25; a further $3bn transfer planned from the DB surplus in 2025-26) alongside WorkCover Queensland and other state pools; the $137bn total includes third-party client money.",
    managers_published="none", managers_url="https://www.qic.com/About-QIC/Corporate-governance/Annual-Reports", managers_note="QIC is largely the manager itself; sub-managers not disclosed.",
    holdings_published="none", holdings_url="", cadence="Annual report (Sep/Oct); Queensland Audit Office 'Managing Queensland's finances' each year",
    sources=["https://www.qic.com/About-QIC/Who-we-are", "https://www.qao.qld.gov.au/reports-resources/reports-parliament/managing-queenslands-finances-2025"])

add(id="funds_sa", name="Funds SA", group=GROUPS[0], jurisdiction="South Australia", run_by="Funds SA (in-house asset allocation; external managers named)",
    aum_bn=32.0, currency="A$", aum_asof="30 Jun 2025",
    mandate="Investment corporation for the SA public sector: Super SA (Triple S, Flexible Rollover, Income Stream), SA defined-benefit schemes, ReturnToWorkSA, Lifetime Support Authority, Motor Accident Commission legacy and other agencies.",
    managers_published="full", managers_url="https://www.funds.sa.gov.au/about-funds-sa/investments/fund-managers/", managers_note="Names every manager by asset class (Airlie, Baillie Gifford, Arrowstreet, Charter Hall, Ardian, EQT, Blackstone, Ares, Oak Hill, Bain, Colchester…), as at 31 Dec 2025.",
    holdings_published="none", holdings_url="", cadence="Annual report (Oct); manager list refreshed half-yearly",
    sources=["https://www.top1000funds.com/asset_owner/funds-sa/", "https://www.funds.sa.gov.au/about-funds-sa/investments/fund-managers/"])

add(id="wa_future_fund", name="Western Australian Future Fund", group=GROUPS[0], jurisdiction="Western Australia", run_by="WA Treasury with the Western Australian Treasury Corporation",
    aum_bn=None, currency="A$", aum_asof="to confirm",
    mandate="Legislated (2012) sovereign fund seeded with royalty income; balance disclosed in WA Treasury budget papers and the Annual Report on State Finances. Size not verified from a primary source in this pass.",
    managers_published="none", managers_url="https://www.watc.wa.gov.au/about-us/news-and-reports/annual-report-2025/", managers_note="No public manager list.",
    holdings_published="none", holdings_url="", cadence="Budget papers (May) and Annual Report on State Finances (Sep)",
    confidence="partial",
    sources=["https://www.wa.gov.au/system/files/2025-09/2024-25-arsf.pdf", "https://www.watc.wa.gov.au/about-us/news-and-reports/annual-report-2025/"])

# ---------------------------------------------------------------- State insurers & compensation schemes
add(id="icare", name="icare — Insurance & Care NSW", group=GROUPS[1], jurisdiction="New South Wales", run_by="TCorp",
    aum_bn=18.5, currency="A$", aum_asof="30 Jun 2025",
    mandate="Workers Compensation Insurance Fund ($18.5bn under TCorp management) plus Treasury Managed Fund, Dust Diseases and other schemes. Lifetime Care & Support Authority ($12.2bn) is a separate NSW scheme also run by TCorp.",
    managers_published="none", managers_url="https://tcorp.nsw.gov.au/wp-content/uploads/2025/12/TCorp_Annual_Report_2025.pdf", managers_note="Via TCorp — no names.",
    holdings_published="none", holdings_url="", cadence="icare annual report (Oct); TCorp annual report",
    sources=["https://tcorp.nsw.gov.au/wp-content/uploads/2025/12/TCorp_Annual_Report_2025.pdf"])

add(id="tac", name="TAC — Transport Accident Commission (Victoria)", group=GROUPS[1], jurisdiction="Victoria", run_by="VFMC",
    aum_bn=18.0, currency="A$", aum_asof="Jun 2025 (CEO estimate to PAEC)",
    mandate="No-fault motor accident insurer; investment portfolio 'in the order of $18 billion' managed by VFMC; returns 9.24% (FY24), 9.48% (FY23).",
    managers_published="none", managers_url="https://www.tac.vic.gov.au/about-the-tac/media-room/annual-reports", managers_note="Via VFMC — no names.",
    holdings_published="none", holdings_url="", cadence="Annual report (Oct)",
    sources=["https://www.parliament.vic.gov.au/49ef1d/contentassets/961ea8c5b21047ab91b0a3ddae865e02/paec-2025-26-budget-estimates-4-june-worksafe-and-the-tac.pdf"])

add(id="worksafe_vic", name="WorkSafe Victoria", group=GROUPS[1], jurisdiction="Victoria", run_by="VFMC",
    aum_bn=None, currency="A$", aum_asof="to confirm",
    mandate="Workers' compensation insurer; assets managed by VFMC (investment expenses ~$65.5m in 2024; contracted future capital contributions of almost $2bn). Portfolio size to confirm from the WorkSafe annual report.",
    managers_published="none", managers_url="https://www.vfmc.vic.gov.au/", managers_note="Via VFMC — no names.",
    holdings_published="none", holdings_url="", cadence="Annual report (Oct)", confidence="partial",
    sources=["https://www.parliament.vic.gov.au/49ef1d/contentassets/961ea8c5b21047ab91b0a3ddae865e02/paec-2025-26-budget-estimates-4-june-worksafe-and-the-tac.pdf"])

add(id="workcover_qld", name="WorkCover Queensland", group=GROUPS[1], jurisdiction="Queensland", run_by="QIC",
    aum_bn=None, currency="A$", aum_asof="to confirm",
    mandate="Statutory workers' compensation insurer; investments managed by QIC. Size to confirm from the WorkCover Queensland annual report.",
    managers_published="none", managers_url="https://www.qic.com/", managers_note="Via QIC — no names.",
    holdings_published="none", holdings_url="", cadence="Annual report (Sep)", confidence="partial",
    sources=["https://www.qao.qld.gov.au/reports-resources/reports-parliament/managing-queenslands-finances-2025"])

add(id="icwa", name="Insurance Commission of Western Australia", group=GROUPS[1], jurisdiction="Western Australia", run_by="ICWA (in-house with external managers)",
    aum_bn=None, currency="A$", aum_asof="to confirm",
    mandate="Motor injury and government self-insurance; one of the few state insurers that historically named its external managers in its annual report — verify in the latest report.",
    managers_published="partial", managers_url="https://www.icwa.wa.gov.au/", managers_note="Historically listed in the annual report; check current edition.",
    holdings_published="none", holdings_url="", cadence="Annual report (Sep)", confidence="partial",
    sources=["https://en.wikipedia.org/wiki/Insurance_Commission_of_Western_Australia"])

add(id="maib", name="MAIB — Motor Accidents Insurance Board (Tasmania)", group=GROUPS[1], jurisdiction="Tasmania", run_by="MAIB (external managers)",
    aum_bn=None, currency="A$", aum_asof="to confirm",
    mandate="Tasmanian compulsory third-party insurer with a multi-billion-dollar investment portfolio; annual report discloses asset allocation. Size to confirm.",
    managers_published="partial", managers_url="https://www.maib.tas.gov.au/", managers_note="Check annual report.",
    holdings_published="none", holdings_url="", cadence="Annual report (Oct)", confidence="partial", sources=["https://www.maib.tas.gov.au/"])

add(id="rtwsa", name="ReturnToWorkSA / Lifetime Support Authority (SA)", group=GROUPS[1], jurisdiction="South Australia", run_by="Funds SA",
    aum_bn=None, currency="A$", aum_asof="to confirm",
    mandate="SA workers' compensation and lifetime support schemes; assets pooled with Funds SA, whose manager list therefore applies.",
    managers_published="full", managers_url="https://www.funds.sa.gov.au/about-funds-sa/investments/fund-managers/", managers_note="Via Funds SA (published).",
    holdings_published="none", holdings_url="", cadence="Annual reports (Oct)", confidence="partial", sources=["https://www.funds.sa.gov.au/about-funds-sa/investments/fund-managers/"])

# ---------------------------------------------------------------- New Zealand Crown investors
add(id="nz_super", name="NZ Super Fund (Guardians of New Zealand Superannuation)", group=GROUPS[2], jurisdiction="New Zealand", run_by="Guardians (reference-portfolio model; internal and external mandates)",
    aum_bn=84.4, currency="NZ$", aum_asof="30 Jun 2025 (implied from 3.2% impact allocation = $2.7bn)",
    mandate="Pre-funds future NZ Superannuation cost; FY25 return 11.84% after costs; 20-year 9.92% pa. Impact investments ~3.2% of assets.",
    managers_published="full", managers_url="https://nzsuperfund.nz/how-we-invest/investment-managers/our-managers/", managers_note="Every external manager and mandate named (AQR, Bridgewater, Citadel, Man AHL, KKR, Stonepeak, CIP, Generation IM, PIMCO carbon credits…), as at 31 Dec 2025.",
    holdings_published="full", holdings_url="https://nzsuperfund.nz/publications/disclosures/annual-equity-listings/", holdings_note="Full listed-equity holdings, NZ holdings with ownership %, external and internal mandates and direct investments published every six months in Excel (latest 31 Dec 2025; series back to 2010) — the best disclosure in the region, and directly ingestible.",
    cadence="Six-monthly portfolio disclosure; annual report (Oct)", confidence="sourced",
    sources=["https://nzsuperfund.nz/news-and-media/guardians-releases-2025-annual-report/", "https://nzsuperfund.nz/publications/disclosures/annual-equity-listings/", "https://nzsuperfund.nz/how-we-invest/investment-managers/our-managers/"])

add(id="acc", name="ACC — Accident Compensation Corporation (NZ)", group=GROUPS[2], jurisdiction="New Zealand", run_by="ACC Investments (largely in-house)",
    aum_bn=None, currency="NZ$", aum_asof="to confirm",
    mandate="Invests reserves against the future cost of injuries already incurred; NZ's largest institutional investor after NZ Super. Publishes investment beliefs, ethical investment policy and climate statement; an independent Treasury-commissioned assurance review (WTW) was released July 2025. Portfolio size to confirm from the 2025 annual report.",
    managers_published="partial", managers_url="https://www.acc.co.nz/about-us/our-investments", managers_note="Mostly internal; external mandates referenced in the annual report.",
    holdings_published="partial", holdings_url="https://www.acc.co.nz/about-us/our-investments", holdings_note="Publishes NZ and global equity holdings lists periodically — verify latest.",
    cadence="Annual report (Oct)", confidence="partial",
    sources=["https://www.acc.co.nz/about-us/our-investments", "https://www.treasury.govt.nz/publications/information-release/acc-investments-independent-review"])

# ---------------------------------------------------------------- Life insurers & friendly societies (investment products)
add(id="acenda", name="Acenda (Resolution Life Australasia + MLC Life; Nippon Life group)", group=GROUPS[3], jurisdiction="Australia / NZ", run_by="Acenda (legacy AMP Life, AIA S&I and MLC Life books)",
    aum_bn=29.0, currency="A$", aum_asof="Dec 2024 (Resolution Life Australasia alone)",
    mandate="Merger announced 11 Dec 2024, completing H2 2025, ~2m customers; holds the largest legacy investment-linked, participating and investment-bond books in Australia (ex-AMP Life, ex-AIA Superannuation & Investments, MLC Life). Option menus and unit prices published per product.",
    managers_published="partial", managers_url="https://resolutionlife.com.au/", managers_note="Underlying managers disclosed per investment option in PDS / option profiles.",
    holdings_published="none", holdings_url="", cadence="PDS updates; APRA quarterly life statistics",
    sources=["https://resolutionlife.com.au/sites/default/files/AUS_Media_Statement-Resolution_Life_Australasia.pdf"])

add(id="generation_life", name="Generation Life (Generation Development Group, ASX: GDG)", group=GROUPS[3], jurisdiction="Australia", run_by="Generation Life (friendly-society structure; external managers per option)",
    aum_bn=None, currency="A$", aum_asof="to confirm (GDG group FUM $46.4bn incl. Evidentia)",
    mandate="Largest specialist investment-bond provider; adviser-led, record inflows FY26; menu of ~70 options from external managers plus LifeIncome annuity-style products.",
    managers_published="full", managers_url="https://www.genlife.com.au/", managers_note="Each option names its manager (Vanguard, Dimensional, Magellan, Pendal…). Option-level allocations in PDS.",
    holdings_published="none", holdings_url="", cadence="Quarterly FUM announcements (ASX); PDS", confidence="partial",
    sources=["https://kalkine.com.au/news/announcements/generation-development-group-reports-464-billion-fum-as-evidentia-and-generation-life-drive-record-growth"])

add(id="australian_unity", name="Australian Unity (Lifeplan investment bonds)", group=GROUPS[3], jurisdiction="Australia", run_by="Australian Unity Life & Super / Lifeplan",
    aum_bn=None, currency="A$", aum_asof="to confirm ($2.2bn at 30 Jun 2018)",
    mandate="Mutual; Lifeplan Investment Bond with the broadest investment-bond menu (74 options incl. ethical and index) plus education and funeral bonds.",
    managers_published="full", managers_url="https://www.australianunity.com.au/wealth/investment-bonds", managers_note="Each option names its underlying manager in the PDS.",
    holdings_published="none", holdings_url="", cadence="PDS; annual report (Sep)", confidence="partial",
    sources=["https://www.australianunity.com.au/media-centre/news-and-media/australian-unity-strengthens-investment-bond-offering"])

add(id="aia_au", name="AIA Australia", group=GROUPS[3], jurisdiction="Australia", run_by="AIA (risk-focused since S&I sale to Resolution Life, 2022)",
    aum_bn=None, currency="A$", aum_asof="n/a",
    mandate="Largest Australian life insurer by premium; sold its Superannuation & Investments business (ex-CommInsure) to Resolution Life in 2022, so investment-option books now sit with Acenda. Retains participating and shareholder funds.",
    managers_published="none", managers_url="https://www.aia.com.au/", managers_note="", holdings_published="none", holdings_url="", cadence="APRA quarterly life statistics", confidence="partial",
    sources=["https://www.resolutionlife.com/news-and-insights/resolution-life-australasia-to-acquire-aia-australia-s-superannuation-investments-business/"])

add(id="tal", name="TAL (Dai-ichi Life)", group=GROUPS[3], jurisdiction="Australia", run_by="TAL", aum_bn=None, currency="A$", aum_asof="n/a",
    mandate="Risk insurer (incl. ex-Westpac Life / ex-Suncorp Life); limited investment-option products; shareholder and statutory fund allocations in APRA returns.",
    managers_published="none", managers_url="https://www.tal.com.au/", managers_note="", holdings_published="none", holdings_url="", cadence="APRA quarterly life statistics", confidence="partial", sources=["https://www.insurancebusinessmag.com/au/guides/the-top-5-life-insurance-companies-in-australia-440994.aspx"])

add(id="zurich_au", name="Zurich Australia (incl. ex-OnePath Life)", group=GROUPS[3], jurisdiction="Australia", run_by="Zurich", aum_bn=None, currency="A$", aum_asof="n/a",
    mandate="Risk insurer with legacy investment-linked policies from the OnePath acquisition; Zurich Investments manages listed funds separately.",
    managers_published="none", managers_url="https://www.zurich.com.au/", managers_note="", holdings_published="none", holdings_url="", cadence="APRA quarterly life statistics", confidence="partial", sources=["https://www.insurancebusinessmag.com/au/guides/the-top-5-life-insurance-companies-in-australia-440994.aspx"])

add(id="foresters", name="Foresters Financial (friendly society)", group=GROUPS[3], jurisdiction="Australia", run_by="Foresters Financial", aum_bn=None, currency="A$", aum_asof="to confirm",
    mandate="Friendly society offering investment, education and funeral bonds with externally managed option menus.",
    managers_published="full", managers_url="https://forestersfinancial.com.au/", managers_note="Per option in PDS.", holdings_published="none", holdings_url="", cadence="PDS; annual report", confidence="partial", sources=["https://forestersfinancial.com.au/"])

add(id="keyinvest", name="KeyInvest (friendly society)", group=GROUPS[3], jurisdiction="Australia", run_by="KeyInvest", aum_bn=None, currency="A$", aum_asof="to confirm",
    mandate="Adelaide-based friendly society; investment and funeral bonds.", managers_published="partial", managers_url="https://www.keyinvest.com.au/", managers_note="Per option in PDS.", holdings_published="none", holdings_url="", cadence="PDS; annual report", confidence="partial", sources=["https://www.keyinvest.com.au/"])

add(id="insignia_bonds", name="Insignia Financial (IOOF WealthBuilder investment bonds)", group=GROUPS[3], jurisdiction="Australia", run_by="IOOF Ltd (Insignia)", aum_bn=None, currency="A$", aum_asof="to confirm",
    mandate="Investment-bond and legacy life-insurance books within the Insignia group (parent of MLC Super Fund in the super universe).", managers_published="partial", managers_url="https://www.insigniafinancial.com.au/", managers_note="Per option in PDS.", holdings_published="none", holdings_url="", cadence="PDS; half-year results", confidence="partial", sources=["https://www.insigniafinancial.com.au/"])

CONTEXT = [
    "None of these entities are covered by the superannuation Portfolio Holdings Disclosure regime (Corporations Regulations Sch 8D), so line-by-line holdings exist only where an owner chooses to publish them: NZ Super Fund (full, six-monthly) and ACC (partial). Everything else is annual-report level: size, mandate, strategic allocation, sometimes a manager list.",
    "For manager-prospecting purposes the three best public manager registers are the Future Fund (~150 names by asset class), Funds SA (every manager by asset class) and NZ Super Fund (every mandate). TCorp, VFMC and QIC run money largely in-house and do not name sub-managers.",
    "State insurers (icare, TAC, WorkSafe Vic, WorkCover Qld, ReturnToWorkSA, Lifetime Care) do not invest directly: their assets sit with the state investment corporation (TCorp, VFMC, QIC, Funds SA), so the corporation's disclosure is the insurer's disclosure.",
    "Life insurers' investment-option books have consolidated into Acenda (Resolution Life + MLC Life + ex-AIA S&I, Nippon Life) and the specialist investment-bond providers (Generation Life, Australian Unity, Foresters, KeyInvest, IOOF). Their disclosure is per option via PDS and unit prices, with underlying managers named per option — structurally like retail super platforms rather than asset owners.",
]

out = {"groups": GROUPS, "context": CONTEXT, "entities": E, "generated_by": "config/build_asset_owners.py (hand-curated, sourced)"}
dest = Path(__file__).resolve().parents[1] / "site" / "data" / "asset_owners.json"
dest.write_text(json.dumps(out, ensure_ascii=False, indent=1))
print(f"wrote {dest} ({len(E)} entities)")
