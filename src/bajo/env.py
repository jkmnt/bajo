from typing import Mapping


class Env:
    def __init__(
        self,
        *,
        ram_region: tuple[int, int],
        code_region: tuple[int, int],
        named_registers: Mapping[str, int],
        max_passes: int = 16,
    ):
        c = code_region
        r = ram_region

        if c[0] > c[1]:
            raise ValueError("Bad code region", c)
        if r[0] > r[1]:
            raise ValueError("Bad ram region", r)
        if c[0] <= r[0] < c[1] or c[0] <= r[1] - 1 < c[1]:
            raise ValueError("Memory regions overlap", r, c)

        # not strictly required, but nice to have
        if r[0] % 4 or r[1] % 4:
            raise ValueError("Ram range must be word-aligned", r)

        if max_passes < 3:
            raise ValueError("At least 3 build passes are required", max_passes)

        self.ram_region = r
        self.code_region = c
        self.max_passes = max_passes
        self.named_registers = named_registers
