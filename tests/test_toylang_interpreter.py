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
