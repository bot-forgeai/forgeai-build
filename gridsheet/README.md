# gridsheet

A small spreadsheet engine: cells hold either a literal number or a
`=formula`, formulas can reference other cells (including ranges), and
the whole sheet recalculates automatically whenever a cell changes.
State is a single JSON file, so a sheet is just a file you can copy,
diff, or check into version control.

## Install

```
pip install -e .
```

This registers a `gridsheet` console script (or run
`python -m gridsheet` instead).

## Usage

```
gridsheet set FILE REF CONTENT   # set a cell to a literal or =formula
gridsheet get FILE REF           # print a cell's computed value
gridsheet show FILE              # print the whole sheet as a grid
gridsheet fill FILE SRC DEST     # copy a cell into a range, shifting refs
gridsheet export FILE CSV_FILE   # export computed values as CSV
gridsheet shell FILE             # interactive REPL
gridsheet --version              # print the installed package version
```

`FILE` is a JSON sheet file; it's created automatically the first time
you `set` a cell in it. `REF` is a cell reference like `A1`, `B12`, or
`AA3` (columns beyond Z use multi-letter names, same as a real
spreadsheet).

### Example

```
$ gridsheet set demo.json A1 10
$ gridsheet set demo.json A2 20
$ gridsheet set demo.json A3 "=SUM(A1:A2)"
$ gridsheet show demo.json
    A
1  10
2  20
3  30
$ gridsheet get demo.json A3
30
```

### Formulas

A formula starts with `=` and can use:

- Arithmetic: `+ - * /`
- Comparisons: `= <> < <= > >=` (evaluate to `1`/`0`, so they can feed
  into `IF` or arithmetic)
- Cell references (`A1`) and ranges (`A1:A5`, expanded column-major)
  as arguments to range functions
- Functions: `SUM`, `AVG`, `MIN`, `MAX`, `COUNT` (each takes one or
  more cells/ranges), `IF(cond, then, else)`, `ROUND(value, digits)`,
  `ABS(value)`

Formula values are numbers only — there is no string-literal syntax,
so `IF`'s branches, for example, must be numeric or cell references,
not quoted text.

Dividing by zero, referencing an empty/non-numeric cell in a numeric
context, or a malformed formula all produce an error value (e.g.
`#DIV/0!`) in that cell rather than crashing the whole sheet.

### Absolute vs. relative references

A reference's column and/or row can be locked with a `$` prefix, the
same convention spreadsheets use:

| Reference | Meaning |
|---|---|
| `A1` | fully relative |
| `$A1` | column locked, row relative |
| `A$1` | column relative, row locked |
| `$A$1` | fully locked |

This matters when a formula is filled into other cells (see below): a
locked part of a reference doesn't shift, an unlocked part does.

### `fill`: copy-and-shift a formula across a range

```
gridsheet fill FILE SRC DEST
```

`SRC` is a single cell; `DEST` is either a single cell or a range
(`B1:B5`). The source cell's content is copied into every destination
cell, with each *unlocked* part of any relative reference shifted by
the same row/column offset as the destination — exactly like dragging
a spreadsheet cell's fill handle. Locked (`$`) parts of a reference
stay fixed no matter where the formula is filled.

```
$ gridsheet set demo.json C1 "=A1*2"
$ gridsheet fill demo.json C1 C2:C3
$ gridsheet show demo.json
    A  B   C
1  10     20
2  20     40
3  30     60
```

### CSV export

```
gridsheet export FILE CSV_FILE
```

Writes the sheet's *computed* values (not formula text) as CSV, one
row per sheet row, in column order.

### Interactive shell

```
gridsheet shell FILE
```

Commands:

```
REF = CONTENT       set a cell (literal or =formula)
get REF             print a cell's computed value
show                print the whole sheet
fill SRC DEST        copy SRC into DEST (cell or range), shifting refs
save                 write changes to FILE immediately
export CSV_FILE      export computed values as CSV
quit / exit          leave the shell (auto-saves if there are unsaved changes)
```

## Tests

```
pytest tests/test_gridsheet.py
```
