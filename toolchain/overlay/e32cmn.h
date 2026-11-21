// toolchain/overlay/e32cmn.h -- include-path overlay in front of the real <e32cmn.h>.
//
// We build with -fno-exceptions, so TRAP is the setjmp-style TTrap::Trap/UnTrap pair
// (__LEAVE_EQUALS_THROW__ undefined). TTrap::Trap RETURNS TWICE (once directly, once when
// User::Leave longjmps back), but the unmodified header cannot tell a modern compiler so.
// GCC 14 at -O2 therefore keeps locals that are live across the TRAP in callee-saved
// registers, and the leave restores their *setjmp-time* values: e.g. efile's
// TDrive::FileOpen saw pS==NULL after a failed open although FileOpenL had created the
// share -> the CFileShare/CFileCB leaked on iMountQ -> later RFs::Replace / opens of the
// same name failed KErrInUse (cenrep commit, apmime type store). The 2010-era compilers
// (GCC 3.x, no aggressive inlining / register promotion) never exposed this.
//
// Fix without touching the source: re-declare the same exported symbol as a free function
// carrying __attribute__((returns_twice)) and route the TRAP macros through it. Same
// mangled name => same euser export, same AAPCS call (this in r0, aResult in r1).
#ifndef SYM_OVERLAY_E32CMN_H
#define SYM_OVERLAY_E32CMN_H
#include_next <e32cmn.h>

#if !defined(__KERNEL_MODE__) && !defined(__LEAVE_EQUALS_THROW__)
extern "C" TInt _ZN5TTrap4TrapERi(TTrap* aThis, TInt& aResult) __attribute__((returns_twice));

#undef TRAP
#undef TRAPD
#undef TRAP_IGNORE
#ifdef __ARM_FP
// Code built with VFP (ARMv8 softfp, docs user-side-smp.md US2) keeps values in d8-d15, which are callee-saved: a leave
// must restore them like r4-r11. TTrap has no room, so the trap frame gets 64 bytes after it and NeoTrapFp (euser
// uc_trp.cia) saves d8-d15 there; the leave puts them back.
extern "C" TInt NeoTrapFp(TTrap* aThis, TInt& aResult) __attribute__((returns_twice));
struct TNeoTrapFp { TTrap iTrap; TUint64 iFp[8]; };
#define NEO_TRAP_FP 1	// for the 2010 code that expands a TRAP by hand (euser ub_act.cpp)
#define TRAP(_r,_s) {TNeoTrapFp __t;if (NeoTrapFp(&__t.iTrap,_r)==0){_s;TTrap::UnTrap();}}
#define TRAPD(_r,_s) TInt _r;{TNeoTrapFp __t;if (NeoTrapFp(&__t.iTrap,_r)==0){_s;TTrap::UnTrap();}}
#define TRAP_IGNORE(_s) {TInt _ignore;TNeoTrapFp __t;if (NeoTrapFp(&__t.iTrap,_ignore)==0){_s;TTrap::UnTrap();}}
#else
#define TRAP(_r,_s) {TTrap __t;if (_ZN5TTrap4TrapERi(&__t,_r)==0){_s;TTrap::UnTrap();}}
#define TRAPD(_r,_s) TInt _r;{TTrap __t;if (_ZN5TTrap4TrapERi(&__t,_r)==0){_s;TTrap::UnTrap();}}
#define TRAP_IGNORE(_s) {TInt _ignore;TTrap __t;if (_ZN5TTrap4TrapERi(&__t,_ignore)==0){_s;TTrap::UnTrap();}}
#endif
#endif

#endif
