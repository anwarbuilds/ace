"""Reviewed factual screening reuse. No attestation or inferred answer reuse."""
import re


def normalized(question: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", question.lower()).strip()


def screening_key(question: str) -> str | None:
    q = normalized(question)
    q = re.sub(r"\bu s\b|\bunited states\b", "us", q)
    q = re.sub(r"\brequired$", "", q).strip()
    if re.search(r"\b(not|never|without|certify|attest|agree|consent|signature|privacy|declare|confirm|acknowledge|disability|gender|race|veteran|criminal|salary|government|military)\b", q):
        return None
    topic = scope = ""
    if re.fullmatch(r"are you (?:a )?us citizen (?:or )?(?:a )?(?:lawful )?permanent resident(?: (?:or )?(?:a )?refugee (?:or )?(?:a )?(?:person granted asylum|asylee))?", q):
        topic = "us-status:citizen,resident"
        if "refugee" in q:
            topic += ",refugee"
        if "asylum" in q or "asylee" in q:
            topic += ",asylee"
    elif re.fullmatch(r"(?:will you|do you) now or in the future (?:require|need) (?:visa sponsorship|sponsorship for employment visa status|sponsorship)(?: (?:to work|to continue working) in the us)?", q):
        topic = "visa-sponsorship:now-or-future"
        scope = "country:us" if re.search(r"\bus\b", q) else "tenant:*"
    else:
        patterns = [
            (r"have you (?:ever |previously )?(?:performed|done|undertaken) temporary work for (.+)", "temporary-work:ever"),
            (r"have you (?:ever |previously )?interviewed for (?:a position|a role|employment) (?:at|with) (.+)", "interview:ever"),
            (r"have you or do you currently work for or with (.+)", "work-relationship:past-or-present"),
            (r"have you (?:ever |previously )?worked (?:for|at) (.+)", "worked:ever"),
        ]
        for pattern, category in patterns:
            match = re.fullmatch(pattern, q)
            if match:
                topic, scope = category, "employer:" + match[1]
                if re.search(r"\bpreviously\b", q):
                    topic = topic.replace(":ever", ":previous")
                break
        if re.fullmatch(r"do you have any post employment obligations to any current or former employer i e non compete non solicitation etc that may prohibit or restrict your employment for a position", q) or re.fullmatch(r"are you subject to any post employment obligations to (?:a|any) current or former employer that may (?:prevent|prohibit) or restrict your employment including non compete (?:or|and) non solicitation agreements", q):
            topic, scope = "employment-obligations:current-or-former:any:restrict-employment", ""
        if re.fullmatch(r"(?:has a search agency|has an employment agency|has a recruitment agency) submitted your application for consideration within the last 12 months", q):
            topic, scope = "agency-submission:last-12-months", "tenant:*"
    if not topic:
        return None
    scope = re.sub(r"\bor any of (?:its|their|the) subsidiaries\b", "including subsidiaries", scope)
    if re.match(r"^employer:(?:us|this company|our company|this employer|our organization|our organisation)(?: |$)", scope):
        scope = "tenant:*:" + scope[9:]
    key = "fact:v1:" + topic + (":" + scope if scope else "")
    return key if len(key) <= 180 else None


def valid_screening_memory(question: str, concept: str, answer: str, answer_type: str, source_host: str) -> bool:
    expected = screening_key(question)
    if not expected or answer_type not in {"choice", "yesno"} or normalized(answer) not in {"yes", "no"}:
        return False
    if "tenant:*" not in expected:
        return concept == expected
    prefix, suffix = expected.split("*", 1)
    tenant = concept.removeprefix(prefix)
    if suffix:
        if not tenant.endswith(suffix):
            return False
        tenant = tenant[:-len(suffix)]
    # Tenant identity travels in the concept, not in application/job records.
    # Only a concrete source host and optional tenant/site path are accepted.
    if not re.fullmatch(r"[a-z0-9.-]+\.[a-z]{2,}", source_host):
        return False
    return (concept.startswith(prefix) and tenant.split("/", 1)[0] == source_host
            and bool(re.fullmatch(r"[a-z0-9.-]+(?:/[a-z0-9_-]+){0,3}", tenant)))
