"""Graph algorithms: BFS shortest path and weakly-connected components."""

from collections import deque

from .model import GraphError


def shortest_path(graph, start, end, edge_type=None, direction="out"):
    """Return a list of node ids from start to end (inclusive), or None if unreachable."""
    if start not in graph.nodes:
        raise GraphError(f"node {start!r} does not exist")
    if end not in graph.nodes:
        raise GraphError(f"node {end!r} does not exist")
    if start == end:
        return [start]
    visited = {start}
    parent = {}
    queue = deque([start])
    while queue:
        node = queue.popleft()
        for neighbor in graph.neighbors(node, edge_type=edge_type, direction=direction):
            if neighbor in visited:
                continue
            visited.add(neighbor)
            parent[neighbor] = node
            if neighbor == end:
                path = [end]
                while path[-1] != start:
                    path.append(parent[path[-1]])
                path.reverse()
                return path
            queue.append(neighbor)
    return None


def connected_components(graph):
    """Return weakly-connected components (edge direction ignored) as sorted id lists."""
    seen = set()
    components = []
    for node in graph.nodes:
        if node in seen:
            continue
        component = set()
        queue = deque([node])
        seen.add(node)
        while queue:
            current = queue.popleft()
            component.add(current)
            for neighbor in graph.neighbors(current, direction="both"):
                if neighbor not in seen:
                    seen.add(neighbor)
                    queue.append(neighbor)
        components.append(sorted(component))
    components.sort(key=lambda c: c[0])
    return components
