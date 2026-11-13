// SPDX-License-Identifier: Apache-2.0
// mbufmgrimpl's sources include "mbufmanager.h" and "mbufsizeallocator.h", meaning their own inc/ files; on a case-sensitive file
// system casefix offers commsbufs/version1's files of those names first. This shim, first on mbufmgrimpl's include path
// (emitter/comms_components.py), names the right one.
#include "../../../src/oss.FCL.sf.os.commsfw/commsfwutils/commsbufs/mbufmgrimpl/inc/MBufSizeAllocator.h"
