from bajo import D, Exit, Label, M, Nop, R

from .helpers import Script, run


def test_smoke():
    l0 = Label()
    l1 = Label()

    # place label at code start,
    # store its address (+ expression) as integer at data region,
    # load it into r1.
    # also place another data (md) and do the same

    md = D(l0 - 1234)

    s = Script(
        [
            l0,
            Nop(),
            Nop(),
            Nop(),
            Nop(),
            R[1].set(M[l1]),
            R[2].set(M[md]),
            Exit(),
            l1,
            D(l0 + 12345),
            md,
            D(md),
        ],
        add_exit=False,
    )

    vm = run(s)
    assert vm.r[1] == s.code_start + 12345
    assert vm.r[2] == s.code_start - 1234
