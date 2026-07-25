import re
from datetime import datetime

from .models import (
    AssignmentAnalysisRequest,
    AssignmentAnalysisResult,
    AssignmentSourceSummary,
    RubricCriterion,
)


FALLBACK_RUBRIC = [
    ("Problem understanding", "Understanding of the assignment problem", 20),
    ("Critical evaluation", "Evaluation of evidence and alternatives", 25),
    ("Solution design and implementation", "Quality of the proposed and implemented solution", 35),
    ("Testing and presentation", "Testing evidence and clear communication", 20),
]


def generate_fallback_rubric(brief: str) -> list[RubricCriterion]:
    deliverables = _extract_deliverables(brief)
    if deliverables:
        selected = deliverables[:4]
        base_marks, remainder = divmod(100, len(selected))
        return [
            RubricCriterion(
                id=f"rubric-{_slug(name)}",
                criterion=f"{name} quality",
                description=f"Completeness, relevance, and quality of the required {name.casefold()}.",
                marks=base_marks + (1 if index < remainder else 0),
            )
            for index, name in enumerate(selected)
        ]
    return [
        RubricCriterion(
            id=f"rubric-{_slug(name)}",
            criterion=name,
            description=description,
            marks=marks,
        )
        for name, description, marks in FALLBACK_RUBRIC
    ]
REQUIREMENT_TERMS = (
    "must", "required", "should", "include", "submit", "demonstrate", "compare",
    "evaluate", "analyse", "analyze", "implement", "build", "test", "present", "document",
)
DELIVERABLE_PATTERNS = [
    ("GitHub repository", r"\bgithub repository\b|\brepository\b"),
    ("Source code", r"\bsource code\b"),
    ("Web application", r"\bweb application\b|\bwebsite\b"),
    ("Working prototype", r"\bworking prototype\b|\bprototype\b"),
    ("Written report", r"\bwritten report\b|\breport\b"),
    ("Presentation", r"\bpresentation\b|\bslide deck\b|\bslides\b"),
    ("Demonstration", r"\bdemonstration\b|\bdemo\b"),
    ("Video", r"\bvideo\b"),
    ("Poster", r"\bposter\b"),
    ("Documentation", r"\bdocumentation\b|\buser guide\b"),
    ("Reflection", r"\breflection\b"),
    ("Testing report", r"\btesting report\b|\btest report\b"),
]


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return slug[:48] or "criterion"


def _unique(items: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        cleaned = re.sub(r"\s+", " ", item).strip(" \t\r\n-–—:;.")
        key = cleaned.casefold()
        if cleaned and key not in seen:
            seen.add(key)
            result.append(cleaned)
    return result


def _extract_title(brief: str) -> str:
    for line in brief.splitlines():
        cleaned = re.sub(r"^\s*(?:#+|\d+[.)])\s*", "", line).strip()
        if 4 <= len(cleaned) <= 100 and len(cleaned.split()) <= 12 and not cleaned.endswith("."):
            return cleaned
    return "Group Assignment Project"


def _parse_date(text: str) -> str | None:
    labelled = re.search(
        r"(?i)\b(?:deadline|due date|due|submission date)\s*[:\-]?\s*"
        r"(\d{4}-\d{1,2}-\d{1,2}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|"
        r"\d{1,2}\s+[A-Za-z]+\s+\d{4}|[A-Za-z]+\s+\d{1,2},?\s+\d{4})",
        text,
    )
    if not labelled:
        return None
    raw = labelled.group(1)
    for pattern in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y", "%d %B %Y",
                    "%d %b %Y", "%B %d %Y", "%B %d, %Y", "%b %d %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(raw, pattern).date().isoformat()
        except ValueError:
            continue
    return None


def _extract_deliverables(brief: str) -> list[str]:
    return [
        label for label, pattern in DELIVERABLE_PATTERNS
        if re.search(pattern, brief, flags=re.IGNORECASE)
    ]


def _extract_requirements(brief: str) -> list[str]:
    candidates: list[str] = []
    for line in brief.splitlines():
        cleaned = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", line).strip()
        if not cleaned:
            continue
        is_list = bool(re.match(r"^\s*(?:[-*•]|\d+[.)])\s+", line))
        has_term = any(re.search(rf"\b{term}\b", cleaned, re.I) for term in REQUIREMENT_TERMS)
        if (is_list or has_term) and 12 <= len(cleaned) <= 260:
            candidates.append(cleaned)
    if len(candidates) < 5:
        for sentence in re.split(r"(?<=[.!?])\s+", re.sub(r"\s+", " ", brief)):
            if 12 <= len(sentence) <= 260 and any(
                re.search(rf"\b{term}\b", sentence, re.I) for term in REQUIREMENT_TERMS
            ):
                candidates.append(sentence)
    return _unique(candidates)[:15]


def _extract_rubric(text: str) -> list[RubricCriterion]:
    criteria: list[RubricCriterion] = []
    seen_ids: dict[str, int] = {}
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    pattern = re.compile(
        r"^(?P<name>.+?)\s*(?:[-–—:|]|\()\s*(?:weight\s*:\s*)?"
        r"(?P<marks>\d{1,3})\s*(?:marks?|%|/\s*100)?\)?\s*$",
        re.I,
    )
    slash_pattern = re.compile(r"^(?P<name>.+?)\s*/\s*(?P<marks>\d{1,3})\s*$")
    for index, line in enumerate(lines):
        match = pattern.match(line) or slash_pattern.match(line)
        if not match:
            continue
        name = match.group("name").strip(" -–—:|()")
        if not name or name.casefold() == "weight":
            continue
        base = _slug(name)
        seen_ids[base] = seen_ids.get(base, 0) + 1
        criterion_id = f"rubric-{base}" + (
            f"-{seen_ids[base]}" if seen_ids[base] > 1 else ""
        )
        description = ""
        if index + 1 < len(lines) and not (pattern.match(lines[index + 1]) or slash_pattern.match(lines[index + 1])):
            description = lines[index + 1][:300]
        criteria.append(
            RubricCriterion(
                id=criterion_id,
                criterion=name,
                description=description,
                marks=int(match.group("marks")),
            )
        )
    return criteria


def analyze_assignment(payload: AssignmentAnalysisRequest) -> AssignmentAnalysisResult:
    warnings: list[str] = []
    deadline = payload.deadline or _parse_date(payload.assignment_brief)
    if deadline is None:
        warnings.append(
            "Deadline not mentioned by the user or in the assignment document."
        )

    deliverables = _extract_deliverables(payload.assignment_brief)
    if not deliverables:
        deliverables = ["Final assignment submission"]
        warnings.append("No clear deliverables were found, so a fallback deliverable was added.")

    requirements = _extract_requirements(payload.assignment_brief)
    if len(requirements) < 5:
        warnings.append("Some requirements may need manual review.")
    if not requirements:
        requirements = ["Review the assignment brief and confirm the required final submission."]

    rubric = _extract_rubric(payload.rubric_text)
    if not rubric:
        rubric = [
            RubricCriterion(id=f"rubric-{_slug(name)}", criterion=name, description=description, marks=marks)
            for name, description, marks in FALLBACK_RUBRIC
        ]
        warnings.append("No clear rubric criteria were recognised, so a fallback rubric was generated.")
    total = sum(item.marks for item in rubric)
    if total != 100:
        warnings.append(f"Rubric marks total {total} rather than 100.")

    return AssignmentAnalysisResult(
        suggested_title=payload.title or _extract_title(payload.assignment_brief),
        suggested_deadline=deadline,
        deliverables=deliverables,
        requirements=requirements,
        rubric=rubric,
        extraction_warnings=warnings,
        analysis_notes=[],
        source_summary=AssignmentSourceSummary(
            assignment_character_count=len(payload.assignment_brief),
            rubric_character_count=len(payload.rubric_text),
        ),
    )
