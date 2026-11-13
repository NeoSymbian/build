// SPDX-License-Identifier: Apache-2.0
// mbufmgrimpl's sources include "mbufmanager.h", meaning their own inc/MBufManager.h; on a case-sensitive file
// system casefix offers commsbufs/version1's file of that name first. This shim, first on mbufmgrimpl's include path
// (emitter/comms_components.py), names the right one.
#include "../../../src/oss.FCL.sf.os.commsfw/commsfwutils/commsbufs/mbufmgrimpl/inc/MBufManager.h"
