import argparse
import sys
from importlib.metadata import version as _get_version, PackageNotFoundError

from gridsheet.refs import expand_range, num_to_col
from gridsheet.sheet import Sheet, SheetError
from gridsheet.storage import export_csv, import_csv, load_sheet, save_sheet


def _get_package_version():
    try:
        return _get_version("eulerlib")
    except PackageNotFoundError:
        return "0.1.0"


def _parse_dest_range(dest):
    """Parse a fill destination: 'B1:B5' (a range) or a single ref like 'B1'."""
    if ":" in dest:
        start, end = dest.split(":", 1)
        return expand_range(start.strip(), end.strip())
    return [dest.strip()]


def _load_or_new(path):
    try:
        return load_sheet(path)
    except FileNotFoundError:
        return Sheet()


def _fmt(value):
    if value is None:
        return ""
    if isinstance(value, float):
        if value == int(value):
            return str(int(value))
        return str(value)
    return str(value)


def render_grid(sheet):
    max_c, max_r = sheet.bounds()
    if max_c == 0 or max_r == 0:
        return "(empty sheet)"
    headers = [""] + [num_to_col(c) for c in range(1, max_c + 1)]
    rows = []
    for r in range(1, max_r + 1):
        row = [str(r)]
        for c in range(1, max_c + 1):
            ref = f"{num_to_col(c)}{r}"
            row.append(_fmt(sheet.get_value(ref)))
        rows.append(row)
    widths = [max(len(headers[i]), *(len(row[i]) for row in rows)) for i in range(len(headers))]
    lines = ["  ".join(h.rjust(widths[i]) for i, h in enumerate(headers))]
    for row in rows:
        lines.append("  ".join(cell.rjust(widths[i]) for i, cell in enumerate(row)))
    return "\n".join(lines)


def cmd_set(args):
    sheet = _load_or_new(args.file)
    try:
        sheet.set_cell(args.ref, args.content)
    except SheetError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    save_sheet(sheet, args.file)
    return 0


def cmd_get(args):
    sheet = _load_or_new(args.file)
    print(_fmt(sheet.get_value(args.ref)))
    return 0


def cmd_show(args):
    sheet = _load_or_new(args.file)
    print(render_grid(sheet))
    return 0


def cmd_fill(args):
    sheet = _load_or_new(args.file)
    try:
        dest_refs = _parse_dest_range(args.dest)
        sheet.fill(args.src, dest_refs)
    except (SheetError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    save_sheet(sheet, args.file)
    return 0


def cmd_export(args):
    sheet = _load_or_new(args.file)
    export_csv(sheet, args.csv_file)
    return 0


def cmd_import(args):
    sheet = Sheet()
    try:
        import_csv(sheet, args.csv_file)
    except SheetError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    save_sheet(sheet, args.file)
    return 0


def cmd_shell(args):
    sheet = _load_or_new(args.file)
    dirty = False
    print(f"gridsheet shell — {args.file} ('help' for commands, 'quit' to exit)")
    while True:
        try:
            line = input("> ").strip()
        except EOFError:
            print()
            break
        if not line:
            continue
        if line in ("quit", "exit"):
            break
        if line == "help":
            print(
                "commands: REF = CONTENT | get REF | show | fill SRC DEST | "
                "save | export CSV_FILE | import CSV_FILE | quit"
            )
            continue
        if line == "show":
            print(render_grid(sheet))
            continue
        if line == "save":
            save_sheet(sheet, args.file)
            dirty = False
            print(f"saved to {args.file}")
            continue
        if line.startswith("get "):
            ref = line[4:].strip()
            print(_fmt(sheet.get_value(ref)))
            continue
        if line.startswith("export "):
            csv_path = line[7:].strip()
            export_csv(sheet, csv_path)
            print(f"exported to {csv_path}")
            continue
        if line.startswith("import "):
            csv_path = line[7:].strip()
            try:
                import_csv(sheet, csv_path)
            except SheetError as e:
                print(f"error: {e}")
                continue
            dirty = True
            print(f"imported {csv_path}")
            continue
        if line.startswith("fill "):
            parts = line[5:].split()
            if len(parts) != 2:
                print("error: usage: fill SRC DEST")
                continue
            try:
                dest_refs = _parse_dest_range(parts[1])
                sheet.fill(parts[0], dest_refs)
            except (SheetError, ValueError) as e:
                print(f"error: {e}")
                continue
            dirty = True
            continue
        if "=" in line:
            ref, content = line.split("=", 1)
            ref = ref.strip()
            content = content.strip()
            try:
                sheet.set_cell(ref, content)
            except SheetError as e:
                print(f"error: {e}")
                continue
            dirty = True
            continue
        print(f"error: unrecognized command {line!r}")
    if dirty:
        save_sheet(sheet, args.file)
        print(f"saved to {args.file}")
    return 0


def build_parser():
    p = argparse.ArgumentParser(prog="gridsheet")
    p.add_argument("--version", action="version", version=_get_package_version())
    sub = p.add_subparsers(dest="command", required=True)

    p_set = sub.add_parser("set", help="set a cell's content (literal or =formula)")
    p_set.add_argument("file")
    p_set.add_argument("ref")
    p_set.add_argument("content")
    p_set.set_defaults(func=cmd_set)

    p_get = sub.add_parser("get", help="print a cell's computed value")
    p_get.add_argument("file")
    p_get.add_argument("ref")
    p_get.set_defaults(func=cmd_get)

    p_show = sub.add_parser("show", help="print the whole sheet as a grid")
    p_show.add_argument("file")
    p_show.set_defaults(func=cmd_show)

    p_fill = sub.add_parser(
        "fill", help="copy a cell's content into a range, shifting relative references"
    )
    p_fill.add_argument("file")
    p_fill.add_argument("src", help="source cell, e.g. A1")
    p_fill.add_argument("dest", help="destination cell or range, e.g. B1 or B1:B5")
    p_fill.set_defaults(func=cmd_fill)

    p_export = sub.add_parser("export", help="export the sheet's computed values as CSV")
    p_export.add_argument("file")
    p_export.add_argument("csv_file")
    p_export.set_defaults(func=cmd_export)

    p_import = sub.add_parser("import", help="create a sheet from a CSV file")
    p_import.add_argument("file", help="gridsheet JSON file to create (overwritten if it exists)")
    p_import.add_argument("csv_file")
    p_import.set_defaults(func=cmd_import)

    p_shell = sub.add_parser("shell", help="interactive REPL")
    p_shell.add_argument("file")
    p_shell.set_defaults(func=cmd_shell)

    return p


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args) or 0
    except SheetError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
