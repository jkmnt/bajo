from bajo import Exit, Jmp, JmpLnk, Label, R, Script

from .helpers import run
from .vm import Vm


def test_call_smoke():
    f = Label()
    lr = R[31]
    vm = run(
        [
            JmpLnk(lr=lr, addr=f),
            R[0].set(R[1] + 20),
            Exit(),
            f,
            R[1].set(10),
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
            reta := R[2].set(1234),  # remember return address
            f,
            R[1].set(5678),
            Exit(),
        ]
    )
    expected_lr = reta.addr_from(script.layout)

    vm = Vm.from_script(script)
    vm.run()
    assert vm[R[2]] == 0
    assert vm[R[1]] == 5678
    assert vm.ru[31] == expected_lr
