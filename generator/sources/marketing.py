"""Marketing exports: Google Ads, Universal Analytics, Mailchimp, Qualtrics NPS.

Renders:
  marketing/google_ads/Campaign_report_2020.csv      UTF-16LE with BOM, tab separated, title rows, 'Total:' rows, costs with commas
  marketing/google_ads/Campaign_report_2019.csv      same format, previous year
  marketing/google_analytics_ua/*.csv                Universal Analytics export with '#' comment headers and blank-line sections
  marketing/mailchimp/{subscribed,unsubscribed,cleaned}_members_export.csv
  marketing/qualtrics/Customer_NPS_2024-2026.csv     three header rows, preview and unfinished responses mixed in

Planted:
  GF33  2020 spend on the 'Classic migration' campaign
  GF34  NPS for Q2 2025 (exclude survey previews and unfinished responses)
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from ..util import add_fact, b62, csv_line, rng_for, write_text

RAW = "data/raw"


def ads_report(r, year, campaigns):
    lines = ["Campaign report", f"January 1, {year} - December 31, {year}",
             "\t".join(["Campaign status", "Campaign", "Month", "Budget", "Budget type", "Currency code", "Impr.", "Clicks", "CTR",
                        "Avg. CPC", "Cost", "Conversions", "Cost / conv."])]
    totals = {}
    for name, status, base in campaigns:
        for m in range(1, 13):
            if base == 0 or (name.startswith("Classic migration") and year == 2020 and m > 9):
                cost = 0.0
            else:
                cost = round(base * r.uniform(0.6, 1.4), 2)
            clicks = int(cost / r.uniform(2.1, 6.5)) if cost else 0
            impr = clicks * r.randint(18, 60)
            conv = round(clicks * r.uniform(0.01, 0.06), 2)
            totals[name] = totals.get(name, 0.0) + cost
            lines.append("\t".join([status, name, f"{date(year, m, 1):%B %Y}", f"{base / 30:,.2f}" if base else "0.00", "Daily", "USD",
                                    f"{impr:,}", f"{clicks:,}", f"{(clicks / impr * 100 if impr else 0):.2f}%", f"{(cost / clicks if clicks else 0):.2f}",
                                    f'"{cost:,.2f}"' if cost >= 1000 else f"{cost:.2f}", f"{conv:.2f}", f"{(cost / conv if conv else 0):,.2f}"]))
    total = sum(totals.values())
    lines.append("\t".join(["Total: Account", "--", "--", "--", "--", "USD", "--", "--", "--", "--", f'"{total:,.2f}"', "--", "--"]))
    lines.append("\t".join(["Total: Search", "--", "--", "--", "--", "USD", "--", "--", "--", "--", f'"{total * 0.94:,.2f}"', "--", "--"]))
    lines.append("\t".join(["Total: Display", "--", "--", "--", "--", "USD", "--", "--", "--", "--", f'"{total * 0.06:,.2f}"', "--", "--"]))
    return "\r\n".join(lines) + "\r\n", totals


def render(world, out, seed):
    r = rng_for(seed, "marketing")
    mk = out / "marketing"

    # ----------------------------------------------------------------- GF33 Google Ads
    c2020 = [("Enabled", "Brand - Brindlecove", 900), ("Enabled", "Field service software - generic", 4200),
             ("Enabled", "Competitor - Plinthwise", 1600), ("Paused", "Classic migration - 2020", 5200),
             ("Removed", "Classic migration - 2020 (copy)", 0), ("Enabled", "Remarketing - display", 700)]
    c2020 = [(n, s, b) for s, n, b in c2020]
    text, totals = ads_report(r, 2020, c2020)
    write_text(mk / "google_ads" / "Campaign_report_2020.csv", text, encoding="utf-16-le", newline="\n", bom=True)
    c2019 = [("Brand - Brindlecove", "Enabled", 850), ("Field service software - generic", "Enabled", 3900),
             ("Classic sunset awareness", "Enabled", 1200), ("Remarketing - display", "Enabled", 650)]
    text19, _ = ads_report(r, 2019, c2019)
    write_text(mk / "google_ads" / "Campaign_report_2019.csv", text19, encoding="utf-16-le", newline="\n", bom=True)
    spend = round(totals["Classic migration - 2020"], 2)
    add_fact(world, {"id": "GF33", "difficulty": "medium", "kind": "ads export",
                     "question": "How much did Brindlecove spend on the Classic migration ad campaign in 2020?",
                     "answer": f"${spend:,.2f} (January to September 2020; the campaign was paused after the Classic sunset). The '(copy)' "
                               f"campaign spent nothing.",
                     "trail": [f"{RAW}/marketing/google_ads/Campaign_report_2020.csv (UTF-16LE, tab separated)"],
                     "traps": ["The file is UTF-16 with two title rows before the header", "Costs over 1,000 are quoted with commas",
                               "'Total:' rows at the bottom are not campaigns"],
                     "values": {"spend_usd": spend}})

    # ----------------------------------------------------------------- Universal Analytics
    for yr in (2019, 2020, 2021, 2022):
        rows = ["# ----------------------------------------", "# Brindlecove.com - All Web Site Data", "# Channels",
                f"# {yr}0101-{yr}1231", "# ----------------------------------------", "", "Default Channel Grouping,Week Index,Sessions,New Users,Bounce Rate,Avg. Session Duration,Goal Conversion Rate"]
        for ch in ["Organic Search", "Paid Search", "Direct", "Referral", "Email", "(Other)"]:
            for w in range(53):
                s = int({"Organic Search": 2400, "Paid Search": 900, "Direct": 1100, "Referral": 300, "Email": 220, "(Other)": 40}[ch] * r.uniform(0.7, 1.3))
                rows.append(f"{ch},{w:04d},\"{s:,}\",\"{int(s * r.uniform(0.5, 0.8)):,}\",{r.uniform(35, 75):.2f}%,"
                            f"00:{r.randint(0, 4):02d}:{r.randint(0, 59):02d},{r.uniform(0.3, 4.5):.2f}%")
        rows += ["", "Day Index,Sessions"] + [f"{(date(yr, 1, 1) + timedelta(days=i)):%-m/%-d/%y},\"{r.randint(400, 1400):,}\"" for i in range(365)]
        rows += ["", f"Week Index,{yr}", ",\"{0:,}\"".format(r.randint(220000, 320000))]
        write_text(mk / "google_analytics_ua" / f"Analytics All Web Site Data Channels {yr}0101-{yr}1231.csv", "\n".join(rows) + "\n")

    # ----------------------------------------------------------------- Mailchimp
    hdr = ["Email Address", "First Name", "Last Name", "Company", "MEMBER_RATING", "OPTIN_TIME", "OPTIN_IP", "CONFIRM_TIME", "CONFIRM_IP",
           "LATITUDE", "LONGITUDE", "GMTOFF", "DSTOFF", "TIMEZONE", "CC", "REGION", "LAST_CHANGED", "LEID", "EUID", "NOTES", "TAGS"]
    groups = {"subscribed": [], "unsubscribed": [], "cleaned": []}
    for c in world.customers:
        for ct in c.contacts:
            g = r.choices(["subscribed", "unsubscribed", "cleaned", None], [55, 12, 6, 27])[0]
            if not g:
                continue
            opt = datetime(2014, 1, 1) + timedelta(minutes=r.randint(0, 6_000_000))
            groups[g].append([ct.email, ct.first, ct.last, c.name, str(r.randint(1, 5)), f"{opt:%Y-%m-%d %H:%M:%S}", "", f"{opt:%Y-%m-%d %H:%M:%S}",
                              "", "", "", "", "", "", c.country, "", f"{opt + timedelta(days=r.randint(0, 900)):%Y-%m-%d %H:%M:%S}",
                              str(r.randint(10 ** 8, 10 ** 9)), b62(r, 10), "", '"Customer"' if c.cloud_start else '"Prospect"'])
    for g, rows in groups.items():
        write_text(mk / "mailchimp" / f"{g}_members_export_8a1f3c.csv", "\n".join(csv_line(x) for x in [hdr] + rows) + "\n")

    # ----------------------------------------------------------------- GF34 Qualtrics NPS
    h1 = ["StartDate", "EndDate", "Status", "IPAddress", "Progress", "Duration (in seconds)", "Finished", "RecordedDate", "ResponseId",
          "RecipientLastName", "RecipientFirstName", "RecipientEmail", "ExternalReference", "LocationLatitude", "LocationLongitude",
          "DistributionChannel", "UserLanguage", "Q1", "Q2", "Q3", "account_name", "plan"]
    h2 = ["Start Date", "End Date", "Response Type", "IP Address", "Progress", "Duration (in seconds)", "Finished", "Recorded Date", "Response ID",
          "Recipient Last Name", "Recipient First Name", "Recipient Email", "External Data Reference", "Location Latitude", "Location Longitude",
          "Distribution Channel", "User Language",
          "How likely are you to recommend Brindle Ops to a friend or colleague? - 0 = Not at all likely, 10 = Extremely likely",
          "What is the main reason for your score?", "Which feature do you use most?", "account_name", "plan"]
    h3 = ['{"ImportId":"' + x + '"}' for x in ["startDate", "endDate", "status", "ipAddress", "progress", "duration", "finished", "recordedDate",
                                               "_recordId", "recipientLastName", "recipientFirstName", "recipientEmail", "externalDataReference",
                                               "locationLatitude", "locationLongitude", "distributionChannel", "userLanguage", "QID1", "QID2_TEXT",
                                               "QID3", "account_name", "plan"]]
    rows = [h1, h2, h3]
    q2 = {"promo": 0, "detr": 0, "n": 0}
    reasons = {True: ["Easy for techs", "Support is great", "Saves us hours", "Mobile app works offline"],
               False: ["Price went up", "Sync issues", "Reports are slow", "Missing features vs Plinthwise", "Billing errors"]}
    active = [c for c in world.customers if c.cloud_start and c.contacts]
    d = date(2024, 1, 3)
    while d <= date(2026, 9, 30):
        for _ in range(r.randint(0, 6)):
            c = r.choice(active)
            if not c.active(d):
                continue
            ct = c.contacts[0]
            score = r.choices(range(11), [3, 2, 2, 3, 3, 5, 6, 10, 18, 20, 16])[0]
            kind = r.choices(["IP Address", "Survey Preview"], [96, 4])[0]
            finished = r.random() > 0.08
            if kind == "Survey Preview":
                score, finished = 10, True
            start = datetime.combine(d, datetime.min.time()) + timedelta(minutes=r.randint(600, 1400))
            dur = r.randint(25, 600)
            prog = 100 if finished else r.choice([33, 50, 66])
            sc = str(score) if (finished or r.random() < 0.6) else ""
            rows.append([f"{start:%Y-%m-%d %H:%M:%S}", f"{start + timedelta(seconds=dur):%Y-%m-%d %H:%M:%S}", kind,
                         "" if kind == "Survey Preview" else f"198.51.100.{r.randint(1, 254)}", str(prog), str(dur), "True" if finished else "False",
                         f"{start + timedelta(seconds=dur + (0 if finished else 604800)):%Y-%m-%d %H:%M:%S}", "R_" + b62(r, 15),
                         "" if kind == "Survey Preview" else ct.last, "" if kind == "Survey Preview" else ct.first,
                         "" if kind == "Survey Preview" else ct.email, "", "", "", "anonymous" if kind == "Survey Preview" else "email", "EN",
                         sc, r.choice(reasons[score >= 9]) if finished else "", r.choice(["Work orders", "Scheduling", "Invoicing", "Mobile app", ""]),
                         "" if kind == "Survey Preview" else c.name, c.plan])
            if kind == "IP Address" and finished and date(2025, 4, 1) <= d <= date(2025, 6, 30):
                q2["n"] += 1
                q2["promo"] += score >= 9
                q2["detr"] += score <= 6
        d += timedelta(days=1)
    write_text(mk / "qualtrics" / "Customer_NPS_2024-2026.csv", "\n".join(csv_line(x) for x in rows) + "\n", bom=True)
    nps = round((q2["promo"] - q2["detr"]) / q2["n"] * 100)
    add_fact(world, {"id": "GF34", "difficulty": "medium", "kind": "survey export",
                     "question": "What was the NPS for Q2 2025?",
                     "answer": f"{nps} ({q2['promo']} promoters, {q2['detr']} detractors out of {q2['n']} finished real responses, "
                               f"April to June 2025). Survey Preview rows and unfinished responses are excluded.",
                     "trail": [f"{RAW}/marketing/qualtrics/Customer_NPS_2024-2026.csv (three header rows)"],
                     "traps": ["Rows 2 and 3 are header rows, not data", "Status 'Survey Preview' rows are test responses (all scored 10)",
                               "Finished=False rows sometimes have a score"],
                     "values": {"nps": nps, "promoters": q2["promo"], "detractors": q2["detr"], "responses": q2["n"]}})
    return {}
