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
    ),
    "oauth": (
        "oauth",
        "jwt",
        "rbac",
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
