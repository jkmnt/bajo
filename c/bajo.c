#include <stdbool.h>
#include <assert.h>

#include "opcodes.h"
#include "bajo.h"

// opspec encoding:
// bits 7-4 - src, bits 3-0 - tgt
//
// src, tgt fields:
// 0 = no operands
// 1 - 8 = 1 - 8 operands, word access
// 9 = var, word access
// 10 = 1 operand, byte access
// 11 = 1 operand, halfword access
// 12 - 14 = reserved
// 15 = reserved (undef)

#define SPEC(_tspec, _sspec) ((_tspec) << 4 | (_sspec))
#define SPEC_UNDEF 0xFF

#define OPD_VAR 9
#define OPD_1B 10
#define OPD_1H 11

#define MAX_TGTS 8
#define MAX_SRCS 8

// signal error on zero division detected
// or leave it to plarform: raise signal, write undefined result etc
#ifndef ERR_ON_ZERO_DIVISION
#define ERR_ON_ZERO_DIVISION false
#endif

// signal error on div overlow
#ifndef ERR_ON_INT_OVERFLOW
#define ERR_ON_INT_OVERFLOW false
#endif

#define INT_MIN_ -2147483648 // trailing underscore to avoid confusion with std

static const uint8_t opspecs[] = {
    [0 ... _MAX_OPCODE] = SPEC_UNDEF,
    [ADD] = SPEC(1, 2),
    [SUB] = SPEC(1, 2),
    [MUL] = SPEC(1, 2),
    [DIV] = SPEC(1, 2),
    [DIV_U] = SPEC(1, 2),
    [REM] = SPEC(1, 2),
    [REM_U] = SPEC(1, 2),
    [LONG_MUL] = SPEC(2, 2),
    [LONG_MUL_U] = SPEC(2, 2),
    [AND2] = SPEC(1, 2),
    [OR2] = SPEC(1, 2),
    [AND] = SPEC(1, OPD_VAR),
    [OR] = SPEC(1, OPD_VAR),
    [BIT_AND] = SPEC(1, 2),
    [BIT_OR] = SPEC(1, 2),
    [BIT_XOR] = SPEC(1, 2),
    [INV] = SPEC(1, 1),
    [L_SHIFT] = SPEC(1, 2),
    [R_SHIFT] = SPEC(1, 2),
    [R_SHIFT_U] = SPEC(1, 2),
    [TST_EQ] = SPEC(1, 2),
    [TST_NE] = SPEC(1, 2),
    [TST_GT] = SPEC(1, 2),
    [TST_GE] = SPEC(1, 2),
    [TST_GT_U] = SPEC(1, 2),
    [TST_GE_U] = SPEC(1, 2),
    [JMP] = SPEC(0, 1),
    [JMP_LNK] = SPEC(1, 1),
    [BR] = SPEC(0, 1),
    [BR_LNK] = SPEC(1, 1),
    [BR_EQ] = SPEC(0, 3),
    [BR_NE] = SPEC(0, 3),
    [BR_GT] = SPEC(0, 3),
    [BR_GE] = SPEC(0, 3),
    [BR_GT_U] = SPEC(0, 3),
    [BR_GE_U] = SPEC(0, 3),
    [MOV_EQ] = SPEC(1, 4),
    [MOV_GT] = SPEC(1, 4),
    [MOV_GE] = SPEC(1, 4),
    [MOV_GT_U] = SPEC(1, 4),
    [MOV_GE_U] = SPEC(1, 4),
    [LD_B] = SPEC(1, OPD_1B),
    [LD_H] = SPEC(1, OPD_1H),
    [LD_B_U] = SPEC(1, OPD_1B),
    [LD_H_U] = SPEC(1, OPD_1H),
    [ST_B] = SPEC(OPD_1B, 1),
    [ST_H] = SPEC(OPD_1H, 1),
    [SYS] = SPEC(OPD_VAR, OPD_VAR),
    [SYS00] = SPEC(0, 1),
    [SYS01] = SPEC(0, 2),
    [SYS02] = SPEC(0, 3),
    [SYS03] = SPEC(0, 4),
    [SYS04] = SPEC(0, 5),
    [SYS10] = SPEC(1, 1),
    [SYS11] = SPEC(1, 2),
    [SYS12] = SPEC(1, 3),
    [SYS13] = SPEC(1, 4),
    [SYS14] = SPEC(1, 5),
    [SYS20] = SPEC(2, 1),
    [SYS21] = SPEC(2, 2),
    [SYS22] = SPEC(2, 3),
    [SYS23] = SPEC(2, 4),
    [SYS24] = SPEC(2, 5),
    [MOV] = SPEC(1, 1),
    [NEG] = SPEC(1, 1),
    [EXIT] = SPEC(0, 1),
    [ABS] = SPEC(1, 1),
    [MAX] = SPEC(1, OPD_VAR),
    [MIN] = SPEC(1, OPD_VAR),
    [NOT] = SPEC(1, 1),
    [BOOL] = SPEC(1, 1),
    [NOP] = SPEC(0, 0),
};

static int decode_varint_size(uint32_t head)
{
#ifdef __GNUC__
    return __builtin_ctz(head) + 1;
#else
#warning "Missing the ctz() intrinsic"
    if (head & 0b1)
        return 1;
    if (head & 0b10)
        return 2;
    if (head & 0b100)
        return 3;
    if (head & 0b1000)
        return 4;
    if (head & 0b10000)
        return 5;
    return 6;
#endif
}

static int read_src(bajo_t *me, uint32_t *addr, unsigned int size)
{
    uint32_t head = me->read(me, *addr, 1);
    *addr += 1;

    const unsigned int nbytes = decode_varint_size(head);
    if (nbytes > 5)
    {
        me->err = BAJO_BAD_VARINT;
        return 0;
    }

    uint32_t tail;
    if (nbytes > 1)
    {
        tail = me->read(me, *addr, nbytes - 1);
        *addr += nbytes - 1;
    }
    else
    {
        tail = 0;
    }

    head >>= nbytes;

    int val;
    if (!(head & 0b1))
    {
        val = (tail << (8 - 2 - nbytes)) | (head >> 2);
        if (head & 0b10)
            val = ~val;

        if (size < 4) // unlikely
        {
            if (size == 1)
                val = val & 0xFF;
            else if (size == 2)
                val = val & 0xFFFF;
            // else if (size == 3)
            //     val = val & 0xFFFFFF;
        }
    }
    else
    {
        val = (tail << (8 - 3 - nbytes)) | (head >> 3);
        if (!(head & 0b100))
            val *= 4;

        if (head & 0b010)
            val = me->read(me, val, 4) + read_src(me, addr, 4);

        val = me->read(me, val, size);
    }

    return val;
}

static int read_dst(bajo_t *me, uint32_t *addr)
{
    uint32_t head = me->read(me, *addr, 1);
    *addr += 1;

    unsigned int nbytes = decode_varint_size(head);
    if (nbytes > 5)
    {
        me->err = BAJO_BAD_VARINT;
        return 0;
    }

    uint32_t tail;
    if (nbytes > 1)
    {
        tail = me->read(me, *addr, nbytes - 1);
        *addr += nbytes - 1;
    }
    else
    {
        tail = 0;
    }

    head >>= nbytes;
    int val = (tail << (8 - 2 - nbytes)) | (head >> 2);

    if (!(head & 0b10))
        val *= 4;

    if (head & 0b01)
        val = me->read(me, val, 4) + read_src(me, addr, 4);

    return val;
}

// NOTE: opcode_t is typedeffed here to catch 'case not handled in switch'.
// The opcodes are mostly monotonic, so compiler is expected to
// generate the jumptable instead of the iffs chain.
static void dispatch(bajo_t *me, opcode_t opcode, int32_t *t, const int32_t *s, unsigned int ns)
{
    switch (opcode)
    {
    case ADD:
        t[0] = s[0] + s[1];
        return;

    case SUB:
        t[0] = s[0] - s[1];
        return;

    case MUL:
        t[0] = s[0] * s[1];
        return;

    case DIV:
        if (ERR_ON_ZERO_DIVISION && s[1] == 0)
        {
            me->err = BAJO_ZERO_DIVISION;
            return;
        }

        if (ERR_ON_INT_OVERFLOW && s[0] == INT_MIN_ && s[1] == -1)
        {
            me->err = BAJO_INTEGER_OVERFLOW;
            return;
        }

        t[0] = s[0] / s[1];
        return;

    case DIV_U:
        if (ERR_ON_ZERO_DIVISION && s[1] == 0)
        {
            me->err = BAJO_ZERO_DIVISION;
            return;
        }

        t[0] = (uint32_t)s[0] / (uint32_t)s[1];
        return;

    case REM:
        if (ERR_ON_ZERO_DIVISION && s[1] == 0)
        {
            me->err = BAJO_ZERO_DIVISION;
            return;
        }

        // raises in runtime, but the correct result (0) fits s32.
        // really no reason to rise.
        if (s[0] == INT_MIN_ && s[1] == -1)
        {
            t[0] = 0;
            return;
        }

        t[0] = s[0] % s[1];
        return;

    case REM_U:
        if (ERR_ON_ZERO_DIVISION && s[1] == 0)
        {
            me->err = BAJO_ZERO_DIVISION;
            return;
        }

        t[0] = (uint32_t)s[0] % (uint32_t)s[1];
        return;

    case LONG_MUL:
    {
        int64_t res = (int64_t)s[0] * (int64_t)s[1];
        t[0] = res;
        t[1] = res >> 32;
        return;
    }

    case LONG_MUL_U:
    {
        uint64_t res = (uint64_t)(uint32_t)s[0] * (uint32_t)s[1];
        t[0] = res;
        t[1] = res >> 32;
        return;
    }

    case AND2:
        t[0] = !s[0] ? s[0] : s[1];
        return;

    case OR2:
        t[0] = s[0] ? s[0] : s[1];
        return;

    case AND:
    {
        if (!ns)
        {
            me->err = BAJO_BAD_OPERAND;
            return;
        }

        int32_t ret;
        for (unsigned int i = 0; i < ns; i += 1)
        {
            ret = s[i];
            if (!ret)
                break;
        }
        t[0] = ret;
        return;
    }

    case OR:
    {
        if (ns < 1)
        {
            me->err = BAJO_BAD_OPERAND;
            return;
        }

        int32_t ret;
        for (unsigned int i = 0; i < ns; i += 1)
        {
            ret = s[i];
            if (ret)
                break;
        }
        t[0] = ret;

        return;
    }

    case BIT_AND:
        t[0] = s[0] & s[1];
        return;

    case BIT_OR:
        t[0] = s[0] | s[1];
        return;

    case BIT_XOR:
        t[0] = s[0] ^ s[1];
        return;

    case INV:
        t[0] = ~s[0];
        return;

    case L_SHIFT:
        if ((uint32_t)(s[1]) >= 32)
            t[0] = 0;
        else
            t[0] = s[0] << s[1];
        return;

    case R_SHIFT_U:
        if ((uint32_t)(s[1]) >= 32)
            t[0] = 0;
        else
            t[0] = ((uint32_t)s[0]) >> s[1];
        return;

    case R_SHIFT:
        if ((uint32_t)(s[1]) >= 32)
            t[0] = s[0] >> 31; // make 0 or ~0
        else
            t[0] = s[0] >> s[1];
        return;

    case TST_EQ:
        t[0] = s[0] == s[1];
        return;

    case TST_NE:
        t[0] = s[0] != s[1];
        return;

    case TST_GT:
        t[0] = s[0] > s[1];
        return;

    case TST_GE:
        t[0] = s[0] >= s[1];
        return;

    case TST_GT_U:
        t[0] = (uint32_t)s[0] > (uint32_t)s[1];
        return;

    case TST_GE_U:
        t[0] = (uint32_t)s[0] >= (uint32_t)s[1];
        return;

    case BR:
        me->pc += s[0];
        return;

    case BR_LNK:
        t[0] = me->pc;
        me->pc += s[0];
        return;

    case BR_EQ:
        if (s[0] == s[1])
            me->pc += s[2];
        return;

    case BR_NE:
        if (s[0] != s[1])
            me->pc += s[2];
        return;

    case BR_GT:
        if (s[0] > s[1])
            me->pc += s[2];
        return;

    case BR_GE:
        if (s[0] >= s[1])
            me->pc += s[2];
        return;

    case BR_GT_U:
        if ((uint32_t)s[0] > (uint32_t)s[1])
            me->pc += s[2];
        return;

    case BR_GE_U:
        if ((uint32_t)s[0] >= (uint32_t)s[1])
            me->pc += s[2];
        return;

    case JMP:
        me->pc = s[0];
        return;

    case JMP_LNK:
        t[0] = me->pc;
        me->pc = s[0];
        return;

    case MOV_EQ:
        t[0] = s[0] == s[1] ? s[2] : s[3];
        return;

    case MOV_GT:
        t[0] = s[0] > s[1] ? s[2] : s[3];
        return;

    case MOV_GE:
        t[0] = s[0] >= s[1] ? s[2] : s[3];
        return;

    case MOV_GT_U:
        t[0] = (uint32_t)s[0] > (uint32_t)s[1] ? s[2] : s[3];
        return;

    case MOV_GE_U:
        t[0] = (uint32_t)s[0] >= (uint32_t)s[1] ? s[2] : s[3];
        return;

    case SYS:
        if (ns < 1)
        {
            me->err = BAJO_BAD_OPERAND;
            return;
        }
        // fall-thru
    case SYS00:
    case SYS01:
    case SYS02:
    case SYS03:
    case SYS04:
    case SYS10:
    case SYS11:
    case SYS12:
    case SYS13:
    case SYS14:
    case SYS20:
    case SYS21:
    case SYS22:
    case SYS23:
    case SYS24:
        me->call(me, s[0], t, s + 1, ns - 1);
        return;

    case MOV:
    case LD_B_U:
    case LD_H_U:
        t[0] = s[0];
        return;

    case ST_B:
    case ST_H:
        t[0] = s[0];
        return;

    case LD_B:
        t[0] = (int8_t)s[0];
        return;

    case LD_H:
        t[0] = (int16_t)s[0];
        return;

    case NEG:
        t[0] = -s[0];
        return;

    case EXIT:
        me->err = BAJO_EXIT;
        me->exit_rc = s[0];
        return;

    case ABS:
        t[0] = s[0] < 0 ? -s[0] : s[0];
        return;

    case MAX:
    {
        if (ns < 1)
        {
            me->err = BAJO_BAD_OPERAND;
            return;
        }

        int32_t v = s[0];
        for (unsigned int i = 1; i < ns; i += 1)
        {
            if (s[i] > v)
                v = s[i];
        }
        t[0] = v;
        return;
    }

    case MIN:
    {
        if (ns < 1)
        {
            me->err = BAJO_BAD_OPERAND;
            return;
        }

        int32_t v = s[0];
        for (unsigned int i = 1; i < ns; i += 1)
        {
            if (s[i] < v)
                v = s[i];
        }
        t[0] = v;
        return;
    }

    case NOT:
        t[0] = !s[0];
        return;

    case BOOL:
        t[0] = !!s[0];
        return;

    case NOP:
        return;
    }

    me->err = BAJO_BUG;
}

void bajo_init(bajo_t *me, uint32_t pc)
{
    me->err = BAJO_OK;
    me->pc = pc;
    me->exit_rc = 0;
}

// TODO: balance the errors checking vs speed
int bajo_step(bajo_t *me)
{
    me->err = BAJO_OK;

    unsigned int opcode = me->read(me, me->pc, 1);
    me->pc += 1;

    const bool rmw0 = opcode & 0x80;
    opcode &= ~0x80;

    if (opcode > _MAX_OPCODE)
        return (me->err = BAJO_UNKNOWN_OPCODE);

    const unsigned int spec = opspecs[opcode];

    if (spec == SPEC_UNDEF)
        return (me->err = BAJO_UNKNOWN_OPCODE);

    const unsigned int tspec = spec >> 4;
    unsigned int ntgts;
    unsigned int tsize;

    if (tspec == OPD_VAR)
    {
        ntgts = read_src(me, &me->pc, 4);
        if (ntgts > MAX_TGTS)
            return (me->err = BAJO_BAD_OPERAND);
        tsize = 4;
    }
    else if (tspec == OPD_1B)
    {
        ntgts = 1;
        tsize = 1;
    }
    else if (tspec == OPD_1H)
    {
        ntgts = 1;
        tsize = 2;
    }
    else
    {
        ntgts = tspec;
        tsize = 4;
    }

    uint32_t tgts[MAX_TGTS];
    for (unsigned int i = 0; i < ntgts; i += 1)
        tgts[i] = read_dst(me, &me->pc);

    const unsigned int sspec = spec & 0x0F;
    unsigned int nsrcs;
    unsigned int ssize;
    if (sspec == OPD_VAR)
    {
        nsrcs = read_src(me, &me->pc, 4);
        if (nsrcs > MAX_SRCS)
            return (me->err = BAJO_BAD_OPERAND);
        ssize = 4;
    }
    else if (sspec == OPD_1B)
    {
        nsrcs = 1;
        ssize = 1;
    }
    else if (sspec == OPD_1H)
    {
        nsrcs = 1;
        ssize = 2;
    }
    else
    {
        nsrcs = sspec;
        ssize = 4;
    }

    int32_t srcs[MAX_SRCS];

    // if rmw0, first src is same as target
    if (rmw0)
    {
        if (nsrcs == 0 || ntgts == 0)
            return (me->err == BAJO_BAD_OPERAND);
        srcs[0] = me->read(me, tgts[0], ssize);
    }

    for (unsigned int i = rmw0 ? 1 : 0; i < nsrcs; i += 1)
        srcs[i] = read_src(me, &me->pc, ssize);

    if (me->err)
        return me->err;

    int32_t results[MAX_TGTS];
    dispatch(me, opcode, results, srcs, nsrcs);

    if (me->err)
        return me->err;

    for (unsigned int i = 0; i < ntgts; i += 1)
        me->write(me, tgts[i], results[i], tsize);

    return me->err;
}

int bajo_run(bajo_t *me)
{
    int rc;
    while ((rc = bajo_step(me)) == BAJO_OK)
        ;

    return rc;
}