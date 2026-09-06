"""Skill vocabulary and extraction for ACE resume matching.

Matching is deliberately keyword-based rather than embedding-based.

Three reasons, in order of importance:

1. It is explainable. A score alone tells the user nothing actionable;
   "matched pyspark, kafka, airflow -- missing scala" tells them what to
   put on the resume and whether the gap is real.
2. It is deterministic. The same resume and posting always produce the
   same score, so a rank cannot drift between polls.
3. It costs nothing and needs no API key, so matching cannot silently
   stop working when a credential expires.

The trade is that synonyms outside the alias table are missed. The alias
table is therefore the part worth extending as gaps appear.

Relatedness
-----------

Exact names alone under-credit a real match. A posting asking for
"scalability" and a resume evidencing "distributed systems" describe
overlapping ability, but as separate strings they score as a total miss.

``RELATED_SKILLS`` is a hand-curated adjacency graph that lets such a
pair earn partial credit. It is curated rather than learned for the same
three reasons the vocabulary is: the user can be told exactly why a
skill counted, the answer never drifts, and nothing here can fail
because a credential expired.

Adjacency is deliberately not transitivity. The graph is read one hop
deep, so "pandas" relating to "python" and "python" to "fastapi" never
makes pandas evidence of fastapi.
"""

from __future__ import annotations

import re


# Canonical skill -> recognised spellings.
#
# Aliases exist because postings and resumes rarely agree on spelling:
# "Node.js" and "NodeJS", "Postgres" and "PostgreSQL", "k8s" and
# "Kubernetes" are the same skill and must not score as three misses.
SKILL_ALIASES: dict[str, tuple[str, ...]] = {
    # Languages
    "python": ("python",),
    "java": ("java",),
    "javascript": (
        "javascript",
        "es6",
    ),
    "typescript": ("typescript",),
    "go": (
        "golang",
        "go lang",
    ),
    "rust": ("rust",),
    "c++": (
        "c\\+\\+",
        "cpp",
    ),
    "c#": (
        "c#",
        "csharp",
        "c sharp",
    ),
    "scala": ("scala",),
    "kotlin": ("kotlin",),
    "swift": ("swift",),
    "ruby": ("ruby",),
    "php": ("php",),
    "matlab": ("matlab",),
    "sql": ("sql",),
    "bash": (
        "bash",
        "shell scripting",
        "shell script",
    ),
    "r": ("r language",),
    # Backend and web
    "fastapi": ("fastapi",),
    "flask": ("flask",),
    "django": ("django",),
    "spring": (
        "spring boot",
        "spring framework",
    ),
    "node.js": (
        "node\\.js",
        "nodejs",
        "node js",
    ),
    "express": ("express\\.js", "expressjs"),
    "react": (
        "react",
        "react\\.js",
        "reactjs",
    ),
    "next.js": (
        "next\\.js",
        "nextjs",
    ),
    "vue": (
        "vue",
        "vue\\.js",
    ),
    "angular": ("angular",),
    "graphql": ("graphql",),
    "grpc": ("grpc",),
    "rest api": (
        "rest api",
        "restful",
        "rest apis",
    ),
    "websockets": (
        "websocket",
        "websockets",
    ),
    "microservices": ("microservices",),
    # Data stores
    "postgresql": (
        "postgresql",
        "postgres",
    ),
    "mysql": ("mysql",),
    "mongodb": ("mongodb", "mongo"),
    "redis": ("redis",),
    "elasticsearch": (
        "elasticsearch",
        "opensearch",
    ),
    "cassandra": ("cassandra",),
    "dynamodb": ("dynamodb",),
    "snowflake": ("snowflake",),
    "firebase": ("firebase",),
    # Data engineering
    "spark": (
        "spark",
        "pyspark",
    ),
    "kafka": ("kafka",),
    "airflow": (
        "airflow",
        "apache airflow",
    ),
    "hadoop": ("hadoop",),
    "dbt": ("dbt",),
    "etl": (
        "etl",
        "elt",
        "data pipeline",
        "data pipelines",
        "batch processing",
    ),
    "celery": ("celery",),
    "delta lake": ("delta lake",),
    # Cloud and platform
    "aws": (
        "aws",
        "amazon web services",
    ),
    "azure": ("azure",),
    "gcp": (
        "gcp",
        "google cloud",
    ),
    "docker": (
        "docker",
        "containerization",
    ),
    "kubernetes": (
        "kubernetes",
        "k8s",
    ),
    "terraform": ("terraform",),
    "ci/cd": (
        "ci/cd",
        "cicd",
        "continuous integration",
        "github actions",
        "jenkins",
    ),
    "linux": (
        "linux",
        "unix",
    ),
    "git": ("git", "github", "gitlab"),
    "serverless": (
        "serverless",
        "lambda",
    ),
    # ML and AI
    "pytorch": ("pytorch",),
    "tensorflow": ("tensorflow",),
    "scikit-learn": (
        "scikit-learn",
        "sklearn",
    ),
    "pandas": ("pandas",),
    "numpy": ("numpy",),
    "transformers": (
        "transformers",
        "hugging ?face",
    ),
    "llm": (
        "llm",
        "large language model",
    ),
    "rag": (
        "rag",
        "retrieval augmented generation",
    ),
    "embeddings": (
        "embedding",
        "embeddings",
    ),
    "nlp": (
        "nlp",
        "natural language processing",
    ),
    "computer vision": (
        "computer vision",
        "opencv",
    ),
    "speech recognition": (
        "speech recognition",
        "whisper",
        "asr",
    ),
    "vector database": (
        "vector database",
        "qdrant",
        "pinecone",
        "weaviate",
        "faiss",
    ),
    "mlops": ("mlops",),
    "model training": (
        "model training",
        "fine-tuning",
        "fine tuning",
    ),
    # Practice
    "distributed systems": (
        "distributed systems",
        "sharding",
        "replication",
        "consensus protocol",
        "raft",
    ),
    "system design": (
        "system design",
    ),
    "concurrency": (
        "concurrency",
        "multithreading",
        "async",
    ),
    "testing": (
        "unit test",
        "pytest",
        "integration test",
    ),
    "agile": (
        "agile",
        "scrum",
    ),
    "observability": (
        "observability",
        "prometheus",
        "grafana",
        "datadog",
        "monitoring",
        "logging",
        "distributed tracing",
        "alerting",
        "on-?call",
    ),
    "authentication": (
        "oauth",
        "jwt",
        "rbac",
        "authentication",
        "authorization",
        "authn",
        "authz",
        "single sign-?on",
        "saml",
    ),
    # Qualities and concerns. Postings name these far more often than
    # they name a framework: "scalable" appears in roughly two thirds of
    # ACE's qualifying descriptions, and before this block none of it
    # was recognised at all.
    "scalability": (
        "scalability",
        "scalable",
        "large[- ]scale",
        "at scale",
        "high[- ]throughput",
        "horizontal(?:ly)? scal\\w+",
    ),
    "high availability": (
        "high[- ]availability",
        "highly available",
        "fault[- ]toleran\\w+",
        "resilien\\w+",
        "disaster recovery",
    ),
    "low latency": (
        "low[- ]latency",
        "real[- ]time",
        "realtime",
        "latency[- ]sensitive",
    ),
    "caching": (
        "caching",
        "cache",
        "memcached",
        "cdn",
    ),
    "event-driven": (
        "event[- ]driven",
        "pub/?sub",
        "publish[- ]subscribe",
        "message queue",
        "message broker",
        "rabbitmq",
        "sqs",
    ),
    "stream processing": (
        "stream processing",
        "streaming data",
        "data streaming",
    ),
    "flink": (
        "flink",
    ),
    "databricks": (
        "databricks",
    ),
    "bigquery": (
        "bigquery",
        "redshift",
    ),
    "data modeling": (
        "data model",
        "data models",
        "data modell?ing",
        "schema design",
    ),
    "api design": (
        "api design",
        "api development",
        "designing apis",
    ),
    "infrastructure as code": (
        "infrastructure as code",
        "\\biac\\b",
        "helm charts?",
        "cloudformation",
        "pulumi",
        "ansible",
    ),
    "experimentation": (
        "a/b test\\w*",
        "ab testing",
        "experimentation",
    ),
    "recommendation systems": (
        "recommendation system",
        "recommendation engine",
        "recommender",
    ),
    "information retrieval": (
        "information retrieval",
        "search relevance",
        "search ranking",
        "ranking system",
    ),
}


def _alias_pattern(
    alias: str,
) -> re.Pattern[str]:
    """Compile one alias into a word-boundary pattern.

    Boundaries are only applied where the alias starts and ends with a
    word character. Without that guard "c++" and "c#" would never match,
    because their final character is not a word character and ``\\b``
    would demand one after it.
    """

    prefix = (
        r"\b"
        if re.match(
            r"\w",
            alias[0],
        )
        else ""
    )

    suffix = (
        r"\b"
        if re.search(
            r"\w$",
            alias,
        )
        else ""
    )

    return re.compile(
        prefix + alias + suffix,
        re.IGNORECASE,
    )


COMPILED_SKILLS: dict[
    str,
    tuple[re.Pattern[str], ...],
] = {
    skill: tuple(
        _alias_pattern(
            alias
        )
        for alias in aliases
    )
    for skill, aliases in (
        SKILL_ALIASES.items()
    )
}


def extract_skills(
    text: str,
) -> frozenset[str]:
    """Return the canonical skills named in a block of text."""

    if not text:
        return frozenset()

    found: set[str] = set()

    for skill, patterns in (
        COMPILED_SKILLS.items()
    ):
        for pattern in patterns:
            if pattern.search(
                text
            ):
                found.add(
                    skill
                )

                break

    return frozenset(
        found
    )


# Pairs of skills that evidence overlapping ability without being the
# same thing. Each pair is declared once and made symmetric below, so
# the graph cannot become one-directional through a typo.
#
# The bar for a pair is: would a hiring engineer accept the one as
# partial evidence of the other? "Distributed systems" and "scalability"
# clear it. "Python" and "Java" do not -- both are languages, but
# knowing one is not evidence of the other.
RELATED_SKILL_PAIRS: tuple[
    tuple[str, str],
    ...,
] = (
    # Backend architecture
    ("distributed systems", "scalability"),
    ("distributed systems", "high availability"),
    ("distributed systems", "microservices"),
    ("distributed systems", "system design"),
    ("distributed systems", "concurrency"),
    ("scalability", "high availability"),
    ("scalability", "low latency"),
    ("scalability", "caching"),
    ("high availability", "observability"),
    ("low latency", "caching"),
    ("caching", "redis"),
    ("system design", "microservices"),
    ("system design", "api design"),
    ("microservices", "event-driven"),
    ("microservices", "api design"),
    # Messaging and streaming
    ("event-driven", "kafka"),
    ("stream processing", "kafka"),
    ("stream processing", "flink"),
    ("stream processing", "spark"),
    ("stream processing", "low latency"),
    # Data
    ("etl", "airflow"),
    ("etl", "spark"),
    ("etl", "data modeling"),
    ("data modeling", "sql"),
    ("data modeling", "postgresql"),
    ("spark", "databricks"),
    ("databricks", "delta lake"),
    ("snowflake", "bigquery"),
    ("bigquery", "sql"),
    ("postgresql", "mysql"),
    ("postgresql", "sql"),
    ("mysql", "sql"),
    ("mongodb", "dynamodb"),
    ("cassandra", "dynamodb"),
    # Platform
    ("kubernetes", "docker"),
    ("infrastructure as code", "terraform"),
    ("infrastructure as code", "kubernetes"),
    ("ci/cd", "docker"),
    ("ci/cd", "testing"),
    ("ci/cd", "git"),
    ("aws", "serverless"),
    ("linux", "bash"),
    ("go", "concurrency"),
    # APIs and web
    ("rest api", "api design"),
    ("rest api", "graphql"),
    ("api design", "graphql"),
    ("react", "javascript"),
    ("react", "next.js"),
    ("vue", "javascript"),
    ("angular", "typescript"),
    ("typescript", "javascript"),
    ("node.js", "javascript"),
    ("node.js", "express"),
    ("fastapi", "python"),
    ("flask", "python"),
    ("django", "python"),
    ("spring", "java"),
    ("java", "kotlin"),
    ("java", "scala"),
    ("c++", "rust"),
    # ML and AI
    ("llm", "rag"),
    ("llm", "transformers"),
    ("llm", "nlp"),
    ("rag", "vector database"),
    ("rag", "embeddings"),
    ("embeddings", "vector database"),
    ("nlp", "transformers"),
    ("pytorch", "tensorflow"),
    ("pytorch", "model training"),
    ("tensorflow", "model training"),
    ("model training", "mlops"),
    ("mlops", "ci/cd"),
    ("scikit-learn", "pandas"),
    ("pandas", "numpy"),
    ("pandas", "python"),
    ("recommendation systems", "information retrieval"),
    ("recommendation systems", "embeddings"),
    ("recommendation systems", "experimentation"),
    ("information retrieval", "elasticsearch"),
)


def _build_related_skills() -> dict[
    str,
    frozenset[str],
]:
    """Expand the declared pairs into a symmetric adjacency map.

    Every name is checked against the vocabulary. A pair naming a skill
    that does not exist is a typo that would otherwise never match and
    never be noticed, so it raises at import rather than degrading
    scoring silently.
    """

    graph: dict[
        str,
        set[str],
    ] = {}

    for left, right in (
        RELATED_SKILL_PAIRS
    ):
        for name in (
            left,
            right,
        ):
            if name not in SKILL_ALIASES:
                raise ValueError(
                    "RELATED_SKILL_PAIRS names "
                    f"unknown skill {name!r}"
                )

        if left == right:
            raise ValueError(
                "skill related to itself: "
                f"{left!r}"
            )

        graph.setdefault(
            left,
            set(),
        ).add(
            right
        )

        graph.setdefault(
            right,
            set(),
        ).add(
            left
        )

    return {
        skill: frozenset(
            neighbours
        )
        for skill, neighbours in (
            graph.items()
        )
    }


RELATED_SKILLS: dict[
    str,
    frozenset[str],
] = _build_related_skills()


def related_skills(
    skill: str,
) -> frozenset[str]:
    """Return the skills one hop from ``skill`` in the graph.

    One hop only. Transitive closure would make pandas evidence of
    fastapi by way of python, which is not a claim ACE should make.
    """

    return RELATED_SKILLS.get(
        skill,
        frozenset(),
    )
