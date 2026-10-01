"""Release-gate smoke 10 for v1.11.0: a deliberately failing test.

Lives only on the throwaway branch smoke/babysit-1.11.0; never merged.
"""


def test_deliberately_red():
    assert False, "release-gate smoke 10: babysit must fix this"
