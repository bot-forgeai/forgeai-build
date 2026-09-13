import pytest

from toylang.interpreter import Interpreter, ToylangRuntimeError
from toylang.parser import parse


def run(source):
    Interpreter().run(parse(source))


def run_capture(source, capsys):
    run(source)
    return capsys.readouterr().out


def test_arithmetic(capsys):
    out = run_capture('print(1 + 2 * 3 - 4 / 2);', capsys)
    assert out == "5\n"


def test_division_keeps_fractional_result(capsys):
    out = run_capture('print(7 / 2);', capsys)
    assert out == "3.5\n"


def test_string_concat_with_number(capsys):
    out = run_capture('print("count: " + 5);', capsys)
    assert out == "count: 5\n"


def test_variables_and_reassignment(capsys):
    out = run_capture('let x = 1; x = x + 1; print(x);', capsys)
    assert out == "2\n"


def test_if_else(capsys):
    out = run_capture('if (1 < 2) { print("yes"); } else { print("no"); }', capsys)
    assert out == "yes\n"


def test_while_loop(capsys):
    out = run_capture(
        'let i = 0; let total = 0; while (i < 5) { total = total + i; i = i + 1; } print(total);',
        capsys,
    )
    assert out == "10\n"


def test_function_call_and_return(capsys):
    out = run_capture(
        'func add(a, b) { return a + b; } print(add(3, 4));', capsys
    )
    assert out == "7\n"


def test_recursion_fibonacci(capsys):
    out = run_capture(
        '''
        func fib(n) {
            if (n <= 1) { return n; }
            return fib(n - 1) + fib(n - 2);
        }
        print(fib(10));
        ''',
        capsys,
    )
    assert out == "55\n"


def test_closures_capture_environment(capsys):
    out = run_capture(
        '''
        func make_counter() {
            let count = 0;
            func increment() {
                count = count + 1;
                return count;
            }
            return increment;
        }
        let c = make_counter();
        print(c(), c(), c());
        ''',
        capsys,
    )
    assert out == "1 2 3\n"


def test_two_closures_are_independent(capsys):
    out = run_capture(
        '''
        func make_counter() {
            let count = 0;
            func increment() { count = count + 1; return count; }
            return increment;
        }
        let a = make_counter();
        let b = make_counter();
        a(); a();
        print(a(), b());
        ''',
        capsys,
    )
    assert out == "3 1\n"


def test_builtin_len():
    interpreter = Interpreter()
    interpreter.run(parse('let n = len("hello");'))
    assert interpreter.globals.get("n") == 5


def test_and_or_short_circuit_values(capsys):
    out = run_capture('print(false and 1); print(true or 2); print(nil or 3);', capsys)
    assert out == "false\ntrue\n3\n"


def test_undefined_variable_raises():
    with pytest.raises(ToylangRuntimeError):
        run("print(missing);")


def test_wrong_arg_count_raises():
    with pytest.raises(ToylangRuntimeError):
        run("func f(a, b) { return a; } f(1);")


def test_division_by_zero_raises():
    with pytest.raises(ToylangRuntimeError):
        run("print(1 / 0);")


def test_type_error_on_arithmetic_with_string():
    with pytest.raises(ToylangRuntimeError):
        run('print("x" - 1);')


def test_calling_non_function_raises():
    with pytest.raises(ToylangRuntimeError):
        run("let x = 5; x();")


def test_list_literal_and_index(capsys):
    out = run_capture('let xs = [1, 2, 3]; print(xs[0]); print(xs[2]);', capsys)
    assert out == "1\n3\n"


def test_list_printed_as_bracketed(capsys):
    out = run_capture('print([1, "a", true]);', capsys)
    assert out == '[1, a, true]\n'


def test_index_assignment(capsys):
    out = run_capture('let xs = [1, 2, 3]; xs[1] = 99; print(xs);', capsys)
    assert out == "[1, 99, 3]\n"


def test_nested_list_index(capsys):
    out = run_capture('let xs = [[1, 2], [3, 4]]; print(xs[1][0]);', capsys)
    assert out == "3\n"


def test_string_indexing(capsys):
    out = run_capture('print("hello"[1]);', capsys)
    assert out == "e\n"


def test_len_on_list(capsys):
    out = run_capture('print(len([1, 2, 3, 4]));', capsys)
    assert out == "4\n"


def test_push_and_pop(capsys):
    out = run_capture(
        'let xs = [1, 2]; push(xs, 3); print(xs); let x = pop(xs); print(x); print(xs);',
        capsys,
    )
    assert out == "[1, 2, 3]\n3\n[1, 2]\n"


def test_list_in_loop(capsys):
    out = run_capture(
        'let xs = [1, 2, 3]; let total = 0; let i = 0; '
        'while (i < len(xs)) { total = total + xs[i]; i = i + 1; } print(total);',
        capsys,
    )
    assert out == "6\n"


def test_index_out_of_range_raises():
    with pytest.raises(ToylangRuntimeError):
        run("let xs = [1, 2]; print(xs[5]);")


def test_pop_empty_list_raises():
    with pytest.raises(ToylangRuntimeError):
        run("let xs = []; pop(xs);")


def test_index_assign_on_non_list_raises():
    with pytest.raises(ToylangRuntimeError):
        run('let x = 5; x[0] = 1;')


def test_string_case_and_trim(capsys):
    out = run_capture('print(upper("hi")); print(lower("HI")); print(trim("  hi  "));', capsys)
    assert out == "HI\nhi\nhi\n"


def test_split_and_join(capsys):
    out = run_capture(
        'let parts = split("a,b,c", ","); print(parts); print(join(parts, "-"));',
        capsys,
    )
    assert out == "[a, b, c]\na-b-c\n"


def test_split_empty_separator_raises():
    with pytest.raises(ToylangRuntimeError):
        run('split("abc", "");')


def test_contains(capsys):
    out = run_capture(
        'print(contains("hello", "ell")); print(contains([1, 2, 3], 2)); '
        'print(contains([1, 2, 3], 9));',
        capsys,
    )
    assert out == "true\ntrue\nfalse\n"


def test_str_and_num(capsys):
    out = run_capture('print(str(42) + "!"); print(num("3.5") + 1);', capsys)
    assert out == "42!\n4.5\n"


def test_num_invalid_raises():
    with pytest.raises(ToylangRuntimeError):
        run('num("not a number");')


def test_math_builtins(capsys):
    out = run_capture(
        'print(abs(-5)); print(floor(3.7)); print(sqrt(9)); print(min(3, 1, 2)); print(max(3, 1, 2));',
        capsys,
    )
    assert out == "5\n3\n3\n1\n3\n"


def test_sqrt_negative_raises():
    with pytest.raises(ToylangRuntimeError):
        run('sqrt(-1);')


def test_range(capsys):
    out = run_capture('print(range(3)); print(range(2, 5));', capsys)
    assert out == "[0, 1, 2]\n[2, 3, 4]\n"


def test_range_used_in_loop(capsys):
    out = run_capture(
        'let total = 0; let xs = range(5); let i = 0; '
        'while (i < len(xs)) { total = total + xs[i]; i = i + 1; } print(total);',
        capsys,
    )
    assert out == "10\n"
