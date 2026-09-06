"""Company tiers, for prioritising who to apply to first.

A queue of 779 openings is not 779 equal opportunities. A posting at a
company the user would drop everything for should look different from
one at a firm they have never heard of, and it should look different
before they read a word of the title.

Tiers are a curated list rather than anything inferred. Headcount,
funding and valuation are all bad proxies for "would this be a great
place to start a career", and any signal derived from them would be
confidently wrong in both directions. A hand-kept list is honest about
being an opinion.

Matching is exact on the lowercased name, plus an explicit alias table.
Deliberately not fuzzy: the same classification has to be reproducible
in SQL for ordering as in Python for display, and a normalisation the
database cannot perform would let a posting sort as big tech while its
badge said otherwise. When a new spelling shows up it goes in ALIASES.
"""

from __future__ import annotations

from enum import StrEnum


class CompanyTier(StrEnum):
    """How much a posting's employer should pull the eye."""

    BIG_TECH = "BIG_TECH"

    TOP_TIER = "TOP_TIER"

    ESTABLISHED = "ESTABLISHED"

    OTHER = "OTHER"


# The household names. Recognisable to anyone, and the ones worth
# interrupting a day for.
BIG_TECH_NAMES = frozenset(
    {
        "amazon",
        "amazon web services",
        "aws",
        "google",
        "alphabet",
        "youtube",
        "meta",
        "facebook",
        "instagram",
        "whatsapp",
        "apple",
        "netflix",
        "microsoft",
        "linkedin",
        "github",
        "nvidia",
        "tesla",
        "bytedance",
        "tiktok",
        "uber",
        "airbnb",
        "spotify",
        "adobe",
        "salesforce",
        "oracle",
        "ibm",
        "intel",
        "qualcomm",
        "cisco",
        "broadcom",
        "amd",
        "sap",
        "paypal",
        "ebay",
        "snap",
        "snapchat",
        "pinterest",
        "block",
        "square",
        "servicenow",
        "vmware",
        "dell",
        "dell technologies",
        "hp",
        "hewlett packard enterprise",
        "intuit",
        "workday",
        "atlassian",
        "shopify",
        "zoom",
        "autodesk",
        "electronic arts",
        "sony",
        "samsung",
        "nintendo",
        "tencent",
        "alibaba",
    }
)


# Elite engineering and the AI frontier. Smaller than big tech, often
# harder to get into, and the places whose names carry weight on a CV.
TOP_TIER_NAMES = frozenset(
    {
        "openai",
        "anthropic",
        "stripe",
        "databricks",
        "snowflake",
        "palantir",
        "palantir technologies",
        "figma",
        "notion",
        "scale ai",
        "anduril",
        "anduril industries",
        "spacex",
        "coinbase",
        "robinhood",
        "doordash",
        "lyft",
        "instacart",
        "roblox",
        "discord",
        "reddit",
        "plaid",
        "ramp",
        "brex",
        "rippling",
        "deel",
        "vercel",
        "supabase",
        "hugging face",
        "cohere",
        "mistral ai",
        "perplexity",
        "perplexity ai",
        "cursor",
        "anysphere",
        "sierra",
        "cerebras",
        "cerebras systems",
        "groq",
        "together ai",
        "waymo",
        "cruise",
        "rivian",
        "lucid motors",
        "nuro",
        "applied intuition",
        "samsara",
        "datadog",
        "mongodb",
        "elastic",
        "confluent",
        "hashicorp",
        "twilio",
        "cloudflare",
        "fastly",
        "okta",
        "crowdstrike",
        "palo alto networks",
        "zscaler",
        "sentinelone",
        "wiz",
        "canva",
        "miro",
        "airtable",
        "asana",
        "linear",
        "retool",
        "amplitude",
        "benchling",
        "verkada",
        "flexport",
        "affirm",
        "chime",
        "marqeta",
        "gusto",
        "carta",
        "addepar",
        "duolingo",
        "airtable",
        "grammarly",
        "quora",
        "dropbox",
        "box",
        "slack",
        "segment",
        "netlify",
        "planetscale",
        "temporal",
        "modal",
        "replit",
        "langchain",
        "weights & biases",
        "scale",
        "harvey",
        "glean",
        "abridge",
        "openevidence",
        # Quantitative trading: among the most selective engineering
        # employers a new graduate can target.
        "two sigma",
        "jane street",
        "citadel",
        "citadel securities",
        "hudson river trading",
        "jump trading",
        "drw",
        "optiver",
        "imc trading",
        "susquehanna international group",
        "de shaw",
        "d. e. shaw",
        "point72",
        "bridgewater associates",
        "akuna capital",
        "old mission capital",
        "five rings",
        "radix trading",
    }
)


# Large, stable employers that are not tech-first: finance, defence,
# hardware, healthcare, retail. Real jobs, worth seeing, but they should
# not compete for attention with the two tiers above.
ESTABLISHED_NAMES = frozenset(
    {
        "american express",
        "mastercard",
        "visa",
        "jpmorgan chase",
        "jpmorgan",
        "goldman sachs",
        "morgan stanley",
        "capital one",
        "wells fargo",
        "bank of america",
        "citi",
        "citigroup",
        "charles schwab",
        "fidelity investments",
        "bloomberg",
        "walmart",
        "target",
        "costco",
        "the home depot",
        "nike",
        "the walt disney company",
        "disney",
        "comcast",
        "verizon",
        "at&t",
        "t-mobile",
        "general electric",
        "boeing",
        "lockheed martin",
        "raytheon",
        "rtx",
        "northrop grumman",
        "general dynamics",
        "general dynamics mission systems",
        "l3harris technologies",
        "leidos",
        "booz allen hamilton",
        "mitre",
        "peraton",
        "noblis",
        "johns hopkins applied physics laboratory",
        "honeywell",
        "3m",
        "caterpillar",
        "john deere",
        "deere & company",
        "ford motor company",
        "ford",
        "general motors",
        "garmin",
        "texas instruments",
        "micron",
        "micron technology",
        "western digital",
        "seagate",
        "analog devices",
        "nxp semiconductors",
        "marvell",
        "arm",
        "synopsys",
        "cadence design systems",
        "keysight technologies",
        "siemens",
        "bosch",
        "philips",
        "medtronic",
        "abbott",
        "johnson & johnson",
        "pfizer",
        "merck",
        "eli lilly",
        "moderna",
        "cvs health",
        "unitedhealth group",
        "optum",
        "kaiser permanente",
        "usaa",
        "progressive",
        "state farm",
        "allstate",
        "liberty mutual",
        "nationwide",
        "principal financial group",
        "prudential financial",
        "metlife",
        "aflac",
        "cigna",
        "humana",
        "elevance health",
        "anthem",
        "centene",
        "molina healthcare",
        "hca healthcare",
        "tenet healthcare",
        "oracle health",
        "cerner",
        "epic systems",
        "sap concur",
        "adp",
        "paychex",
        "fiserv",
        "fis",
        "global payments",
        "discover financial services",
        "synchrony",
        "ally financial",
        "truist",
        "pnc",
        "us bank",
        "regions bank",
        "keybank",
        "huntington bank",
        "fifth third bank",
        "m&t bank",
        "citizens bank",
        "santander",
        "hsbc",
        "barclays",
        "deutsche bank",
        "ubs",
        "credit suisse",
        "bnp paribas",
        "societe generale",
        "nomura",
        "mizuho",
        "smbc",
        "mufg",
    }
)


# Spellings that appear in the wild mapped onto the canonical name the
# tier sets use. This is where a new variant goes; it is the only place
# fuzziness is permitted, and it stays explicit so SQL can mirror it.
ALIASES: dict[str, str] = {
    "amazon.com": "amazon",
    "amazon web services (aws)": "amazon",
    "aws elemental": "amazon",
    "google llc": "google",
    "meta platforms": "meta",
    "apple inc": "apple",
    "microsoft corporation": "microsoft",
    "nvidia corporation": "nvidia",
    "bytedance inc": "bytedance",
    "tiktok inc": "tiktok",
    "stripe inc": "stripe",
    "openai inc": "openai",
    "anthropic pbc": "anthropic",
    "scale ai inc": "scale ai",
    "the d. e. shaw group": "de shaw",
    "d.e. shaw": "de shaw",
    "sig susquehanna": "susquehanna international group",
    "jane street capital": "jane street",
    "jpmorgan chase & co.": "jpmorgan chase",
    "american express company": "american express",
}


def normalize_company_name(
    value: str | None,
) -> str:
    """Reduce a company name to its tier-lookup key.

    Lowercase and trimmed, and nothing else. The database performs
    exactly this transformation when ordering, so a posting can never
    sort into a tier its badge disagrees with.
    """

    return str(
        value or ""
    ).strip().lower()


def classify_company(
    company: str | None,
) -> CompanyTier:
    """Return the tier a company belongs to."""

    name = normalize_company_name(
        company
    )

    if not name:
        return CompanyTier.OTHER

    name = ALIASES.get(
        name,
        name,
    )

    if name in BIG_TECH_NAMES:
        return CompanyTier.BIG_TECH

    if name in TOP_TIER_NAMES:
        return CompanyTier.TOP_TIER

    if name in ESTABLISHED_NAMES:
        return CompanyTier.ESTABLISHED

    return CompanyTier.OTHER


# Rank used when sorting by employer prominence. Lower sorts first.
TIER_RANK: dict[CompanyTier, int] = {
    CompanyTier.BIG_TECH: 0,
    CompanyTier.TOP_TIER: 1,
    CompanyTier.ESTABLISHED: 2,
    CompanyTier.OTHER: 3,
}


def names_for_tier(
    tier: CompanyTier,
) -> frozenset[str]:
    """Return every lowercase spelling that resolves to one tier.

    Includes the aliases, so a SQL ``lower(company) IN (...)`` test
    reproduces :func:`classify_company` exactly rather than
    approximately.
    """

    direct = {
        CompanyTier.BIG_TECH: BIG_TECH_NAMES,
        CompanyTier.TOP_TIER: TOP_TIER_NAMES,
        CompanyTier.ESTABLISHED: ESTABLISHED_NAMES,
    }.get(
        tier,
        frozenset(),
    )

    aliased = {
        spelling
        for spelling, canonical in (
            ALIASES.items()
        )
        if canonical in direct
    }

    return frozenset(
        direct | aliased
    )
