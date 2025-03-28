import random
from typing import Final, Iterable, Iterator, Mapping, overload

from .asm import Align, Directive, Label, NoPad
from .core import Inst, Nop
from .env import Env
from .exc import AddrError, BuildError, DetachedLabelError, DuplicateDefError, MissingDefError

# Monkeypatched by tests
_FIX_OSCILLATIONS = True
_VERIFY_ADDRS = True


# This context class is seems to be slow.
# To be optimized later after gaining more understanding of the assembly quirks
# Now it's a struct completely describing the code layout - i.e. code may rendered with different
# contexts and compared
class BuildCtx:
    def __init__(self, env: Env):
        self.env: Final = env
        # populated pre-build
        self.labels_by_inst: dict[Label, Inst] = {}
        self.insts: list[Inst] = []
        # dynamic mappings Inst->int populated during the build
        self.addrs: dict[Inst, int] = {}
        self.sizes: dict[Inst, int] = {}
        self.aligns: dict[Inst, int] = {}
        self.nopads: set[Inst] = set()

    def __iter__(self) -> Iterator[Inst]:
        yield from self.insts

    @overload
    def __getitem__(self, obj: int, /) -> Inst: ...

    @overload
    def __getitem__(self, obj: Inst | Label | str, /) -> int: ...

    def __getitem__(self, obj: Inst | Label | str | int, /) -> int | Inst:
        if isinstance(obj, int):
            return self.insts_by_addr[obj]
        return self.addrof(obj)

    def addrof(self, obj: Inst | Label | str | int, /) -> int:
        if isinstance(obj, Inst):
            try:
                return self.addrs[obj]
            except KeyError as e:
                raise MissingDefError("No instruction", obj) from e
        if isinstance(obj, Label):
            try:
                return self.addrs[self.labels_by_inst[obj]]
            except KeyError as e:
                raise MissingDefError("No label", obj) from e
        # this one is slow !
        if isinstance(obj, str):
            try:
                return self.addrs[self.labels_by_name[obj]]
            except KeyError as e:
                raise MissingDefError("No label", obj) from e

        # check if address is valid: operands may use it
        if isinstance(obj, int):
            if self.code_range[0] <= obj < self.code_range[1]:
                return obj
            if self.env.ram_region[0] <= obj < self.env.ram_region[1]:
                return obj
            raise AddrError("Address outside of any region", obj)
        #
        raise TypeError("Unsupported object type", obj)

    def sizeof(self, obj: Inst, /) -> int:
        return self.sizes[obj]

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, BuildCtx):
            return NotImplemented
        return self.addrs == other.addrs

    def clone(self):
        clone = BuildCtx(self.env)
        clone.labels_by_inst = self.labels_by_inst.copy()  # won't be changed in fact
        clone.insts = self.insts.copy()
        clone.addrs = self.addrs.copy()
        clone.sizes = self.sizes.copy()
        clone.aligns = self.aligns.copy()
        clone.nopads = self.nopads.copy()

        return clone

    def is_code(self, addr: int):
        region = self.code_range
        return region[0] <= addr < region[1]

    def is_ram(self, addr: int):
        region = self.env.ram_region
        return region[0] <= addr < region[1]

    def check(self):
        used = self.code_range
        avail = self.env.code_region
        if not (avail[0] <= used[1] - 1 < avail[1]):
            raise AddrError("Available code range overflow", used, avail)
        for inst in self.insts:
            inst.check_against(self)

    @property
    def code_range(self) -> tuple[int, int]:
        """Code [start, end)"""
        first = self.insts[0]
        last = self.insts[-1]
        return (self.addrs[first], self.addrs[last] + self.sizes[last])

    @property
    def size(self):
        """Code size"""
        region = self.code_range
        return region[1] - region[0]

    @property
    def labels_by_name(self) -> dict[str, Inst]:
        """
        Return mapping of label name -> instruction.
        Useful for marking entry points and passing them to the loader.
        """
        return {lab.name: inst for lab, inst in self.labels_by_inst.items()}

    @property
    def insts_by_addr(self) -> dict[int, Inst]:
        return {addr: inst for inst, addr in self.addrs.items()}

    @property
    def labels_by_insts(self) -> dict[Inst, list[Label]]:
        # slow, but it's should be called just once for listing
        out: dict[Inst, list[Label]] = {}
        labels = self.labels_by_inst.items()
        for inst in self.insts:
            out[inst] = [k for k, v in labels if v == inst]
        return out

    @property
    def named_registers(self) -> Mapping[str, int]:
        return self.env.named_registers


def check(code: Iterable[Inst | Label | Directive]):
    dupeset: set[Label | Inst] = set()
    insts_and_labels = [item for item in code if isinstance(item, (Inst, Label))]
    for obj in insts_and_labels:
        if obj in dupeset:
            raise DuplicateDefError("Object is placed twice", obj)
        dupeset.add(obj)
    if insts_and_labels and isinstance(last_label := insts_and_labels[-1], Label):
        raise DetachedLabelError("Label must be followed by instruction", last_label)


# it's the simple algo better implemented as a big function.
# the flow is:
# - 1) associate labels
# - 2) obtain align directives
# - 3) assign (pessimistic) addresses and sizes to the instructions
# - 4) iteratively resolve while waiting for Converge (there won'be stagediving, sorry).
#   three last passes must result in same layout.
# - 5) if failed to find the solution due to oscillations, align(4) some randomly choosen instruction
#   and try again.
# - 6) fill the gaps left by aligns with 1-byte nops
def build(code: Iterable[Inst | Label | Directive], env: Env):
    lay = BuildCtx(env)

    start = env.code_region[0]

    pending_labels: set[Label] = set()
    pending_align = None
    pending_nopad = None

    # 1), 2)
    p = start
    for obj in code:
        if isinstance(obj, Label):
            pending_labels.add(obj)
        elif isinstance(obj, Directive):
            if isinstance(obj, Align):
                pending_align = obj.n
            elif isinstance(obj, NoPad):
                pending_nopad = True
        else:
            lay.addrs[obj] = p
            size = obj.max_size()
            lay.sizes[obj] = size
            p += size
            if pending_align:
                lay.aligns[obj] = pending_align
                pending_align = None
            if pending_nopad:
                lay.nopads.add(obj)
                pending_nopad = None
            for lab in pending_labels:
                lay.labels_by_inst[lab] = obj
            pending_labels.clear()

    # set it here once
    lay.insts = [item for item in code if isinstance(item, Inst)]
    passes: list[BuildCtx] = []

    rnd: random.Random | None = None

    next_fix_thres = env.max_passes
    remaining_fixes = env.max_passes if _FIX_OSCILLATIONS else 0

    # 3)
    # The loop logic is kinda hard to follow. Need to refactor it.
    while True:
        p = start
        for inst in lay.insts:
            p += -p % lay.aligns.get(inst, 1)
            lay.addrs[inst] = p
            size = inst.size_from(lay)
            lay.sizes[inst] = size
            p += size
        passes.append(lay)

        if len(passes) >= 3 and passes[-1] == passes[-2] == passes[-3]:
            break

        lay = lay.clone()

        # 4)
        if len(passes) >= next_fix_thres:
            if remaining_fixes:
                # Insert random Align(4) to break the oscillations and restart search.
                # Random is seeded to make the builds reproducible (at least on the same platform)
                # search the same number of attempts.
                remaining_fixes -= 1
                next_fix_thres += env.max_passes
                rnd = rnd or random.Random(42)
                fixed = lay.nopads | lay.aligns.keys()
                candidates_for_align = [inst for inst in lay.insts if inst not in fixed]
                if candidates_for_align:
                    align_it = rnd.choice(candidates_for_align)
                    lay.aligns[align_it] = 4
                    continue
            raise BuildError("Failed to converge", [it.size for it in passes])

    # 5)
    if lay.aligns:
        # NOTE: the addresses dict is not in instruction (insertion) order no longer
        patched: list[Inst] = []
        p = start
        for inst in lay.insts:
            assigned_addr = lay.addrs[inst]
            while p < assigned_addr:
                nop = Nop()
                patched.append(nop)
                lay.addrs[nop] = p
                size = nop.size_from(lay)
                assert size == 1
                lay.sizes[nop] = size
                p += size
            patched.append(inst)
            p = assigned_addr + inst.size_from(lay)
        # rough patch !
        lay.insts = patched

    if _VERIFY_ADDRS:
        lay.check()

    return lay
