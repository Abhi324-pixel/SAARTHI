from datetime import timedelta

import pytest

from app import db as dbm
from app.engines import mastery as m
from app.models import Learner, new_id


@pytest.fixture()
def session():
    dbm.configure("sqlite://")
    dbm.init_db()
    s = dbm.SessionLocal()
    yield s
    s.close()


def make_learner(s, **kw):
    lr = Learner(id=new_id("t_"), name="T", **kw)
    s.add(lr)
    s.flush()
    return lr


def test_correct_answers_raise_p_and_wrong_lowers():
    p = 0.2
    up = m.bkt_update(p, 1.0, "question", 0.2)
    down = m.bkt_update(p, 0.0, "question", 0.2)
    assert up > p > down


def test_work_product_is_stronger_evidence_than_a_guessable_question():
    assert m.bkt_update(0.2, 1.0, "work_product", 0.15) > m.bkt_update(0.2, 1.0, "question", 0.15)


def test_levels():
    assert m.level_of(0.1, 0, []) == "not_assessed"
    assert m.level_of(0.2, 2, ["question"]) == "unknown"
    assert m.level_of(0.6, 2, ["question"]) == "developing"
    assert m.level_of(0.85, 3, ["question"]) == "proficient"


def test_mastered_requires_application_evidence_and_two_source_types():
    assert m.level_of(0.97, 5, ["question"]) == "proficient"
    assert m.level_of(0.97, 5, ["question", "mentor"]) == "proficient"
    assert m.level_of(0.97, 5, ["question", "work_product"]) == "mastered"


def test_feedback_and_self_report_never_move_mastery(session):
    lr = make_learner(session)
    before = m.apply_evidence(session, lr, "sql_inner_join", "feedback", correct=True)
    assert not before["moved_mastery"] and before["p_after"] == before["p_before"]
    r = m.apply_evidence(session, lr, "sql_inner_join", "self_report", score=1.0)
    assert not r["moved_mastery"]
    cs = m.ensure_states(session, lr)["sql_inner_join"]
    assert cs.n_evidence == 0


def test_stated_confidence_never_raises_mastery(session):
    lr = make_learner(session)
    a = m.apply_evidence(session, lr, "sql_select", "question", correct=True, stated_confidence=1)
    lr2 = make_learner(session)
    b = m.apply_evidence(session, lr2, "sql_select", "question", correct=True, stated_confidence=5)
    assert a["p_after"] == b["p_after"]


def test_overconfident_flag_after_two_confident_misses(session):
    lr = make_learner(session)
    for _ in range(2):
        m.apply_evidence(session, lr, "sql_null", "question", correct=False, stated_confidence=5)
    v = m.concept_views(session, lr)["sql_null"]
    assert "overconfident" in v["flags"]


def test_low_confidence_llm_grade_is_recorded_but_does_not_move_mastery(session):
    lr = make_learner(session)
    r = m.apply_evidence(session, lr, "sql_outer_join", "explain_back", score=1.0, grader_confidence=0.2)
    assert not r["moved_mastery"] and r["low_grader_confidence"]
    assert m.ensure_states(session, lr)["sql_outer_join"].n_evidence == 0


def test_forgetting_decays_toward_prior_and_marks_review(session):
    lr = make_learner(session)
    for _ in range(3):
        m.apply_evidence(session, lr, "sql_select", "work_product", correct=True)
    v0 = m.concept_views(session, lr)["sql_select"]
    assert v0["level"] in ("proficient", "mastered", "developing")
    lr.clock_offset_days = 30
    v1 = m.concept_views(session, lr)["sql_select"]
    assert v1["p"] < v0["p"]
    assert v1["due_for_review"]


def test_blocked_flag_when_an_assessed_prerequisite_is_weak(session):
    lr = make_learner(session)
    m.apply_evidence(session, lr, "sql_inner_join", "question", correct=False)
    v = m.concept_views(session, lr)
    assert "blocked" in v["sql_outer_join"]["flags"]
    assert "sql_inner_join" in v["sql_outer_join"]["blocked_by"]


def test_unassessed_prerequisite_does_not_block(session):
    lr = make_learner(session)
    v = m.concept_views(session, lr)
    assert "blocked" not in v["sql_outer_join"]["flags"]


def test_next_review_interval_grows():
    from datetime import datetime
    t = datetime(2026, 1, 1)
    assert m.next_review_at(t, 1) == t + timedelta(days=1)
    assert m.next_review_at(t, 3) == t + timedelta(days=7)
    assert m.next_review_at(t, 99) == t + timedelta(days=30)


def test_evidence_is_append_only_with_provenance(session):
    from sqlalchemy import select
    from app.models import EvidenceEvent
    lr = make_learner(session)
    m.apply_evidence(session, lr, "sql_select", "question", correct=True, item_id="q1", grader="mcq")
    m.apply_evidence(session, lr, "sql_select", "feedback", correct=True)
    evs = list(session.scalars(select(EvidenceEvent).where(EvidenceEvent.learner_id == lr.id)))
    assert [e.source_type for e in evs] == ["question", "feedback"]
    assert evs[0].changed_mastery and not evs[1].changed_mastery
