// bajo vm interpreter
//
// Licenced under the MIT License: https://www.opensource.org/licenses/mit-license.php

#ifndef _BAJO_H_
#define _BAJO_H_

#include "stdint.h"

enum bajo_err_e
{
    BAJO_OK = 0,
    BAJO_EXIT = 1,
    BAJO_BAD_VARINT = 2,
    BAJO_UNKNOWN_OPCODE = 3,
    BAJO_BAD_OPERAND = 4,
    BAJO_BUG = 5,
    BAJO_ZERO_DIVISION = 6,
    BAJO_INTEGER_OVERFLOW = 7,
};

typedef struct bajo_t bajo_t;

struct bajo_t
{
    // Program counter
    uint32_t pc;
    // bajo_err_e or interface error code
    int err;
    // Exit instruction rc code
    int exit_rc;
    // Host api callbacks:
    // Read 1, 2, 3, or 4-byte integer from `addr`.
    // Little-endian.
    uint32_t (*read)(bajo_t *me, uint32_t addr, unsigned int len);
    // Write 1, 2, 3, or 4 bytes of integer `val` to `addr`.
    // Little-endian.
    void (*write)(bajo_t *me, uint32_t addr, uint32_t val, unsigned int len);
    // Call host function with number `fn`.
    void (*call)(bajo_t *me, int fn, int32_t *res, const int32_t *args, unsigned int nargs);
};

// reset pc to pc, clear errors
void bajo_init(bajo_t *me, uint32_t pc);
// execure single instruction.
// returns the rc
int bajo_step(bajo_t *me);
// run until error or exit instruction.
// returns the rc
int bajo_run(bajo_t *me);

#endif