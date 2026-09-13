"""Tree-walking interpreter over the AST."""

from . import ast_nodes as ast


class ToylangRuntimeError(Exception):
    pass


class _Return(Exception):
    """Internal control-flow signal for `return`, not a user-facing error."""

    def __init__(self, value):
        self.value = value


class Environment:
    def __init__(self, parent=None):
        self.vars = {}
        self.parent = parent

    def define(self, name, value):
        self.vars[name] = value

    def get(self, name):
        env = self
        while env is not None:
            if name in env.vars:
                return env.vars[name]
            env = env.parent
        raise ToylangRuntimeError(f"undefined variable '{name}'")

    def set(self, name, value):
        env = self
        while env is not None:
            if name in env.vars:
                env.vars[name] = value
                return
            env = env.parent
        raise ToylangRuntimeError(f"undefined variable '{name}'")


class Function:
    def __init__(self, params, body, closure, name="<anonymous>"):
        self.params = params
        self.body = body
        self.closure = closure
        self.name = name

    def call(self, interpreter, args):
        if len(args) != len(self.params):
            raise ToylangRuntimeError(
                f"{self.name}: expected {len(self.params)} argument(s), got {len(args)}"
            )
        env = Environment(parent=self.closure)
        for param, value in zip(self.params, args):
            env.define(param, value)
        try:
            interpreter._exec_block(self.body, env)
        except _Return as ret:
            return ret.value
        return None


def _is_truthy(value):
    if value is None or value is False:
        return False
    if value == 0:
        return False
    return True


def _stringify(value):
    if value is None:
        return "nil"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if isinstance(value, Function):
        return f"<function {value.name}>"
    if isinstance(value, list):
        return "[" + ", ".join(_stringify(v) for v in value) + "]"
    return str(value)


def _builtin_print(args):
    print(" ".join(_stringify(a) for a in args))
    return None


def _builtin_len(args):
    if len(args) != 1:
        raise ToylangRuntimeError("len: expected 1 argument")
    value = args[0]
    if isinstance(value, (str, list)):
        return len(value)
    raise ToylangRuntimeError(f"len: unsupported value {_stringify(value)!r}")


def _builtin_push(args):
    if len(args) != 2:
        raise ToylangRuntimeError("push: expected 2 arguments (list, value)")
    lst, value = args
    if not isinstance(lst, list):
        raise ToylangRuntimeError(f"push: expected a list, got {_stringify(lst)!r}")
    lst.append(value)
    return lst


def _builtin_pop(args):
    if len(args) != 1:
        raise ToylangRuntimeError("pop: expected 1 argument (list)")
    lst = args[0]
    if not isinstance(lst, list):
        raise ToylangRuntimeError(f"pop: expected a list, got {_stringify(lst)!r}")
    if not lst:
        raise ToylangRuntimeError("pop: list is empty")
    return lst.pop()


class BuiltinFunction:
    def __init__(self, name, fn):
        self.name = name
        self.fn = fn

    def call(self, interpreter, args):
        return self.fn(args)


BUILTINS = {
    "print": BuiltinFunction("print", _builtin_print),
    "len": BuiltinFunction("len", _builtin_len),
    "push": BuiltinFunction("push", _builtin_push),
    "pop": BuiltinFunction("pop", _builtin_pop),
}


class Interpreter:
    def __init__(self):
        self.globals = Environment()
        for name, fn in BUILTINS.items():
            self.globals.define(name, fn)

    def run(self, program):
        for stmt in program.statements:
            self._exec(stmt, self.globals)

    # --- statement execution ---

    def _exec(self, node, env):
        method = getattr(self, f"_exec_{type(node).__name__}")
        return method(node, env)

    def _exec_LetStmt(self, node, env):
        env.define(node.name, self._eval(node.value, env))

    def _exec_ExprStmt(self, node, env):
        self._eval(node.expr, env)

    def _exec_IfStmt(self, node, env):
        if _is_truthy(self._eval(node.condition, env)):
            self._exec_block(node.then_block, env)
        elif node.else_block is not None:
            if isinstance(node.else_block, ast.IfStmt):
                self._exec(node.else_block, env)
            else:
                self._exec_block(node.else_block, env)

    def _exec_WhileStmt(self, node, env):
        while _is_truthy(self._eval(node.condition, env)):
            self._exec_block(node.body, env)

    def _exec_ReturnStmt(self, node, env):
        value = self._eval(node.value, env) if node.value is not None else None
        raise _Return(value)

    def _exec_FuncDecl(self, node, env):
        env.define(node.name, Function(node.params, node.body, env, name=node.name))

    def _exec_Block(self, node, env):
        self._exec_block(node, env)

    def _exec_block(self, block, env):
        inner = Environment(parent=env)
        for stmt in block.statements:
            self._exec(stmt, inner)

    # --- expression evaluation ---

    def _eval(self, node, env):
        method = getattr(self, f"_eval_{type(node).__name__}")
        return method(node, env)

    def _eval_NumberLit(self, node, env):
        return node.value

    def _eval_StringLit(self, node, env):
        return node.value

    def _eval_BoolLit(self, node, env):
        return node.value

    def _eval_NilLit(self, node, env):
        return None

    def _eval_Var(self, node, env):
        return env.get(node.name)

    def _eval_Assign(self, node, env):
        value = self._eval(node.value, env)
        env.set(node.name, value)
        return value

    def _eval_UnaryOp(self, node, env):
        value = self._eval(node.operand, env)
        if node.op == "-":
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise ToylangRuntimeError(f"cannot negate {_stringify(value)!r}")
            return -value
        if node.op == "NOT":
            return not _is_truthy(value)
        raise ToylangRuntimeError(f"unknown unary operator {node.op}")

    def _eval_BinOp(self, node, env):
        if node.op == "and":
            left = self._eval(node.left, env)
            return self._eval(node.right, env) if _is_truthy(left) else left
        if node.op == "or":
            left = self._eval(node.left, env)
            return left if _is_truthy(left) else self._eval(node.right, env)

        left = self._eval(node.left, env)
        right = self._eval(node.right, env)
        op = node.op

        if op == "+":
            if isinstance(left, str) or isinstance(right, str):
                return _stringify(left) + _stringify(right)
            self._check_numeric(left, right, op)
            return left + right
        if op in ("-", "*", "/", "%"):
            self._check_numeric(left, right, op)
            if op == "-":
                return left - right
            if op == "*":
                return left * right
            if op == "/":
                if right == 0:
                    raise ToylangRuntimeError("division by zero")
                return left / right
            if right == 0:
                raise ToylangRuntimeError("modulo by zero")
            return left % right
        if op == "==":
            return left == right
        if op == "!=":
            return left != right
        if op in ("<", ">", "<=", ">="):
            self._check_numeric(left, right, op)
            if op == "<":
                return left < right
            if op == ">":
                return left > right
            if op == "<=":
                return left <= right
            return left >= right
        raise ToylangRuntimeError(f"unknown operator {op}")

    @staticmethod
    def _check_numeric(left, right, op):
        for value in (left, right):
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise ToylangRuntimeError(
                    f"operator '{op}' requires numbers, got {_stringify(value)!r}"
                )

    def _eval_Call(self, node, env):
        callee = self._eval(node.callee, env)
        args = [self._eval(arg, env) for arg in node.args]
        if not hasattr(callee, "call"):
            raise ToylangRuntimeError(f"{_stringify(callee)!r} is not callable")
        return callee.call(self, args)

    def _eval_FuncExpr(self, node, env):
        return Function(node.params, node.body, env)

    def _eval_ListLit(self, node, env):
        return [self._eval(el, env) for el in node.elements]

    def _eval_Index(self, node, env):
        collection = self._eval(node.collection, env)
        index = self._eval(node.index, env)
        return self._index_get(collection, index)

    def _eval_IndexAssign(self, node, env):
        collection = self._eval(node.collection, env)
        index = self._eval(node.index, env)
        value = self._eval(node.value, env)
        if not isinstance(collection, list):
            raise ToylangRuntimeError(
                f"cannot index-assign into {_stringify(collection)!r}"
            )
        i = self._check_index(collection, index)
        collection[i] = value
        return value

    @staticmethod
    def _check_index(collection, index):
        if not isinstance(index, int) or isinstance(index, bool):
            raise ToylangRuntimeError(f"index must be an integer, got {_stringify(index)!r}")
        if index < 0 or index >= len(collection):
            raise ToylangRuntimeError(f"index {index} out of range (length {len(collection)})")
        return index

    def _index_get(self, collection, index):
        if isinstance(collection, list):
            i = self._check_index(collection, index)
            return collection[i]
        if isinstance(collection, str):
            i = self._check_index(collection, index)
            return collection[i]
        raise ToylangRuntimeError(f"cannot index {_stringify(collection)!r}")
