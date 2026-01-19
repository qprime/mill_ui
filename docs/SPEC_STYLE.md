<!-- spec-style -->
# AI Specification Style Guide

This document defines the style rules for writing AI-oriented technical specifications.

Documents marked with `<!-- spec-style -->` MUST follow these rules.

---

## Purpose

Produce documentation optimized for AI coding agents operating under tight context limits.

---

## Style Rules

1. Write in controlled natural language.
2. Prefer short, declarative sentences.
3. One sentence = one rule or fact.
4. No metaphors, no narrative prose, no marketing language.
5. Avoid adjectives unless they are measurable or defined.
6. Use lists and tables instead of paragraphs whenever possible.

---

## Normative Language

7. Use RFC-style keywords exactly as follows: MUST, MUST NOT, SHOULD, MAY.
8. Any sentence using these keywords is normative.
9. If behavior is not explicitly specified, it is forbidden to assume it.

---

## Structure Rules

10. Organize the document as a contract, not a tutorial.
11. Include these sections unless explicitly told otherwise:
    - Purpose
    - Non-Goals
    - Terminology
    - Canonical Pipeline (if applicable)
    - Data / IR Contracts
    - Invariants
    - Validation Guarantees and Exclusions
    - Extension Points
    - AI Instructions
12. Clearly separate normative content from informational examples.
13. Label examples as NON-NORMATIVE if they are included.
14. Examples MUST NOT introduce behavior not stated in normative text.

---

## Semantic Rules

15. Define all terms before use.
16. Use each defined term consistently. No synonyms.
17. Do not infer intent from examples.
18. Do not invent missing requirements.
19. Do not "improve" the design.
20. Preserve existing behavior exactly unless explicitly instructed otherwise.

---

## AI Behavior Safety

21. If any requirement is ambiguous, stop and request clarification.
22. Do not fill gaps with best practices.
23. Do not optimize unless explicitly required.

---

## Staleness Management

24. Include As-Of Date at the top of the document.
25. Mark sections that may drift from implementation with a staleness warning.
26. Prefer file:line references over inline code snippets when the source is authoritative.

---

## Output Goal

- Produce the shortest document that fully constrains correct implementation.
- Optimize for correctness under context truncation.
- Assume this document will be the ONLY documentation an AI sees.

---

## When Rewriting Existing Text

- Preserve factual meaning.
- Remove redundancy.
- Collapse evidence into references when possible.
- Keep invariants explicit and early.
