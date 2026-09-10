"""What kind of thing each stored answer is, and what it may be called.

The bank began as a flat list of text boxes: every question, including
the ones a form only ever asks as Yes/No or as a dropdown, was answered
by typing. That put two jobs on the user that are not theirs.

The first was typing "No" thirteen times. A question whose only possible
answers are yes and no should be a toggle, and a question whose answers
are a known set should be a list to pick from.

The second was worse, and is why this module exists rather than just a
nicer form. A typed answer has to match wording ACE has never seen. A
stored "Job Portal" matches nothing on a Dell form offering "Job Board
(e.g., LinkedIn, Indeed, Glassdoor)", and the fix on offer was for the
user to hand-write every synonym they could think of. Knowing that a
job board and a job portal are the same thing is ACE's job. So each
option carries the wordings a real form might use, shipped here and sent
to the extension, and the user picks the concept once.

Free text stays free text. A name is not a choice.
"""

from __future__ import annotations

from dataclasses import (
    dataclass,
    field,
)


BOOLEAN = "boolean"

CHOICE = "choice"

TEXT = "text"


@dataclass(frozen=True, slots=True)
class Option:
    """One value a choice question can take.

    ``label`` is what ACE shows and stores. ``aliases`` are the other
    wordings a form might print for the same thing, and exist only so
    the extension can recognise the option on a page. They are never
    shown and never stored.
    """

    label: str

    aliases: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Question:
    """One row of the answer bank, and how it should be answered."""

    label: str

    kind: str = TEXT

    options: tuple[Option, ...] = ()

    # Shown under the control where the question alone is not enough to
    # answer confidently.
    hint: str = ""


def _yes_no(
    label: str,
    *,
    hint: str = "",
) -> Question:
    """A question a form asks as Yes/No, however it words the buttons."""

    return Question(
        label=label,
        kind=BOOLEAN,
        hint=hint,
    )


# Options offered for a yes/no question. Held here rather than in the
# extension so the answers page and the matcher agree on what "Yes"
# means, including on the consent controls that say "I Agree" instead.
BOOLEAN_OPTIONS = (
    Option(
        label="Yes",
        aliases=(
            "yes",
            "y",
            "true",
            "i agree",
            "agree",
            "i accept",
            "accept",
            "i consent",
            "consent",
            "i acknowledge",
            "i certify",
            "confirm",
        ),
    ),
    Option(
        label="No",
        aliases=(
            "no",
            "n",
            "false",
            "i do not agree",
            "i disagree",
            "disagree",
            "decline",
            "i decline",
        ),
    ),
)


GENDER = (
    Option("Male", ("male", "man")),
    Option("Female", ("female", "woman")),
    Option(
        "Non-binary",
        ("non binary", "nonbinary", "non-binary", "genderqueer"),
    ),
    Option(
        "Prefer not to say",
        (
            "decline to self identify",
            "decline to self-identify",
            "prefer not to answer",
            "i do not wish to answer",
            "do not wish to disclose",
        ),
    ),
)


RACE = (
    Option("Asian", ("asian", "asian not hispanic or latino")),
    Option(
        "Black or African American",
        ("black", "african american", "black or african american"),
    ),
    Option(
        "Hispanic or Latino",
        ("hispanic", "latino", "latinx", "hispanic or latino"),
    ),
    Option("White", ("white", "caucasian", "white not hispanic or latino")),
    Option(
        "Native American or Alaska Native",
        ("american indian", "alaska native", "native american"),
    ),
    Option(
        "Native Hawaiian or Pacific Islander",
        ("native hawaiian", "pacific islander"),
    ),
    Option("Two or more races", ("two or more races", "multiracial")),
    Option(
        "Prefer not to say",
        (
            "decline to self identify",
            "decline to self-identify",
            "prefer not to answer",
            "i do not wish to answer",
        ),
    ),
)


VETERAN = (
    Option(
        "I am not a protected veteran",
        (
            "i am not a protected veteran",
            "not a protected veteran",
            "no i am not a veteran",
            "not a veteran",
        ),
    ),
    Option(
        "I am a protected veteran",
        (
            "i identify as one or more of the classifications of a "
            "protected veteran",
            "i am a protected veteran",
            "yes i am a veteran",
        ),
    ),
    Option(
        "Prefer not to say",
        (
            "i do not wish to answer",
            "decline to self identify",
            "decline to self-identify",
            "prefer not to answer",
        ),
    ),
)


DISABILITY = (
    Option(
        "I do not have any disability",
        (
            "no i do not have a disability",
            "no i don't have a disability",
            "i do not have a disability",
            "no disability",
        ),
    ),
    Option(
        "I have a disability, or have had one",
        (
            "yes i have a disability",
            "yes i have a disability or have had one in the past",
            "i have a disability",
        ),
    ),
    Option(
        "Prefer not to say",
        (
            "i do not wish to answer",
            "i don't wish to answer",
            "prefer not to answer",
            "decline to self identify",
        ),
    ),
)


PRONOUNS = (
    Option("He/Him", ("he him", "he/him", "he")),
    Option("She/Her", ("she her", "she/her", "she")),
    Option("They/Them", ("they them", "they/them", "they")),
    Option(
        "Prefer not to say",
        ("prefer not to say", "i do not wish to answer"),
    ),
)


# The question that made the case for this whole module. Every one of
# these is the same concept under a different name, and which name a
# form uses is not something the user should have to predict.
REFERRAL = (
    Option(
        "Job board",
        (
            "job board",
            "job boards",
            "job portal",
            "job site",
            "job posting",
            "online job board",
            "indeed",
            "glassdoor",
            "ziprecruiter",
            "monster",
            "job board e g linkedin indeed glassdoor",
        ),
    ),
    Option("LinkedIn", ("linkedin", "linked in")),
    Option(
        "Company website",
        ("company website", "our website", "careers page", "company site"),
    ),
    Option(
        "Employee referral",
        (
            "employee referral",
            "referral",
            "referred by an employee",
            "friend or colleague",
            "word of mouth",
        ),
    ),
    Option(
        "Search engine",
        ("search engine", "google", "web search", "internet search"),
    ),
    Option(
        "University or career fair",
        (
            "university",
            "career fair",
            "job fair",
            "campus",
            "college",
            "school",
        ),
    ),
    Option(
        "Social media",
        ("social media", "twitter", "facebook", "instagram", "x"),
    ),
    Option("Other", ("other", "none of the above")),
)


CONTACT_METHOD = (
    Option("Email", ("email", "e mail", "e-mail")),
    Option("Phone", ("phone", "call", "telephone")),
    Option(
        "Text message",
        ("text", "sms", "text message", "email sms", "whatsapp"),
    ),
)


TRANSGENDER = (
    Option("No", ("no", "i do not identify as transgender")),
    Option("Yes", ("yes", "i identify as transgender")),
    Option(
        "Prefer not to say",
        ("prefer not to say", "i do not wish to answer", "decline"),
    ),
)


ORIENTATION = (
    Option("Heterosexual", ("heterosexual", "straight")),
    Option("Gay or lesbian", ("gay", "lesbian", "homosexual")),
    Option("Bisexual", ("bisexual",)),
    Option(
        "Prefer not to say",
        ("prefer not to say", "i do not wish to answer", "decline"),
    ),
)


# Ordered the way the answers page groups them, which is roughly the
# order a form asks. The label is the key: it is what the bank stores
# and what the extension's rules resolve to, so it must not drift.
QUESTIONS: tuple[Question, ...] = (
    # --- You ---
    Question("First name"),
    Question("Last name"),
    Question("Full name"),
    Question("Email"),
    Question("Phone"),
    Question("Pronouns", kind=CHOICE, options=PRONOUNS),
    # --- Address ---
    Question("Location"),
    Question("Address"),
    Question("City"),
    Question("State"),
    Question("Postcode"),
    Question("Country"),
    # --- Links ---
    Question("LinkedIn"),
    Question("GitHub"),
    Question("Portfolio"),
    # --- Work authorisation ---
    _yes_no(
        "Work authorisation",
        hint="Yes if you may work in the US now, under any authorisation.",
    ),
    _yes_no(
        "Need sponsorship now",
        hint="Yes only if you need sponsorship to start.",
    ),
    _yes_no(
        "Need sponsorship in future",
        hint="Yes if you will need sponsorship later, even if not now.",
    ),
    _yes_no(
        "On a temporary work visa",
        hint="Asked separately from your current authorisation. H-1B, "
        "L-1 and TN are what forms usually mean.",
    ),
    _yes_no("US citizen or permanent resident"),
    _yes_no(
        "Citizen of an embargoed country",
        hint="Cuba, Iran, North Korea, Syria and parts of Ukraine.",
    ),
    _yes_no("Security clearance"),
    # --- Background ---
    _yes_no("Employed by the federal government"),
    _yes_no("Employed by state or local government"),
    _yes_no("Involuntarily discharged from a job"),
    _yes_no("Criminal conviction"),
    _yes_no("Bound by a non-compete"),
    _yes_no("Previously employed by this company"),
    _yes_no("Related to an employee here"),
    _yes_no(
        "Employer relationship with this company",
        hint="Whether your employer resells for, or works with, the "
        "company you are applying to.",
    ),
    _yes_no("Relative owns a competing business"),
    # --- Consent ---
    _yes_no(
        "Consent to keep my application on file",
        hint="Yes lets them consider you for other roles later.",
    ),
    _yes_no(
        "Agree to the terms shown",
        hint="For the consent controls that say I Agree rather than Yes.",
    ),
    # --- Education ---
    Question("University"),
    Question("Degree"),
    Question("Field of study"),
    Question("GPA"),
    Question("Graduation date"),
    Question("Years of experience"),
    _yes_no("Recent graduate"),
    # --- Logistics ---
    Question("Earliest start date"),
    Question("Salary expectation"),
    Question(
        "How did you hear about us",
        kind=CHOICE,
        options=REFERRAL,
    ),
    Question(
        "Preferred contact method",
        kind=CHOICE,
        options=CONTACT_METHOD,
    ),
    _yes_no("At least 18 years old"),
    _yes_no("Role is located in the US"),
    _yes_no("Willing to relocate"),
    _yes_no("Willing to work onsite"),
    _yes_no("Willing to travel"),
    _yes_no("Driving licence"),
    _yes_no("Needs an accommodation"),
    # --- Voluntary disclosures ---
    Question("Gender", kind=CHOICE, options=GENDER),
    Question("Race or ethnicity", kind=CHOICE, options=RACE),
    Question("Veteran status", kind=CHOICE, options=VETERAN),
    Question("Disability status", kind=CHOICE, options=DISABILITY),
    Question("Transgender", kind=CHOICE, options=TRANSGENDER),
    Question("Sexual orientation", kind=CHOICE, options=ORIENTATION),
    # --- Written ---
    Question("Why this company"),
)


_BY_LABEL = {
    question.label: question
    for question in QUESTIONS
}


def question_for(
    label: str,
) -> Question | None:
    """Return the catalogue entry for a label, or None if it is the
    user's own question rather than one ACE ships."""

    return _BY_LABEL.get(
        label
    )


def options_for(
    question: Question,
) -> tuple[Option, ...]:
    """Return the options a question offers, yes/no included."""

    if question.kind == BOOLEAN:
        return BOOLEAN_OPTIONS

    return question.options


def aliases_for(
    label: str,
    value: str,
) -> tuple[str, ...]:
    """Return the other wordings a form might use for a stored value.

    Empty for free text and for anything the catalogue does not know:
    the extension then has only the value itself to go on, which is
    what it had before this existed.
    """

    question = question_for(
        label
    )

    if question is None:
        return ()

    wanted = value.strip().casefold()

    for option in options_for(
        question
    ):
        if option.label.casefold() == wanted:
            return option.aliases

    return ()


def describe(
    label: str,
) -> dict:
    """Render one question's shape for the API."""

    question = question_for(
        label
    )

    if question is None:
        # The user's own question. Free text, because ACE has no idea
        # what it is asking and must not pretend to.
        return {
            "kind": TEXT,
            "options": [],
            "hint": "",
            "known": False,
        }

    return {
        "kind": question.kind,
        "options": [
            option.label
            for option in options_for(
                question
            )
        ],
        "hint": question.hint,
        "known": True,
    }
