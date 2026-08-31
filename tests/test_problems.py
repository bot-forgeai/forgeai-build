import eulerlib

EXPECTED = {
    "p1": 233168,
    "p2": 4613732,
    "p3": 6857,
    "p4": 906609,
    "p5": 232792560,
    "p6": 25164150,
    "p7": 104743,
    "p9": 31875000,
    "p10": 142913828922,
    "p12": 76576500,
    "p14": 837799,
    "p15": 137846528820,
    "p16": 1366,
    "p19": 171,
    "p20": 648,
    "p21": 31626,
    "p23": 4179871,
    "p24": 2783915460,
    "p25": 4782,
    "p26": 983,
    "p28": 669171001,
    "p29": 9183,
    "p30": 443839,
    "p31": 73682,
}


def test_all_problems_have_expected_answers():
    assert set(EXPECTED) == set(eulerlib.__all__)


def make_test(name, expected):
    def test(name=name, expected=expected):
        fn = getattr(eulerlib, name)
        assert fn() == expected

    test.__name__ = f"test_{name}"
    return test


for _name, _expected in EXPECTED.items():
    globals()[f"test_{_name}"] = make_test(_name, _expected)
