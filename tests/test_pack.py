from bajo import Align, D, Label, R, Script
from bajo.asm import NoPad
from bajo.core import Inst
from bajo.macro import pack
from bajo.script import flat_code


def test_pack():
    orig = [
        R[0].set(11),
        pack(
            [
                R[0].set(12),
                R[1].set(13),
                Label(),
                Label(),
                D(1234),
                Label(),
                R[0].set(14),
                Align(1),
                Align(1),
                Align(1),
                Align(1),
                R[0].set(14),
            ]
        ),
        R[0].set(12),
    ]

    # just build
    _ = Script(orig).result

    cooked = [
        Inst,
        NoPad,
        Inst,
        NoPad,
        Inst,
        Label,
        Label,
        NoPad,
        Inst,
        Label,
        NoPad,
        Inst,
        Align,
        Align,
        Align,
        Align,
        NoPad,
        Inst,
        Inst,
    ]
    assert all(isinstance(a, t) for a, t in zip(flat_code(orig), cooked, strict=False)), orig
