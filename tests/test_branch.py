from bajo import (
    Add,
    Br,
    BrEq,
    BrGe,
    BrGeU,
    BrGt,
    BrGtU,
    BrLe,
    BrLeU,
    BrLnk,
    BrLt,
    BrLtU,
    BrNe,
    Exit,
    Jmp,
    Label,
    Mov,
    R,
    Script,
)

from .helpers import run, u32
from .vm import Vm


def test_b():
    end = Label()
    assert run([Mov(R[0], 1234), Br(end), Mov(R[0], 5678), end]).r[0] == 1234


def test_bcmp():
    for a in [0, 1, -1, -0x80000000, 0x7FFFFFFF]:
        for b in [0, 1, -1, -0x80000000, 0x7FFFFFFF]:
            end = Label()
            assert run([Mov(R[0], a), BrEq(addr=end, a=R[0], b=b), Mov(R[0], 5678), end]).r[0] == (
                a if a == b else 5678
            )
            end = Label()
            assert run([Mov(R[0], a), BrNe(addr=end, a=R[0], b=b), Mov(R[0], 5678), end]).r[0] == (
                a if a != b else 5678
            )
            end = Label()
            assert run([Mov(R[0], a), BrGt(addr=end, a=R[0], b=b), Mov(R[0], 5678), end]).r[0] == (a if a > b else 5678)
            end = Label()
            assert run([Mov(R[0], a), BrGe(addr=end, a=R[0], b=b), Mov(R[0], 5678), end]).r[0] == (
                a if a >= b else 5678
            )
            end = Label()
            assert run([Mov(R[0], a), BrLt(addr=end, a=R[0], b=b), Mov(R[0], 5678), end]).r[0] == (a if a < b else 5678)
            end = Label()
            assert run([Mov(R[0], a), BrLe(addr=end, a=R[0], b=b), Mov(R[0], 5678), end]).r[0] == (
                a if a <= b else 5678
            )
            # unsigneds
            end = Label()
            assert run([Mov(R[0], a), BrGtU(addr=end, a=R[0], b=b), Mov(R[0], 5678), end]).r[0] == (
                a if u32(a) > u32(b) else 5678
            )
            end = Label()
            assert run([Mov(R[0], a), BrGeU(addr=end, a=R[0], b=b), Mov(R[0], 5678), end]).r[0] == (
                a if u32(a) >= u32(b) else 5678
            )
            end = Label()
            assert run([Mov(R[0], a), BrLtU(addr=end, a=R[0], b=b), Mov(R[0], 5678), end]).r[0] == (
                a if u32(a) < u32(b) else 5678
            )
            end = Label()
            assert run([Mov(R[0], a), BrLeU(addr=end, a=R[0], b=b), Mov(R[0], 5678), end]).r[0] == (
                a if u32(a) <= u32(b) else 5678
            )


def test_call_smoke():
    f = Label()
    lr = R[31]
    vm = run(
        [
            BrLnk(lr=lr, addr=f),
            Add(R[0], R[1], 20),
            Exit(),
            f,
            Mov(R[1], 10),
            Jmp(lr),  # return
        ]
    )

    assert vm.r[0] == 30


def test_call():
    f = Label()
    lr = R[31]
    script = Script(
        [
            BrLnk(lr=lr, addr=f),
            ret := Mov(R[2], 1234),  # return address
            f,
            Mov(R[1], 5678),
            Exit(),
        ]
    )
    expected_lr = ret.addr_from(script.layout)

    vm = Vm.from_script(script)
    vm.run()
    assert vm[R[2]] == 0
    assert vm[R[1]] == 5678
    assert vm.ru[31] == expected_lr
