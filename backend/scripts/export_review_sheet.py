"""Exports the curated SQL/backend content as a human-readable review sheet (docs/CONTENT_REVIEW.md).

    python scripts/export_review_sheet.py

The content was AI-drafted and is pending expert review. This sheet lets a SQL-literate reviewer check everything in
about an hour: tick the boxes, fix anything wrong in app/content/*.json, then run `pytest tests/test_sqlcheck.py tests/test_content.py`
- those tests execute every SQL task and every wrong-variant against the real practice database.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.content import get_content  # noqa: E402
from app.engines import sqlcheck  # noqa: E402

c = get_content()
out: list[str] = []
w = out.append

w("# Content review sheet (AI-drafted — needs your review)\n")
w(f"Content version: `{c.version}`. Source files: `backend/app/content/*.json`.\n")
w("**How to review:** read each block, tick the box if it is correct, edit the JSON if not. Priority order: (1) SQL tasks and misconceptions, "
  "(2) questions marked `correct`, (3) rubrics, (4) notes.\n")
w("After editing run: `cd backend && python -m pytest tests/test_sqlcheck.py tests/test_content.py` — every task and every wrong-variant is executed against the practice database.\n")

w("\n## 1. Practice database\n")
w("Tables: customers(8), products(7), orders(12), order_items(16). Deliberate traps: customer 6 has `city = NULL`; order 106 has `status = NULL`; "
  "product 4 has `category = NULL`; customers 7 and 8 have no orders; product 7 was never ordered; customer 1 bought *Pen Set* in two orders.\n")
w("- [ ] Data and traps are suitable\n")

w("\n## 2. SQL tasks (each with the expected result and the wrong variants SAARTHI recognises)\n")
for t in c.tasks.values():
    ref = sqlcheck.run_query(t["reference_query"])
    w(f"\n### {t['id']} — {c.concepts[t['concept_id']].name}\n")
    w(f"**Prompt:** {t['prompt']}\n")
    w(f"```sql\n{t['reference_query']}\n```")
    w(f"Expected: {len(ref.rows)} row(s), columns `{', '.join(ref.columns)}`" + (" (order matters)" if t.get("order_sensitive") else ""))
    w("- [ ] Reference query is correct for the prompt")
    for v in t.get("variants", []):
        m = c.misconceptions[v["misconception_id"]]
        w(f"\n  *Wrong variant → recognised as* **{m['name']}**" + (f" (by error text `{v['error_contains']}`)" if v.get("error_contains") else ""))
        w(f"  ```sql\n  {v['query']}\n  ```\n  Note shown to learner: {v.get('note', '')}")
        w("  - [ ] This variant really reflects that misconception")

w("\n## 3. Misconception library\n")
for m in c.misconceptions.values():
    w(f"\n### {m['name']}  (`{m['id']}` · {c.concepts[m['concept_id']].name})\n")
    w(f"{m['description']}\n")
    w(f"- Typical learner statements: {'; '.join('“' + s + '”' for s in m.get('statements', []))}")
    w(f"- Check question: {m['check_question']}")
    if m["counter_example"].get("query"):
        w(f"- Counter-example: `{m['counter_example']['query']}`")
    w(f"- Explanation: {m['counter_example']['explanation']}")
    w(f"- Fix hint: {m['fix_hint']}")
    w("- [ ] Accurate and clearly worded")

w("\n## 4. Multiple-choice questions (the correct answer is marked ✔; options tied to a misconception are in brackets)\n")
for cid in c.order:
    items = c.items_by_concept.get(cid, [])
    if not items:
        continue
    w(f"\n### {c.concepts[cid].name}\n")
    for it in items:
        w(f"**{it['id']}** — {it['stem'].replace(chr(10), ' ')}")
        for o in it["options"]:
            tag = " ✔" if o.get("correct") else ""
            mi = f" [{o['misconception_id']}]" if o.get("misconception_id") else ""
            w(f"- {o['text']}{tag}{mi}")
        w(f"- Explanation: {it['explain']}")
        w("- [ ] Exactly one correct answer, distractors fair\n")

w("\n## 5. Explain-back rubrics (what the grader looks for)\n")
for cid, r in c.rubrics.items():
    w(f"\n### {c.concepts[cid].name}\n")
    w(f"Question: {r['prompt']}")
    for it in r["checklist"]:
        w(f"- ({it['weight']}) {it['text']}")
    w(f"- Model answer: {r['reference']}")
    w("- [ ] Checklist covers what a good answer needs; weights sensible\n")

w("\n## 6. Teaching notes (used to ground explanations)\n")
for cid in c.order:
    n = c.note(cid)
    w(f"\n### {c.concepts[cid].name}\n{n['summary']}\n")
    if n.get("example"):
        w(f"Example: `{n['example']}`")
    w("- [ ] Accurate\n")

Path(__file__).resolve().parents[2].joinpath("docs").mkdir(exist_ok=True)
dest = Path(__file__).resolve().parents[2] / "docs" / "CONTENT_REVIEW.md"
dest.write_text("\n".join(out), encoding="utf-8")
print("wrote", dest, f"({len(out)} blocks)")
