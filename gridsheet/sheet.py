"""Sheet: cell storage, dependency graph, and formula recalculation."""
from gridsheet import formula
from gridsheet.refs import normalize_ref


class SheetError(Exception):
    pass


class Cell:
    def __init__(self, raw="", ast=None, value=None):
        self.raw = raw      # exact text the user typed, e.g. "=A1+1" or "5" or "hello"
        self.ast = ast       # parsed formula.Node, or None for a literal
        self.value = value   # computed value: float, str, None (empty), or an error string


class Sheet:
    def __init__(self):
        self.cells = {}          # ref -> Cell
        self.depends_on = {}     # ref -> set(ref) this cell's formula reads from
        self.dependents = {}     # ref -> set(ref) of cells that read this cell

    def _reachable(self, start, target):
        """True if target is reachable from start by following depends_on edges."""
        seen = set()
        stack = [start]
        while stack:
            cur = stack.pop()
            if cur == target:
                return True
            if cur in seen:
                continue
            seen.add(cur)
            stack.extend(self.depends_on.get(cur, ()))
        return False

    def set_cell(self, ref, content):
        ref = normalize_ref(ref)
        content = content if content is not None else ""

        if content == "":
            self._clear_cell(ref)
            return

        if content.startswith("="):
            try:
                ast = formula.parse(content[1:])
            except formula.FormulaError as e:
                raise SheetError(f"invalid formula: {e}") from e
            new_deps = formula.extract_refs(ast)
            for dep in new_deps:
                if dep == ref or self._reachable(dep, ref):
                    raise SheetError(f"circular reference: {ref} depends on itself via {dep}")
            self._rewire(ref, new_deps)
            self.cells[ref] = Cell(raw=content, ast=ast)
        else:
            self._rewire(ref, set())
            try:
                num = float(content)
                self.cells[ref] = Cell(raw=content, ast=None, value=num)
            except ValueError:
                self.cells[ref] = Cell(raw=content, ast=None, value=content)

        self._recompute_from(ref)

    def _clear_cell(self, ref):
        self._rewire(ref, set())
        self.cells.pop(ref, None)
        self._recompute_from(ref)

    def _rewire(self, ref, new_deps):
        old_deps = self.depends_on.get(ref, set())
        for old in old_deps - new_deps:
            self.dependents.get(old, set()).discard(ref)
        for new in new_deps - old_deps:
            self.dependents.setdefault(new, set()).add(ref)
        if new_deps:
            self.depends_on[ref] = set(new_deps)
        else:
            self.depends_on.pop(ref, None)

    def _closure(self, ref):
        """ref plus every cell transitively dependent on it."""
        seen = set()
        stack = [ref]
        while stack:
            cur = stack.pop()
            if cur in seen:
                continue
            seen.add(cur)
            stack.extend(self.dependents.get(cur, ()))
        return seen

    def _recompute_from(self, ref):
        affected = self._closure(ref)
        order = self._topo_order(affected)
        for r in order:
            cell = self.cells.get(r)
            if cell is None:
                continue
            if cell.ast is None:
                continue  # literal, value already set
            try:
                cell.value = formula.evaluate(cell.ast, self.get_value)
            except formula.SheetEvalError as e:
                cell.value = str(e)

    def _topo_order(self, refs):
        """Order refs so each cell comes after everything it depends on (within refs)."""
        refs = set(refs)
        in_degree = {r: 0 for r in refs}
        for r in refs:
            for dep in self.depends_on.get(r, ()):
                if dep in refs:
                    in_degree[r] += 1
        ready = [r for r in refs if in_degree[r] == 0]
        order = []
        while ready:
            r = ready.pop()
            order.append(r)
            for dependent in self.dependents.get(r, ()):
                if dependent in in_degree:
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        ready.append(dependent)
        return order

    def get_value(self, ref):
        ref = normalize_ref(ref)
        cell = self.cells.get(ref)
        if cell is None:
            return None
        return cell.value

    def get_raw(self, ref):
        ref = normalize_ref(ref)
        cell = self.cells.get(ref)
        return cell.raw if cell else ""

    def bounds(self):
        """(max_col, max_row) among cells with content, or (0, 0) if empty."""
        from gridsheet.refs import parse_ref

        max_c = max_r = 0
        for ref in self.cells:
            c, r = parse_ref(ref)
            max_c = max(max_c, c)
            max_r = max(max_r, r)
        return max_c, max_r

    def to_dict(self):
        return {ref: cell.raw for ref, cell in self.cells.items()}

    @classmethod
    def from_dict(cls, data):
        sheet = cls()
        # Insert raw content directly, then do one full recompute in dependency order,
        # since inserting cell-by-cell via set_cell would recompute redundantly and could
        # reject a forward reference (B1 referring to A1 before A1 exists yet).
        for ref, raw in data.items():
            ref = normalize_ref(ref)
            if raw.startswith("="):
                try:
                    ast = formula.parse(raw[1:])
                except formula.FormulaError as e:
                    raise SheetError(f"invalid formula in {ref}: {e}") from e
                deps = formula.extract_refs(ast)
                sheet.cells[ref] = Cell(raw=raw, ast=ast)
                if deps:
                    sheet.depends_on[ref] = deps
                    for dep in deps:
                        sheet.dependents.setdefault(dep, set()).add(ref)
            else:
                try:
                    num = float(raw)
                    sheet.cells[ref] = Cell(raw=raw, ast=None, value=num)
                except ValueError:
                    sheet.cells[ref] = Cell(raw=raw, ast=None, value=raw)

        # Full recompute in one topo pass across every formula cell. A loaded sheet
        # could contain a hand-edited cycle; Kahn's algorithm silently drops any
        # node still stuck in a cycle, so a short-count order means one exists.
        formula_refs = {r for r, c in sheet.cells.items() if c.ast is not None}
        relevant = formula_refs | set(sheet.depends_on.keys()) | set(sheet.dependents.keys())
        order = sheet._topo_order(relevant)
        if len(order) < len(relevant):
            raise SheetError("circular reference detected while loading sheet")
        for r in order:
            cell = sheet.cells.get(r)
            if cell is None or cell.ast is None:
                continue
            try:
                cell.value = formula.evaluate(cell.ast, sheet.get_value)
            except formula.SheetEvalError as e:
                cell.value = str(e)
        return sheet
