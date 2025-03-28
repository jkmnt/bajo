from bajo import Bytes, Exit, Label, M, Mov, R

from .helpers import makevm


def test_ref():
    lab = Label()
    v = makevm(
        [
            R[0].set(lab),
            Mov(R[1], M[R[0]]),
            R[2].set(M[lab]),
            R[3].set(M[lab + 2]),
            Exit(),
            lab,
            Bytes.from32(-2),
            Bytes.from16(0x1234),
            # Nop(),
        ]
    )
    v.run()
    assert v.r[1] == -2
    assert v.r[2] == -2
    assert v.ru[3] == 0x1234FFFF
