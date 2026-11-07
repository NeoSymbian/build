/* SPDX-License-Identifier: Apache-2.0
 * imgtools-pre.h -- the preinclude for building the 2010 image tools (rofsbuild, readimage) with today's Linux g++:
 * the compiler settings Symbian's gcc.h gives a TOOLS2 build, without its definitions that clash with glibc
 * (__THROW, va_list); the C++ runtime headers first, so e32cmn.h skips its own operator new / std::terminate. */
#include <cstdio>
#include <cstring>
#include <cstdlib>
#include <cstdarg>
#include <cwchar>
#include <ctime>
#include <climits>
#include <new>
#include <exception>
#define __OPERATOR_NEW_DECLARED__	/* <new> declared them; e32cmn.h then skips its own */
#undef TIME_UTC			/* C11 macro; boost 1.39's xtime.hpp uses the name as an enumerator */
#define __GCC32__ 1
#define __PLACEMENT_NEW_INLINE
#define __PLACEMENT_VEC_NEW_INLINE
#define IMPORT_C
#define EXPORT_C
#define IMPORT_D
#define EXPORT_D
#define __NO_CLASS_CONSTS__
#define I64LIT(x) x##LL
#define UI64LIT(x) x##ULL
#define __NORETURN__ __attribute__((noreturn))
#define NONSHARABLE_CLASS(x) class x
#define NONSHARABLE_STRUCT(x) struct x
#define __NO_THROW
#define TEMPLATE_SPECIALIZATION template<>
#define VA_LIST va_list
#define __VA_LIST_defined
#define VA_START(ap,pn) va_start(ap, pn)
#define VA_ARG(ap,type) va_arg(ap,type)
#define VA_END(ap) va_end(ap)
