ENTRY(_start)
SECTIONS {
 . = 0x80000000;
 .text : { *(.text.init) *(.text*) }
 .rodata : { *(.rodata*) }
 .data : { *(.data*) *(.sdata*) }
 . = ALIGN(8);
 PROVIDE(__global_pointer$ = . + 0x800);
 _bss_start = .;
 .bss : { *(.bss*) *(.sbss*) *(COMMON) }
 . = ALIGN(8);
 _bss_end = .;
 . += 0x20000;
 _stack_top = .;
}

