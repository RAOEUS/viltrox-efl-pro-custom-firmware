MEMORY { FLASH (rx) : ORIGIN = 0x0802D9E0, LENGTH = 0x6D4 }
SECTIONS {
  .text : { KEEP(*(.list)) *(.text*) *(.rodata*) } > FLASH
  /DISCARD/ : { *(.ARM.attributes) *(.comment) *(.data*) *(.bss*) }
}
