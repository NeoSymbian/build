/* mmp_dll.ld — link script for build_mmp.py DLLs. euser.ld plus: _E32Dll
 * (toolchain/dll_rt/dll_entry.s) pinned at code offset 0 = the image entry
 * point; .init_array surfaced (KEEPed + bracketed) so the builder can SEE a
 * DLL that needs static construction instead of silently dropping it. */
ENTRY(_E32Dll)
SECTIONS {
  . = 0x8000;
  .text : {
    *dll_entry.s.o(.text)
    *(.text) *(.text.*) *(.rodata) *(.rodata.*) *(.ARM.extab*)
    . = ALIGN(4);
    __init_array_start = .;
    KEEP(*(SORT_BY_INIT_PRIORITY(.init_array.*)))
    KEEP(*(.init_array))
    __init_array_end = .;
    LONG(0)
  }
  /* NeoSymbian: the unwind index, its own output section so ld sorts it (SHF_LINK_ORDER); elf.extract appends it
     to the code with a TExceptionDescriptor (C++ exceptions of old RVCT binaries unwind through our frames) */
  .ARM.exidx : { __exidx_start = .; *(.ARM.exidx*) __exidx_end = .; }
  . = ALIGN(8);
  .data : { *(.data) *(.data.*) }
  .bss  : { *(.bss) *(.bss.*) *(COMMON) }
  /DISCARD/ : { *(.ARM.attributes) *(.comment) *(.note*) }
}
