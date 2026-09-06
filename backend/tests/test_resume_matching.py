"""Tests for ACE resume-to-job matching.

The properties pinned here are the ones that make partial credit safe to
ship. Partial credit is the only part of ACE that can *raise* a score
without new evidence, so the tests concentrate on the guarantees that
stop it from overstating fit: credit is never double counted, adjacency
never outranks naming the skill, and relatedness never chains.
"""

from datetime import (
    datetime,
    timezone,
)

import pytest
from sqlalchemy import (
    create_engine,
    select,
)
from sqlalchemy.orm import (
    Session,
    sessionmaker,
)

from backend.app.db.base import Base
from backend.app.db.models import (
    JobEvaluationRecord,
    JobRecord,
    JobResumeScoreRecord,
)
from backend.app.matching.scoring import (
    MATCHING_ALGORITHM_VERSION,
    MIN_JOB_SKILLS_FOR_SCORE,
    RELATED_SKILL_CREDIT,
    build_skills_gap,
    score_job,
)
from backend.app.matching.service import (
    rescore_corpus,
    stale_score_count,
    store_resume,
)
from backend.app.matching.skills import (
    RELATED_SKILL_PAIRS,
    RELATED_SKILLS,
    SKILL_ALIASES,
    extract_skills,
    related_skills,
)


NOW = datetime(
    2026,
    9,
    5,
    12,
    0,
    tzinfo=timezone.utc,
)


@pytest.fixture(name="session_factory")
def fixture_session_factory():
    """Provide an isolated in-memory database."""

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={
            "check_same_thread": False,
        },
    )

    Base.metadata.create_all(
        engine
    )

    return sessionmaker(
        bind=engine,
        class_=Session,
        expire_on_commit=False,
    )


def add_job(
    session: Session,
    *,
    external_id: str,
    description: str,
    verified: bool = True,
) -> JobRecord:
    """Store one evaluated job ready for scoring."""

    job = JobRecord(
        source="greenhouse",
        source_account="example",
        external_id=external_id,
        company="Example",
        requisition_id=None,
        title="Software Engineer",
        location="Seattle, Washington",
        description=description,
        official_url=(
            "https://example.com/"
            f"{external_id}"
        ),
        content_hash=external_id * 8,
        first_seen_at=NOW,
        last_seen_at=NOW,
        is_active=True,
    )

    session.add(
        job
    )

    session.flush()

    session.add(
        JobEvaluationRecord(
            job_id=job.id,
            eligibility_status="PASS",
            role_family="SOFTWARE_ENGINEERING",
            role_priority="TIER_1",
            rule_version="test",
            content_hash=job.content_hash,
            requirements_verified=verified,
            evaluated_at=NOW,
        )
    )

    session.flush()

    return job


# --- vocabulary ------------------------------------------------------


def test_extraction_recognizes_scale_language() -> None:
    """Postings describe qualities, not only named technologies."""

    skills = extract_skills(
        "Design large-scale services that stay "
        "highly available under load, with "
        "low-latency reads served from cache."
    )

    assert "scalability" in skills

    assert "high availability" in skills

    assert "low latency" in skills

    assert "caching" in skills


def test_extraction_handles_non_word_final_characters() -> None:
    """Skills ending in punctuation must still match.

    A trailing word boundary after "c++" can never be satisfied, so
    these two would silently never match if the boundary logic
    regressed.
    """

    skills = extract_skills(
        "Strong C++ or C# background."
    )

    assert "c++" in skills

    assert "c#" in skills


def test_extraction_ignores_the_helm_idiom() -> None:
    """Aliases must not collide with ordinary English.

    "At the helm" appears in real postings, and bare "helm" as an alias
    for infrastructure-as-code would match it.
    """

    assert (
        "infrastructure as code"
        not in extract_skills(
            "You will be at the helm of "
            "a growing team."
        )
    )


# --- the relationship graph ------------------------------------------


def test_related_graph_names_only_known_skills() -> None:
    """Every graph entry must be a real canonical skill."""

    for skill, neighbours in (
        RELATED_SKILLS.items()
    ):
        assert skill in SKILL_ALIASES

        for neighbour in neighbours:
            assert (
                neighbour
                in SKILL_ALIASES
            )


def test_related_graph_is_symmetric() -> None:
    """Relatedness must not depend on direction.

    An asymmetric edge would score a resume differently depending on
    which side happened to name the skill.
    """

    for skill, neighbours in (
        RELATED_SKILLS.items()
    ):
        for neighbour in neighbours:
            assert (
                skill
                in RELATED_SKILLS[
                    neighbour
                ]
            )


def test_related_graph_has_no_self_edges() -> None:
    """A skill is not evidence of itself at a discount."""

    for skill, neighbours in (
        RELATED_SKILLS.items()
    ):
        assert (
            skill not in neighbours
        )


def test_declared_pairs_are_unique() -> None:
    """A duplicated pair is a curation slip worth catching."""

    normalized = {
        frozenset(
            pair
        )
        for pair in RELATED_SKILL_PAIRS
    }

    assert len(
        normalized
    ) == len(
        RELATED_SKILL_PAIRS
    )


# --- scoring ---------------------------------------------------------


def test_naming_every_requirement_scores_full() -> None:
    result = score_job(
        resume_skills=frozenset(
            {
                "python",
                "kafka",
                "airflow",
            }
        ),
        job_text=(
            "Python, Kafka and Airflow."
        ),
    )

    assert result.score == 100

    assert result.missing_skills == ()

    assert result.related_skills == ()


def test_related_skill_earns_partial_credit() -> None:
    """Adjacent experience counts, at the partial rate."""

    result = score_job(
        resume_skills=frozenset(
            {
                "distributed systems",
                "python",
                "kafka",
            }
        ),
        job_text=(
            "Python and Kafka required. "
            "You will build scalable services."
        ),
    )

    assert (
        "scalability"
        in result.related_skills
    )

    assert (
        "scalability"
        not in result.matched_skills
    )

    assert (
        "scalability"
        not in result.missing_skills
    )

    expected = round(
        100
        * (
            2
            + RELATED_SKILL_CREDIT
        )
        / 3
    )

    assert result.score == expected


def test_related_credit_never_outranks_naming_the_skill() -> None:
    """A resume that names the requirement must win.

    This is the guarantee that keeps partial credit honest: it can lift
    a near-miss up the ranking, but never past a genuine match.
    """

    job_text = (
        "We need Python, Kafka and "
        "scalability experience."
    )

    exact = score_job(
        resume_skills=frozenset(
            {
                "python",
                "kafka",
                "scalability",
            }
        ),
        job_text=job_text,
    )

    adjacent = score_job(
        resume_skills=frozenset(
            {
                "python",
                "kafka",
                "distributed systems",
            }
        ),
        job_text=job_text,
    )

    unrelated = score_job(
        resume_skills=frozenset(
            {
                "python",
                "kafka",
            }
        ),
        job_text=job_text,
    )

    assert (
        exact.score
        > adjacent.score
        > unrelated.score
    )


def test_matched_and_related_never_overlap() -> None:
    """Credit must not be counted twice for one requirement.

    "python" is on the resume and also related to "fastapi", so a
    requirement naming both is the case where double counting would
    push a score above what the evidence supports.
    """

    result = score_job(
        resume_skills=frozenset(
            {
                "python",
                "pandas",
                "numpy",
            }
        ),
        job_text=(
            "Python, pandas and numpy, "
            "plus FastAPI and Django."
        ),
    )

    assert not (
        set(
            result.matched_skills
        )
        & set(
            result.related_skills
        )
    )

    assert result.score <= 100


def test_relatedness_does_not_chain() -> None:
    """The graph is read one hop deep, never transitively.

    pandas relates to python and python relates to fastapi. If the walk
    were transitive, a pandas-only resume would claim credit for a
    FastAPI requirement it has no evidence for.
    """

    assert (
        "python"
        in related_skills(
            "pandas"
        )
    )

    assert (
        "python"
        in related_skills(
            "fastapi"
        )
    )

    result = score_job(
        resume_skills=frozenset(
            {
                "pandas",
            }
        ),
        job_text=(
            "FastAPI, Kubernetes and "
            "Terraform experience."
        ),
    )

    assert (
        "fastapi"
        in result.missing_skills
    )


def test_related_evidence_names_a_resume_skill() -> None:
    """The explanation must point at something the user actually has."""

    resume = frozenset(
        {
            "distributed systems",
            "redis",
            "python",
        }
    )

    result = score_job(
        resume_skills=resume,
        job_text=(
            "Scalable, highly available "
            "services with caching."
        ),
    )

    assert result.related_evidence

    for (
        requirement,
        evidence,
    ) in result.related_evidence:
        assert (
            requirement
            in result.related_skills
        )

        assert evidence in resume

        assert (
            evidence
            in related_skills(
                requirement
            )
        )


def test_scoring_is_deterministic() -> None:
    """Identical inputs must produce an identical explanation."""

    kwargs = {
        "resume_skills": frozenset(
            {
                "distributed systems",
                "redis",
                "sql",
            }
        ),
        "job_text": (
            "Scalable services, caching, "
            "and data modeling."
        ),
    }

    first = score_job(
        **kwargs
    )

    second = score_job(
        **kwargs
    )

    assert first == second


def test_unverified_posting_is_unscored() -> None:
    """A posting ACE never read has no requirements to match."""

    result = score_job(
        resume_skills=frozenset(
            {
                "python",
            }
        ),
        job_text=(
            "Python, Kafka, Airflow."
        ),
        requirements_verified=False,
    )

    assert result.score is None

    assert result.related_skills == ()


def test_thin_posting_is_unscored_but_still_explained() -> None:
    """Too little signal to rank is not the same as a poor match."""

    result = score_job(
        resume_skills=frozenset(
            {
                "distributed systems",
            }
        ),
        job_text=(
            "Work on scalable systems."
        ),
    )

    assert result.score is None

    assert (
        len(
            extract_skills(
                "Work on scalable systems."
            )
        )
        < MIN_JOB_SKILLS_FOR_SCORE
    )

    assert (
        "scalability"
        in result.related_skills
    )


def test_skills_gap_counts_only_true_misses() -> None:
    """Adjacency is weaker evidence, but it is not a gap.

    Listing a related-but-covered skill here would send the user to
    learn something they can already speak to.
    """

    result = score_job(
        resume_skills=frozenset(
            {
                "distributed systems",
                "python",
                "kafka",
            }
        ),
        job_text=(
            "Python, Kafka, scalability "
            "and Terraform."
        ),
    )

    gap = dict(
        build_skills_gap(
            [
                result.missing_skills,
            ]
        )
    )

    assert "terraform" in gap

    assert "scalability" not in gap


# --- persistence -----------------------------------------------------


def test_rescore_stores_related_skills_and_version(
    session_factory,
) -> None:
    with session_factory() as session:
        job = add_job(
            session,
            external_id="1",
            description=(
                "Python and Kafka "
                "required, building "
                "scalable services."
            ),
        )

        resume = store_resume(
            session,
            label="CV",
            filename="cv.pdf",
            raw_text=(
                "Python, Kafka, and "
                "distributed systems."
            ),
            now=NOW,
        )

        rescore_corpus(
            session,
            resume=resume,
        )

        stored = session.scalars(
            select(
                JobResumeScoreRecord
            ).where(
                JobResumeScoreRecord
                .job_id
                == job.id
            )
        ).one()

        assert stored.related_skills == [
            "scalability",
        ]

        assert (
            stored.algorithm_version
            == MATCHING_ALGORITHM_VERSION
        )


def test_rescore_refreshes_stale_resume_skills(
    session_factory,
) -> None:
    """A vocabulary change must reach resumes uploaded before it.

    Skills are extracted at upload time. Without re-extraction the
    resume keeps the vocabulary it was parsed with, and every later
    score silently inherits that gap.
    """

    with session_factory() as session:
        add_job(
            session,
            external_id="1",
            description=(
                "Python, Kafka, Airflow."
            ),
        )

        resume = store_resume(
            session,
            label="CV",
            filename="cv.pdf",
            raw_text=(
                "Python, Kafka and "
                "distributed systems."
            ),
            now=NOW,
        )

        # Simulate a resume parsed by an older, smaller vocabulary.
        resume.extracted_skills = [
            "python",
        ]

        session.flush()

        rescore_corpus(
            session,
            resume=resume,
        )

        assert (
            "distributed systems"
            in resume.extracted_skills
        )


def test_stale_scores_are_detectable(
    session_factory,
) -> None:
    """Scores from retired rules must not pass as current."""

    with session_factory() as session:
        add_job(
            session,
            external_id="1",
            description=(
                "Python, Kafka, Airflow."
            ),
        )

        resume = store_resume(
            session,
            label="CV",
            filename="cv.pdf",
            raw_text="Python and Kafka.",
            now=NOW,
        )

        rescore_corpus(
            session,
            resume=resume,
        )

        assert stale_score_count(
            session,
            resume=resume,
        ) == 0

        session.execute(
            JobResumeScoreRecord
            .__table__
            .update()
            .values(
                algorithm_version=(
                    "v1-exact"
                )
            )
        )

        assert stale_score_count(
            session,
            resume=resume,
        ) == 1


def test_rescore_remembers_the_previous_score(
    session_factory,
) -> None:
    """A re-score reshuffles the ranking; the move must be recoverable.

    Without this the list quietly reorders and the user cannot tell
    whether ACE improved or drifted.
    """

    with session_factory() as session:
        job = add_job(
            session,
            external_id="1",
            description=(
                "Python, Kafka, Airflow and "
                "Terraform required."
            ),
        )

        resume = store_resume(
            session,
            label="CV",
            filename="cv.pdf",
            raw_text="Python only.",
            now=NOW,
        )

        rescore_corpus(
            session,
            resume=resume,
        )

        first = session.scalars(
            select(
                JobResumeScoreRecord
            ).where(
                JobResumeScoreRecord.job_id
                == job.id
            )
        ).one()

        # No predecessor on the first ever score. That is not the same
        # as "did not move".
        assert (
            first.previous_score is None
        )

        original = first.score

        resume.raw_text = (
            "Python, Kafka and Airflow."
        )

        session.flush()

        rescore_corpus(
            session,
            resume=resume,
        )

        second = session.scalars(
            select(
                JobResumeScoreRecord
            ).where(
                JobResumeScoreRecord.job_id
                == job.id
            )
        ).one()

        assert (
            second.previous_score
            == original
        )

        assert (
            second.score
            > second.previous_score
        )


def test_skills_gap_can_be_narrowed_to_one_role_family(
    session_factory,
) -> None:
    """"What am I missing for ML roles" is a different question."""

    from backend.app.matching.service import (
        skills_gap,
    )

    with session_factory() as session:
        backend_job = add_job(
            session,
            external_id="1",
            description=(
                "Python, Kafka and Terraform."
            ),
        )

        ml_job = add_job(
            session,
            external_id="2",
            description=(
                "Python, pytorch and "
                "computer vision."
            ),
        )

        session.get(
            JobEvaluationRecord,
            ml_job.id,
        ).role_family = "AI_ML_ENGINEERING"

        session.flush()

        resume = store_resume(
            session,
            label="CV",
            filename="cv.pdf",
            raw_text="Python.",
            now=NOW,
        )

        rescore_corpus(
            session,
            resume=resume,
        )

        everything = {
            row["skill"]
            for row in skills_gap(
                session,
                resume=resume,
            )
        }

        assert "terraform" in everything

        ml_only = {
            row["skill"]
            for row in skills_gap(
                session,
                resume=resume,
                role_family=(
                    "AI_ML_ENGINEERING"
                ),
            )
        }

        assert "pytorch" in ml_only

        # The backend posting's gap must not leak into the ML report.
        assert "terraform" not in ml_only
