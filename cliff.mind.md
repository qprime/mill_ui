# cliff.mind.md

## CliffMind System Ground Truth

This document defines the core architecture, roles, and boundaries for all CliffMind agents and subsystems.  
Humans are always present as supervisors, auditors, and collaborators, but must interact **only** via standard system interfaces (chat, web UI, CLI, etc.).  
No human or agent is to bypass these pathways for data or code changes—system integrity and auditability are paramount.

**This file is the collaborative “contract” between CliffMind agents and human supervisors. It must be kept up to date as the ground truth.**

- All data, actions, and adaptations are traceable and explainable to the supervising human.
- The human may initiate or approve updates to this file, but changes should also be proposed by agents as the system evolves.
- Ideally, a hybrid process (LLM + deterministic scanning) periodically audits the codebase and directory structure to suggest updates to this document, maintaining alignment between system state and ground truth.

---

## Folders and Their Roles

- **memories/**
    - *Definition:* Atomic memory units; store all events, artifacts, data, tasks, ideas, insights, and more.
    - *Usage:* Every input or output is stored as a memory. Memories are atomic, linkable, and timestamped.
    - *Note:* All data must be discoverable via memories, never hidden in external databases.

- **cortex/**
    - *Definition:* Executive function; context assembly, reasoning, and LLM orchestration.
    - *Usage:* Handles query decomposition, active reasoning, planning, and prompt assembly.
    - *Note:* All agent decisions must be reasoned through cortex, referencing relevant memories and skills.

- **continuum/**
    - *Definition:* Self-reflection and adaptive change; includes code analysis, meta-cognition, self-healing.
    - *Usage:* Executes periodic scans, triggers introspection events, manages code graphing and system adaptation.
    - *Note:* All changes to architecture or capabilities should be tracked and summarized in continuum.

- **skills/**
    - *Definition:* Modular internal abilities; code, logic, or workflows that accomplish tasks.
    - *Usage:* Skills may be invoked by cortex, interfaces, or services. Skills should be documented and self-describing.
    - *Note:* All actions and tools are implemented as skills for composability and audit.

- **interfaces/**
    - *Definition:* Points of interaction with external actors or devices (web UI, API, CLI, device protocols).
    - *Usage:* All input/output flows through interfaces. Interfaces may call skills, cortex, or memories as needed.
    - *Note:* Interfaces must not duplicate skill logic.

- **services/**
    - *Definition:* Always-on system helpers: daemons, background workers, schedulers, watchdogs.
    - *Usage:* Maintain availability, handle scheduling, monitor for events, manage system uptime.
    - *Note:* Services are not user-facing but must record key events to memories and/or vitals.

- **vitals/**
    - *Definition:* System vital signs; all diagnostics, status, health checks, and test results.
    - *Usage:* Track live and historical system health, including unit tests, integration tests, hardware diagnostics, and resource logs.
    - *Note:* All health and status signals should be written here for ongoing monitoring.

---

## Operating Principles

- Humans and agents co-supervise CliffMind.  
    All major actions, code changes, or architecture updates are transparent and traceable.
- The human collaborates with agents to review, update, and approve changes to ground truth and system configuration.
- All new data, directives, and code from humans must enter through standard interfaces (chat, web UI, CLI, etc.), not by direct file edits, unless under supervised development or system bootstrapping.
- Skills and interfaces are to be modular and composable; all code must be discoverable and callable by agents.
- Self-reflection, self-healing, and change tracking must be logged through continuum.
- Vitals are to be continuously updated and monitored; all failures or anomalies must be surfaced here.
- No module is permitted to break boundaries or override ground truth defined here without explicit documentation in continuum.

---

## Ground Truth Update Policy

- This file is the canonical reference for all agents and human supervisors.
- It should be reviewed and updated collaboratively whenever the codebase, folder structure, or system metaphor evolves.
- Agents are encouraged to propose updates via chat or system notifications when discrepancies or changes are detected.
- All updates require human review and confirmation before becoming active ground truth.

---

**END cliff.mind.md**
