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


def p30(power=5):
    """Sum of all numbers equal to the sum of the `power`-th power of their digits."""
    upper = (power + 1) * 9**power
    return sum(n for n in range(10, upper) if n == sum(int(d)**power for d in str(n)))


def p19(start_year=1901, end_year=2000):
    """Number of Sundays falling on the first of the month in [start_year, end_year]."""
    import datetime

    return sum(
        datetime.date(year, month, 1).weekday() == 6
        for year in range(start_year, end_year + 1)
        for month in range(1, 13)
    )


def p31(target=200, coins=(1, 2, 5, 10, 20, 50, 100, 200)):
    """Number of ways to make `target` (in pence) using the given UK coins."""
    ways = [1] + [0] * target
    for coin in coins:
        for amount in range(coin, target + 1):
            ways[amount] += ways[amount - coin]
    return ways[target]


def p32():
    """Sum of all products expressible as a 1-9 pandigital multiplicand/multiplier/product identity."""
    from itertools import permutations

    products = set()
    digits = "123456789"
    for perm in permutations(digits):
        s = "".join(perm)
        for i in range(1, 5):
            for j in range(i + 1, 8):
                a, b, c = s[:i], s[i:j], s[j:]
                if len(c) < 4:
                    continue
                if int(a) * int(b) == int(c):
                    products.add(int(c))
    return sum(products)


def p33():
    """Denominator (lowest terms) of the product of the four non-trivial
    two-digit "digit canceling" fractions less than one."""
    from fractions import Fraction

    matches = []
    for d in range(10, 100):
        for n in range(10, d):
            n1, n2 = divmod(n, 10)
            d1, d2 = divmod(d, 10)
            if n2 == 0 and d2 == 0:
                continue
            nd, dd = [n1, n2], [d1, d2]
            for i in range(2):
                for j in range(2):
                    if nd[i] == dd[j] and nd[i] != 0:
                        rem_n, rem_d = nd[1 - i], dd[1 - j]
                        if rem_d != 0 and Fraction(n, d) == Fraction(rem_n, rem_d):
                            matches.append((n, d))

    product = Fraction(1, 1)
    for n, d in matches:
        product *= Fraction(n, d)
    return product.denominator


def p34():
    """Sum of all numbers equal to the sum of the factorial of their digits."""
    from math import factorial

    fact = [factorial(d) for d in range(10)]

    def digit_factorial_sum(n):
        total = 0
        while n:
            n, d = divmod(n, 10)
            total += fact[d]
        return total

    # 7 digits * 9! = 2540160 is a safe upper bound.
    return sum(n for n in range(10, 2540160) if digit_factorial_sum(n) == n)


def p35(limit=1_000_000):
    """Count circular primes below limit."""
    is_p = bytearray([1]) * limit
    is_p[0] = is_p[1] = 0
    for i in range(2, int(limit**0.5) + 1):
        if is_p[i]:
            for j in range(i * i, limit, i):
                is_p[j] = 0
    primes = set(i for i in range(2, limit) if is_p[i])

    def rotations(n):
        s = str(n)
        return [int(s[i:] + s[:i]) for i in range(len(s))]

    return sum(1 for p in primes if all(r in primes for r in rotations(p)))


def p36(limit=1_000_000):
    """Sum of numbers below limit that are palindromic in base 10 and base 2."""

    def is_pal(s):
        return s == s[::-1]

    return sum(n for n in range(1, limit) if is_pal(str(n)) and is_pal(bin(n)[2:]))


def p37(count=11):
    """Sum of the primes that are truncatable from both left and right."""
    limit = 1_000_000
    is_p = bytearray([1]) * (limit + 1)
    is_p[0] = is_p[1] = 0
    for i in range(2, int(limit**0.5) + 1):
        if is_p[i]:
            for j in range(i * i, limit + 1, i):
                is_p[j] = 0

    def truncatable(n):
        s = str(n)
        left = [int(s[i:]) for i in range(len(s))]
        right = [int(s[:i]) for i in range(1, len(s) + 1)]
        return all(is_p[x] for x in left) and all(is_p[x] for x in right)

    found = []
    n = 11
    while len(found) < count:
        n += 2
        if is_p[n] and truncatable(n):
            found.append(n)

    return sum(found)


def p38(digits=9):
    """Largest 1-to-`digits` pandigital number formed as a concatenated
    product of an integer with (1, 2, ..., n) for some n > 1."""
    target = set(str(i) for i in range(1, digits + 1))

    best = 0
    for base in range(1, 10 ** ((digits // 2) + 1)):
        s = ""
        k = 1
        while len(s) < digits:
            s += str(base * k)
            k += 1
        if len(s) == digits and set(s) == target and int(s) > best:
            best = int(s)

    return best


def p39(limit=1000):
    """The perimeter p <= limit for which the number of integer right
    triangles {a,b,c} with a+b+c = p is maximised."""
    counts = [0] * (limit + 1)
    for a in range(1, limit // 3 + 1):
        for b in range(a, (limit - a) // 2 + 1):
            c_sq = a * a + b * b
            c = int(c_sq**0.5)
            if c * c == c_sq:
                p = a + b + c
                if p <= limit:
                    counts[p] += 1

    return max(range(1, limit + 1), key=lambda p: counts[p])


def p40():
    """Product of the digits dn of Champernowne's constant at positions
    n = 1, 10, 100, 1000, 10000, 100000, 1000000."""
    positions = [1, 10, 100, 1000, 10000, 100000, 1000000]
    target = max(positions)

    digits = []
    i = 1
    while len(digits) < target:
        digits.extend(str(i))
        i += 1

    product = 1
    for n in positions:
        product *= int(digits[n - 1])

    return product


def _is_prime(n):
    if n < 2:
        return False
    i = 2
    while i * i <= n:
        if n % i == 0:
            return False
        i += 1
    return True


def p41(max_digits=9):
    """Largest n-digit pandigital (uses digits 1..n exactly once) prime,
    for n up to `max_digits`."""
    from itertools import permutations

    best = 0
    for length in range(1, max_digits + 1):
        digits = [str(d) for d in range(1, length + 1)]
        for perm in permutations(digits):
            n = int("".join(perm))
            if n > best and _is_prime(n):
                best = n
    return best


def p43():
    """Sum of all 0-to-9 pandigital numbers with the sub-string
    divisibility property: d2d3d4 % 2 == 0, d3d4d5 % 3 == 0, and so on
    through d8d9d10 % 17 == 0."""
    from itertools import permutations

    primes = (2, 3, 5, 7, 11, 13, 17)
    total = 0
    for perm in permutations("0123456789"):
        if perm[0] == "0":
            continue
        if all(
            int("".join(perm[i + 1 : i + 4])) % primes[i] == 0 for i in range(7)
        ):
            total += int("".join(perm))
    return total


def p42():
    """How many words in the bundled 0042_words.txt are "triangle
    words" — words whose letter-value sum (A=1, B=2, ...) equals some
    triangle number t(n) = n(n+1)/2?"""
    import math
    import re
    from pathlib import Path

    words_path = Path(__file__).parent / "resources" / "p042_words.txt"
    words = re.findall(r'"([A-Z]+)"', words_path.read_text())

    def is_triangle(n):
        t = round((-1 + math.sqrt(1 + 8 * n)) / 2)
        return t * (t + 1) // 2 == n

    return sum(1 for w in words if is_triangle(sum(ord(c) - 64 for c in w)))


def p44(limit=3000):
    """Find the minimal D = |Pk - Pj| for pentagonal numbers Pj, Pk
    where both their sum and difference are also pentagonal."""

    def is_pentagonal(x):
        n = (1 + (1 + 24 * x) ** 0.5) / 6
        n = round(n)
        return n > 0 and n * (3 * n - 1) // 2 == x

    pent = [n * (3 * n - 1) // 2 for n in range(1, limit)]
    pentset = set(pent)

    best = None
    for i in range(len(pent)):
        for j in range(i + 1, len(pent)):
            a, b = pent[i], pent[j]
            if (a + b) in pentset and is_pentagonal(abs(a - b)):
                d = abs(a - b)
                if best is None or d < best:
                    best = d
    return best


def p45():
    """Find the next triangle number after T(285)=40755 that is also
    pentagonal and hexagonal."""

    def is_pentagonal(x):
        d = 1 + 24 * x
        s = int(d**0.5)
        while s * s < d:
            s += 1
        while s * s > d:
            s -= 1
        return s * s == d and (1 + s) % 6 == 0

    def is_hexagonal(x):
        d = 1 + 8 * x
        s = int(d**0.5)
        while s * s < d:
            s += 1
        while s * s > d:
            s -= 1
        return s * s == d and (1 + s) % 4 == 0

    n = 285
    while True:
        n += 1
        t = n * (n + 1) // 2
        if is_pentagonal(t) and is_hexagonal(t):
            return t


def p46():
    """Smallest odd composite that cannot be written as the sum of a
    prime and twice a square."""

    def is_prime(x):
        if x < 2:
            return False
        if x % 2 == 0:
            return x == 2
        i = 3
        while i * i <= x:
            if x % i == 0:
                return False
            i += 2
        return True

    def has_goldbach_form(n):
        k = 1
        while 2 * k * k < n:
            if is_prime(n - 2 * k * k):
                return True
            k += 1
        return False

    n = 9
    while True:
        n += 2
        if is_prime(n):
            continue
        if not has_goldbach_form(n):
            return n


def p47(target=4, limit=200000):
    """First of the first `target` consecutive integers that each have
    `target` distinct prime factors."""

    spf = list(range(limit + 1))
    for i in range(2, int(limit**0.5) + 1):
        if spf[i] == i:
            for j in range(i * i, limit + 1, i):
                if spf[j] == j:
                    spf[j] = i

    def num_distinct_prime_factors(n):
        count = 0
        prev = -1
        while n > 1:
            p = spf[n]
            if p != prev:
                count += 1
                prev = p
            n //= p
        return count

    run = 0
    for n in range(2, limit + 1):
        if num_distinct_prime_factors(n) == target:
            run += 1
            if run == target:
                return n - target + 1
        else:
            run = 0


def p48(count=1000, digits=10):
    """Last `digits` digits of the sum 1^1 + 2^2 + ... + count^count."""

    mod = 10**digits
    return sum(pow(n, n, mod) for n in range(1, count + 1)) % mod
