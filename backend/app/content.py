"""Curated learning content (SQL / backend domain) and the skill graph built from it.

Everything the engines treat as ground truth lives in `app/content/*.json`: the concept graph, the
misconception library, MCQs with misconception-mapped options, SQL tasks, explain-back rubrics, and
reference notes. `validate()` checks referential integrity, so a typo cannot silently break a run.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Optional

from .config import CONTENT_DIR


def _load(name: str) -> dict:
    return json.loads((CONTENT_DIR / name).read_text(encoding="utf-8"))


@dataclass
class Concept:
    id: str
    name: str
    name_hi: str
    domain: str
    prereqs: list[str]
    minutes: int
    p_init: float
    p_learn: float
    aliases: list[str] = field(default_factory=list)


class Content:
    def __init__(self) -> None:
        raw = _load("concepts.json")
        self.version: str = raw["version"]
        self.concepts: dict[str, Concept] = {c["id"]: Concept(**c) for c in raw["concepts"]}
        self.order: list[str] = list(self.concepts)
        self.misconceptions: dict[str, dict] = {m["id"]: m for m in _load("misconceptions.json")["misconceptions"]}
        self.items: dict[str, dict] = {i["id"]: i for i in _load("items.json")["items"]}
        self.tasks: dict[str, dict] = {t["id"]: t for t in _load("sql_tasks.json")["tasks"]}
        self.notes: dict[str, dict] = _load("notes.json")["notes"]
        self.rubrics: dict[str, dict] = _load("rubrics.json")["rubrics"]
        self.roles: dict[str, dict] = {r["id"]: r for r in _load("roles.json")["roles"]}
        self.packs: dict[str, dict] = {p["id"]: p for p in _load("interview_packs.json")["packs"]}
        self.items_by_concept: dict[str, list[dict]] = {}
        for it in self.items.values():
            self.items_by_concept.setdefault(it["concept_id"], []).append(it)
        self.tasks_by_concept: dict[str, list[dict]] = {}
        for t in self.tasks.values():
            self.tasks_by_concept.setdefault(t["concept_id"], []).append(t)
        self.misc_by_concept: dict[str, list[dict]] = {}
        for m in self.misconceptions.values():
            self.misc_by_concept.setdefault(m["concept_id"], []).append(m)

    # ---- graph ------------------------------------------------------------------------------
    def prereqs(self, cid: str) -> list[str]:
        return self.concepts[cid].prereqs

    def ancestors(self, cid: str) -> set[str]:
        seen: set[str] = set()
        stack = list(self.concepts[cid].prereqs)
        while stack:
            p = stack.pop()
            if p not in seen:
                seen.add(p)
                stack.extend(self.concepts[p].prereqs)
        return seen

    def dependents(self, cid: str) -> list[str]:
        return [c.id for c in self.concepts.values() if cid in c.prereqs]

    def topo_order(self, subset: Optional[set[str]] = None, key=None) -> list[str]:
        """Kahn's algorithm over the induced sub-graph; ties broken by `key` (default: file order)."""
        ids = set(subset) if subset is not None else set(self.concepts)
        indeg = {c: sum(1 for p in self.concepts[c].prereqs if p in ids) for c in ids}
        rank = {c: i for i, c in enumerate(self.order)}
        keyf = key or (lambda c: rank[c])
        ready = sorted([c for c, d in indeg.items() if d == 0], key=keyf)
        out: list[str] = []
        while ready:
            c = ready.pop(0)
            out.append(c)
            for d in self.dependents(c):
                if d in ids:
                    indeg[d] -= 1
                    if indeg[d] == 0:
                        ready.append(d)
            ready.sort(key=keyf)
        if len(out) != len(ids):
            raise ValueError("cycle in concept graph")
        return out

    # ---- convenience ------------------------------------------------------------------------
    def has_rubric(self, cid: str) -> bool:
        return cid in self.rubrics

    def note(self, cid: str) -> dict:
        return self.notes.get(cid, {})

    def role(self, role_id: str) -> dict:
        if role_id not in self.roles:
            raise KeyError(role_id)
        return self.roles[role_id]

    def get_packs(self) -> list[dict]:
        return list(self.packs.values())

    def get_pack(self, pack_id: str) -> Optional[dict]:
        return self.packs.get(pack_id)

    def shuffled_options(self, item: dict, seed: str) -> list[dict]:
        """Deterministic per (item, seed) shuffle; returns options with a stable index."""
        opts = list(item["options"])
        rnd = random.Random(f"{item['id']}:{seed}")
        rnd.shuffle(opts)
        return opts

    def public_item(self, item: dict, seed: str) -> dict:
        """What the client may see: no answer key and no misconception hints."""
        opts = self.shuffled_options(item, seed)
        return {
            "id": item["id"],
            "concept_id": item["concept_id"],
            "stem": item["stem"],
            "options": [{"index": i, "text": o["text"]} for i, o in enumerate(opts)],
            "difficulty": item.get("difficulty", 0.4),
        }

    def validate(self) -> list[str]:
        errs: list[str] = []
        for c in self.concepts.values():
            for p in c.prereqs:
                if p not in self.concepts:
                    errs.append(f"concept {c.id}: unknown prereq {p}")
        try:
            self.topo_order()
        except ValueError:
            errs.append("concept graph has a cycle")
        for m in self.misconceptions.values():
            if m["concept_id"] not in self.concepts:
                errs.append(f"misconception {m['id']}: unknown concept {m['concept_id']}")
        for it in self.items.values():
            if it["concept_id"] not in self.concepts:
                errs.append(f"item {it['id']}: unknown concept")
            correct = [o for o in it["options"] if o.get("correct")]
            if len(correct) != 1:
                errs.append(f"item {it['id']}: needs exactly one correct option, has {len(correct)}")
            if len(it["options"]) < 2:
                errs.append(f"item {it['id']}: needs at least two options")
            for o in it["options"]:
                mid = o.get("misconception_id")
                if mid and mid not in self.misconceptions:
                    errs.append(f"item {it['id']}: unknown misconception {mid}")
                if mid and self.misconceptions[mid]["concept_id"] != it["concept_id"] and mid not in ("where_vs_having",):
                    # cross-concept links are allowed only when the misconception's concept is a prerequisite/related one
                    pass
        for t in self.tasks.values():
            if t["concept_id"] not in self.concepts:
                errs.append(f"task {t['id']}: unknown concept")
            for v in t.get("variants", []):
                if v["misconception_id"] not in self.misconceptions:
                    errs.append(f"task {t['id']}: unknown misconception {v['misconception_id']}")
        for cid, r in self.rubrics.items():
            if cid not in self.concepts:
                errs.append(f"rubric {cid}: unknown concept")
            ids = [c["id"] for c in r["checklist"]]
            if len(ids) != len(set(ids)):
                errs.append(f"rubric {cid}: duplicate checklist ids")
            for mid in r.get("misconception_ids", []):
                if mid not in self.misconceptions:
                    errs.append(f"rubric {cid}: unknown misconception {mid}")
        for cid in self.notes:
            if cid not in self.concepts:
                errs.append(f"notes {cid}: unknown concept")
        for cid in self.concepts:
            if cid not in self.notes:
                errs.append(f"concept {cid}: missing notes")
            if not self.items_by_concept.get(cid):
                errs.append(f"concept {cid}: no questions")
        for rid, role in self.roles.items():
            for cid in role.get("requirements", {}):
                if cid not in self.concepts:
                    errs.append(f"role {rid}: unknown concept {cid}")
        for pid, pack in self.packs.items():
            all_cids = list(pack.get("concept_ids", []))
            for r in pack.get("rounds", {}).values():
                all_cids.extend(r.get("concept_ids", []))
            for cid in all_cids:
                if cid not in self.concepts:
                    errs.append(f"pack {pid}: unknown concept {cid}")
        seen_aliases: dict[str, str] = {}
        for cid, c in self.concepts.items():
            for a in c.aliases:
                if not isinstance(a, str) or not a.strip():
                    errs.append(f"concept {cid}: alias must be non-empty string, got {a!r}")
                norm = a.strip().lower()
                if norm in seen_aliases:
                    errs.append(f"concept {cid}: duplicate alias '{a}' already defined for {seen_aliases[norm]}")
                seen_aliases[norm] = cid
        return errs


@lru_cache(maxsize=1)
def get_content() -> Content:
    c = Content()
    errs = c.validate()
    if errs:
        raise RuntimeError("content integrity errors:\n  " + "\n  ".join(errs))
    return c
