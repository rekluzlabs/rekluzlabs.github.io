"""Conservative exact-ID extraction from Google's Markdown documentation."""
import re
import datetime as dt
from dataclasses import dataclass

ID = re.compile(r"(?<![\w/-])(gemini-[a-z0-9][a-z0-9.-]{1,126})(?![\w.-])")
HEADING = re.compile(r"^##\s+(.+)$", re.M)


def sections(markdown):
    matches = list(HEADING.finditer(markdown))
    return [(m.group(1), markdown[m.end():matches[i + 1].start() if i + 1 < len(matches) else len(markdown)])
            for i, m in enumerate(matches)]


def roster(markdown):
    # Model code is an explicit Google field; incidental model mentions do not qualify.
    return set(re.findall(r"\*Model code\*\s*\*\*(gemini-[a-z0-9][a-z0-9.-]{1,126})\*\*", markdown))


@dataclass(frozen=True)
class Pricing:
    tier: str
    caveat: str
    confident: bool


def prices(markdown):
    result = {}
    for title, body in sections(markdown):
        ids = set(re.findall(r'id="(gemini-[a-z0-9][a-z0-9.-]{1,126})"', title))
        if not ids:
            ids = set(re.findall(r"`(gemini-[a-z0-9][a-z0-9.-]{1,126})`", body[:600]))
        if not ids or len(ids) != 1:
            continue
        model = next(iter(ids))
        standard = re.search(r'(?:\{% tab title="Standard" %\}|^### Standard\s*$)([\s\S]*?)(?=\{% /tab %\}|^### |\Z)', body, re.M)
        block = standard.group(1) if standard else ""
        def free_row(name):
            return bool(re.search(r"\* " + name + r" price[^\n]*\n\s*\* Free of charge", block, re.I))
        def unavailable_row(name):
            return bool(re.search(r"\* " + name + r" price[^\n]*\n\s*\* Not available", block, re.I))
        free = free_row("Input") and free_row("Output")
        paid_note = bool(re.search(r"(?:not available on the Free tier|no free tier|paid tier only)", body, re.I))
        paid = paid_note or unavailable_row("Input") and unavailable_row("Output")
        restricted = bool(re.search(r"(?:existing|prior|previous) (?:active )?(?:API )?(?:users|use)|limited to.*(?:users|accounts)", body, re.I))
        conflict = free and paid or (free and bool(re.search(r"Every token.*billed", body, re.I)))
        tier = "RESTRICTED_FREE" if free and restricted else "FREE" if free else "PAID_ONLY" if paid else "UNKNOWN"
        caveat = "Standard API free input/output; account eligibility and charges are not guaranteed." if free else "Google documents no Standard API free tier." if paid else "Standard API pricing is not explicit."
        if restricted:
            caveat += " Google documents an access restriction."
        if conflict:
            caveat += " Conflicting billing statements require review."
        value = Pricing(tier, caveat, bool((free or paid) and not conflict))
        if model in result and result[model] != value:
            result[model] = Pricing("UNKNOWN", "Conflicting exact-model sections require review.", False)
        else:
            result[model] = value
    return result


def capabilities(model_markdown):
    # The roster card alone is insufficient evidence for API support or request schemas.
    return {model: {"purpose": "UNKNOWN", "release": "UNKNOWN", "capabilities": []}
            for model in roster(model_markdown)}


def detail_capabilities(markdown, model):
    """Only assert fields explicit on an exact model's own Google specification."""
    if not re.search(r"(?:Model code\s*\n\s*\*\s*|^##\s+)`?" + re.escape(model) + r"`?", markdown, re.M):
        return {}
    result = {}
    match = re.search(r"\*\*Inputs\*\*\s*([^\n]+)\s+\*\*Output\*\*\s*([^\n]+)", markdown)
    if match:
        inputs, outputs = match.group(1), match.group(2)
        if re.search(r"\bText\b", inputs):
            result["TEXT_INPUT"] = "SUPPORTED"
        if re.search(r"\bImage\b", inputs):
            result["IMAGE_INPUT"] = "SUPPORTED"
        if re.search(r"\bText\b", outputs):
            result["TEXT_OUTPUT"] = "SUPPORTED"
    return result


def lifecycle(markdown):
    # Deprecation tables say earliest possible dates. Never promote them to confirmed shutdown.
    records = {}
    rows = re.findall(r"^\s*\* `(gemini-[a-z0-9][a-z0-9.-]{1,126})`\n\s*\* ([^\n]*)\n\s*\* ([^\n]*)\n\s*\* ?([^\n]*)", markdown, re.M)
    for model, _, date, replacement in rows:
        if model in records:
            records[model] = {"review": "duplicate lifecycle row"}
            continue
        if "No shutdown date announced" in date:
            records[model] = {"facts": ["NO_SHUTDOWN_ANNOUNCED"]}
        else:
            records[model] = {"review": f"Review earliest possible shutdown: {date}; replacement: {replacement}"}
    return records


def lifecycle_notices(markdown):
    found = []
    for title, body in sections(markdown):
        if not re.search(r"\d{4}", title):
            continue
        for line in re.split(r"\n\s*\*\s+", body):
            if re.search(r"deprecat|retir|shutdown|redirec|correct|replac", line, re.I):
                for model in sorted(set(ID.findall(line))):
                    found.append(f"{title}: {model}: inspect official announcement/correction and exact deadline")
    return found[:100]


API_TERMS = re.compile(r"generateContent|Interactions API|models\.list|model.list|authentication|API key|v1beta|structured output|response schema|image input|error response|API endpoint|API version", re.I)
BREAK_TERMS = re.compile(r"breaking|must migrate|no longer|sunset|retire|shut down|removed|deprecated|legacy|deadline", re.I)
DEADLINE = re.compile(r"\b(?:by|on|effective|starting)\s+([A-Z][a-z]+ \d{1,2}, \d{4})", re.I)


def api_notices(markdown):
    notices = []
    for title, body in sections(markdown):
        dated = re.match(r"([A-Z][a-z]+ \d{1,2}, \d{4})", title)
        if not dated:
            continue
        try:
            day = dt.datetime.strptime(dated.group(1), "%B %d, %Y").date()
        except ValueError:
            continue
        age = (dt.datetime.now(dt.timezone.utc).date() - day).days
        for line in re.split(r"\n\s*\*\s+", body):
            short = " ".join(line.split())[:500]
            if API_TERMS.search(short) and BREAK_TERMS.search(short):
                deadline = DEADLINE.search(short)
                due = None
                if deadline:
                    try:
                        due = dt.datetime.strptime(deadline.group(1), "%B %d, %Y").date()
                    except ValueError:
                        pass
                until = (due - dt.datetime.now(dt.timezone.utc).date()).days if due else None
                if age < 0 or (age > 60 and (until is None or until < 0 or until > 30)):
                    continue
                notice = {"date": title.strip(), "summary": short, "source": "https://aistudio.google.com/docs/changelog"}
                if due:
                    notice["deadline"] = due.isoformat()
                notices.append(notice)
    return notices[:100]


def migration_risks(markdown):
    introduction = markdown[:1200]
    if re.search(r"generateContent", introduction, re.I) and re.search(r"Interactions API", introduction, re.I) and re.search(r"legacy|deprecat|sunset|no longer|must migrate", introduction, re.I):
        return [{"date": "undated migration guide", "summary": "Google documents migration from GenerateContent to the Interactions API; inspect continued availability and deadlines.", "source": "https://aistudio.google.com/docs/migrate-to-interactions"}]
    return []
