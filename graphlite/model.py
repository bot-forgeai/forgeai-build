"""In-memory property graph: nodes with labels/properties, directed typed edges."""


class GraphError(Exception):
    pass


class Graph:
    def __init__(self):
        self.nodes = {}  # node_id -> {"labels": [...], "props": {...}}
        self.edges = {}  # edge_id -> {"from": id, "to": id, "type": str, "props": {...}}
        self._out = {}  # node_id -> [edge_id, ...]
        self._in = {}  # node_id -> [edge_id, ...]

    def add_node(self, node_id, labels=None, props=None):
        if node_id in self.nodes:
            raise GraphError(f"node {node_id!r} already exists")
        self.nodes[node_id] = {"labels": list(labels or []), "props": dict(props or {})}
        self._out[node_id] = []
        self._in[node_id] = []

    def has_node(self, node_id):
        return node_id in self.nodes

    def remove_node(self, node_id):
        if node_id not in self.nodes:
            raise GraphError(f"node {node_id!r} does not exist")
        for edge_id in list(self._out[node_id]) + list(self._in[node_id]):
            self.edges.pop(edge_id, None)
        self._reindex()
        del self.nodes[node_id]
        self._out.pop(node_id, None)
        self._in.pop(node_id, None)

    def add_edge(self, edge_id, from_id, to_id, edge_type, props=None):
        if edge_id in self.edges:
            raise GraphError(f"edge {edge_id!r} already exists")
        if from_id not in self.nodes:
            raise GraphError(f"node {from_id!r} does not exist")
        if to_id not in self.nodes:
            raise GraphError(f"node {to_id!r} does not exist")
        self.edges[edge_id] = {
            "from": from_id,
            "to": to_id,
            "type": edge_type,
            "props": dict(props or {}),
        }
        self._out[from_id].append(edge_id)
        self._in[to_id].append(edge_id)

    def remove_edge(self, edge_id):
        if edge_id not in self.edges:
            raise GraphError(f"edge {edge_id!r} does not exist")
        edge = self.edges.pop(edge_id)
        self._out[edge["from"]].remove(edge_id)
        self._in[edge["to"]].remove(edge_id)

    def _reindex(self):
        self._out = {n: [] for n in self.nodes}
        self._in = {n: [] for n in self.nodes}
        for edge_id, edge in self.edges.items():
            self._out.setdefault(edge["from"], []).append(edge_id)
            self._in.setdefault(edge["to"], []).append(edge_id)

    def neighbors(self, node_id, edge_type=None, direction="out"):
        if node_id not in self.nodes:
            raise GraphError(f"node {node_id!r} does not exist")
        edge_ids = []
        if direction in ("out", "both"):
            edge_ids += self._out.get(node_id, [])
        if direction in ("in", "both"):
            edge_ids += self._in.get(node_id, [])
        result = []
        for edge_id in edge_ids:
            edge = self.edges[edge_id]
            if edge_type is not None and edge["type"] != edge_type:
                continue
            other = edge["to"] if edge["from"] == node_id else edge["from"]
            result.append(other)
        return result

    def out_edges(self, node_id, edge_type=None):
        if node_id not in self.nodes:
            raise GraphError(f"node {node_id!r} does not exist")
        for edge_id in self._out.get(node_id, []):
            edge = self.edges[edge_id]
            if edge_type is not None and edge["type"] != edge_type:
                continue
            yield edge_id, edge

    def to_dict(self):
        return {"nodes": self.nodes, "edges": self.edges}

    @classmethod
    def from_dict(cls, data):
        graph = cls()
        for node_id, node in data.get("nodes", {}).items():
            graph.nodes[node_id] = {
                "labels": list(node.get("labels", [])),
                "props": dict(node.get("props", {})),
            }
        for edge_id, edge in data.get("edges", {}).items():
            graph.edges[edge_id] = {
                "from": edge["from"],
                "to": edge["to"],
                "type": edge["type"],
                "props": dict(edge.get("props", {})),
            }
        graph._reindex()
        return graph
