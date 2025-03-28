# VM instructions

| Name | Code | Operands | Action |
|---|---|---|---|
| Nop | 0 | \-\-\- | no operation |
| Add | 1 | t, a, b | t = a \+ b |
| Sub | 2 | t, a, b | t = a \- b |
| Mul | 3 | t, a, b | t = a \* b |
| Div | 4 | t, a, b | t = a / b<br>truncating division |
| DivU | 5 | t, a, b | t = a / b<br>_unsigned_<br>truncating division |
| Rem | 6 | t, a, b | t = a % b<br>remainder of the truncating division |
| RemU | 7 | t, a, b | t = a % b<br>_unsigned_<br>remainder of the truncating division |
| And | 8 | t, n, s\[0\], \.\.\., s\[n\-1\] | t = s\[0\] && \.\.\. && s\[n\-1\]\)<br>result is the last arg if all args are truthy, otherwise 0 |
| Or | 9 | t, n, s\[0\], \.\.\., s\[n\-1\] | t = s\[0\] \|\| \.\.\. \|\| s\[n\-1\]\)<br>result is the first truthy arg, otherwise 0 |
| BitAnd | 10 | t, a, b | t = a & b |
| BitOr | 11 | t, a, b | t = a \| b |
| BitXor | 12 | t, a, b | t = a ^ b |
| Inv | 13 | t, a | t = ~a |
| LShift | 14 | t, a, b | t = a << b<br>b is limited to 32 |
| RShift | 15 | t, a, b | t = a >> b<br>b is limited to 31 |
| RShiftU | 16 | t, a, b | t = a >> b<br>_unsigned_<br>b is limited to 32 |
| TstEq | 17 | t, a, b | t = a == b |
| TstNe | 18 | t, a, b | t = a \!= b |
| TstGt | 19 | t, a, b | t = a > b |
| TstGe | 20 | t, a, b | t = a >= b |
| TstGtU | 21 | t, a, b | t = a > b<br>_unsigned_ |
| TstGeU | 22 | t, a, b | t = a >= b<br>_unsigned_ |
| Jmp | 23 | addr | pc = addr |
| JmpLnk | 24 | lr, addr | lr = pc, pc = addr<br>call |
| Br | 25 | offset | pc \+= offset |
| BrLnk | 26 | lr, offset | lr = pc, pc \+= offset<br>call |
| BrEq | 27 | a, b, offset | if a == b then pc \+= offset |
| BrNe | 28 | a, b, offset | if a \!= b then pc \+= offset |
| BrGt | 29 | a, b, offset | if a > b then pc \+= offset |
| BrGe | 30 | a, b, offset | if a >= b then pc \+= offset |
| BrGtU | 31 | a, b, offset | if a > b then pc \+= offset<br>_unsigned_ |
| BrGeU | 32 | a, b, offset | if a >= b then pc \+= offset<br>_unsigned_ |
| MovEq | 33 | t, a, b, x, y | t = a == b ? x : y |
| MovGt | 34 | t, a, b, x, y | t = a > b ? x : y |
| MovGe | 35 | t, a, b, x, y | t = a >= b ? x : y |
| MovGtU | 36 | t, a, b, x, y | t = a > b ? x : y<br>_unsigned_ |
| MovGeU | 37 | t, a, b, x, y | t = a >= b ? x : y<br>_unsigned_ |
| LdB | 38 | t, a | t = sign\_extend\(a\[b7\.\.b0\]\)<br>load byte |
| LdH | 39 | t, a | t = sign\_extend\(a\[b15\.\.b0\]\)<br>load halfword |
| LdBU | 40 | t, a | t = zero\_extend\(a\[b7\.\.b0\]\)<br>_unsigned_<br>load byte |
| LdHU | 41 | t, a | t = zero\_extend\(a\[b15\.\.b0\]\)<br>_unsigned_<br>load halfword |
| StB | 42 | t, a | t\[b7\.\.b0\] = a\[b7\.\.b0\]<br>store byte to 8 lsbits of t\. other bits are unchanged |
| StH | 43 | t, a | t\[b15\.\.b0\] = a\[b15\.\.b0\]<br>store harfword to 16 lsbits of t\. other bits are unchanged |
| Sys | 44 | m, t\[0\], \.\.\., t\[m\-1\], n\+1, func, s\[0\], \.\.\., s\[n\-1\] | t\[0\] \.\.\. t\[m\-1\] = sysfuncs\[func\]\(s\[0\], \.\.\., s\[n\-1\]\)<br>call host function `func` with arg vector `s` of len `n` and result vector `t` of size `m` |
| Exit | 45 | a | exit rc = a<br>sets errcode = 1 to be catched by host, sets exit rc |
| Sys00 | 46 | func | sysfuncs\[func\]\(\) |
| Sys01 | 47 | func, a | sysfuncs\[func\]\(a\) |
| Sys02 | 48 | func, a, b | sysfuncs\[func\]\(a, b\) |
| Sys03 | 49 | func, a, b, c | sysfuncs\[func\]\(a, b, c\) |
| Sys04 | 50 | func, a, b, c, d | sysfuncs\[func\]\(a, b, c, d\) |
| Sys10 | 51 | t, func | t = sysfuncs\[func\]\(\) |
| Sys11 | 52 | t, func, a | t = sysfuncs\[func\]\(a\) |
| Sys12 | 53 | t, func, a, b | t = sysfuncs\[func\]\(a, b\) |
| Sys13 | 54 | t, func, a, b, c | t = sysfuncs\[func\]\(a, b, c\) |
| Sys14 | 55 | t, func, a, b, c, d | t = sysfuncs\[func\]\(a, b, c, d\) |
| Sys20 | 56 | t, u, func | t, u = sysfuncs\[func\]\(\) |
| Sys21 | 57 | t, u, func, a | t, u = sysfuncs\[func\]\(a\) |
| Sys22 | 58 | t, u, func, a, b | t, u = sysfuncs\[func\]\(a, b\) |
| Sys23 | 59 | t, u, func, a, b, c | t, u = sysfuncs\[func\]\(a, b, c\) |
| Sys24 | 60 | t, u, func, a, b, c, d | t, u = sysfuncs\[func\]\(a, b, c, d\) |
| Mov | 61 | t, a | t = a |
| Neg | 62 | t, a | t = \-a |
| Abs | 63 | t, a | t = abs\(a\) |
| And2 | 64 | t, a, b | t = a && b<br>result is the last arg if all args are truthy, otherwise 0 |
| Or2 | 65 | t, a, b | t = a \|\| b<br>result is the first truthy arg, otherwise 0 |
| Max | 66 | t, n, s\[0\], \.\.\., s\[n\-1\] | t = max\(s\[0\], \.\.\., s\[n\-1\]\) |
| Min | 67 | t, n, s\[0\], \.\.\., s\[n\-1\] | t = min\(s\[0\], \.\.\., s\[n\-1\]\) |
| Not | 68 | t, a | t = \! a |
| Bool | 69 | t, a | t = \!\! a |
| LongMul | 70 | tl, th, a, b | th:tl = a \* b<br>64\-bit result |
| LongMulU | 71 | tl, th, a, b | th:tl = a \* b<br>_unsigned_<br>64\-bit result |
