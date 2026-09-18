"""Recursive-descent parser for nanosql's SQL subset."""

from .ast_nodes import (
    AggCall,
    AlterTableAddColumn,
    AlterTableDropColumn,
    Begin,
    BoolOp,
    Commit,
    CreateIndex,
    CreateTable,
    Cmp,
    Delete,
    Insert,
    Join,
    JoinCond,
    Rollback,
    Select,
    Update,
)

AGGREGATE_FUNCS = {"COUNT", "SUM", "AVG", "MIN", "MAX"}
from .lexer import tokenize

COMPARISON_OPS = {"=", "!=", "<", "<=", ">", ">="}


class ParseError(Exception):
    pass


class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    def peek(self):
        return self.tokens[self.pos]

    def advance(self):
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def expect(self, kind, value=None):
        tok = self.peek()
        if tok.kind != kind or (value is not None and tok.value != value):
            raise ParseError(f"expected {kind} {value!r}, got {tok.kind} {tok.value!r}")
        return self.advance()

    def at_keyword(self, *words):
        tok = self.peek()
        return tok.kind == "KEYWORD" and tok.value in words

    def parse_one_statement(self):
        if self.at_keyword("CREATE"):
            next_tok = self.tokens[self.pos + 1]
            if next_tok.kind == "KEYWORD" and next_tok.value == "INDEX":
                return self.parse_create_index()
            return self.parse_create_table()
        if self.at_keyword("ALTER"):
            return self.parse_alter_table()
        if self.at_keyword("INSERT"):
            return self.parse_insert()
        if self.at_keyword("SELECT"):
            return self.parse_select()
        if self.at_keyword("UPDATE"):
            return self.parse_update()
        if self.at_keyword("DELETE"):
            return self.parse_delete()
        if self.at_keyword("BEGIN"):
            self.advance()
            return Begin()
        if self.at_keyword("COMMIT"):
            self.advance()
            return Commit()
        if self.at_keyword("ROLLBACK"):
            self.advance()
            return Rollback()
        tok = self.peek()
        raise ParseError(f"unrecognized statement starting at {tok.kind} {tok.value!r}")

    def parse_statement(self):
        stmt = self.parse_one_statement()
        if self.peek().kind == "PUNCT" and self.peek().value == ";":
            self.advance()
        self.expect("EOF")
        return stmt

    def parse_program(self):
        statements = []
        while self.peek().kind != "EOF":
            statements.append(self.parse_one_statement())
            if self.peek().kind == "PUNCT" and self.peek().value == ";":
                self.advance()
            else:
                break
        self.expect("EOF")
        return statements

    def parse_ident(self):
        tok = self.peek()
        if tok.kind == "IDENT":
            return self.advance().value
        raise ParseError(f"expected identifier, got {tok.kind} {tok.value!r}")

    def parse_column_ref(self):
        """A column reference, optionally table-qualified: col, or table.col."""
        name = self.parse_ident()
        if self.peek().kind == "PUNCT" and self.peek().value == ".":
            self.advance()
            col = self.parse_ident()
            return f"{name}.{col}"
        return name

    def parse_create_table(self):
        self.expect("KEYWORD", "CREATE")
        self.expect("KEYWORD", "TABLE")
        table = self.parse_ident()
        self.expect("PUNCT", "(")
        columns = []
        while True:
            name = self.parse_ident()
            type_tok = self.expect("KEYWORD")
            if type_tok.value not in ("INT", "REAL", "TEXT"):
                raise ParseError(f"unknown column type {type_tok.value!r}")
            columns.append((name, type_tok.value))
            if self.peek().kind == "PUNCT" and self.peek().value == ",":
                self.advance()
                continue
            break
        self.expect("PUNCT", ")")
        return CreateTable(table, columns)

    def parse_alter_table(self):
        self.expect("KEYWORD", "ALTER")
        self.expect("KEYWORD", "TABLE")
        table = self.parse_ident()
        if self.at_keyword("ADD"):
            self.advance()
            if self.at_keyword("COLUMN"):
                self.advance()
            name = self.parse_ident()
            type_tok = self.expect("KEYWORD")
            if type_tok.value not in ("INT", "REAL", "TEXT"):
                raise ParseError(f"unknown column type {type_tok.value!r}")
            return AlterTableAddColumn(table, name, type_tok.value)
        if self.at_keyword("DROP"):
            self.advance()
            if self.at_keyword("COLUMN"):
                self.advance()
            name = self.parse_ident()
            return AlterTableDropColumn(table, name)
        tok = self.peek()
        raise ParseError(f"expected ADD or DROP after ALTER TABLE, got {tok.kind} {tok.value!r}")

    def parse_create_index(self):
        self.expect("KEYWORD", "CREATE")
        self.expect("KEYWORD", "INDEX")
        index_name = self.parse_ident()
        self.expect("KEYWORD", "ON")
        table = self.parse_ident()
        self.expect("PUNCT", "(")
        column = self.parse_ident()
        self.expect("PUNCT", ")")
        return CreateIndex(index_name, table, column)

    def parse_literal(self):
        tok = self.peek()
        if tok.kind == "NUMBER":
            return self.advance().value
        if tok.kind == "STRING":
            return self.advance().value
        if tok.kind == "KEYWORD" and tok.value == "NULL":
            self.advance()
            return None
        if tok.kind == "KEYWORD" and tok.value == "TRUE":
            self.advance()
            return True
        if tok.kind == "KEYWORD" and tok.value == "FALSE":
            self.advance()
            return False
        raise ParseError(f"expected a literal value, got {tok.kind} {tok.value!r}")

    def parse_insert(self):
        self.expect("KEYWORD", "INSERT")
        self.expect("KEYWORD", "INTO")
        table = self.parse_ident()
        columns = None
        if self.peek().kind == "PUNCT" and self.peek().value == "(":
            self.advance()
            columns = []
            while True:
                columns.append(self.parse_ident())
                if self.peek().kind == "PUNCT" and self.peek().value == ",":
                    self.advance()
                    continue
                break
            self.expect("PUNCT", ")")
        self.expect("KEYWORD", "VALUES")
        self.expect("PUNCT", "(")
        values = []
        while True:
            values.append(self.parse_literal())
            if self.peek().kind == "PUNCT" and self.peek().value == ",":
                self.advance()
                continue
            break
        self.expect("PUNCT", ")")
        return Insert(table, columns, values)

    def parse_where(self):
        return self.parse_or_expr()

    def parse_or_expr(self):
        left = self.parse_and_expr()
        while self.at_keyword("OR"):
            self.advance()
            right = self.parse_and_expr()
            left = BoolOp("OR", left, right)
        return left

    def parse_and_expr(self):
        left = self.parse_comparison()
        while self.at_keyword("AND"):
            self.advance()
            right = self.parse_comparison()
            left = BoolOp("AND", left, right)
        return left

    def parse_comparison(self):
        column = self.parse_column_ref()
        tok = self.peek()
        if tok.kind == "KEYWORD" and tok.value == "LIKE":
            self.advance()
            pattern = self.parse_literal()
            if not isinstance(pattern, str):
                raise ParseError("LIKE pattern must be a string literal")
            return Cmp(column, "LIKE", pattern)
        op_tok = tok
        if op_tok.kind != "OP" or op_tok.value not in COMPARISON_OPS:
            raise ParseError(f"expected a comparison operator, got {op_tok.kind} {op_tok.value!r}")
        self.advance()
        value = self.parse_literal()
        return Cmp(column, op_tok.value, value)

    def parse_select_column(self):
        tok = self.peek()
        if tok.kind == "KEYWORD" and tok.value in AGGREGATE_FUNCS:
            func = self.advance().value
            self.expect("PUNCT", "(")
            if func == "COUNT" and self.peek().kind == "PUNCT" and self.peek().value == "*":
                self.advance()
                column = "*"
            else:
                column = self.parse_column_ref()
            self.expect("PUNCT", ")")
            return AggCall(func, column)
        return self.parse_column_ref()

    def parse_select(self):
        self.expect("KEYWORD", "SELECT")
        columns = ["*"]
        if self.peek().kind == "PUNCT" and self.peek().value == "*":
            self.advance()
        else:
            columns = [self.parse_select_column()]
            while self.peek().kind == "PUNCT" and self.peek().value == ",":
                self.advance()
                columns.append(self.parse_select_column())
        self.expect("KEYWORD", "FROM")
        table = self.parse_ident()
        join = None
        if self.at_keyword("JOIN"):
            self.advance()
            join_table = self.parse_ident()
            self.expect("KEYWORD", "ON")
            left = self.parse_column_ref()
            op_tok = self.peek()
            if op_tok.kind != "OP" or op_tok.value not in COMPARISON_OPS:
                raise ParseError(f"expected a comparison operator, got {op_tok.kind} {op_tok.value!r}")
            self.advance()
            right = self.parse_column_ref()
            join = Join(join_table, JoinCond(left, op_tok.value, right))
        where = None
        if self.at_keyword("WHERE"):
            self.advance()
            where = self.parse_where()
        group_by = None
        if self.at_keyword("GROUP"):
            self.advance()
            self.expect("KEYWORD", "BY")
            group_by = self.parse_column_ref()
        order_by = None
        if self.at_keyword("ORDER"):
            self.advance()
            self.expect("KEYWORD", "BY")
            col = self.parse_column_ref()
            direction = "ASC"
            if self.at_keyword("ASC", "DESC"):
                direction = self.advance().value
            order_by = (col, direction)
        limit = None
        if self.at_keyword("LIMIT"):
            self.advance()
            tok = self.expect("NUMBER")
            limit = int(tok.value)
        return Select(table, columns, where, group_by, order_by, limit, join=join)

    def parse_update(self):
        self.expect("KEYWORD", "UPDATE")
        table = self.parse_ident()
        self.expect("KEYWORD", "SET")
        assignments = []
        while True:
            col = self.parse_ident()
            self.expect("OP", "=")
            value = self.parse_literal()
            assignments.append((col, value))
            if self.peek().kind == "PUNCT" and self.peek().value == ",":
                self.advance()
                continue
            break
        where = None
        if self.at_keyword("WHERE"):
            self.advance()
            where = self.parse_where()
        return Update(table, assignments, where)

    def parse_delete(self):
        self.expect("KEYWORD", "DELETE")
        self.expect("KEYWORD", "FROM")
        table = self.parse_ident()
        where = None
        if self.at_keyword("WHERE"):
            self.advance()
            where = self.parse_where()
        return Delete(table, where)


def parse(sql):
    return Parser(tokenize(sql)).parse_statement()


def parse_script(sql):
    """Parse a ';'-separated sequence of statements into a list of AST nodes."""
    return Parser(tokenize(sql)).parse_program()
