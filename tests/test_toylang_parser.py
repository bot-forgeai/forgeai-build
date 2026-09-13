import pytest

from toylang import ast_nodes as ast
from toylang.lexer import ToylangSyntaxError
from toylang.parser import parse


def test_let_and_expr_stmt():
    program = parse("let x = 1 + 2;")
    assert len(program.statements) == 1
    stmt = program.statements[0]
    assert isinstance(stmt, ast.LetStmt)
    assert stmt.name == "x"
    assert isinstance(stmt.value, ast.BinOp)
    assert stmt.value.op == "+"


def test_operator_precedence():
    program = parse("let x = 1 + 2 * 3;")
    value = program.statements[0].value
    assert value.op == "+"
    assert isinstance(value.right, ast.BinOp)
    assert value.right.op == "*"


def test_comparison_and_logic():
    program = parse("let x = 1 < 2 and 3 > 4 or not false;")
    value = program.statements[0].value
    assert value.op == "or"


def test_if_else_if_chain():
    program = parse("if (x) { let a = 1; } else if (y) { let b = 2; } else { let c = 3; }")
    stmt = program.statements[0]
    assert isinstance(stmt, ast.IfStmt)
    assert isinstance(stmt.else_block, ast.IfStmt)
    assert isinstance(stmt.else_block.else_block, ast.Block)


def test_while_loop():
    program = parse("while (x < 10) { x = x + 1; }")
    stmt = program.statements[0]
    assert isinstance(stmt, ast.WhileStmt)


def test_func_decl_and_call():
    program = parse("func add(a, b) { return a + b; } add(1, 2);")
    decl, call_stmt = program.statements
    assert isinstance(decl, ast.FuncDecl)
    assert decl.params == ["a", "b"]
    assert isinstance(call_stmt.expr, ast.Call)
    assert len(call_stmt.expr.args) == 2


def test_func_expr_assigned_to_variable():
    program = parse("let f = func(x) { return x; };")
    assert isinstance(program.statements[0].value, ast.FuncExpr)


def test_assignment_vs_equality():
    program = parse("x = 1; let y = x == 1;")
    assert isinstance(program.statements[0].expr, ast.Assign)
    assert program.statements[1].value.op == "=="


def test_missing_semicolon_raises():
    with pytest.raises(ToylangSyntaxError):
        parse("let x = 1")


def test_unclosed_block_raises():
    with pytest.raises(ToylangSyntaxError):
        parse("if (x) { let a = 1; ")
