"""Recursive-descent parser: Tokens -> AST."""

from .lexer import ToylangSyntaxError
from . import ast_nodes as ast


class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    def _peek(self):
        return self.tokens[self.pos]

    def _at(self, *types):
        return self._peek().type in types

    def _advance(self):
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def _expect(self, type_, what=None):
        tok = self._peek()
        if tok.type != type_:
            raise ToylangSyntaxError(
                f"expected {what or type_}, got {tok.type!r}", tok.line
            )
        return self._advance()

    def parse_program(self):
        statements = []
        while not self._at("EOF"):
            statements.append(self._statement())
        return ast.Program(statements)

    # --- statements ---

    def _statement(self):
        if self._at("LET"):
            return self._let_stmt()
        if self._at("IF"):
            return self._if_stmt()
        if self._at("WHILE"):
            return self._while_stmt()
        if self._at("RETURN"):
            return self._return_stmt()
        if self._at("FUNC"):
            return self._func_decl()
        if self._at("{"):
            return self._block()
        return self._expr_stmt()

    def _let_stmt(self):
        self._advance()
        name = self._expect("IDENT", "identifier").value
        self._expect("=")
        value = self._expr()
        self._expect(";")
        return ast.LetStmt(name, value)

    def _if_stmt(self):
        self._advance()
        self._expect("(")
        cond = self._expr()
        self._expect(")")
        then_block = self._block()
        else_block = None
        if self._at("ELSE"):
            self._advance()
            else_block = self._if_stmt() if self._at("IF") else self._block()
        return ast.IfStmt(cond, then_block, else_block)

    def _while_stmt(self):
        self._advance()
        self._expect("(")
        cond = self._expr()
        self._expect(")")
        body = self._block()
        return ast.WhileStmt(cond, body)

    def _return_stmt(self):
        self._advance()
        value = None
        if not self._at(";"):
            value = self._expr()
        self._expect(";")
        return ast.ReturnStmt(value)

    def _func_decl(self):
        self._advance()
        name = self._expect("IDENT", "function name").value
        params = self._param_list()
        body = self._block()
        return ast.FuncDecl(name, params, body)

    def _param_list(self):
        self._expect("(")
        params = []
        if not self._at(")"):
            params.append(self._expect("IDENT", "parameter name").value)
            while self._at(","):
                self._advance()
                params.append(self._expect("IDENT", "parameter name").value)
        self._expect(")")
        return params

    def _block(self):
        self._expect("{")
        statements = []
        while not self._at("}"):
            statements.append(self._statement())
        self._expect("}")
        return ast.Block(statements)

    def _expr_stmt(self):
        expr = self._expr()
        self._expect(";")
        return ast.ExprStmt(expr)

    # --- expressions, lowest to highest precedence ---

    def _expr(self):
        return self._assignment()

    def _assignment(self):
        if self._at("IDENT") and self.tokens[self.pos + 1].type == "=":
            name = self._advance().value
            self._advance()  # '='
            value = self._assignment()
            return ast.Assign(name, value)
        return self._logic_or()

    def _logic_or(self):
        expr = self._logic_and()
        while self._at("OR"):
            self._advance()
            expr = ast.BinOp("or", expr, self._logic_and())
        return expr

    def _logic_and(self):
        expr = self._equality()
        while self._at("AND"):
            self._advance()
            expr = ast.BinOp("and", expr, self._equality())
        return expr

    def _equality(self):
        expr = self._comparison()
        while self._at("==", "!="):
            op = self._advance().type
            expr = ast.BinOp(op, expr, self._comparison())
        return expr

    def _comparison(self):
        expr = self._term()
        while self._at("<", ">", "<=", ">="):
            op = self._advance().type
            expr = ast.BinOp(op, expr, self._term())
        return expr

    def _term(self):
        expr = self._factor()
        while self._at("+", "-"):
            op = self._advance().type
            expr = ast.BinOp(op, expr, self._factor())
        return expr

    def _factor(self):
        expr = self._unary()
        while self._at("*", "/", "%"):
            op = self._advance().type
            expr = ast.BinOp(op, expr, self._unary())
        return expr

    def _unary(self):
        if self._at("NOT", "-"):
            op = self._advance().type
            return ast.UnaryOp(op, self._unary())
        return self._call()

    def _call(self):
        expr = self._primary()
        while self._at("("):
            self._advance()
            args = []
            if not self._at(")"):
                args.append(self._expr())
                while self._at(","):
                    self._advance()
                    args.append(self._expr())
            self._expect(")")
            expr = ast.Call(expr, args)
        return expr

    def _primary(self):
        tok = self._peek()
        if tok.type == "NUMBER":
            self._advance()
            return ast.NumberLit(tok.value)
        if tok.type == "STRING":
            self._advance()
            return ast.StringLit(tok.value)
        if tok.type == "TRUE":
            self._advance()
            return ast.BoolLit(True)
        if tok.type == "FALSE":
            self._advance()
            return ast.BoolLit(False)
        if tok.type == "NIL":
            self._advance()
            return ast.NilLit()
        if tok.type == "IDENT":
            self._advance()
            return ast.Var(tok.value)
        if tok.type == "(":
            self._advance()
            expr = self._expr()
            self._expect(")")
            return expr
        if tok.type == "FUNC":
            self._advance()
            params = self._param_list()
            body = self._block()
            return ast.FuncExpr(params, body)
        raise ToylangSyntaxError(f"unexpected token {tok.type!r}", tok.line)


def parse(source):
    from .lexer import tokenize
    return Parser(tokenize(source)).parse_program()
