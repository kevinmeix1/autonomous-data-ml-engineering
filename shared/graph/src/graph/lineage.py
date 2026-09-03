from __future__ import annotations

from typing import Any

import networkx as nx

from domain.models import LineageEdge


class LineageGraph:
    def __init__(self) -> None:
        self.g = nx.DiGraph()

    def add_node(self, node_id: str, node_type: str, **attrs: Any) -> None:
        self.g.add_node(node_id, node_type=node_type, **attrs)

    def add_edge(self, edge: LineageEdge) -> None:
        self.g.add_edge(
            edge.source_id,
            edge.target_id,
            edge_id=edge.edge_id,
            transformation=edge.transformation,
            confidence=edge.confidence,
            source_type=edge.source_type,
            target_type=edge.target_type,
        )

    def upstream(self, node_id: str, depth: int | None = None) -> list[dict[str, Any]]:
        if node_id not in self.g:
            return []
        nodes = nx.ancestors(self.g, node_id)
        if depth is not None:
            lengths = nx.single_source_shortest_path_length(self.g.reverse(copy=False), node_id, cutoff=depth)
            nodes = {n for n in nodes if n in lengths}
        return [{"id": n, **self.g.nodes[n]} for n in nodes]

    def downstream(self, node_id: str, depth: int | None = None) -> list[dict[str, Any]]:
        if node_id not in self.g:
            return []
        nodes = nx.descendants(self.g, node_id)
        if depth is not None:
            lengths = nx.single_source_shortest_path_length(self.g, node_id, cutoff=depth)
            nodes = {n for n in nodes if n in lengths}
        return [{"id": n, **self.g.nodes[n]} for n in nodes]

    def impact(self, node_id: str) -> dict[str, list[dict[str, Any]]]:
        down = self.downstream(node_id)
        grouped: dict[str, list[dict[str, Any]]] = {}
        for node in down:
            grouped.setdefault(node.get("node_type", "unknown"), []).append(node)
        return grouped

    def path(self, source: str, target: str) -> list[str]:
        try:
            return nx.shortest_path(self.g, source, target)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return []

    def to_cytoscape(self) -> dict[str, Any]:
        elements = []
        for node_id, data in self.g.nodes(data=True):
            elements.append({"data": {"id": node_id, "label": node_id, **data}})
        for u, v, data in self.g.edges(data=True):
            elements.append({"data": {"id": f"{u}->{v}", "source": u, "target": v, **data}})
        return {"elements": elements}
