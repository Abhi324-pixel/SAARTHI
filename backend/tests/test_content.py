from app.content import Content, get_content


def test_content_integrity():
    c = Content()
    assert c.validate() == []


def test_graph_is_acyclic_and_ordered():
    c = get_content()
    order = c.topo_order()
    pos = {cid: i for i, cid in enumerate(order)}
    for cid in c.concepts:
        for p in c.prereqs(cid):
            assert pos[p] < pos[cid]


def test_topo_order_of_subset_respects_prereqs():
    c = get_content()
    sub = {"sql_outer_join", "sql_inner_join", "sql_null"}
    order = c.topo_order(sub)
    assert order.index("sql_inner_join") < order.index("sql_outer_join")


def test_ancestors():
    c = get_content()
    anc = c.ancestors("sql_outer_join")
    assert {"sql_inner_join", "sql_null", "sql_select", "sql_relational_model"} <= anc


def test_every_concept_in_the_role_has_questions_and_notes():
    c = get_content()
    for cid in c.role("backend_developer")["requirements"]:
        assert c.items_by_concept[cid]
        assert c.note(cid)["summary"]


def test_deep_sql_concepts_have_tasks_and_misconceptions():
    c = get_content()
    for cid in ["sql_filtering", "sql_null", "sql_aggregates", "sql_group_by", "sql_having",
                "sql_inner_join", "sql_outer_join", "sql_multi_table"]:
        assert c.tasks_by_concept.get(cid), cid
        assert c.misc_by_concept.get(cid), cid


def test_public_item_hides_answer_and_misconception_ids():
    c = get_content()
    it = c.items["q_sql_outer_join_1"]
    pub = c.public_item(it, "seed")
    assert "correct" not in str(pub) and "misconception" not in str(pub)
    assert len(pub["options"]) == 4


def test_shuffle_is_deterministic_and_covers_all_options():
    c = get_content()
    it = c.items["q_sql_outer_join_1"]
    a = c.shuffled_options(it, "s1")
    b = c.shuffled_options(it, "s1")
    assert a == b
    assert sorted(o["text"] for o in a) == sorted(o["text"] for o in it["options"])
