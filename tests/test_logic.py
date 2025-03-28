from bajo import And, Bool, Not, Or, Or2, R

from .helpers import run


# pytest.mark.parametrize is awfully slow, doing it manually
def test_logic():
    for a in [0, 1, 10, -10, -0x80000000, 0x7FFFFFFF]:
        for b in [0, 1, 10, -10, -0x80000000, 0x7FFFFFFF]:
            assert run(And(R[0], a, b)).r[0] == (a and b)
            assert run(Or2(R[0], a, b)).r[0] == (a or b)
            assert run(Not(R[0], a)).r[0] == (not a)
            assert run(Bool(R[0], a)).r[0] == bool(a)

    for a in [0, 1, 10, -10, -0x80000000, 0x7FFFFFFF]:
        for b in [0, 1, 10, -10, -0x80000000, 0x7FFFFFFF]:
            for c in [0, 1, 10, -10, -0x80000000, 0x7FFFFFFF]:
                for d in [0, 1, 10, -10, -0x80000000, 0x7FFFFFFF]:
                    assert run(And(R[0], a, b, c, d)).r[0] == (a and b and c and d)
                    assert run(Or(R[0], a, b, c, d)).r[0] == (a or b or c or d)

    # these should apply rmw compression and still be ok
    assert run([R[0].set(0), Or(R[0], R[0])]).r[0] == 0
    assert run([R[0].set(0), Or(R[0], R[0], 10)]).r[0] == 10
    assert run([R[0].set(0), Or(R[0], R[0], R[0], R[0], R[0], R[0], R[0], 10)]).r[0] == 10
