from bajo import Exit, Label, R, Script
from bajo.macro import Subroutine, when

from .helpers import run


def test_recursive():
    # stack is at 1000.
    # 16 registers.
    # one lr register is pushed per iteration.
    # 1000 / 4 - 16 = 234
    #
    # run 234 times
    #
    # at the end sp must point back to 1000
    #
    # declaration
    sub = Subroutine()
    sub.define(
        [
            R[0].set(R[0] + 1),
            when(R[0] < 234, sub.call()),
        ],
    )

    vm = run(
        [
            R["sp"].set(1000),
            sub(),
            Exit(),
            sub,
        ]
    )

    assert vm.r[0] == 234
    assert vm[R[13]] == 1000


def test_w_store():
    sp = R["sp"]
    sub = Subroutine()
    sub.define(
        [
            R[0].set(R[0] + 1),
            R[1].set(111),
            R[2].set(333),
            when(R[0] < 8, sub.call()),
        ],
        save_regs=[R[1], R[2], R[3], R[4]],
    )

    vm = run(
        [
            sp.set(1000),
            R[1].set(1),
            R[2].set(2),
            sub(),
            Exit(),
            sub,
        ]
    )

    assert vm[R[0]] == 8
    assert vm[R[1]] == 1
    assert vm[R[2]] == 2
    assert vm[R[13]] == 1000


def test_leaf():
    sp = R["sp"]
    sub = Subroutine()

    vm = run(
        [
            sp.set(1000),
            R[1].set(1),
            R[2].set(2),
            sub(),
            Exit(),
            sub.define(
                R[0].set(R[0] + 1),
                is_leaf=True,
                save_regs=[R[0], R[1], R[2], R[3], R[4]],
            ),
        ]
    )

    assert vm[R[0]] == 0
    assert vm[R[13]] == 1000


def test_leaf2():
    s0 = Subroutine("sub1").define(R[0].set(1234), is_leaf=True)
    # a lot of duplicate saves with ram overlow. Subroutine should dedup.
    s1 = Subroutine("sub2").define(R[1].set(R[0] + 1), save_regs=[R[2] for i in range(1000)], is_leaf=True)
    s2 = Subroutine("sub3").define(R[1].set(R[1] + 2), is_leaf=True)

    s = Script(
        [
            Label("start"),
            R["sp"].set(1000),
            s0(),
            s1(),
            s2(),
            s2(),
            Exit(),
            s0.code,
            s1.code,
            s2.code,
        ]
    )

    vm = run(s)

    assert vm[R[0]] == 1234
    assert vm[R[1]] == 1239
    assert vm[R[13]] == 1000
