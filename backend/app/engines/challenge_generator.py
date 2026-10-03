"""Dynamic Challenge Generator: creates tailored practical build challenges for Vakh.

Connects concepts, learner mastery levels, and specific misconceptions to practical project challenges
that are submitted and reviewed via Vakh.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import CONTENT_DIR
from ..content import get_content
from ..llm import gateway
from ..models import Learner
from ..models_ext.G01 import VakhChallenge
from . import misconception

log = logging.getLogger("saarthi.challenges")

# Curated practical challenge blueprints tailored to misconceptions and mastery gaps
CHALLENGE_BLUEPRINTS: dict[str, dict[str, Any]] = {
    "sql_outer_join": {
        "title": "Customer Retention Audit & Outer Join Bug Fix",
        "objective": "Query an e-commerce database to identify inactive accounts without counting NULL rows as active orders.",
        "difficulty": "intermediate",
        "requirements": [
            "Write a query using LEFT JOIN between customers and orders.",
            "Identify all customers with zero completed orders.",
            "Verify that COUNT(orders.id) is used instead of COUNT(*) so NULL matched rows are not falsely counted as 1.",
            "Document your findings in the project reflection."
        ],
        "starter_code": "SELECT c.id, c.name, COUNT(o.id) AS total_orders\nFROM customers c\nLEFT JOIN orders o ON o.customer_id = c.id\nGROUP BY c.id, c.name\nHAVING COUNT(o.id) = 0;",
        "expected_output": "Rows showing customers with zero orders, correctly excluding false counts.",
        "evaluation_criteria": [
            {"criterion": "Correct use of LEFT JOIN", "weight": 0.3},
            {"criterion": "Avoidance of COUNT(*) over NULL rows", "weight": 0.4},
            {"criterion": "Grouped output correctness", "weight": 0.3}
        ],
        "vakh_form_id": "vakh_form_sql_outer_join"
    },
    "sql_inner_join": {
        "title": "Order Fulfillment & Shipping Dispatch Pipeline",
        "objective": "Join customers, orders, and products to generate shipping manifests for confirmed transactions.",
        "difficulty": "intermediate",
        "requirements": [
            "Perform an INNER JOIN between orders and order_items.",
            "Join products to retrieve item descriptions and prices.",
            "Calculate total parcel value and ensure unmatched or unconfirmed orders are filtered."
        ],
        "starter_code": "SELECT o.id, c.name, p.name AS product, oi.qty, (oi.qty * p.price) AS subtotal\nFROM orders o\nINNER JOIN customers c ON o.customer_id = c.id\nINNER JOIN order_items oi ON oi.order_id = o.id\nINNER JOIN products p ON oi.product_id = p.id;",
        "expected_output": "Itemized dispatch list for fulfilled orders.",
        "evaluation_criteria": [
            {"criterion": "Multi-table join correctness", "weight": 0.4},
            {"criterion": "Accurate arithmetic and aliases", "weight": 0.3},
            {"criterion": "Appropriate join conditions", "weight": 0.3}
        ],
        "vakh_form_id": "vakh_form_sql_inner_join"
    },
    "sql_group_by": {
        "title": "Revenue by Product Category",
        "objective": "Aggregate the shop's order lines by product category and keep only the categories that earn enough, using HAVING.",
        "difficulty": "beginner",
        "requirements": [
            "Join order_items to products and group the result by products.category.",
            "Compute the revenue per category as SUM(order_items.qty * products.price) and the number of units as SUM(order_items.qty).",
            "Keep only categories whose revenue is above a threshold you choose, using HAVING (not WHERE), and say why you chose it."
        ],
        "starter_code": "SELECT p.category, SUM(oi.qty * p.price) AS revenue, SUM(oi.qty) AS units\nFROM order_items oi\nJOIN products p ON p.id = oi.product_id\nGROUP BY p.category\nHAVING SUM(oi.qty * p.price) > 500;",
        "expected_output": "One row per category that clears your threshold, with its revenue and units.",
        "evaluation_criteria": [
            {"criterion": "Correct distinction between WHERE and HAVING", "weight": 0.5},
            {"criterion": "Appropriate aggregate functions", "weight": 0.5}
        ],
        "vakh_form_id": "vakh_form_sql_group_by"
    },
    "fastapi_basics": {
        "title": "Microservice Health & Customer Profile API",
        "objective": "Construct a production-ready FastAPI endpoint with Pydantic validation and database connection.",
        "difficulty": "intermediate",
        "requirements": [
            "Define a Pydantic schema for CustomerRequest and CustomerResponse.",
            "Implement GET /customers/{id} with 404 error handling.",
            "Add automated test coverage using TestClient."
        ],
        "starter_code": "from fastapi import FastAPI, HTTPException\nfrom pydantic import BaseModel\n\napp = FastAPI()\n\nclass Customer(BaseModel):\n    id: int\n    name: str\n    email: str\n",
        "expected_output": "Runnable FastAPI server responding with JSON schemas.",
        "evaluation_criteria": [
            {"criterion": "Pydantic validation schemas", "weight": 0.4},
            {"criterion": "Proper HTTP status codes", "weight": 0.3},
            {"criterion": "Endpoint structure", "weight": 0.3}
        ],
        "vakh_form_id": "vakh_form_fastapi_basics"
    }
}


_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"}, "objective": {"type": "string"}, "difficulty": {"type": "string"},
        "requirements": {"type": "array", "items": {"type": "string"}},
        "starter_code": {"type": "string"}, "expected_output": {"type": "string"},
        "evaluation_criteria": {"type": "array", "items": {"type": "object", "properties": {"criterion": {"type": "string"}, "weight": {"type": "number"}}, "required": ["criterion", "weight"]}},
    },
    "required": ["title", "objective", "requirements", "expected_output", "evaluation_criteria"],
}

_SYSTEM = (
    "You design one small, practical build challenge that a learner completes on their own and submits for human review.\n"
    "Rules: it must be doable in 1 to 3 hours with free tools; every requirement must be concrete and checkable by a reviewer; "
    "do not mention any website, brand or link; no placeholder text. For SQL concepts use ONLY the practice database described below "
    "(table and column names must match exactly). Evaluation criteria weights must add up to 1."
)


def _shop_schema() -> str:
    try:
        return (CONTENT_DIR / "shop.sql").read_text(encoding="utf-8").split("INSERT", 1)[0][:2500]
    except OSError:
        return ""


def _generate(concept_id: str) -> Optional[dict[str, Any]]:
    """A concept-specific challenge written by the model, or None if the model is unavailable or its answer is not usable."""
    c = get_content()
    conc = c.concepts[concept_id]
    note = c.note(concept_id)
    prereqs = ", ".join(c.concepts[p].name for p in conc.prereqs if p in c.concepts) or "none"
    prompt = (f"Concept: {conc.name} (domain: {conc.domain}).\nWhat it covers: {note.get('summary', '')}\n"
              f"Key points: {'; '.join(note.get('key_points', []))}\nCommon pitfall: {note.get('pitfall', '')}\nPrerequisites the learner already has: {prereqs}\n")
    if conc.domain == "sql":
        prompt += f"\nPractice database (use only these tables):\n{_shop_schema()}\n"
    prompt += "\nWrite the challenge. difficulty must be one of beginner, intermediate, advanced."
    try:
        raw = gateway.generate_json("challenge", _SYSTEM, prompt, _SCHEMA, fake=lambda: {}, cache=True, max_tokens=1400, temperature=0.4)
    except Exception as e:
        log.warning("challenge generation failed for %s: %s", concept_id, type(e).__name__)
        return None
    return _validate(raw, conc.name)


def _validate(raw: dict[str, Any], concept_name: str) -> Optional[dict[str, Any]]:
    """Keep the model's challenge only if it has the right shape; clean it, never repair it with invented content."""
    try:
        title = " ".join(str(raw["title"]).split())[:90]
        objective = " ".join(str(raw["objective"]).split())[:300]
        reqs = [" ".join(str(r).split())[:240] for r in raw["requirements"] if str(r).strip()][:6]
        expected = " ".join(str(raw["expected_output"]).split())[:300]
        crit = [{"criterion": " ".join(str(x["criterion"]).split())[:120], "weight": float(x["weight"])} for x in raw["evaluation_criteria"] if str(x.get("criterion", "")).strip()][:6]
    except (KeyError, TypeError, ValueError):
        return None
    total = sum(max(0.0, x["weight"]) for x in crit)
    if not title or not objective or len(reqs) < 3 or not expected or len(crit) < 2 or total <= 0:
        return None
    for x in crit:
        x["weight"] = round(max(0.0, x["weight"]) / total, 2)
    text = " ".join([title, objective, expected, *reqs])
    if re.search(r"https?://|www\.", text, re.I):
        return None
    diff = str(raw.get("difficulty", "")).lower()
    return {"title": title, "objective": objective, "difficulty": diff if diff in ("beginner", "intermediate", "advanced") else "intermediate",
            "requirements": reqs, "starter_code": str(raw.get("starter_code") or "")[:1500], "expected_output": expected, "evaluation_criteria": crit}


def _fallback(concept_id: str) -> dict[str, Any]:
    """Only used when the model is unavailable. It says plainly what to do and makes no claim about the topic's content."""
    c = get_content()
    conc = c.concepts.get(concept_id)
    name = conc.name if conc else concept_id.replace("_", " ").title()
    return {
        "title": f"Build something small with {name}",
        "objective": f"Apply {name} in one small piece of work of your own and explain what you did.",
        "difficulty": "intermediate" if conc and len(conc.prereqs) > 1 else "beginner",
        "requirements": [
            f"Choose a small problem where {name} is the main tool, and write down the problem in two sentences.",
            "Solve it, and test it on at least two normal cases and one tricky case.",
            "Write a short reflection: what went wrong first, and how you fixed it.",
        ],
        "starter_code": "",
        "expected_output": "A working solution, your test cases and your reflection.",
        "evaluation_criteria": [{"criterion": "The solution works on the tests", "weight": 0.5}, {"criterion": "Tests include a tricky case", "weight": 0.3}, {"criterion": "Clear reflection", "weight": 0.2}],
    }


def _view(ch: VakhChallenge) -> dict[str, Any]:
    return {"id": ch.id, "concept_id": ch.concept_id, "title": ch.title, "objective": ch.objective, "difficulty": ch.difficulty,
            "requirements": list(ch.requirements or []), "starter_code": ch.starter_code, "expected_output": ch.expected_output,
            "evaluation_criteria": ch.evaluation_criteria, "vakh_form_id": ch.vakh_form_id}


def get_or_create_challenge(
    db: Session,
    concept_id: str,
    learner: Optional[Learner] = None
) -> dict[str, Any]:
    """The practical challenge for a concept: curated if we have one, otherwise written by the model, otherwise a plain fallback.

    The stored challenge is the same for everyone. What is personal (a focus on this learner's own misconception) is added to the
    returned copy only and never saved."""
    existing = db.scalars(select(VakhChallenge).where(VakhChallenge.concept_id == concept_id)).first()
    curated = CHALLENGE_BLUEPRINTS.get(concept_id)
    legacy_placeholder = existing is not None and existing.title.startswith("Hands-on Implementation Challenge:")     # the old generic template
    stale_curated = existing is not None and curated is not None and (existing.title != curated["title"] or existing.starter_code != curated.get("starter_code", ""))
    if existing is None or legacy_placeholder or stale_curated:
        bp = curated or (_generate(concept_id) if concept_id in get_content().concepts else None) or _fallback(concept_id)
        if existing is None:
            existing = VakhChallenge(concept_id=concept_id, title="", objective="", difficulty="beginner", requirements=[], starter_code="", expected_output="",
                                     evaluation_criteria=[], vakh_form_id="")
            db.add(existing)
        existing.title, existing.objective, existing.difficulty = bp["title"], bp["objective"], bp["difficulty"]
        existing.requirements, existing.starter_code = list(bp["requirements"]), bp.get("starter_code", "")
        existing.expected_output, existing.evaluation_criteria = bp["expected_output"], bp["evaluation_criteria"]
        existing.vakh_form_id = bp.get("vakh_form_id") or f"vakh_form_{concept_id}"
        db.commit()
    out = _view(existing)
    if learner is not None:
        mine = [m for m in misconception.describe(db, learner.id) if m["concept_id"] == concept_id and m["status"] in ("candidate", "confirmed", "correcting")]
        if mine:
            out["requirements"] = out["requirements"] + [f"Focus area for you: {mine[0]['name']}. Explicitly show in your solution how you avoid this mistake."]
            out["personal_focus"] = mine[0]["name"]
    return out
