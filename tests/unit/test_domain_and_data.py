from data_generation.generator import generate_platform
from graph.lineage import LineageGraph
from retrieval.kb import KnowledgeBase


def test_generate_platform_has_failures_and_lineage():
    p = generate_platform(seed=1, n_incidents=20)
    assert len(p.tables) >= 10
    assert len(p.incidents) == 20
    assert any(t.status.value == "failed" for d in p.dags for t in d.tasks)
    assert p.scenarios


def test_lineage_impact():
    g = LineageGraph()
    g.add_node("a", "source")
    g.add_node("b", "dbt_model")
    g.add_node("c", "ml_model")
    from domain.models import LineageEdge

    g.add_edge(LineageEdge(edge_id="1", source_id="a", target_id="b", source_type="source", target_type="dbt_model"))
    g.add_edge(LineageEdge(edge_id="2", source_id="b", target_id="c", source_type="dbt_model", target_type="ml_model"))
    impact = g.impact("a")
    assert "ml_model" in impact


def test_knowledge_base_search():
    kb = KnowledgeBase("knowledge-base")
    kb.index()
    hits = kb.search("late arriving claims duplicates")
    assert hits
