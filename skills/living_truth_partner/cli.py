# name: cli.py
# path: skills/living_truth_partner/cli.py
# role: Command-line interface for Living Truth Partner skill
# deps: argparse, json, sys, pathlib, typing, skills.living_truth_partner modules
# inputs: argv
# outputs: exit code

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable, List

from skills.living_truth_partner.config import Config
from skills.living_truth_partner.distill import Distill
from skills.living_truth_partner.export_doc import ExportDoc
from skills.living_truth_partner.guardrails import analyze
from skills.living_truth_partner.action_items import append as append_action, load as load_actions, set_state
from skills.living_truth_partner.persona_builder import add_persona
from skills.living_truth_partner.project_store import ProjectStore
from skills.living_truth_partner.revision import apply as apply_revision, prepare
from skills.living_truth_partner.search_index import SearchIndex
from skills.living_truth_partner.section_patch import SectionPatch
from skills.living_truth_partner.target_patch import TargetPatch
from skills.living_truth_partner.voice_append import VoiceAppend

__all__ = ["api"]


def _csv(values: Iterable[str]) -> List[str]:
    out: List[str] = []
    for value in values:
        for part in value.split(","):
            item = part.strip()
            if item:
                out.append(item)
    return out


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ltp")
    sub = parser.add_subparsers(dest="command", required=True)
    new_cmd = sub.add_parser("new")
    new_cmd.add_argument("title")
    new_cmd.add_argument("--slug", default="")
    new_cmd.add_argument("--owners", nargs="*", default=[])
    new_cmd.add_argument("--tags", nargs="*", default=[])
    open_cmd = sub.add_parser("open")
    open_cmd.add_argument("slug")
    voice_cmd = sub.add_parser("voice")
    voice_cmd.add_argument("slug")
    voice_cmd.add_argument("--file")
    voice_cmd.add_argument("--record-seconds", type=int, default=None)
    voice_cmd.add_argument("--auto-distill", dest="auto_distill", action="store_true")
    voice_cmd.add_argument("--no-auto-distill", dest="auto_distill", action="store_false")
    voice_cmd.set_defaults(auto_distill=True)
    distill_cmd = sub.add_parser("distill")
    distill_cmd.add_argument("slug")
    distill_cmd.add_argument("--max-notes", type=int, default=5)
    patch_cmd = sub.add_parser("patch")
    patch_cmd.add_argument("slug")
    patch_cmd.add_argument("--intent", required=True)
    choice = patch_cmd.add_mutually_exclusive_group(required=True)
    choice.add_argument("--section")
    choice.add_argument("--target")
    patch_cmd.add_argument("--constraint", action="append", default=[])
    export_cmd = sub.add_parser("export")
    export_cmd.add_argument("slug")
    export_cmd.add_argument("kind")
    find_cmd = sub.add_parser("find")
    find_cmd.add_argument("query")
    find_cmd.add_argument("--limit", type=int, default=10)
    sections_cmd = sub.add_parser("sections")
    sections_cmd.add_argument("slug")
    prompts_cmd = sub.add_parser("prompts")
    prompts_cmd.add_argument("slug")
    actions_cmd = sub.add_parser("actions")
    actions_cmd.add_argument("slug")
    actions_cmd.add_argument("--set", type=int)
    actions_cmd.add_argument("--done", choices=["true", "false"])
    actions_cmd.add_argument("--add")
    revise_cmd = sub.add_parser("revise")
    revise_cmd.add_argument("slug")
    revise_cmd.add_argument("--sections", nargs="*", default=[])
    revise_cmd.add_argument("--apply", action="store_true")
    persona_cmd = sub.add_parser("persona")
    persona_cmd.add_argument("slug")
    persona_cmd.add_argument("--name", required=True)
    persona_cmd.add_argument("--role", default="")
    persona_cmd.add_argument("--goals", default="")
    persona_cmd.add_argument("--pains", default="")
    persona_cmd.add_argument("--section", default="market")
    return parser


def _cmd_new(config: Config, args: argparse.Namespace) -> int:
    store = ProjectStore.create(config, args.slug or args.title, args.title, _csv(args.owners), _csv(args.tags))
    payload = {"slug": store.slug, "doc": str(store.doc_path)}
    print(json.dumps(payload, indent=2))
    return 0


def _cmd_open(config: Config, args: argparse.Namespace) -> int:
    store = ProjectStore.open(config, args.slug)
    payload = {"slug": store.slug, "doc": str(store.doc_path)}
    print(json.dumps(payload, indent=2))
    return 0


def _cmd_voice(config: Config, args: argparse.Namespace) -> int:
    store = ProjectStore.open(config, args.slug)
    audio_path = Path(args.file) if args.file else None
    result = VoiceAppend.run(store, config, audio_path, args.record_seconds)
    payload = {
        "transcript": result.transcript,
        "notes_path": str(result.notes_path),
        "words": result.words,
        "segments": result.segments
    }
    if args.auto_distill:
        distill_result = Distill.run(store, config)
        payload["distill"] = {
            "summary_path": str(distill_result.summary_path),
            "prompts_path": str(distill_result.prompts_path),
            "links_path": str(distill_result.links_path),
            "action_items_path": str(distill_result.action_items_path)
        }
    print(json.dumps(payload, indent=2))
    return 0


def _cmd_distill(config: Config, args: argparse.Namespace) -> int:
    store = ProjectStore.open(config, args.slug)
    result = Distill.run(store, config, args.max_notes)
    payload = {
        "summary_path": str(result.summary_path),
        "links_path": str(result.links_path),
        "prompts_path": str(result.prompts_path),
        "action_items_path": str(result.action_items_path)
    }
    print(json.dumps(payload, indent=2))
    return 0


def _cmd_patch(config: Config, args: argparse.Namespace) -> int:
    store = ProjectStore.open(config, args.slug)
    constraints = args.constraint
    if args.section:
        result = SectionPatch.run(store, config, args.section, args.intent, constraints)
    else:
        result = TargetPatch.run(store, config, args.target, args.intent, constraints)
    payload = {
        "doc": str(result.doc_path),
        "patch": str(result.patch_path) if result.patch_path else None,
        "changed": result.changed
    }
    print(json.dumps(payload, indent=2))
    return 0


def _cmd_export(config: Config, args: argparse.Namespace) -> int:
    store = ProjectStore.open(config, args.slug)
    result = ExportDoc.run(store, config, args.kind)
    payload = {"output": str(result.output_path), "command": result.command}
    print(json.dumps(payload, indent=2))
    return 0


def _cmd_find(config: Config, args: argparse.Namespace) -> int:
    index = SearchIndex.build(config)
    hits = index.search(args.query, args.limit)
    payload = [{"doc": hit.doc, "section": hit.section, "title": hit.title, "snippet": hit.snippet} for hit in hits]
    print(json.dumps(payload, indent=2))
    return 0


def _cmd_sections(config: Config, args: argparse.Namespace) -> int:
    store = ProjectStore.open(config, args.slug)
    insights = analyze(store)
    payload = []
    for insight in insights:
        payload.append({
            "id": insight.section_id,
            "title": insight.title,
            "word_count": insight.word_count,
            "snippet": insight.snippet,
            "issues": insight.issues,
            "quick_actions": insight.quick_actions
        })
    print(json.dumps(payload, indent=2))
    return 0


def _cmd_prompts(config: Config, args: argparse.Namespace) -> int:
    store = ProjectStore.open(config, args.slug)
    data = json.loads(store.prompts_path.read_text(encoding="utf-8"))
    print(json.dumps(data, indent=2))
    return 0


def _cmd_actions(config: Config, args: argparse.Namespace) -> int:
    store = ProjectStore.open(config, args.slug)
    if args.add:
        items = append_action(store, args.add)
    elif args.set is not None and args.done in {"true", "false"}:
        items = set_state(store, args.set, args.done == "true")
    else:
        items = load_actions(store)
    print(json.dumps({"action_items": items}, indent=2))
    return 0


def _serialize_suggestions(suggestions: List[object]) -> List[dict]:
    out = []
    for s in suggestions:
        out.append({
            "section_id": s.section_id,
            "title": s.title,
            "intent": s.intent,
            "constraints": s.constraints,
            "reason": s.reason
        })
    return out


def _apply_suggestions(store: ProjectStore, config: Config, suggestions: List[object], apply_flag: bool) -> List[dict]:
    if not apply_flag or not suggestions:
        return []
    results = []
    applied = apply_revision(store, config, suggestions, True)
    for result in applied:
        results.append({
            "section": result.doc_path.name,
            "changed": result.changed,
            "patch": str(result.patch_path) if result.patch_path else None
        })
    return results


def _cmd_revise(config: Config, args: argparse.Namespace) -> int:
    store = ProjectStore.open(config, args.slug)
    suggestions = prepare(store, args.sections)
    payload = {
        "suggestions": _serialize_suggestions(suggestions),
        "results": _apply_suggestions(store, config, suggestions, args.apply)
    }
    print(json.dumps(payload, indent=2))
    return 0


def _cmd_persona(config: Config, args: argparse.Namespace) -> int:
    store = ProjectStore.open(config, args.slug)
    ok = add_persona(store, {
        "name": args.name,
        "role": args.role,
        "goals": args.goals,
        "pains": args.pains,
        "section_id": args.section
    })
    payload = {"ok": ok}
    print(json.dumps(payload, indent=2))
    return 0


def api(argv: List[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    config = Config.load()
    if args.command == "new":
        return _cmd_new(config, args)
    if args.command == "open":
        return _cmd_open(config, args)
    if args.command == "voice":
        return _cmd_voice(config, args)
    if args.command == "distill":
        return _cmd_distill(config, args)
    if args.command == "patch":
        return _cmd_patch(config, args)
    if args.command == "export":
        return _cmd_export(config, args)
    if args.command == "find":
        return _cmd_find(config, args)
    if args.command == "sections":
        return _cmd_sections(config, args)
    if args.command == "prompts":
        return _cmd_prompts(config, args)
    if args.command == "actions":
        return _cmd_actions(config, args)
    if args.command == "revise":
        return _cmd_revise(config, args)
    if args.command == "persona":
        return _cmd_persona(config, args)
    return 1


def main() -> None:
    sys.exit(api())


if __name__ == "__main__":
    main()
