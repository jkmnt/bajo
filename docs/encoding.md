# VM instructions encoding

## General format:

```
mopcode | [targets operands count] | target operands | [source operands count] | source operands
```

Counts are included only for instructions with the variable number of operands.

## Mopcode

The mopcode stands for m + opcode:

`mooooooo`

The mopcode packs 7 bits of the opcode
`o` and the optional flag `m` into one byte.

Assembler sets the flag `m` if the first source is the same as the [first], target and thus omitted. Instructions such as `Add R0, R0, #10` use this optimization.

## Operands

The operand value `x` is encoded as the little-endian prefix varint.

The head byte carries the varint size and a few least significant bits of the value.
The head is followed by up to 4 tail bytes.

|  Head byte | Varint size, bits | Encoded size, bytes | Tail size, bytes |
| ---------: | ----------------- | ------------------- | ---------------- |
| `xxxxxxx1` | 7                 | 1                   | 0                |
| `xxxxxx10` | 14                | 2                   | 1                |
| `xxxxx100` | 21                | 3                   | 2                |
| `xxxx1000` | 28                | 4                   | 3                |
| `xxx10000` | 35                | 5                   | 4                |

### Source

The source operand value `x` packs the integer `v` with `mode` prefix bits.

|  Code | Mode                             | Action                                              |
| ----: | -------------------------------- | --------------------------------------------------- |
|  `00` | Positive or zero immediate const | t = v                                               |
|  `10` | Negative immediate constant      | t = ~v                                              |
| `001` | Direct word address              | t = mem\[v \* 4\]                                   |
| `101` | Direct byte address              | t = mem\[v\]                                        |
| `011` | Indirect word address            | base = mem\[v \* 4\], <br> t = mem\[base + offset\] |
| `111` | Indirect byte address            | base = mem\[v\],<br>t = mem\[base + offset\]        |

In indirect mode, the base address operand is implicitly followed by the offset. The offset is encoded as the source operand.

```
base | offset
```

The offset operand may be indirect too, effectively forming the pointer chain.

The longest possible prefix varint is 5 bytes.

### Target

The target operand is encoded almost the same as the source one, except there is no immediate mode.

Mode bits:

| Code | Mode                  | Action                                            |
| ---: | --------------------- | ------------------------------------------------- |
| `00` | Direct word address   | mem\[v \* 4\] = t                                 |
| `10` | Direct byte address   | mem\[v\] = t                                      |
| `01` | Indirect word address | base = mem\[v \* 4\],<br>mem\[base + offset\] = t |
| `11` | Indirect byte address | base = mem\[v\],<br>mem\[base + offset\] = t      |

The offset is encoded as the source operand.

## Counts

Operand counts are encoded as source operands.
