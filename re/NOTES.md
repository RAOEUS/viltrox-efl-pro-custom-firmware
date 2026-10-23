# Reverse-engineering map (EF-L v1.2 app, base 0x08020400)

Addresses refer to `all.c` / `all.asm`. `DAT_2000xxxx` are RAM globals; initial values in
`ram_init_0x20000000.bin` (first 0x9FC bytes of RAM; the rest is zero at boot).

## Main flow
| Function | Role |
|---|---|
| `FUN_08020684` | Reset_Handler (Keil). `FUN_08020594` = `__main`, scatter table at 0x0802D898 (compressed .data). |
| `FUN_08026e90` | `main()`: `FUN_08022dd8` (clocks/GPIO/SysTick), `FUN_08023e84` (mode select, lens power-up), loop: heartbeat PA5, lens-detect poll, `FUN_08024a44`. Exits (SYSRESETREQ) only if `DAT_20000353` is cleared, which nothing does. |
| `FUN_08023e84` | Reads switch PA12: `DAT_20000004` = 1 (O, native-lens emulation, "LDAFR!") or 2 (A, adapter, "LDAFRP"). Sets `DAT_200002e9` (1 = no profile/generic, 0 = profile mode). |
| `FUN_08022508` | Lens detect (PA15 low 16x). |
| `FUN_08022424` / `FUN_080223a8` | Lens bus on (USART1 AF7 on PA8/9/10, TIM2 one-pulse, IRQ28) / off. |

## Lens (EF) side
| Item | Address / meaning |
|---|---|
| `FUN_080229dc(byte)` | Send one bit-reversed byte on USART1, start TIM2. |
| `FUN_080260d4` | TIM2 ISR: stores received byte at `*DAT_200004c4`, runs reply handler `FUN_080228c0` when the command byte `DAT_20000491` changes, then runs queued step functions (ring at 0x20000008, head `DAT_200002e5`, tail `DAT_200002e6`), refilling from the secondary queue (0x20000088, `DAT_200002e7/e8`). |
| Step contract | `int step(void)`: return 0 = byte/delay in flight (called again next tick), 1 = done. Sub-state in `DAT_20000492` (0 between steps). Set `DAT_200004c4` to where the reply of the byte you are about to send must land. |
| `FUN_08022358` / `FUN_08022524` | Enqueue a step on the main / secondary queue. `FUN_08022540(list)` enqueues a `0x080221e5`-terminated list. `FUN_0802230c` kicks TIM2. |
| `FUN_08022108` | Delay step: one tick with TIM2 ARR = `DAT_20000300` (one-shot) or `DAT_20000304`. Ticks are in TIM2 clocks (84 MHz, `DAT_200009e8`). |
| `FUN_08026554` | USART1 100 kHz; `FUN_080264e0`/`FUN_08026514` 500 kHz (byte period 0x2b/0x67 us). |
| Steps by command | 0x0A poll `FUN_08022274` (expects 0xAA, sets `DAT_20000332`); 0x80 lens info `FUN_080215f0` (params `DAT_20000478..482` = `0A FE 03 00..`; reply at 0x200060c7..; builds lens key `DAT_20000308` = Oct2<<8 \| Oct9, focal `DAT_2000030e/0x310`, zoom flag `DAT_20000348`, then table lookup `FUN_08025c28` -> `DAT_20000343`); 0x81 `FUN_08021850`; 0x86 `FUN_08021a98`; 0x82/0x83 name `FUN_0802190c` (into 0x20000108); 0xB0 aperture `FUN_08021de0` (-> `DAT_20000320..322`); 0xA0 focal `FUN_08021cfc`; 0xC0 counter `FUN_08021e44` (-> `DAT_200004bc`); 0xC2 distance `FUN_08021f94`; 0xE0 `FUN_08022154`; 0xE4 `FUN_0802219c`; 0x90/0x91 status `FUN_08021b60`/`FUN_08021ba8`; 0x44 focus move `FUN_08021524` (`DAT_20000328` steps); 0x30 move+speed `FUN_08021434`; 0x50 speed `FUN_080215a4`; 0x05/0x06/0x07 `FUN_08021170`/`FUN_080211bc`/`FUN_080211fc`; 0x0C `FUN_08021308`; 0x0B `FUN_0802129c`; 0x0E/0x0F `FUN_08021338`/`FUN_08021398`; 0x12/0x13 aperture `FUN_080213c8`; 0x93 IS `FUN_08021c10`; 0x08 sleep `FUN_0802123c`; 0x97 `FUN_08021ca4`; 0xA1/0xA2/0xC3/0xC4 `FUN_08021d54`/`FUN_08021da4`/`FUN_08022020`/`FUN_08022060`. `FUN_08021144` = send 0x00. `FUN_08022268` = call `*DAT_200002d0`. |
| Lens init list | 0x0802a7f4 (10 steps), enqueued by `FUN_0802591c` when the lens answers; ends with `FUN_08022268` -> `FUN_08025cb0` (`DAT_20000342` = init done, `DAT_20000347` = new lens). Variant A points the literal at 0x0802597c to its own list. |
| Status handling | `FUN_08022584` (0x90 Oct2 in `DAT_20000000`; bit-band aliases `DAT_22000008` motor running, `DAT_22000010` at end stop, `DAT_2200001c` MF switch). `FUN_08025894` sets position `DAT_200002ee` to 0x1000 (infinity) or `DAT_200002f2`+0x1000 (near) at end stops. 0xCF pseudo-command in `FUN_080228c0` tracks position from counter deltas. |

## Lens tables and profiles
* Table A (A mode) at 0x08029f88: 58 x {u16 key, u16 fmin, u16 fmax, u32 profile ptr}. Table B (O mode) at 0x0802a1cc: 8 x {key, fmin, fmax, handler} (Sigma 85/50 Art emulation etc.). Lookup `FUN_08025c28`, loader `FUN_08024c80(profile)`.
* Profile block: `u16 hdr` (bits0-6 = N distance entries, bit7 = use generic 9-point curve at 0x08029f76 + one `s16 total`, bit8 `DAT_2000034f` (new move while moving), bit9 `DAT_20000351`, bit10 `DAT_20000350` (use 0x30 moves), bit11 `DAT_20000352` (IS/0x91), bit15 extra s16 pair); `s16 dist[N]` cm, `dist[0]` = -1 = infinity; `s16 steps[N+1]` counter position (total at infinity .. 0 at near); zooms: `u16 M` (bit7 = aperture list follows), `u16 focal[M]` mm, `[u16 apert[M]]`.
* Loader output: `DAT_20005d04` distances, `DAT_20005d84` steps, `DAT_20000335` N, `DAT_200002f2` total, `DAT_20005c04` focals, `DAT_200002e9` = 0.

## Camera (L-mount) side
* `FUN_0802496c` dispatches on state `DAT_2000035c` (camera command class). State 0xFF builds the lens descriptor (generic 5 entries from 0x0802a234 when no profile, otherwise 7 + 6 computed entries, name from 0x20000108). `FUN_08024634` handles the periodic command 9: sub-byte `DAT_20005fbf` bits -> `FUN_08020e7c` (focus: `DAT_20005fc8` 2 = absolute, 3/4 = relative, target `DAT_20005fc9`), `FUN_08020f54` (aperture), `FUN_08025388` (0x39/0x3a focus variants). Responses: `FUN_08024f80` (profile mode, 0x32 bytes) / `FUN_08025104` (generic, 0x18 bytes), checksum `FUN_08022cde`.
* SPI1 slave DMA setup `FUN_08024a1c`, TIM4 ISR `FUN_0802622c`.
