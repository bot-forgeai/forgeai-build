"""Solutions to the Project Euler problems tracked by this library.

Docstrings summarize the problem; see projecteuler.net for full text.
"""


def p1(limit=1000):
    """Sum of all multiples of 3 or 5 below `limit`."""
    return sum(n for n in range(limit) if n % 3 == 0 or n % 5 == 0)


def p2(limit=4_000_000):
    """Sum of even Fibonacci terms not exceeding `limit`."""
    total = 0
    a, b = 1, 2
    while a <= limit:
        if a % 2 == 0:
            total += a
        a, b = b, a + b
    return total


def p3(n=600_851_475_143):
    """Largest prime factor of `n`."""
    largest = 1
    d = 2
    while d * d <= n:
        while n % d == 0:
            largest = d
            n //= d
        d += 1
    if n > 1:
        largest = n
    return largest


def p4(digits=3):
    """Largest palindrome that is a product of two `digits`-digit numbers."""
    lo, hi = 10 ** (digits - 1), 10**digits - 1
    best = 0
    for a in range(hi, lo - 1, -1):
        if a * hi <= best:
            break
        for b in range(hi, a - 1, -1):
            product = a * b
            if product <= best:
                break
            if str(product) == str(product)[::-1]:
                best = product
    return best


def p5(limit=20):
    """Smallest positive number evenly divisible by all of 1..limit."""
    def gcd(a, b):
        while b:
            a, b = b, a % b
        return a

    result = 1
    for i in range(1, limit + 1):
        result = result * i // gcd(result, i)
    return result


def p6(limit=100):
    """Difference between the square of the sum and the sum of squares, 1..limit."""
    numbers = range(1, limit + 1)
    return sum(numbers) ** 2 - sum(n * n for n in numbers)


def p7(index=10_001):
    """The `index`-th prime number (1-indexed)."""
    def is_prime(n):
        if n < 2:
            return False
        if n % 2 == 0:
            return n == 2
        d = 3
        while d * d <= n:
            if n % d == 0:
                return False
            d += 2
        return True

    found = 0
    candidate = 1
    while found < index:
        candidate += 1
        if is_prime(candidate):
            found += 1
    return candidate


def p9(perimeter=1000):
    """Product abc of the Pythagorean triplet with a+b+c == perimeter."""
    for a in range(1, perimeter):
        for b in range(a + 1, perimeter - a):
            c = perimeter - a - b
            if c <= b:
                break
            if a * a + b * b == c * c:
                return a * b * c
    raise ValueError("no triplet found")


def p10(limit=2_000_000):
    """Sum of all primes below `limit`, via sieve of Eratosthenes."""
    sieve = bytearray([1]) * limit
    sieve[0:2] = b"\x00\x00"
    for i in range(2, int(limit**0.5) + 1):
        if sieve[i]:
            sieve[i * i :: i] = bytearray(len(sieve[i * i :: i]))
    return sum(i for i, is_p in enumerate(sieve) if is_p)


def p12(divisor_count=500):
    """First triangle number with more than `divisor_count` divisors."""
    def num_divisors(n):
        count_ = 1
        d = 2
        while d * d <= n:
            exp = 0
            while n % d == 0:
                n //= d
                exp += 1
            if exp:
                count_ *= exp + 1
            d += 1
        if n > 1:
            count_ *= 2
        return count_

    n = 1
    triangle = 1
    while num_divisors(triangle) <= divisor_count:
        n += 1
        triangle += n
    return triangle


def p14(limit=1_000_000):
    """Starting number below `limit` with the longest Collatz chain."""
    cache = {1: 1}

    def chain_length(n):
        stack = []
        m = n
        while m not in cache:
            stack.append(m)
            m = m // 2 if m % 2 == 0 else 3 * m + 1
        length = cache[m]
        for value in reversed(stack):
            length += 1
            cache[value] = length
        return cache[n]

    return max(range(1, limit), key=chain_length)


def p15(size=20):
    """Lattice paths across a `size` x `size` grid (binomial coefficient)."""
    from math import comb

    return comb(2 * size, size)


def p16(exponent=1000):
    """Digit sum of 2^exponent."""
    return sum(int(d) for d in str(2**exponent))


def p20(n=100):
    """Digit sum of n!."""
    from math import factorial

    return sum(int(d) for d in str(factorial(n)))


def p21(limit=10_000):
    """Sum of all amicable numbers below `limit`."""
    def divisor_sum(n):
        total = 1
        d = 2
        while d * d <= n:
            if n % d == 0:
                total += d
                other = n // d
                if other != d:
                    total += other
            d += 1
        return total if n > 1 else 0

    total = 0
    for a in range(2, limit):
        b = divisor_sum(a)
        if b != a and divisor_sum(b) == a:
            total += a
    return total


def p23(limit=28_123):
    """Sum of positive integers up to `limit` that can't be written as a sum of two abundant numbers."""
    def divisor_sum(n):
        total = 1
        d = 2
        while d * d <= n:
            if n % d == 0:
                total += d
                other = n // d
                if other != d:
                    total += other
            d += 1
        return total if n > 1 else 0

    abundant = [n for n in range(12, limit + 1) if divisor_sum(n) > n]
    can_write = bytearray(limit + 1)
    for i, a in enumerate(abundant):
        if a > limit:
            break
        for b in abundant[i:]:
            total = a + b
            if total > limit:
                break
            can_write[total] = 1
    return sum(n for n in range(1, limit + 1) if not can_write[n])


def p24(digits="0123456789", target=1_000_000):
    """The `target`-th lexicographic permutation of `digits` (1-indexed)."""
    from math import factorial

    remaining = list(digits)
    result = []
    k = target - 1
    n = len(remaining)
    for i in range(n, 0, -1):
        f = factorial(i - 1)
        index, k = divmod(k, f)
        result.append(remaining.pop(index))
    return int("".join(result))


def p25(num_digits=1000):
    """Index of the first Fibonacci term with `num_digits` digits."""
    a, b = 1, 1
    index = 2
    while len(str(b)) < num_digits:
        a, b = b, a + b
        index += 1
    return index


def p26(limit=1000):
    """The denominator d < limit for which 1/d has the longest recurring decimal cycle."""
    def cycle_length(d):
        seen = {}
        remainder = 1 % d
        position = 0
        while remainder != 0 and remainder not in seen:
            seen[remainder] = position
            remainder = (remainder * 10) % d
            position += 1
        return position - seen[remainder] if remainder != 0 else 0

    return max(range(2, limit), key=cycle_length)


def p28(size=1001):
    """Sum of the numbers on the diagonals of a `size`x`size` clockwise number spiral."""
    total = 1
    n = 1
    step = 2
    while step < size:
        for _ in range(4):
            n += step
            total += n
        step += 2
    return total


def p29(a_max=100, b_max=100):
    """Number of distinct terms in a**b for 2 <= a <= a_max, 2 <= b <= b_max."""
    return len({a**b for a in range(2, a_max + 1) for b in range(2, b_max + 1)})
