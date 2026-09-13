# Sample toylang program: fibonacci, a loop, and closures.

func fib(n) {
    if (n <= 1) {
        return n;
    }
    return fib(n - 1) + fib(n - 2);
}

let i = 0;
while (i < 8) {
    print("fib(" + i + ") =", fib(i));
    i = i + 1;
}

func make_counter() {
    let count = 0;
    func increment() {
        count = count + 1;
        return count;
    }
    return increment;
}

let counter = make_counter();
print("counter:", counter(), counter(), counter());
