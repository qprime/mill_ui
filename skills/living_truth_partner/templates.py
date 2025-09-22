# name: templates.py
# path: skills/living_truth_partner/templates.py
# role: Surface Living Truth Partner writing presets and skeleton templates
# deps: dataclasses, pathlib, typing
# inputs: Config
# outputs: template metadata and markdown skeleton bodies

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List

from skills.living_truth_partner.config import Config

__all__ = [
    "TemplateSpec",
    "TonePreset",
    "QuickCheck",
    "list_templates",
    "load_template_body",
    "tone_presets",
    "quick_checks",
]


@dataclass(frozen=True)
class TemplateSpec:
    id: str
    title: str
    description: str
    filename: str | None = None


@dataclass(frozen=True)
class TonePreset:
    id: str
    label: str
    instructions: str


@dataclass(frozen=True)
class QuickCheck:
    id: str
    label: str
    intent: str
    constraints: List[str]
    section_hint: str | None = None


_DEFAULT_TEMPLATES: Dict[str, TemplateSpec] = {
    "whitepaper": TemplateSpec(
        id="whitepaper",
        title="Technical Whitepaper",
        description="Abstract, problem framing, approach, architecture, results, and call to action.",
        filename="whitepaper.md",
    ),
    "business_plan": TemplateSpec(
        id="business_plan",
        title="Business Plan",
        description="Executive summary with market, product, go-to-market, operations, and financial outlook.",
        filename="business_plan.md",
    ),
    "sop": TemplateSpec(
        id="sop",
        title="SOP / Policy",
        description="Purpose, scope, roles, procedure, safety/compliance, and revision control.",
        filename="sop.md",
    ),
    "proposal": TemplateSpec(
        id="proposal",
        title="Proposal / SOW",
        description="Problem statement, deliverables, timeline, success criteria, and commercial terms.",
        filename="proposal.md",
    ),
    "prd": TemplateSpec(
        id="prd",
        title="Product Requirements (PRD/RFC)",
        description="Context, goals, user stories, requirements, UX notes, risks, and open questions.",
        filename="prd.md",
    ),
    "difficult_email": TemplateSpec(
        id="difficult_email",
        title="Difficult Email",
        description="Objective, facts, impact, ask, next steps, and tone guardrails.",
        filename="difficult_email.md",
    ),
    "press_release": TemplateSpec(
        id="press_release",
        title="Press Release",
        description="Headline, subhead, lead paragraph, supporting quotes, boilerplate, and CTA.",
        filename="press_release.md",
    ),
    "investor_update": TemplateSpec(
        id="investor_update",
        title="Investor Update",
        description="Highlights, lowlights, pipeline, metrics, hiring, asks, and upcoming milestones.",
        filename="investor_update.md",
    ),
}

_DEFAULT_TEMPLATE_BODIES: Dict[str, str] = {
    "whitepaper": """# {title}\n\n## Abstract\n- One paragraph summary of the problem, approach, and result.\n\n## Problem\n- Define the audience and pain.\n- Quantify the urgency or cost of the status quo.\n\n## Approach\n- Outline the solution concept and guiding principles.\n- Highlight what makes this approach different.\n\n## Architecture\n- Diagram or describe the major components.\n- Explain data flow, interfaces, and dependencies.\n\n## Results & Evidence\n- Provide metrics, benchmarks, or case study data.\n- Include testimonials or third-party validation.\n\n## Call to Action\n- State the next step for the reader.\n- Provide contact information or links.\n""",
    "business_plan": """# {title}\n\n## Executive Summary\n- Three crisp sentences: what we do, for whom, why now.\n\n## Market & Customer\n- Total addressable market and segments.\n- Ideal customer profile and pain points.\n\n## Product & Offering\n- Core value proposition and differentiators.\n- Roadmap highlights.\n\n## Go-To-Market\n- Distribution channels and pricing strategy.\n- Marketing motions and sales play.\n\n## Operations\n- Team structure and key hires.\n- Systems, partners, or suppliers.\n\n## Financial Plan\n- Revenue model, unit economics, and forecast checkpoints.\n- Funding requirement and use of proceeds.\n\n## Risks & Mitigations\n- Top risks with countermeasures.\n\n## Appendices\n- Supporting data, research, or models.\n""",
    "sop": """# {title}\n\n## Purpose\n- Why this procedure exists.\n\n## Scope\n- When the SOP applies and when it does not.\n\n## Roles & Responsibilities\n- Who owns execution and approvals.\n\n## Prerequisites\n- Tools, data, or conditions required before starting.\n\n## Procedure\n1. Step-by-step instructions.\n2. Include decision points and checks.\n\n## Safety & Compliance\n- Regulatory requirements, record keeping, and audits.\n\n## Troubleshooting\n- Common issues and resolutions.\n\n## Revision History\n- Version, date, author, and summary of changes.\n""",
    "proposal": """# {title}\n\n## Executive Summary\n- Problem to solve and desired outcome.\n\n## Deliverables\n- Bullet list of tangible outputs.\n- Acceptance criteria for each item.\n\n## Scope & Approach\n- What is included and excluded.\n- Methodology, tools, and collaborators.\n\n## Timeline & Milestones\n- Phases with target dates.\n\n## Team & Responsibilities\n- Primary contacts and supporting roles.\n\n## Commercials\n- Pricing, payment terms, and assumptions.\n\n## Risks & Dependencies\n- Known blockers and mitigation plan.\n\n## Acceptance\n- Signature or next-step CTA.\n""",
    "prd": """# {title}\n\n## Context\n- Background, customer insights, and linked docs.\n\n## Goals & Non-Goals\n- Desired outcomes and explicit exclusions.\n\n## User Stories\n- Persona, need, and success measure.\n\n## Requirements\n- Functional specs, edge cases, and telemetry.\n\n## UX Notes\n- Wireframe references, accessibility, and content strategy.\n\n## Technical Considerations\n- Architecture notes, dependencies, and performance targets.\n\n## Risks & Open Questions\n- What could fail and the investigation plan.\n\n## Launch & Rollout\n- Phases, timing, and comms plan.\n""",
    "difficult_email": """# {title}\n\n## Objective\n- State the intent of the note.\n\n## Facts\n- Bullet list of observable facts (no interpretation).\n\n## Impact\n- How those facts affect people, work, or outcomes.\n\n## Ask\n- The specific action or decision requested.\n\n## Tone Guide\n- Keep language direct, respectful, and calm.\n\n## Next Steps\n- Deadlines, meetings, or follow-ups.\n""",
    "press_release": """# {title}\n\n## Headline\n- Single sentence capturing the news.\n\n## Subhead\n- Supporting line with key metric or proof.\n\n## Lead Paragraph\n- Who, what, when, where, why.\n\n## Supporting Details\n- Product capabilities, customer impact, or partnerships.\n\n## Quotes\n- Executive quote.\n- Customer or partner quote.\n\n## Boilerplate\n- Company description and contact info.\n\n## Call to Action\n- Link to learn more or talk to the team.\n""",
    "investor_update": """# {title}\n\n## Highlights\n- Wins worth celebrating.\n\n## Lowlights\n- Misses, root cause, and fix.
\n## Pipeline & Customers\n- Deals in flight, expansion, churn watchlist.\n\n## Product & Operations\n- Shipping status, incidents, experiments.\n\n## Metrics Snapshot\n- Growth, retention, cash, runway, hiring.\n\n## Hiring & Team\n- Open roles, key hires, culture notes.\n\n## Asks\n- Help needed (introductions, talent, decisions).\n\n## Next Milestones\n- What is coming up before the next update.\n""",
}

_TONE_PRESETS: List[TonePreset] = [
    TonePreset("formal", "Formal", "Adopt a confident, authoritative tone while remaining respectful."),
    TonePreset("direct_warm", "Direct but Warm", "Be candid about facts while keeping empathy and partnership in the wording."),
    TonePreset("regulatory", "Regulatory", "Use precise, policy-aligned phrasing that references controls or compliance obligations."),
    TonePreset("executive", "Executive", "Lead with outcomes, keep paragraphs short, and surface metrics or commitments."),
]

_QUICK_CHECKS: List[QuickCheck] = [
    QuickCheck(
        id="tighten_exec_summary",
        label="Tighten executive summary",
        intent="Rewrite the executive summary to be concise (≤120 words) and outcome-focused.",
        constraints=["Highlight top three insights.", "Keep paragraphs to 2 sentences."],
        section_hint="executive-summary",
    ),
    QuickCheck(
        id="add_acceptance_criteria",
        label="Add acceptance criteria",
        intent="Add bullet acceptance criteria that make success measurable.",
        constraints=["Use action-oriented bullet points."],
        section_hint=None,
    ),
    QuickCheck(
        id="bulletize_metrics",
        label="Bulletize key metrics",
        intent="Convert metrics into a quick-scan bullet list with trend context.",
        constraints=["Include absolute value and delta.", "Limit to 4 bullets."],
        section_hint=None,
    ),
    QuickCheck(
        id="clarify_next_steps",
        label="Clarify next steps",
        intent="Add a Next Steps section with owners, actions, and due dates.",
        constraints=["Use bold names for owners.", "List at least three actions."],
        section_hint="next-steps",
    ),
]


def _skeletons_dir(config: Config) -> Path:
    return config.templates / "skeletons"


def _load_from_disk(directory: Path, spec: TemplateSpec) -> str | None:
    if not directory.exists():
        return None
    if not spec.filename:
        return None
    candidate = directory / spec.filename
    if candidate.exists():
        return candidate.read_text(encoding="utf-8")
    return None


def list_templates(config: Config) -> List[TemplateSpec]:
    # Merge defaults (ensuring deterministic order) with any additional skeleton files.
    directory = _skeletons_dir(config)
    templates = list(_DEFAULT_TEMPLATES.values())
    if directory.exists():
        for path in directory.glob("*.md"):
            slug = path.stem
            if slug in _DEFAULT_TEMPLATES:
                continue
            templates.append(
                TemplateSpec(
                    id=slug,
                    title=slug.replace("_", " ").title(),
                    description="Custom template",
                    filename=path.name,
                )
            )
    return templates


def load_template_body(config: Config, template_id: str, *, title: str | None = None) -> str:
    spec = _DEFAULT_TEMPLATES.get(template_id)
    directory = _skeletons_dir(config)
    body: str | None = None
    if spec:
        body = _load_from_disk(directory, spec)
        if body is None:
            body = _DEFAULT_TEMPLATE_BODIES.get(template_id)
    elif directory.exists():
        candidate = directory / f"{template_id}.md"
        if candidate.exists():
            body = candidate.read_text(encoding="utf-8")
    if body is None:
        raise KeyError(template_id)
    if title:
        body = body.replace("{title}", title)
    return body


def tone_presets() -> List[TonePreset]:
    return list(_TONE_PRESETS)


def quick_checks() -> List[QuickCheck]:
    return list(_QUICK_CHECKS)
