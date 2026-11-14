ENTRY(__unimpl_export)
SECTIONS {
  . = 0x8000;
  .text : { *(.text) *(.text.*) *(.rodata) *(.rodata.*) *(.rodata) *(.ARM.extab*) }
  /* NeoSymbian: the unwind index, its own output section so ld sorts it (SHF_LINK_ORDER); elf.extract appends it
     to the code with a TExceptionDescriptor (C++ exceptions of old RVCT binaries unwind through our frames) */
  .ARM.exidx : { __exidx_start = .; *(.ARM.exidx*) __exidx_end = .; }
  . = ALIGN(4);
  .data : { *(.data) *(.data.*) }
  .bss  : { *(.bss) *(.bss.*) *(COMMON) }
  /DISCARD/ : { *(.ARM.attributes) *(.comment) *(.note*) }
}
