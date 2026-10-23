/* Viltrox EF-L v1.2 add-on: auto-profile for EF lenses missing from the lens table.
 * Runs as the last step of the lens-init sequence (TIM2 ISR step-function contract:
 * return 0 = byte/delay in flight, call me again next tick; return 1 = done, run next step).
 * Unknown lens -> sweep to MFD (0x06) and infinity (0x05), read the 0xC0 counter at both ends,
 * optionally read 0xC2 distance at MFD, then synthesize a profile block and feed it to the
 * firmware's own profile loader (FUN_08024c80). Known lenses: pass straight through. */
#include <stdint.h>
typedef void (*send_t)(uint8_t);
typedef void (*apply_t)(uint16_t *);
typedef int  (*step_t)(void);
#define SEND      ((send_t)0x080229ddu)
#define APPLY     ((apply_t)0x08024c81u)
#define g_cmd     (*(volatile uint8_t *)0x20000491u)   /* current EF command byte (0 = no reply handler) */
#define g_sub     (*(volatile uint8_t *)0x20000492u)   /* shared step sub-state, 0 between steps */
#define g_rxptr   (*(volatile uint8_t **)0x200004c4u)  /* where ISR stores the next received byte */
#define g_scratch ((uint8_t *)0x20000493u)
#define g_found   (*(volatile uint8_t *)0x20000343u)   /* lens-table lookup result */
#define g_ready   (*(volatile uint8_t *)0x20000332u)   /* lens answered 0xAA */
#define g_zoom    (*(volatile uint8_t *)0x20000348u)
#define g_fmin    (*(volatile uint16_t *)0x2000030eu)
#define g_fmax    (*(volatile uint16_t *)0x20000310u)
#define g_hasc2   (*(volatile uint8_t *)0x2000032cu)
#define g_lensid  (*(volatile uint16_t *)0x20000308u)
#define g_name    ((char *)0x20000108u)
#define g_next    (*(volatile step_t *)0x200002d0u)
#define g_pos     (*(volatile uint16_t *)0x200002eeu)
#define g_lastc0  (*(volatile uint16_t *)0x20000316u)
#define g_clk     (*(volatile uint32_t *)0x200009e8u)
#define g_speed   (*(volatile uint8_t *)0x200002e4u)    /* AF speed byte the stock focus path sends with 0x50 */
#define TIM2_CR1  (*(volatile uint32_t *)0x40000000u)
#define TIM2_ARR  (*(volatile uint32_t *)0x4000002cu)

struct cal {
    uint8_t  st, after, phase, stable, flags, parked, stop_next;   /* flags: 1 fallback, 2 MF/busy, 4 timeout, 8 reversed counter, 16 estimated near limit */
    uint16_t polls, c0, last, c0_mfd, c0_inf, mfd_cm;
    uint32_t saved_arr;
    uint8_t  rx[4];
    uint16_t blk[48];
};
#define C ((struct cal *)0x20007440u)   /* first bytes above the firmware's RAM top (0x20007438): unused, exists on every F4 */

enum { S_STAT, S_STATB, S_STATC, S_STATD, S_STOP, S_SPD, S_SPDB, S_START, S_SETTLE, S_C0, S_C0B, S_C0C, S_C0D, S_C2, S_C2B, S_C2C, S_C2D, S_C2E, S_C2F, S_LEG2, S_FINISH, S_DLY };

#define POLL_MS   20
#define MAX_POLLS 150    /* 3 s per leg */

static void delay_ms(uint32_t ms, uint8_t after) {
    C->saved_arr = TIM2_ARR;
    TIM2_ARR = (g_clk / 1000u) * ms;
    C->after = after; C->st = S_DLY;
    TIM2_CR1 |= 1u;                      /* one-pulse: fire the next tick after ARR */
}
static void send(uint8_t b, uint8_t *rx, uint8_t next) { g_rxptr = rx; C->st = next; SEND(b); }

static char *putu(char *p, uint32_t v) {
    char t[10]; int n = 0;
    do { t[n++] = '0' + v % 10; v /= 10; } while (v);
    while (n) *p++ = t[--n];
    return *p = 0, p;
}
static char *puts_(char *p, const char *s) { while (*s) *p++ = *s++; *p = 0; return p; }

static void finish(void) {
    int total = (int16_t)(C->c0_inf - C->c0_mfd);       /* stock convention: counter decreases toward near */
    if (total < 0) C->flags |= 8;                        /* counter runs the other way: tracker would invert */
    if (C->flags || total < 200 || total > 20000) { total = 1500; C->flags |= 1; }   /* implausible: safe fallback */
    uint32_t mfd = C->mfd_cm;
    if (mfd < 10 || mfd > 3000) {                        /* no/odd encoder: estimate ~10x focal, same clamps */
        mfd = g_fmin * 10u; C->flags |= 16;
        if (mfd < 25) mfd = 25;
        if (mfd > 3000) mfd = 3000;
    }
    static const uint16_t curve[8] = {300, 100, 70, 50, 40, 35, 32, 30};  /* firmware's generic curve, ends at MFD */
    uint16_t *b = C->blk;
    b[0] = 9;                            /* 9 distance entries, no flags */
    b[1] = 0xffff;                       /* infinity */
    for (int i = 0; i < 8; i++) b[2 + i] = (uint16_t)(mfd * curve[i] / 30u);
    b[10] = (uint16_t)total;             /* counter position at infinity */
    for (int i = 0; i < 8; i++) b[11 + i] = (uint16_t)(total - total * 30 / curve[i]);  /* 1/distance model */
    b[19] = 0;
    int n = 20;
    if (g_zoom) {
        b[n++] = 20;
        for (int i = 0; i < 20; i++) b[n++] = (uint16_t)(g_fmin + (g_fmax - g_fmin) * i / 19);
    }
    APPLY(b);
    if (C->parked) { g_pos = 0x1000; g_lastc0 = C->c0_inf; }   /* only if the infinity leg really completed */
    /* EXIF-visible diagnostics: "<name> #<id> S<steps> D<mfd cm>" */
    char *p = g_name;
    if ((uint8_t)g_name[0] == 0 || (uint8_t)g_name[0] == 0xff) {
        p = puts_(p, "EF"); p = putu(p, g_fmin);
        if (g_zoom) { *p++ = '-'; p = putu(p, g_fmax); }
        p = puts_(p, "mm");
    } else { while (*p && p < g_name + 38) p++; }
    if (p <= g_name + 38) {              /* suffix is at most 25 chars incl. NUL: always fits the 64-byte buffer */
        p = puts_(p, " #"); for (int s = 12; s >= 0; s -= 4) *p++ = "0123456789ABCDEF"[(g_lensid >> s) & 15];
        p = puts_(p, " S"); p = putu(p, (uint32_t)total);
        p = puts_(p, " D"); p = putu(p, mfd);
        if (C->flags & 1)  *p++ = '!';   /* fallback step count in use */
        if (C->flags & 2)  *p++ = 'M';   /* lens in MF / busy, not measured */
        if (C->flags & 4)  *p++ = 'T';   /* a leg timed out */
        if (C->flags & 8)  *p++ = 'R';   /* counter direction reversed */
        if (C->flags & 16) *p++ = 'E';   /* near limit estimated (no distance encoder) */
        *p = 0;
    }
    for (char *q = p; q < g_name + 0x40; q++) *q = 0;
}

int autocal_step(void) {
    if (!g_ready) {                      /* lens gone (also catches a stale sweep replayed after re-attach) */
        g_sub = 0; C->st = S_STAT; g_rxptr = g_scratch; g_next(); return 1;
    }
    if (g_sub == 0) {                    /* first call for this lens */
        if (g_found || g_fmin == 0) { g_next(); return 1; }   /* table lens, or no 0x80 info: original behaviour */
        g_sub = 1; g_cmd = 0; g_rxptr = g_scratch;
        C->st = S_STAT; C->phase = 0; C->mfd_cm = 0; C->flags = 0; C->parked = 0; C->c0_mfd = C->c0_inf = 0;
    }
    for (;;) switch (C->st) {
    /* 0x90 status before touching the motor: skip the sweep if the lens is in MF or reports busy/error */
    case S_STAT:   send(0x90, g_scratch, S_STATB); return 0;
    case S_STATB:  send(0, &C->rx[0], S_STATC); return 0;
    case S_STATC:  send(0, &C->rx[1], S_STATD); return 0;
    case S_STATD:  g_rxptr = g_scratch;
                   if (C->rx[1] & 0xa0) { C->flags |= 2; C->st = S_FINISH; } else { C->after = S_START; C->st = S_SPD; }
                   break;
    case S_STOP:   send(0x07, g_scratch, C->stop_next); return 0;  /* stop the AF motor after a timeout */
    case S_SPD:    send(0x50, g_scratch, S_SPDB); return 0;         /* AF speed, as the stock focus path does before 0x05/0x06 */
    case S_SPDB:   send(g_speed ? g_speed : 0x60, g_scratch, C->after); return 0;
    case S_START:  send(0x06, g_scratch, S_SETTLE); return 0;        /* drive to MFD */
    case S_LEG2:   C->phase = 1; send(0x05, g_scratch, S_SETTLE); return 0;  /* drive to infinity */
    case S_SETTLE: C->polls = 0; C->stable = 0; delay_ms(10, S_C0); return 0;
    case S_C0:     send(0xc0, g_scratch, S_C0B); return 0;
    case S_C0B:    send(0, &C->rx[0], S_C0C); return 0;
    case S_C0C:    send(0, &C->rx[1], S_C0D); return 0;
    case S_C0D:
        g_rxptr = g_scratch;
        C->c0 = (uint16_t)(C->rx[0] << 8 | C->rx[1]);
        if (C->c0 == C->last) C->stable++; else C->stable = 0;
        C->last = C->c0; C->polls++;
        if ((C->stable >= 3 && C->polls >= 5) || C->polls >= MAX_POLLS) {
            uint8_t nxt;
            if (C->phase == 0) { C->c0_mfd = C->c0; nxt = g_hasc2 ? S_C2 : S_SPD; C->after = S_LEG2; }
            else               { C->c0_inf = C->c0; nxt = S_FINISH; C->parked = (C->polls < MAX_POLLS); }
            if (C->polls >= MAX_POLLS) { C->flags |= 4; C->stop_next = nxt; C->st = S_STOP; }   /* still moving: stop it first */
            else C->st = nxt;
        } else delay_ms(POLL_MS, S_C0);
        if (C->st == S_DLY) return 0;
        break;
    case S_C2:     send(0xc2, g_scratch, S_C2B); return 0;
    case S_C2B:    send(0, &C->rx[0], S_C2C); return 0;
    case S_C2C:    send(0, &C->rx[1], S_C2D); return 0;
    case S_C2D:    send(0, &C->rx[2], S_C2E); return 0;
    case S_C2E:    send(0, &C->rx[3], S_C2F); return 0;
    case S_C2F:    g_rxptr = g_scratch; C->mfd_cm = (uint16_t)(C->rx[2] << 8 | C->rx[3]); C->after = S_LEG2; C->st = S_SPD; break;
    case S_DLY:    TIM2_ARR = C->saved_arr; C->st = C->after; break;
    case S_FINISH: finish(); g_sub = 0; g_next(); return 1;
    default:       g_sub = 0; g_next(); return 1;
    }
}

/* Replacement lens-init step list: original 10 entries with the last (FUN_08022268) swapped for autocal_step. */
__attribute__((section(".list"), used))
const uint32_t init_list[10] = {
    0x08022109u, 0x08022275u, 0x080215f1u, 0x08021851u, 0x08021a99u,
    0x0802190du, 0x08022275u, 0x08021de1u, 0x08021145u, (uint32_t)autocal_step,
};
