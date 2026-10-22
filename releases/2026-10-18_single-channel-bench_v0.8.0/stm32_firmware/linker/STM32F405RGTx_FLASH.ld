ENTRY(Reset_Handler)

MEMORY
{
  /* Sector 11 (0x080E0000..0x080FFFFF) is reserved for profiles/calibration. */
  FLASH (rx)  : ORIGIN = 0x08000000, LENGTH = 896K
  RAM   (xrw) : ORIGIN = 0x20000000, LENGTH = 128K
  CCMRAM(xrw) : ORIGIN = 0x10000000, LENGTH = 64K
}

_estack = ORIGIN(RAM) + LENGTH(RAM);
_Min_Heap_Size = 0x200;
_Min_Stack_Size = 0x1000;

SECTIONS
{
  .isr_vector : { . = ALIGN(4); KEEP(*(.isr_vector)); . = ALIGN(4); } > FLASH
  .text :
  {
    . = ALIGN(4); *(.text) *(.text*) *(.glue_7) *(.glue_7t)
    KEEP(*(.init)) KEEP(*(.fini))
    . = ALIGN(4); _etext = .;
  } > FLASH
  .rodata : { . = ALIGN(4); *(.rodata) *(.rodata*) . = ALIGN(4); } > FLASH
  .ARM.extab : { *(.ARM.extab* .gnu.linkonce.armextab.*) } > FLASH
  .ARM.exidx : { __exidx_start = .; *(.ARM.exidx*) __exidx_end = .; } > FLASH
  _sidata = LOADADDR(.data);
  .data :
  {
    . = ALIGN(4); _sdata = .; *(.data) *(.data*) . = ALIGN(4); _edata = .;
  } > RAM AT> FLASH
  .bss :
  {
    . = ALIGN(4); _sbss = .; *(.bss) *(.bss*) *(COMMON) . = ALIGN(4); _ebss = .;
  } > RAM
  .ccmram (NOLOAD) : { . = ALIGN(4); *(.ccmram) *(.ccmram*) . = ALIGN(4); } > CCMRAM
  ._user_heap_stack (NOLOAD) :
  {
    . = ALIGN(8); PROVIDE(end = .); PROVIDE(_end = .);
    . = . + _Min_Heap_Size; . = . + _Min_Stack_Size; . = ALIGN(8);
  } > RAM
  /DISCARD/ : { *(.note.GNU-stack) }
}
