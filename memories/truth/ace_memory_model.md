# Cliff / ACE Memory Model - Working Reference

## Purpose
This document captures the core mental model behind the memory system. It is not implementation detail or training material for others yet. It exists as a ground truth reference so that I (and any AI working with me) can stay aligned on what a brief, an artifact, a decision, and a narrative are supposed to mean.

As the system expands, this document can be updated to keep the definitions consistent.

---

## The Four Primitives

### 1. Brief = the Verb
- A brief is any expression of intent or input of context.
- It is the active voice of the system: the "do something," "note this," or "ask that."
- Examples:
  - "Draft a new SOP for machine shutdown."
  - "Check CPU and RAM usage on eqbeelink."
  - "File Acme invoice #1234."
  - "We should think about adding a vine border feature."
- Briefs can be immediate (ops commands, code runs), deferred (tasks, backlog items), or exploratory (ideas, notes).
- Tags classify briefs (task, idea, ops, finance, etc.) so they can be filtered, grouped, and surfaced later.
- Briefs are always ledgered (append-only, hash-chained) so they become part of the permanent story.

### 2. Artifact = the Noun
- An artifact is the durable output associated with a brief.
- It is the "thing" that gets produced or attached to fulfill the intent.
- Examples:
  - A PDF invoice.
  - A code diff.
  - A generated image.
  - A shipping label.
  - A Markdown policy doc.
- Artifacts can be external (uploaded files, scans) or generated (outputs from AI, build systems, or ops commands).
- Artifacts are linked to their originating brief or briefs.
- They should be stored with stable paths or hashes so they can be re-referenced or compared later.

### 3. Decision = the Signature
- A decision marks the approval, rejection, or conclusion of a brief's intent.
- It is the "signature" that closes the loop.
- Examples:
  - "Approve SOP v1."
  - "Invoice paid."
  - "Pull request merged."
  - "Hire Jane Doe."
- Decisions reference both briefs and artifacts.
- They are durable entries in the ledger so every important outcome is auditable.
- They can be human-signed or AI-signed, but they always mark the turning point from open to resolved.

### 4. Narrative = the Story
- A narrative is a thread of linked briefs, artifacts, and decisions.
- It is the storyline that emerges when you look across time.
- Narratives give meaning: they show how intentions, outputs, and approvals connect into a bigger arc.
- Examples:
  - "Accounts Payable, May 2025" (briefs to log invoices, artifacts as PDFs, decisions to mark payment).
  - "Employee Onboarding 2025" (briefs for handbook and onboarding, artifacts as docs and forms, decisions to approve hires).
  - "Vine Border Feature" (briefs for design and implementation, artifacts as diffs and images, decisions to merge).
- Narratives can be generated dynamically by following relationships or curated manually as story bundles.
- Narratives are how you replay the past and understand how decisions were made.

---

## Mental Shortcut
- Brief = Verb
- Artifact = Noun
- Decision = Signature
- Narrative = Story

This four-part model is enough to represent nearly any type of work or information a company needs to track.

---

## How Company "Paperwork" Maps to the Model
- Operating procedures become artifacts (policy docs) with briefs like "draft procedure" and decisions like "approve policy."
- HR data becomes artifacts (employee forms, payroll stubs) with briefs like "add employee" and decisions like "approve hire."
- Invoices, bills, and orders become artifacts (PDFs, spreadsheets) with briefs like "log invoice" and decisions like "mark paid."
- Internal docs, notes, and stories become artifacts (Markdowns, logs) with briefs like "record note" and decisions like "archive note."
- Code and system operations become artifacts (diffs, logs, build outputs) with briefs like "implement feature" and decisions like "merge" or "deploy."

---

## Why This Matters
- Unification: everything flows through the same primitives. No more separate task, doc, and ops systems; it is all briefs, artifacts, decisions, and narratives.
- Durability: the hash-chained ledger ensures nothing disappears or gets tampered with.
- Query power: views are just filters. A task list is briefs tagged task. A finance dashboard is artifacts tagged invoice. HR views surface briefs and artifacts tagged hr.
- Auditability: decisions are explicit, so the record of what was done and why is traceable.
- Extensibility: because it is all typed JSON, the model can evolve. New domains (R&D, marketing, legal) are just more briefs, artifacts, and decisions wrapped into narratives.

---

## Living the Concept
To "live the concept," apply this discipline:
1. When you want something, make a brief.
2. When something is produced, capture it as an artifact linked to the brief.
3. When it is resolved, record a decision.
4. When you want to understand, pull up the narrative.

Over time, this becomes second nature. The primitives fade into the background, and what you see is simply: "our company's story, ledgered."

---

## Open Edges (To Explore Later)
- How do we best curate narratives (automatic versus manual)?
- What tags and types are most useful for surfacing work across domains?
- How do we balance raw capture (everything) versus distilled summaries (signal)?
- How do we teach new users to think in briefs, artifacts, and decisions without overwhelming them?

---

End of document.
