"""The single source of truth that every fake source system is rendered from.

Nothing in here is written to disk directly. Each module in generator/sources
reads this world and renders its own (partial, stale, messy) view of it.
That is what makes cross-source questions answerable *and* hard: the truth
exists, but no single file holds all of it.

ALL NAMES, COMPANIES, PEOPLE AND NUMBERS ARE INVENTED.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, timedelta

from .util import AS_OF, add_months, b62, hexid, month_iter, rand_date, rng_for, uuid_like

# ----------------------------------------------------------------------------- company constants
COMPANY = "Brindlecove Software, Inc."
COMPANY_OLD = "Brindle Data Systems, Inc."
HQ = "Dayton, Ohio"

ERA = {
    "founded": date(1994, 3, 1),
    "brix_start": date(1994, 4, 1),          # COBOL billing on the midrange box
    "brix_readable_from": date(1996, 1, 1),   # older tapes unreadable
    "sugar_start": date(2006, 2, 1),
    "saas_launch": date(2011, 7, 1),
    "ledger_start": date(2011, 7, 1),         # home-grown MySQL billing
    "tallyflow_acq": date(2014, 9, 15),
    "sugar_to_sfdc": date(2016, 5, 14),       # CRM migration weekend
    "billing_v3": date(2017, 4, 1),           # Stripe-style subscription billing
    "log_tz_switch": date(2018, 3, 12),       # app logs go from US/Central local to UTC
    "meridian_acq": date(2018, 2, 1),
    "meridian_billing_moved": date(2019, 7, 1),
    "helpdesk_to_jira": date(2019, 7, 1),
    "classic_sunset": date(2020, 6, 30),
    "kestrel_acq": date(2021, 6, 1),
    "kestrel_billing_moved": date(2022, 4, 1),
    "aws_move": date(2023, 2, 18),
}

# list price per seat / month (USD) by effective date; customers are grandfathered
PRICE_BOOK = [
    (date(2011, 7, 1), {"Starter": 15.0, "Pro": 29.0, "Enterprise": 45.0}),
    (date(2015, 1, 1), {"Starter": 17.0, "Pro": 32.0, "Enterprise": 49.0}),
    (date(2019, 1, 1), {"Starter": 19.0, "Pro": 35.0, "Enterprise": 54.0}),
    (date(2023, 1, 1), {"Starter": 22.0, "Pro": 39.0, "Enterprise": 59.0}),
]
ADDON_PRICE = {"Invoicing": 6.0, "Dispatch": 9.0, "Insights": 400.0}  # Insights is flat / month
CLASSIC_LICENSE = (8_000, 60_000)          # one-off license, USD
CLASSIC_MAINT_RATE = 0.18                  # annual maintenance as % of license, billed quarterly
FX_TO_USD = {"USD": 1.0, "CAD": 0.75, "GBP": 1.27}   # flat "planning" rates; real files disagree

FIRST = """James Mary Robert Patricia John Jennifer Michael Linda David Elizabeth William Barbara Richard Susan Joseph
Jessica Thomas Sarah Charles Karen Christopher Lisa Daniel Nancy Matthew Betty Anthony Margaret Mark Sandra Donald Ashley
Steven Kimberly Paul Emily Andrew Donna Joshua Michelle Kenneth Carol Kevin Amanda Brian Dorothy George Melissa Timothy
Deborah Ronald Stephanie Edward Rebecca Jason Sharon Jeffrey Laura Ryan Cynthia Jacob Kathleen Gary Amy Nicholas Angela
Eric Shirley Jonathan Anna Stephen Brenda Larry Pamela Justin Emma Scott Nicole Brandon Helen Benjamin Samantha Samuel
Katherine Gregory Christine Alexander Debra Patrick Rachel Frank Carolyn Raymond Janet Jack Maria Dennis Olivia Jerry
Heather Tyler Diane Aaron Julie Jose Joyce Adam Victoria Nathan Ruth Henry Virginia Zachary Lauren Douglas Kelly Peter
Christina Kyle Joan Noah Evelyn Ethan Judith Jeremy Andrea Walter Hannah Christian Megan Keith Cheryl Roger Jacqueline
Terry Martha Austin Madison Sean Teresa Gerald Gloria Carl Sara Harold Janice Dylan Ann Arthur Kathryn Lawrence Abigail
Jordan Sophia Jesse Frances Bryce Jean Bruce Alice Gabriel Judy Joe Isabella Logan Julia Albert Grace Willie Amber
Alan Denise Vincent Danielle Eugene Marilyn Russell Beverly Elijah Charlotte Randy Natalie Philip Theresa Harry Diana
Priya Arjun Wei Mei Hiroshi Yuki Oluwaseun Chidi Amara Kwame Fatima Omar Layla Mateo Sofia Diego Valentina Camila
Santiago Lucia Nikolai Anastasia Pierre Amelie Siobhan Declan Aoife Lars Ingrid Bjorn Astrid Ravi Anika Sanjay Deepa
Thuy Minh Jae-won Soo-ah Tomasz Katarzyna Javier Rosa Femi Ngozi Hamid Leila Yusuf Zainab Elif Emre Marguerite Theodora
Desmond Ines Joao Thiago Renata Mireille Etienne Genevieve Rhys Bronwen Callum Isla Tariq Noor""".split()

LAST = """Smith Johnson Williams Brown Jones Garcia Miller Davis Rodriguez Martinez Hernandez Lopez Gonzalez Wilson Anderson
Thomas Taylor Moore Jackson Martin Lee Perez Thompson White Harris Sanchez Clark Ramirez Lewis Robinson Walker Young Allen
King Wright Scott Torres Nguyen Hill Flores Green Adams Nelson Baker Hall Rivera Campbell Mitchell Carter Roberts Gomez
Phillips Evans Turner Diaz Parker Cruz Edwards Collins Reyes Stewart Morris Morales Murphy Cook Rogers Gutierrez Ortiz
Morgan Cooper Peterson Bailey Reed Kelly Howard Ramos Kim Cox Ward Richardson Watson Brooks Chavez Wood James Bennett Gray
Mendoza Ruiz Hughes Price Alvarez Castillo Sanders Patel Myers Long Ross Foster Jimenez Okafor Adeyemi Mensah Boateng
Haddad Nasser Rahman Chaudhry Iyer Raghunathan Venkatesan Tanaka Watanabe Yamamoto Takahashi Chen Wang Zhang Liu Huang
Pham Tran Le Park Choi Kowalski Nowak Lindqvist Johansson Dubois Lefebvre Tremblay Gagnon Bouchard Cote Pelletier Lavoie
O'Brien O'Connor McCarthy Byrne Fitzgerald MacLeod Campbell-Rhys Llewellyn Price-Jones Okonkwo-Hale Fairweather Vance
Ostrander Calloway Whitlock Ashdown Penhallow Quillfeather Marchetti Esposito Romano Moreau Fontaine Sorensen Halvorsen
Abernathy Blackwood Cartwright Delacroix Ellsworth Fenwick Goodenough Hargreaves Ingleby Jessop Kittredge Lockwood""".split()

PLACE = """Harbortown Pinecrest Oakmere Riverbend Calloway Ostrander Westbrook Elmhurst Maplewood Stonebridge Fairhaven
Brookside Cedar Ridgeline Lakeshore Summit Granite Copperfield Willow Ashford Kingsley Northgate Southport Eastlake Bayview
Highland Meadowlark Bluewater Silverleaf Ironwood Redstone Clearwater Foxglove Hawthorne Larkspur Millbrook Ravenwood
Thornbury Wexford Yarrow Juniper Sycamore Tamarack Prairie Lindenwood Blackhawk Sandpiper Kestrel Heron Osprey Marrow
Quarry Tidewater Gatehouse Lantern Beacon Anchor Keystone Cornerstone Tri-County Three Rivers Twin Lakes Great Plains
Crescent Pioneer Frontier Heritage Liberty Patriot Union Commonwealth Allegheny Ozark Cumberland Shenandoah Wabash
Saginaw Muskingum Scioto Miami Valley Huron Erie Superior Tillamook Cascade Sierra Mesa Pueblo Saguaro Bayou Magnolia""".split()

KIND = {
    "Property Management": ["Property Group", "Properties", "Realty Management", "Property Services", "Residential"],
    "Healthcare": ["Health System", "Medical Center", "Clinics", "Health Partners", "Hospital"],
    "Education": ["School District", "Academy", "College", "Unified Schools", "University Facilities"],
    "Manufacturing": ["Mills", "Manufacturing", "Fabrication", "Industries", "Works"],
    "Logistics": ["Logistics", "Freight", "Distribution", "Warehousing", "Couriers"],
    "Hospitality": ["Hotels", "Resorts", "Hospitality Group", "Inns", "Suites"],
    "Government": ["County Facilities", "Township", "Municipal Services", "Public Works", "Transit Authority"],
    "Retail": ["Stores", "Markets", "Retail Group", "Outfitters", "Supply Co"],
    "Facilities Services": ["Facilities Management", "Building Services", "Maintenance Co", "Janitorial", "Mechanical"],
    "Construction": ["Builders", "Contracting", "Construction", "Homes", "Restoration"],
}
SUFFIX = ["Inc.", "LLC", "Co.", "Corp.", "Ltd.", "", "", "", "Group", "Holdings"]

US_CITIES = [("Dayton", "OH"), ("Columbus", "OH"), ("Cincinnati", "OH"), ("Cleveland", "OH"), ("Indianapolis", "IN"),
             ("Louisville", "KY"), ("Pittsburgh", "PA"), ("Philadelphia", "PA"), ("Chicago", "IL"), ("Detroit", "MI"),
             ("Grand Rapids", "MI"), ("Milwaukee", "WI"), ("Minneapolis", "MN"), ("St. Louis", "MO"), ("Kansas City", "MO"),
             ("Nashville", "TN"), ("Atlanta", "GA"), ("Charlotte", "NC"), ("Raleigh", "NC"), ("Richmond", "VA"),
             ("Baltimore", "MD"), ("Newark", "NJ"), ("Boston", "MA"), ("Hartford", "CT"), ("Buffalo", "NY"),
             ("Albany", "NY"), ("Dallas", "TX"), ("Austin", "TX"), ("Houston", "TX"), ("San Antonio", "TX"),
             ("Denver", "CO"), ("Phoenix", "AZ"), ("Salt Lake City", "UT"), ("Boise", "ID"), ("Portland", "OR"),
             ("Seattle", "WA"), ("Sacramento", "CA"), ("San Diego", "CA"), ("Omaha", "NE"), ("Tulsa", "OK"),
             ("Birmingham", "AL"), ("Jacksonville", "FL"), ("Tampa", "FL"), ("Des Moines", "IA"), ("Madison", "WI")]
CA_CITIES = [("Winnipeg", "MB"), ("Brandon", "MB"), ("Regina", "SK"), ("Saskatoon", "SK"), ("Calgary", "AB"),
             ("Edmonton", "AB"), ("Toronto", "ON"), ("Ottawa", "ON"), ("Montréal", "QC"), ("Québec", "QC"),
             ("Halifax", "NS"), ("Vancouver", "BC")]
UK_CITIES = [("Leeds", "West Yorkshire"), ("Manchester", "Greater Manchester"), ("Sheffield", "South Yorkshire"),
             ("York", "North Yorkshire"), ("Bristol", "Bristol"), ("Birmingham", "West Midlands"), ("Glasgow", "Scotland"),
             ("Cardiff", "Wales"), ("Newcastle", "Tyne and Wear"), ("Nottingham", "Nottinghamshire")]

CHURN_REASONS = ["Price", "Moved to competitor", "Went out of business", "Acquired by another company",
                 "Product gaps", "Poor onboarding", "Budget cuts", "Consolidated vendors", "Support experience",
                 "Outage / reliability", "Champion left", "Brought in-house"]
COMPETITORS = ["Plinthwise", "Corbelry", "Tessaroo", "Quillmark Ops", "Lintelo"]  # invented


# ----------------------------------------------------------------------------- data classes
@dataclass
class Person:
    pid: str
    first: str
    last: str
    title: str
    dept: str
    hired: date
    left: date | None
    origin: str = "brindle"       # brindle / tallyflow / meridian / kestrel

    @property
    def name(self):
        return f"{self.first} {self.last}"

    def email(self, on: date) -> str:
        f, l = self.first.lower().replace("'", ""), self.last.lower().replace("'", "").replace(" ", "")
        if self.origin == "tallyflow" and on < date(2015, 6, 1):
            return f"{f}@tallyflow.io"
        if self.origin == "meridian" and on < date(2019, 1, 1):
            return f"{f}.{l}@meridiandispatch.ca"
        if self.origin == "kestrel" and on < date(2022, 1, 1):
            return f"{f[0]}.{l}@kestrel-analytics.co.uk"
        if on < ERA["saas_launch"]:
            return f"{f}.{l}@brindledata.com"
        return f"{f[0]}{l}@brindlecove.com"


@dataclass
class Contact:
    first: str
    last: str
    title: str
    phone: str
    email_domain: str

    @property
    def name(self):
        return f"{self.first} {self.last}"

    @property
    def email(self):
        return f"{self.first.lower()}.{self.last.lower().replace(chr(39), '')}@{self.email_domain}"


@dataclass
class Customer:
    key: str                    # canonical internal key; NEVER written to raw data
    name: str
    industry: str
    city: str
    region: str
    country: str
    currency: str
    origin: str                 # classic / cloud / tallyflow / meridian / kestrel
    first_seen: date            # first contract / license date
    cloud_start: date | None    # first month on SaaS billing (any system)
    end: date | None            # churn date (last day of service), None = active
    churn_reason: str | None
    plan: str
    seats0: int
    growth: float               # yearly seat growth multiplier
    discount: float
    addons: list = field(default_factory=list)
    classic_license: float = 0.0
    owner: str = ""             # sales rep pid
    csm: str = ""
    contacts: list = field(default_factory=list)
    variants: list = field(default_factory=list)
    ids: dict = field(default_factory=dict)
    annual: bool = False
    deleted_in_crm: date | None = None
    notes: list = field(default_factory=list)
    price_year: date | None = None
    signed: date | None = None      # contract signature (CRM close date)

    def active(self, d: date) -> bool:
        if self.end and d > self.end:
            return False
        return d >= self.first_seen

    def seats(self, d: date) -> int:
        start = self.cloud_start or self.first_seen
        yrs = max(0.0, (d - start).days / 365.25)
        return max(1, int(round(self.seats0 * (self.growth ** yrs))))

    def unit_price(self, d: date) -> float:
        anchor = self.price_year or self.cloud_start or d
        book = PRICE_BOOK[0][1]
        for eff, prices in PRICE_BOOK:
            if anchor >= eff:
                book = prices
        return book[self.plan]


@dataclass
class Invoice:
    """Canonical invoice. Each billing system renders a subset of these."""
    inv_key: str
    cust: Customer
    system: str                 # brix / ledger / tallyflow / meridian / kestrel / billing
    issued: date
    period_start: date
    period_end: date
    currency: str
    lines: list                 # (description, qty, unit_price)
    status: str                 # paid / open / void / uncollectible / refunded
    paid_on: date | None
    seq: int = 0

    @property
    def total(self) -> float:
        return round(sum(q * p for _, q, p in self.lines), 2)


@dataclass
class World:
    seed: int
    people: list
    customers: list
    invoices: list
    golden: dict                # name -> Customer (or other entity) planted for golden facts
    prospects: list

    def by_name(self, name):
        for c in self.customers:
            if c.name == name:
                return c
        raise KeyError(name)


# ----------------------------------------------------------------------------- builders
TITLES = {
    "Executive": ["CEO", "CFO", "COO", "CTO", "VP Sales", "VP Customer Success", "VP Engineering", "VP Finance", "General Counsel"],
    "Sales": ["Account Executive", "Senior Account Executive", "Sales Development Rep", "Sales Manager", "Regional Director"],
    "Customer Success": ["Customer Success Manager", "Senior CSM", "Onboarding Specialist", "Renewals Manager"],
    "Support": ["Support Engineer", "Senior Support Engineer", "Support Lead", "Tier 2 Support"],
    "Engineering": ["Software Engineer", "Senior Software Engineer", "Staff Engineer", "SRE", "Engineering Manager", "DBA"],
    "Finance": ["Staff Accountant", "Billing Specialist", "Controller", "FP&A Analyst", "AR Specialist"],
    "Operations": ["IT Administrator", "Data Analyst", "RevOps Analyst", "Office Manager", "Mainframe Operator"],
}

NAMED_STAFF = [
    # pid, first, last, title, dept, hired, left, origin
    ("E001", "Margaret", "Okonkwo-Hale", "CEO", "Executive", date(1994, 3, 1), None, "brindle"),
    ("E002", "Desmond", "Fairweather", "CTO", "Executive", date(1994, 3, 1), date(2015, 12, 31), "brindle"),
    ("E003", "Lorraine", "Whitlock", "CFO", "Executive", date(2009, 5, 4), None, "brindle"),
    ("E004", "Gideon", "Ashdown", "VP Sales", "Executive", date(2012, 1, 9), date(2021, 3, 31), "brindle"),
    ("E005", "Priya", "Raghunathan", "VP Customer Success", "Executive", date(2014, 2, 3), None, "brindle"),
    ("E006", "Tomasz", "Kowalski", "VP Engineering", "Executive", date(2016, 1, 4), None, "brindle"),
    ("E007", "Renata", "Esposito", "VP Sales", "Executive", date(2021, 4, 12), None, "brindle"),
    ("E008", "Harold", "Penhallow", "Mainframe Operator", "Operations", date(1995, 6, 5), date(2012, 3, 30), "brindle"),
    ("E009", "Yuki", "Tanaka", "DBA", "Engineering", date(2010, 8, 16), date(2019, 10, 31), "brindle"),
    ("E010", "Callum", "MacLeod", "SRE", "Engineering", date(2015, 3, 2), None, "brindle"),
    ("E011", "Femi", "Adeyemi", "RevOps Analyst", "Operations", date(2016, 2, 1), None, "brindle"),
    ("E012", "Ines", "Delacroix", "Controller", "Finance", date(2013, 7, 8), None, "brindle"),
    ("E013", "Bryce", "Kittredge", "Senior Account Executive", "Sales", date(2008, 4, 7), date(2017, 6, 30), "brindle"),
    ("E014", "Sofia", "Marchetti", "Senior CSM", "Customer Success", date(2012, 10, 1), date(2018, 1, 12), "brindle"),
    ("E015", "Jae-won", "Park", "Support Lead", "Support", date(2013, 5, 6), None, "brindle"),
    ("E016", "Abigail", "Fenwick", "General Counsel", "Executive", date(2017, 9, 5), None, "brindle"),
    ("E017", "Ravi", "Iyer", "Founder & CEO, TallyFlow", "Executive", date(2014, 9, 15), date(2016, 9, 30), "tallyflow"),
    ("E018", "Etienne", "Gagnon", "GM, Meridian Dispatch", "Executive", date(2018, 2, 1), date(2020, 8, 31), "meridian"),
    ("E019", "Bronwen", "Llewellyn", "Managing Director, Kestrel", "Executive", date(2021, 6, 1), date(2023, 5, 31), "kestrel"),
    ("E020", "Noor", "Haddad", "Data Analyst", "Operations", date(2020, 1, 13), None, "brindle"),
]


def build_people(r):
    people = [Person(*row) for row in NAMED_STAFF]
    n = 21
    for dept, titles in TITLES.items():
        if dept == "Executive":
            continue
        count = {"Sales": 34, "Customer Success": 22, "Support": 26, "Engineering": 40, "Finance": 12, "Operations": 10}[dept]
        for _ in range(count):
            hired = rand_date(r, date(1996, 1, 1), date(2025, 6, 1))
            left = None
            if r.random() < 0.55:
                left = rand_date(r, hired + timedelta(days=200), min(AS_OF, hired + timedelta(days=365 * 9)))
            origin = r.choices(["brindle", "tallyflow", "meridian", "kestrel"], [85, 5, 6, 4])[0]
            if origin == "tallyflow":
                hired = max(hired, ERA["tallyflow_acq"])
            if origin == "meridian":
                hired = max(hired, ERA["meridian_acq"])
            if origin == "kestrel":
                hired = max(hired, ERA["kestrel_acq"])
            if left and left <= hired:
                left = None
            people.append(Person(f"E{n:03d}", r.choice(FIRST), r.choice(LAST), r.choice(titles), dept, hired, left, origin))
            n += 1
    return people


def staff_on(people, dept, d, r, titles=None):
    pool = [p for p in people if p.dept == dept and p.hired <= d and (p.left is None or p.left >= d)
            and (titles is None or p.title in titles)]
    if not pool:
        pool = [p for p in people if p.dept == dept]
    return r.choice(pool)


def company_name(r, industry, used):
    for _ in range(50):
        place = r.choice(PLACE)
        if r.random() < 0.25:
            place = f"{r.choice(LAST)}"
        nm = f"{place} {r.choice(KIND[industry])}"
        suf = r.choice(SUFFIX)
        full = f"{nm} {suf}".strip()
        if nm not in used:
            used.add(nm)
            return full
    return f"{r.choice(PLACE)} {r.choice(KIND[industry])} {r.randint(2, 9)}"


def name_variants(r, name: str) -> list:
    """The ways a customer's name gets mangled across systems."""
    base = name
    for s in [" Inc.", " LLC", " Co.", " Corp.", " Ltd.", " Group", " Holdings"]:
        if base.endswith(s):
            base = base[: -len(s)]
    v = {name, base, name.upper(), base.upper()[:30], base.replace(" and ", " & "),
         base.replace("Saint ", "St. ").replace("St. ", "St "), base + ", Inc", base.replace("'", ""),
         base.replace("Management", "Mgmt").replace("Services", "Svcs").replace("Health System", "Health Sys")}
    words = base.split()
    if len(words) > 2:
        v.add(" ".join(words[:2]))
    v.add(base.replace("’", "'"))
    return sorted(v)


def make_contacts(r, c: Customer, n: int):
    dom = "".join(ch for ch in c.name.lower().split(" ")[0] if ch.isalnum()) + r.choice([".com", ".org", ".net", "-inc.com"])
    if c.country == "CA":
        dom = dom.replace(".com", ".ca")
    if c.country == "GB":
        dom = dom.split(".")[0] + ".co.uk"
    titles = ["Facilities Director", "Maintenance Manager", "Operations Manager", "IT Manager", "Controller",
              "AP Clerk", "Office Manager", "VP Operations", "Building Engineer", "Procurement Lead"]
    out = []
    for _ in range(n):
        if c.country == "CA":
            phone = f"+1 (204) {r.randint(200, 999)}-{r.randint(1000, 9999)}"
        elif c.country == "GB":
            phone = f"+44 113 {r.randint(100, 999)} {r.randint(1000, 9999)}"
        else:
            phone = f"({r.randint(201, 989)}) 555-{r.randint(100, 199):04d}"  # 555-01xx: fiction range
        out.append(Contact(r.choice(FIRST), r.choice(LAST), r.choice(titles), phone, dom))
    return out


def build_customers(r, people, n_total: int):
    used = set()
    customers = []
    i = 0

    def new(origin, first_seen, country="US"):
        nonlocal i
        i += 1
        industry = r.choice(list(KIND))
        if country == "US":
            city, region = r.choice(US_CITIES)
            currency = "USD"
        elif country == "CA":
            city, region = r.choice(CA_CITIES)
            currency = "CAD"
        else:
            city, region = r.choice(UK_CITIES)
            currency = "GBP"
        size = r.lognormvariate(3.0, 0.9)
        seats0 = max(3, min(900, int(size)))
        plan = "Starter" if seats0 < 15 else ("Pro" if seats0 < 80 else "Enterprise")
        if r.random() < 0.15:
            plan = r.choice(["Starter", "Pro", "Enterprise"])
        c = Customer(
            key=f"K{i:05d}", name=company_name(r, industry, used), industry=industry, city=city, region=region,
            country=country, currency=currency, origin=origin, first_seen=first_seen, cloud_start=None, end=None,
            churn_reason=None, plan=plan, seats0=seats0, growth=r.choice([0.85, 0.95, 1.0, 1.0, 1.05, 1.1, 1.2, 1.35]),
            discount=r.choice([0, 0, 0, 0, 0.05, 0.1, 0.1, 0.15, 0.2]), annual=(plan == "Enterprise" and r.random() < 0.6),
        )
        c.owner = staff_on(people, "Sales", first_seen, r).pid
        c.csm = staff_on(people, "Customer Success", max(first_seen, date(2011, 1, 1)), r).pid
        c.contacts = make_contacts(r, c, r.randint(2, 6))
        return c

    # classic (on-prem) customers 1994-2011; some convert to cloud, some churn, all classic ends by sunset
    for _ in range(int(n_total * 0.18)):
        fs = rand_date(r, ERA["brix_start"], date(2011, 6, 1))
        c = new("classic", fs)
        c.classic_license = round(r.uniform(*CLASSIC_LICENSE), -2)
        roll = r.random()
        if roll < 0.45:   # converts to cloud
            c.cloud_start = rand_date(r, ERA["saas_launch"], ERA["classic_sunset"]).replace(day=1)
        elif roll < 0.85:  # churns on-prem
            c.end = rand_date(r, fs + timedelta(days=700), ERA["classic_sunset"])
            c.churn_reason = r.choice(CHURN_REASONS)
        else:             # stayed on Classic until forced sunset, then left
            c.end = ERA["classic_sunset"]
            c.churn_reason = "Classic sunset - did not migrate"
        customers.append(c)

    # TallyFlow customers (acquired 2014)
    for _ in range(int(n_total * 0.07)):
        fs = rand_date(r, date(2012, 3, 1), ERA["tallyflow_acq"])
        c = new("tallyflow", fs)
        c.cloud_start = fs.replace(day=1)
        c.plan = "Starter" if c.seats0 < 40 else "Pro"
        c.addons = ["Invoicing"]
        customers.append(c)

    # Meridian Dispatch customers (Canada, acquired 2018)
    for _ in range(int(n_total * 0.08)):
        fs = rand_date(r, date(2015, 1, 1), ERA["meridian_acq"])
        c = new("meridian", fs, country="CA")
        c.cloud_start = fs.replace(day=1)
        c.addons = ["Dispatch"]
        customers.append(c)

    # Kestrel Analytics customers (UK, acquired 2021)
    for _ in range(int(n_total * 0.05)):
        fs = rand_date(r, date(2018, 1, 1), ERA["kestrel_acq"])
        c = new("kestrel", fs, country="GB")
        c.cloud_start = fs.replace(day=1)
        c.addons = ["Insights"]
        c.plan = "Pro"
        customers.append(c)

    # native cloud customers
    while len(customers) < n_total:
        fs = rand_date(r, ERA["saas_launch"], date(2026, 9, 1))
        c = new("cloud", fs, country=r.choices(["US", "CA"], [93, 7])[0])
        c.cloud_start = fs.replace(day=1)
        if fs >= ERA["tallyflow_acq"] and r.random() < 0.3:
            c.addons.append("Invoicing")
        if fs >= ERA["meridian_acq"] and r.random() < 0.2:
            c.addons.append("Dispatch")
        if fs >= ERA["kestrel_acq"] and r.random() < 0.15:
            c.addons.append("Insights")
        customers.append(c)

    # churn for cloud-era customers (hazard ~ 9%/yr, higher for small)
    for c in customers:
        if c.cloud_start and c.end is None:
            d = c.cloud_start
            hazard = 0.13 if c.seats0 < 15 else (0.08 if c.seats0 < 80 else 0.05)
            while d < AS_OF:
                if r.random() < hazard / 12:
                    c.end = min(AS_OF, add_months(d, 1) - timedelta(days=1))
                    c.churn_reason = r.choice(CHURN_REASONS)
                    break
                d = add_months(d, 1)
        # some customers re-priced on renewal (not grandfathered)
        if c.cloud_start and r.random() < 0.2:
            c.price_year = rand_date(r, c.cloud_start, AS_OF)
        c.variants = name_variants(r, c.name)
    return customers


# ----------------------------------------------------------------------------- golden entities
def plant_golden(r, people, customers):
    """Force specific customers to exist with specific histories.

    The answer key (generator/golden.py) reads these back. Values that
    depend on random draws are computed from the world, never hand-typed.
    """
    g = {}

    def take(i, **kw):
        c = customers[i]
        for k, v in kw.items():
            setattr(c, k, v)
        c.variants = name_variants(r, c.name)
        return c

    classic = [i for i, c in enumerate(customers) if c.origin == "classic"]
    cloud = [i for i, c in enumerate(customers) if c.origin == "cloud" and c.first_seen < date(2013, 1, 1)]
    meridian = [i for i, c in enumerate(customers) if c.origin == "meridian"]

    # GF01 churn reason lives only in an email thread
    g["harbortown"] = take(cloud[0], name="Harbortown Property Group", industry="Property Management",
                           city="Columbus", region="OH", country="US", currency="USD", plan="Pro", seats0=120,
                           growth=1.05, first_seen=date(2012, 2, 13), cloud_start=date(2012, 3, 1),
                           end=date(2016, 8, 31), churn_reason="Other", discount=0.1, addons=[])
    # GF02 pricing exception only in a scanned 2013 contract
    g["calloway"] = take(classic[0], name="Calloway Facilities Management, Inc.", industry="Facilities Services",
                         city="Cincinnati", region="OH", country="US", currency="USD", plan="Enterprise",
                         seats0=180, growth=1.06, first_seen=date(2001, 9, 17), cloud_start=date(2013, 7, 1),
                         end=None, churn_reason=None, discount=0.38, classic_license=42000.0, price_year=date(2013, 7, 1),
                         annual=False, addons=[])
    # GF11 EBCDIC packed-decimal billing, 1999
    g["ostrander"] = take(classic[1], name="Ostrander Mills Co.", industry="Manufacturing", city="Dayton",
                          region="OH", country="US", currency="USD", first_seen=date(1996, 11, 4),
                          cloud_start=None, end=date(2009, 12, 31), churn_reason="Went out of business",
                          classic_license=36500.0)
    # GF03 crosswalk error: BRIX customer mapped to the wrong CRM account
    g["xwalk_true"] = take(classic[2], name="Riverbend Unified Schools", industry="Education", city="Louisville",
                           region="KY", country="US", currency="USD", first_seen=date(2004, 8, 2),
                           cloud_start=date(2014, 1, 1), end=None, churn_reason=None, plan="Pro", seats0=60)
    g["xwalk_wrong"] = take(classic[3], name="Riverbend Unified Services LLC", industry="Facilities Services",
                            city="Lexington", region="KY", country="US", currency="USD", first_seen=date(2005, 3, 14),
                            cloud_start=date(2012, 5, 1), end=date(2019, 4, 30), churn_reason="Price", plan="Starter",
                            seats0=9)
    # GF13 one customer, many spellings, two currencies (bought Meridian Dispatch separately)
    g["brigid_us"] = take(cloud[1], name="St. Brigid’s Health System", industry="Healthcare", city="Detroit",
                          region="MI", country="US", currency="USD", plan="Enterprise", seats0=260, growth=1.08,
                          first_seen=date(2012, 6, 4), cloud_start=date(2012, 7, 1), end=None, churn_reason=None,
                          discount=0.15, annual=True, addons=["Invoicing"])
    g["brigid_ca"] = take(meridian[0], name="Saint Brigid Health System (Windsor Campus)", industry="Healthcare",
                          city="Windsor", region="ON", country="CA", currency="CAD", plan="Pro", seats0=40,
                          growth=1.04, first_seen=date(2016, 10, 3), cloud_start=date(2016, 10, 1), end=None,
                          churn_reason=None, discount=0.0, addons=["Dispatch"])
    # GF14 soft-deleted in CRM, still billed
    pine_idx = [i for i in cloud[2:40]][0]
    g["pinecrest"] = take(pine_idx, name="Pinecrest Logistics LLC", industry="Logistics", city="Tulsa", region="OK",
                          country="US", currency="USD", plan="Pro", seats0=35, growth=1.0, end=date(2023, 9, 30),
                          churn_reason="Consolidated vendors", deleted_in_crm=date(2021, 2, 9))
    # extra soft-deletes with and without trailing invoices
    planted = {id(c) for c in g.values()}
    for c in [c for c in customers if c.origin == "cloud" and c.end is None and id(c) not in planted][5:17]:
        c.deleted_in_crm = rand_date(r, max(c.first_seen, ERA["sugar_to_sfdc"]) + timedelta(days=90), date(2025, 6, 1))
    for c in [c for c in customers if c.end is not None and c.cloud_start and c.end > ERA["sugar_to_sfdc"] and id(c) not in planted][10:40]:
        c.deleted_in_crm = c.end + timedelta(days=r.randint(30, 400))
    # GF08 Classic sunset customer that migrated on the 25% credit
    g["sunset_migrator"] = take(classic[4], name="Tri-County Public Works", industry="Government", city="Dayton",
                                region="OH", country="US", currency="USD", first_seen=date(1998, 5, 11),
                                cloud_start=date(2020, 6, 1), end=None, churn_reason=None, plan="Pro", seats0=55,
                                classic_license=28000.0)
    # GF16 classic customer whose BRIX status is 'X' (migrated to Ledger)
    g["status_x"] = g["calloway"]
    for k in ("calloway", "xwalk_true", "xwalk_wrong", "sunset_migrator"):
        g[k].owner = "E013"
    g["harbortown"].owner = "E013"
    g["harbortown"].csm = "E014"
    g["calloway"].contacts[0] = Contact("Theodora", "Vance", "Facilities Director", "(513) 555-0142",
                                        "callowayfm.com")
    g["harbortown"].contacts[0] = Contact("Lionel", "Ashby", "VP Operations", "(614) 555-0177", "harbortownpg.com")
    return g


# ----------------------------------------------------------------------------- ids per system
def assign_ids(r, customers, golden):
    brix_no = 4000
    ledger_no = 1000
    nets = 10010
    tf = 1
    md = 1
    ks = 1
    for c in customers:
        ids = {}
        if c.origin == "classic":
            brix_no += r.randint(1, 9)
            ids["brix"] = f"{brix_no:06d}"
        if c.first_seen < ERA["sugar_to_sfdc"] and (c.end is None or c.end >= ERA["sugar_start"]) and c.origin in ("classic", "cloud", "tallyflow"):
            ids["sugar"] = uuid_like(r)
        crm_relevant = (c.end is None or c.end >= ERA["sugar_to_sfdc"] - timedelta(days=365 * 2))
        if crm_relevant:
            ids["sfdc"] = "001" + b62(r, 15)  # 18-char style ids
        if c.cloud_start and (c.end is None or c.end >= ERA["ledger_start"]) and c.cloud_start < ERA["billing_v3"] and c.origin in ("classic", "cloud", "tallyflow"):
            ledger_no += 1
            ids["ledger"] = str(ledger_no)
        if c.cloud_start and (c.end is None or c.end >= ERA["billing_v3"]):
            ids["billing"] = "cus_" + b62(r, 14)
        if c.origin == "tallyflow":
            ids["tallyflow"] = f"TF-{tf:04d}"
            tf += 1
        if c.origin == "meridian":
            ids["meridian"] = f"MD-CA-{md:05d}"
            md += 1
        if c.origin == "kestrel":
            ids["kestrel"] = f"KST/UK/{ks:04d}"
            ks += 1
        if c.cloud_start and (c.end is None or c.end >= date(2015, 1, 1)):
            nets += r.randint(1, 3)
            ids["netsuite"] = str(nets)
        c.ids = ids
    # GF03: pin the legacy number the answer key talks about
    golden["xwalk_true"].ids["brix"] = "004417"
    golden["xwalk_wrong"].ids["brix"] = "004471"   # transposed digits; the crosswalk confuses them
    golden["calloway"].ids["brix"] = "002318"
    golden["ostrander"].ids["brix"] = "001207"
    pinned = {golden[k].ids["brix"] for k in ("xwalk_true", "xwalk_wrong", "calloway", "ostrander")}
    pinned_owner = {golden[k].key for k in ("xwalk_true", "xwalk_wrong", "calloway", "ostrander")}
    for c in customers:
        if c.key not in pinned_owner and c.ids.get("brix") in pinned:
            c.ids["brix"] = f"{int(c.ids['brix']) + 7000:06d}"


# ----------------------------------------------------------------------------- invoices
def build_invoices(r, customers):
    """Canonical billing history across every billing system in every era."""
    out = []
    seq = 0

    def add(c, system, issued, ps, pe, lines, currency=None):
        nonlocal seq
        seq += 1
        due = issued + timedelta(days=30)
        roll = r.random()
        if issued > AS_OF - timedelta(days=35) and roll < 0.6:
            status, paid = "open", None
        elif roll < 0.012:
            status, paid = "void", None
        elif roll < 0.02:
            status, paid = "uncollectible", None
        elif roll < 0.026:
            status, paid = "refunded", issued + timedelta(days=r.randint(3, 40))
        else:
            status = "paid"
            late = r.random() < 0.12
            paid = issued + timedelta(days=r.randint(31, 120) if late else r.randint(0, 29))
        out.append(Invoice(f"I{seq:07d}", c, system, issued, ps, pe, currency or c.currency, lines, status, paid, seq))

    for c in customers:
        # ---- classic: license + quarterly maintenance in BRIX
        if c.origin == "classic":
            add(c, "brix", c.first_seen, c.first_seen, c.first_seen,
                [("CLASSIC PERPETUAL LICENSE", 1, c.classic_license)])
            stop = c.end or ERA["classic_sunset"]
            if c.cloud_start:
                stop = min(stop, c.cloud_start - timedelta(days=1))
            q = date(c.first_seen.year, ((c.first_seen.month - 1) // 3) * 3 + 1, 1)
            q = add_months(q, 3)
            while q <= stop:
                fee = round(c.classic_license * CLASSIC_MAINT_RATE / 4 * (1 + 0.03 * ((q.year - c.first_seen.year))), 2)
                system = "brix" if q < ERA["ledger_start"] else "ledger"
                add(c, system, q, q, add_months(q, 3) - timedelta(days=1), [("CLASSIC MAINT & SUPPORT QTR", 1, fee)])
                q = add_months(q, 3)
        # ---- cloud subscription
        if not c.cloud_start:
            continue
        end = c.end or AS_OF
        step = 12 if c.annual else 1
        m = c.cloud_start
        while m <= end:
            if c.origin == "tallyflow" and m < date(2015, 1, 1):
                system = "tallyflow"
            elif c.origin == "meridian" and m < ERA["meridian_billing_moved"]:
                system = "meridian"
            elif c.origin == "kestrel" and m < ERA["kestrel_billing_moved"]:
                system = "kestrel"
            elif m < ERA["billing_v3"]:
                system = "ledger"
            else:
                system = "billing"
            seats = c.seats(m)
            price = round(c.unit_price(m) * (1 - c.discount), 2)
            fx = {"USD": 1.0, "CAD": 1.32, "GBP": 0.79}[c.currency]   # local list price ~= USD book * fx
            price = round(price * fx, 2)
            lines = [(f"Brindle Ops Cloud - {c.plan} (per seat)", seats * step, price)]
            for a in c.addons:
                if a == "Insights":
                    lines.append(("Brindle Insights (flat)", step, round(ADDON_PRICE[a] * fx, 2)))
                else:
                    lines.append((f"{a} add-on (per seat)", seats * step, round(ADDON_PRICE[a] * fx, 2)))
            pe = add_months(m, step) - timedelta(days=1)
            add(c, system, m, m, pe, lines)
            m = add_months(m, step)
    out.sort(key=lambda i: (i.issued, i.seq))
    return out


def build_prospects(r, people, n):
    used = set()
    out = []
    for i in range(n):
        ind = r.choice(list(KIND))
        city, region = r.choice(US_CITIES)
        created = rand_date(r, date(2006, 1, 1), date(2026, 10, 1))
        out.append({"name": company_name(r, ind, used), "industry": ind, "city": city, "region": region,
                    "created": created, "owner": staff_on(people, "Sales", created, r).pid,
                    "seats": max(3, int(r.lognormvariate(3, 0.9)))})
    return out


def build_world(seed: int = 42, scale: float = 1.0) -> World:
    r = rng_for(seed, "world")
    people = build_people(r)
    customers = build_customers(r, people, int(3200 * scale))
    golden = plant_golden(r, people, customers)
    assign_ids(r, customers, golden)
    for c in customers:
        c.signed = c.first_seen - timedelta(days=r.randint(3, 60))
    invoices = build_invoices(r, customers)
    for inv in invoices:     # keep the GF10 answer unambiguous: every 1990s Ostrander invoice was paid
        if inv.cust is golden["ostrander"] and inv.status != "paid":
            inv.status, inv.paid_on = "paid", inv.issued + timedelta(days=21)
    prospects = build_prospects(r, people, int(1800 * scale))
    return World(seed, people, customers, invoices, golden, prospects)


def arr_at(world: World, d: date, currency_to_usd=None) -> float:
    """Finance definition: annualised recurring revenue of subscriptions *live* on d (USD at planning FX)."""
    fx = currency_to_usd or FX_TO_USD
    total = 0.0
    for c in world.customers:
        if not c.cloud_start or c.cloud_start > d or (c.end and c.end < d):
            continue
        seats = c.seats(d)
        price = c.unit_price(d) * (1 - c.discount) * {"USD": 1.0, "CAD": 1.32, "GBP": 0.79}[c.currency]
        mrr = seats * price
        for a in c.addons:
            loc = ADDON_PRICE[a] * {"USD": 1.0, "CAD": 1.32, "GBP": 0.79}[c.currency]
            mrr += loc if a == "Insights" else seats * loc
        total += mrr * 12 * fx[c.currency]
    return round(total, 2)


def first_year_arr_local(c: Customer) -> float:
    d = c.cloud_start or c.first_seen
    fx = {"USD": 1.0, "CAD": 1.32, "GBP": 0.79}[c.currency]
    seats = c.seats(d)
    mrr = seats * c.unit_price(d) * (1 - c.discount) * fx
    for a in c.addons:
        mrr += ADDON_PRICE[a] * fx * (1 if a == "Insights" else seats)
    return round(mrr * 12, 2)
