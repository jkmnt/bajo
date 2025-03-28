from bajo import Add, Exit, Jmp, JmpLnk, Label, Mov, R, Script

from .helpers import run
from .vm import Vm


def test_j():
    end = Label()
    assert run([Mov(R[0], 1234), Jmp(end), Mov(R[0], 5678), end]).r[0] == 1234


def test_call_smoke():
    f = Label()
    lr = R[31]
    vm = run(
        [
            JmpLnk(lr=lr, addr=f),
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
            JmpLnk(lr=lr, addr=f),
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
