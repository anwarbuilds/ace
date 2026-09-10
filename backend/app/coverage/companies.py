"""Companies this user wants covered, whether or not a tracker lists them.

Discovery used to be entirely downstream of three community-maintained
README files (``HELD_OUT_LISTS`` in benchmark.py). That made ACE's recall
a function of whoever edits those files. A real example settled it: the
user found a Cursor posting by hand and asked why ACE had missed it.
Cursor runs on Ashby, an adapter ACE has supported from the start, and
``find_board("Cursor")`` resolves its board in one call with 128 jobs
behind it. None of the three lists mentions Cursor even once, so no
automated path could ever have reached it.

The machinery was never the problem. The list of names was.

So this is the list ACE owns. Add a company here and the next
``discover_boards`` run probes it, verifies the board really belongs to
that employer, and registers it. Nothing is registered on a guess: the
prober checks the board's own metadata or page text against the name
before accepting it, because two employers can share a name and a wrong
subscription fills the queue with somebody else's jobs under a name the
user recognises -- harder to notice than a gap.

A name that resolves to nothing is not a mistake. It stays here and is
retried, because a company that self-hosts today may move onto a
supported board tomorrow, and because the careers-page route finds
tokens the name-guessing route cannot.

Grouped only for readability; the grouping carries no behaviour.
"""

from __future__ import annotations


# AI labs, model providers and the tooling around them. The tier this
# user targets most heavily, and the one the community trackers are
# slowest to pick up because these companies are newest.
AI_AND_TOOLING = (
    "Cursor",
    "Perplexity",
    "Cohere",
    "Mistral",
    "Glean",
    "Harvey",
    "Sierra",
    "Abridge",
    "Runway",
    "ElevenLabs",
    "Suno",
    "Together AI",
    "Fireworks AI",
    "Groq",
    "Cerebras",
    "Lambda",
    "Modal",
    "Replicate",
    "Baseten",
    "LangChain",
    "Pinecone",
    "Chroma",
    "Weights & Biases",
    "Scale AI",
)


# Developer tools, infrastructure and data platforms.
INFRASTRUCTURE = (
    "Vercel",
    "Supabase",
    "Render",
    "Fly.io",
    "Temporal",
    "Confluent",
    "Databricks",
    "Snowflake",
    "dbt Labs",
    "Fivetran",
    "Airbyte",
    "Grafana Labs",
    "HashiCorp",
    "Cloudflare",
    "Datadog",
    "Sentry",
    "Sourcegraph",
)


# Product companies with large engineering organisations.
PRODUCT = (
    "Linear",
    "Retool",
    "Airtable",
    "Notion",
    "Figma",
    "Canva",
    "Miro",
    "Loom",
    "Webflow",
    "Reddit",
    "Discord",
    "Twitch",
    "Roblox",
    "Unity",
    "Epic Games",
    "Instacart",
    "DoorDash",
)


# Fintech.
FINTECH = (
    "Ramp",
    "Brex",
    "Mercury",
    "Plaid",
    "Chime",
    "Affirm",
    "Marqeta",
    "Coinbase",
    "Robinhood",
    "Stripe",
    "Block",
    "Deel",
    "Rippling",
    "Gusto",
    "Justworks",
)


# Robotics, autonomy, aerospace and defence. Several of these are
# export-controlled and will be rejected by the gate on citizenship
# grounds; they are listed anyway, because the gate deciding is the
# right outcome and silently not looking is not.
AUTONOMY_AND_HARDWARE = (
    "Anduril",
    "Applied Intuition",
    "Waymo",
    "Zoox",
    "Nuro",
    "Rivian",
    "Lucid Motors",
    "Joby Aviation",
    "Astranis",
)


TARGET_COMPANIES: tuple[str, ...] = (
    AI_AND_TOOLING
    + INFRASTRUCTURE
    + PRODUCT
    + FINTECH
    + AUTONOMY_AND_HARDWARE
)


# Curated names are probed before the trackers' names, and polled more
# often once registered, because they are the user's own picks rather
# than a list someone else happened to publish.
CURATED_POLL_INTERVAL_SECONDS = 900
