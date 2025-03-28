import random

from bajo import Add, M, Mov, R, Script
from bajo.core import encode_varint

from .helpers import no_addr_verify, u32_ok


def test_max_imm():
    with u32_ok(), no_addr_verify():
        Script(Mov(M[0xFFFFFFFF], 0xFFFFFFFF)).encode()
        Script(Mov(M[M[0xFFFFFFFF]], 0xFFFFFFFF)).encode()
        Script(Mov(M[R[0xFFFFFFFF // 4]], 0xFFFFFFFF)).encode()


def _decode_prefix_varint(a: bytes):
    val = int.from_bytes(a, "little", signed=False)
    if val & 0b1:
        return val >> 1
    if val & 0b10:
        return val >> 2
    if val & 0b100:
        return val >> 3
    if val & 0b1000:
        return val >> 4
    return val >> 5


def test_decode_prefix_varint():
    for a in [
        0,
        1,
        2**7 - 1,
        2**7,
        2**14 - 1,
        2**14,
        2**21 - 1,
        2**21,
        2**28 - 1,
        2**28,
        2**35 - 1,
        (0xFFFFFFFF << 3) | 0x7,
        *(random.randint(0, 2**35 - 1) for _ in range(2048)),
    ]:
        e = encode_varint(a)
        assert _decode_prefix_varint(e) == a


def test_rmw():
    a = Script(Mov(R[0], R[0])).encode()
    b = Script(Mov(R[0], R[1])).encode()

    assert len(a) < len(b)
    assert a[0] & 0x80
    assert not (b[0] & 0x80)

    a = Script(Add(R[0], R[0], 10)).encode()
    b = Script(Add(R[0], R[1], 10)).encode()

    assert len(a) < len(b)
    assert a[0] & 0x80
    assert not (b[0] & 0x80)
