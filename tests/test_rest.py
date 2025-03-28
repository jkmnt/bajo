from bajo import Exit, Nop, R, Script

from .helpers import run
from .vm import Vm


def test_nop():
    vm = run([Nop(), R[1].set(1), Nop(), Nop(), R[2].set(2), Nop()])
    assert vm[R[1]] == 1
    assert vm[R[2]] == 2


def test_exit():
    script = Script([Nop(), R[1].set(1), Exit(-12345678), end := Nop(), R[2].set(2), Nop()])
    vm = Vm.from_script(script)
    rc = vm.run()
    assert vm.pc == end.addr_from(script.layout)
    assert rc == -12345678
