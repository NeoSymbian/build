"""components -- the registry build_mmp.py builds from: Symbian's minigui configuration.

Key = the LIBRARY stem clients name in their .mmp (`LIBRARY estor.lib` -> "estor").
Fields:
    mmp     path of the REAL 2010 .mmp, relative to src/
    rom     file name in the ROM / import-block name (default: <key>.dll|.exe by type)
    def     override .def path (relative to src/) when the abld rule can't find it
    defs    extra -D macros          flags   extra g++ flags
    nosrc   True: ignore the mmp SOURCE list (component is extra-only, e.g. a null provider)
    extra   extra source files (repo-relative) -- our own null providers
    rtti    True: compile with -frtti
    heap_max    EXE heap max override (bytes) when the mmp's EPOCHEAPSIZE is too small
    foff_dynamic  True: _FOFF with a run-time index (estor) -- keep the classic _FOFF from the prefix header
    allow_wsd   True to accept writable static data in a DLL
    rsc_only    True: build the mmp's resources only (no image)
    rom_data    data files the component needs in the ROM: ["Z path=repo-relative file", ...] (kernel/rom_args.py)

BUILTIN: providers built by their own scripts (euser/efsrv/hal/efile).
"""
import os

import devlink

G = "oss.FCL.sf.os.graphics"
OSSRV = "oss.FCL.sf.os.ossrv"
PDATA = "oss.FCL.sf.os.persistentdata"
TXT = "oss.FCL.sf.os.textandloc"
CUI = "oss.FCL.sf.mw.classicui"
APF = "oss.FCL.sf.mw.appsupport/appfw"
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# FindUtil.h is only in classicui master (BRANCH_RCL_3 dropped findutil_api): that one directory, not master's headers
FINDUTIL_INC = ["-I", os.path.join(REPO, "src", "oss.FCL.sf.mw.classicui@master", "classicui_plat", "findutil_api", "inc")]

BUILTIN = {
    "euser": ("euser.dll", __import__("build_euser_dll").DEF_PATH),
    "efsrv": ("efsrv.dll", devlink.EFSRV_DEF),
    "hal": ("hal.dll", devlink.HAL_DEF),
    "efile": ("efile.exe", devlink.EFILE_DEF),
}

COMPONENTS = {
    # --- tier 1: euser-only leaves ---
    "palette": dict(mmp=f"{G}/graphicsdeviceinterface/colourpalette/group/palette.mmp"),
    "lookuptable": dict(mmp=f"{G}/graphicsdeviceinterface/gdi/group/lookuptable.mmp"),
    "linebreak": dict(mmp=f"{TXT}/fontservices/textbase/group/LineBreak.mmp"),
    # --- tier 2 ---
    "estor": dict(mmp=f"{PDATA}/persistentstorage/store/BMAKE/ESTOR.MMP", foff_dynamic=True),
    "bsul": dict(mmp=f"{OSSRV}/lowlevellibsandfws/apputils/bsul/group/bsul.mmp"),
    "centralrepository": dict(mmp=f"{PDATA}/persistentstorage/centralrepository/group/cenrepcli.mmp"),
    "centralrepositorysrv": dict(mmp=f"{PDATA}/persistentstorage/centralrepository/group/cenrepsrv.mmp"),
    "abclient": dict(mmp=f"{OSSRV}/genericservices/activebackupclient/group/abclient.mmp"),
    "bsulinifile": dict(mmp=f"{OSSRV}/lowlevellibsandfws/apputils/bsul/group/bsulinifile.mmp"),
    "charconv": dict(mmp=f"{TXT}/charconvfw/charconv_fw/group/charconv.mmp"),
    "sysutil": dict(mmp="oss.FCL.sf.os.devicesrv/commonservices/sysutil/group/sysutil.mmp"),
    # the System Agent server defines the platform's P&S keys (e.g. the software-install key apparc's installation monitor needs)
    "sysagt2svr": dict(mmp=f"{OSSRV}/genericservices/systemagent/group/SysAgt2Svr.mmp"),
    "sysagt2cli": dict(mmp=f"{OSSRV}/genericservices/systemagent/group/SysAgt2Cli.mmp"),
    # the backup server (CBaBackupSessionWrapper: the apparc server registers with it at start-up)
    "baksrv": dict(mmp=f"{OSSRV}/lowlevellibsandfws/apputils/group/Baksrv.mmp"),
    "baksrvs": dict(mmp=f"{OSSRV}/lowlevellibsandfws/apputils/group/Baksrvs.mmp"),
    # ...which, with a window server running, loads Uikon's full backup server
    "eikbackupsrv": dict(mmp=f"{CUI}/commonuisupport/uikon/group/EIKBACKUPSRV.MMP"),
    # --- tier 3 ---
    "bafl": dict(mmp=f"{OSSRV}/lowlevellibsandfws/apputils/group/BAFL.MMP"),
    "ecompatchdata": dict(mmp=f"{OSSRV}/lowlevellibsandfws/pluginfw/Framework/MMPFiles/EComPatchData.mmp"),
    "ecom": dict(mmp=f"{OSSRV}/lowlevellibsandfws/pluginfw/Framework/MMPFiles/ECom.mmp"),
    "ecomserver": dict(mmp=f"{OSSRV}/lowlevellibsandfws/pluginfw/Framework/MMPFiles/EComServer.mmp"),
    # --- graphics ---
    "gdi": dict(mmp=f"{G}/graphicsdeviceinterface/gdi/group/GDI.MMP"),
    "fntstr": dict(mmp=f"{TXT}/fontservices/fontstore/group/FNTSTORE.MMP"),
    "fbscli": dict(mmp=f"{G}/fbs/fontandbitmapserver/group/FBSCLI.MMP", rtti=True),
    "fbserv": dict(mmp=f"{G}/fbs/fontandbitmapserver/group/FBSERV.MMP"),
    "scdv": dict(mmp=f"{G}/graphicsdeviceinterface/screendriver/group/generic.mmp", rom="scdv.dll"),
    "bitgdi": dict(mmp=f"{G}/graphicsdeviceinterface/bitgdi/group/BITGDI.MMP", rom="bitgdi.dll"),
    # no GPU resource provider and no compositor on this board: null providers with the REAL .def ordinal tables
    "sgresource": dict(mmp=f"{G}/graphicsresourceservices/graphicsresourceimplementation/group/sgresource_sw.mmp",
                       rom="sgresource.dll", nosrc=True, extra=["toolchain/shims/sgresource_null.cpp"],
                       **{"def": f"{G}/graphicsresourceservices/graphicsresourceinterface/eabi/sgresourceu.def"}),
    "surfaceupdateclient": dict(mmp=f"{G}/graphicscomposition/surfaceupdate/group/surfaceupdateclient.mmp",
                                nosrc=True, extra=["toolchain/shims/surfaceupdateclient_null.cpp"],
                                **{"def": f"{G}/graphicscomposition/surfaceupdate/eabi/surfaceupdateclientU.def"}),
    # the bitmap font rasterizer plug-in: FBS's own stub (no vector stack in this configuration)
    "fbsrasterizer": dict(mmp=f"{G}/fbs/fontandbitmapserver/group/stubrasterizer.mmp", rom="fbsrasterizer.dll",
                          **{"def": f"{G}/fbs/fontandbitmapserver/eabi/fbsrasterizeru.def"}),
    # --- window server (non-NGA) ---
    "ektran": dict(mmp="oss.FCL.sf.os.kernelhwsrv/kernel/eka/ewsrv/ektran.mmp"),
    "ws32": dict(mmp=f"{G}/windowing/windowserver/group/w32_nonnga.mmp", rom="ws32.dll", rtti=True),
    "wsgraphicdrawer": dict(mmp=f"{G}/windowing/windowserver/group/wsgraphicdrawer_nonnga.mmp",
                            rom="wsgraphicdrawer.dll"),
    "wserv": dict(mmp=f"{G}/windowing/windowserver/group/openwfc/wserv_nonnga.mmp", rom="wserv.exe",
                  heap_max=16777216),
    "wsstdplugin": dict(mmp=f"{G}/windowing/windowserver/group/stdplugin_nonnga.mmp", rom="2001b70b.dll"),
    "domaincli": dict(mmp="oss.FCL.sf.os.kernelhwsrv/userlibandfileserver/domainmgr/group/domaincli.mmp"),
    "domainsrv": dict(mmp="oss.FCL.sf.os.kernelhwsrv/userlibandfileserver/domainmgr/group/domainsrv.mmp"),
    "econswserv": dict(mmp=f"{G}/windowing/windowserver/minigui/group/econswserv.mmp"),
    # NeoSymbian: the stock text console (a client of !E32WindowServer), ECONS.DLL in the UI ROM (kernel/rom_args.py)
    # where the Rust UI replaces the window server and its Terminal app serves !E32WindowServer
    "econs": dict(mmp="oss.FCL.sf.os.kernelhwsrv/kernel/eka/ewsrv/econs.mmp", rom="econs_twin.dll"),
    # the Symbian Foundation's MiniGUI test app (a plain RWsSession client): the first legacy GUI program
    "grid": dict(mmp="symbian-qemu/applications/Symbian_MiniGUI_TestApp/Grid.mmp"),
    # --- the application framework and control environment (legacy GUI apps; Phorepoc's registry is the map) ---
    "numberconversion": dict(mmp=f"{TXT}/textrendering/numberformatting/group/NumberConversion.mmp"),
    "field": dict(mmp=f"{TXT}/textrendering/texthandling/group/FIELD.MMP"),
    "etext": dict(mmp=f"{TXT}/textrendering/texthandling/group/ETEXT.MMP"),
    "tagma": dict(mmp=f"{TXT}/textrendering/textformatting/group/TAGMA.MMP"),
    "form": dict(mmp=f"{TXT}/textrendering/textformatting/group/FORM2.MMP"),
    "apmime": dict(mmp=f"{OSSRV}/genericservices/mimerecognitionfw/apmime/APMIME.MMP"),
    "apparc": dict(mmp=f"{APF}/apparchitecture/group/APPARC.MMP"),
    "apgrfx": dict(mmp=f"{APF}/apparchitecture/group/APGRFX.MMP"),
    "apfile": dict(mmp=f"{APF}/apparchitecture/group/APFILE.MMP"),
    "aplist": dict(mmp=f"{APF}/apparchitecture/group/APLIST.MMP"),
    # the server's Central Repository settings (apparc's own and the icon/caption overrides), as the 2010 release shipped them
    "apserv": dict(mmp=f"{APF}/apparchitecture/group/APSERV.MMP", rom_data=[
        f"private\\10202be9\\{uid}.txt=src/{APF}/apparchitecture/tdata/{uid}.txt" for uid in ("10003a3f", "1028583d")]),
    "apsexe": dict(mmp=f"{APF}/apparchitecture/group/APSEXE.MMP"),
    "viewcli": dict(mmp=f"{APF}/viewserver/group/VIEWCLI.MMP"),
    "viewsrv": dict(mmp=f"{APF}/viewserver/group/VIEWSRV.MMP"),
    "egul": dict(mmp=f"{CUI}/lafagnosticuifoundation/uigraphicsutils/group/EGUL.MMP"),
    "cone": dict(mmp=f"{CUI}/lafagnosticuifoundation/cone/group/CONE.MMP"),
    # with the FEP framework's Central Repository settings (CCoeEnv's FEP tracker opens 10272618 at start-up)
    "fepbase": dict(mmp="oss.FCL.sf.mw.inputmethods/fep/frontendprocessor/group/FEPBASE.MMP", rom_data=[
        f"private\\10202be9\\{uid}.txt=src/oss.FCL.sf.mw.inputmethods/fep/frontendprocessor/group/{uid}.txt"
        for uid in ("10272618", "10272619", "10009793")]),
    # the error-resolver texts (errorres.rsg is included by eikcore and commonengine); also at the path S60's CTextResolver opens
    "errorres": dict(mmp="oss.FCL.sf.os.devicesrv/commonservices/commonengineresources/group/commonengineresources.mmp",
                     rsc_only=True, rom_data=[r"resource\errors\errorres.rsc=emitter/rsc/resource/errorres.rsc"]),
    # --- Uikon + Avkon (S60 classicui) and their support libraries: the legacy GUI apps' base (map: Phorepoc's registry) ---
    "commonengine": dict(mmp=f"{OSSRV}/genericservices/s60compatibilityheaders/commonengine/group/commonengine.mmp"),
    "featmgr": dict(mmp=f"{PDATA}/featuremgmt/featuremgr/group/featmgr.mmp"),
    "featmgrserver": dict(mmp=f"{PDATA}/featuremgmt/featuremgr/group/featmgrserver.mmp", rom_data=[r"private\10205054\features.dat=emitter/features.dat"]),
    "cenrepnotifhandler": dict(mmp=f"{PDATA}/persistentstorage/centralrepository/cenrepnotifierhandler/group/cenrepnotifhandler.mmp"),
    "platformenv": dict(mmp="oss.FCL.sf.os.devicesrv/commonservices/PlatformEnv/group/PlatformEnv.mmp", **{"def": "oss.FCL.sf.os.devicesrv/commonservices/PlatformEnv/EABI/PlatformEnvCenRepU.DEF"}),
    "sysversioninfo": dict(mmp="oss.FCL.sf.os.devicesrv/commonservices/PlatformEnv/sysversioninfo/group/sysversioninfo.mmp"),
    "platformver": dict(mmp="oss.FCL.sf.os.devicesrv/commonservices/PlatformEnv/platformver/group/platformver.mmp"),
    "disknotifyhandler": dict(mmp="oss.FCL.sf.os.devicesrv/commonservices/PlatformEnv/disknotifyhandler/group/disknotifyhandler.mmp"),
    "syslangutil": dict(mmp="oss.FCL.sf.os.devicesrv/sysstatemgmt/syslangutil/group/syslangutil.mmp"),
    "jplangutil": dict(mmp=f"{TXT}/textandlocutils/jplangutil/group/jplangutil.mmp"),
    "numbergrouping": dict(mmp=f"{TXT}/textandlocutils/numbergrouping/group/NumberGrouping.mmp"),
    "etul": dict(mmp=f"{CUI}/lafagnosticuifoundation/uigraphicsutils/group/etul.mmp"),
    "clock": dict(mmp=f"{CUI}/lafagnosticuifoundation/clockanim/group/CLOCK.MMP"),
    "clocka": dict(mmp=f"{CUI}/lafagnosticuifoundation/clockanim/group/CLOCKA.MMP"),
    "bmpanim": dict(mmp=f"{CUI}/lafagnosticuifoundation/bmpanimation/group/BmpAnim.mmp"),
    "bmpansrv": dict(mmp=f"{CUI}/lafagnosticuifoundation/bmpanimation/group/BmpAnSrv.mmp"),
    "eiksrvc": dict(mmp=f"{CUI}/commonuisupport/uikon/group/EIKSRVC.MMP"),
    "eikcore": dict(mmp=f"{CUI}/commonuisupport/uikon/group/EIKCORE.MMP", foff_dynamic=True, rtti=True),   # dynamic_cast<CAknAppUi*> needs the typeinfo; eikprivate.cpp: _FOFF(.., iBuf[maxLength])
    "eiksrv": dict(mmp=f"{CUI}/commonuisupport/uikon/group/eiksrv.mmp"),
    "eiksrvs": dict(mmp=f"{CUI}/commonuisupport/uikon/group/EIKSRVS.MMP"),
    "eiksrvui": dict(mmp=f"{CUI}/uifw/EikStd/srvuisrc/EIKSRVUI.MMP"),
    "eikalert": dict(mmp=f"{CUI}/uifw/EikStd/alertsrc/Eikalert.mmp"),
    "uiklaf": dict(mmp=f"{CUI}/uifw/uiklaf/Group/UIKLAF.MMP", **{"def": f"{CUI}/commonuisupport/uilaf/eabi/uiklaf_unbranchedu.def"}),
    "eikcoctllaf": dict(mmp=f"{CUI}/uifw/uiklaf/Group/EikCoCtlLaf.MMP"),
    "eikcoctl": dict(mmp=f"{CUI}/uifw/EikStd/coctlsrc/EIKCOCTL.MMP", flags=["-fkeep-inline-functions"], rtti=True),
    "eikctl": dict(mmp=f"{CUI}/uifw/eikctl/group/eikctl.mmp"),
    "eikdlg": dict(mmp=f"{CUI}/uifw/EikStd/dlgsrc/EIKDLG.MMP"),
    "eikcdlg": dict(mmp=f"{CUI}/uifw/EikStd/cdlgsrc/EIKCDLG.MMP"),
    "avkon": dict(mmp=f"{CUI}/uifw/AvKon/group/avkon.mmp", rtti=True, flags=FINDUTIL_INC, rom_data=[f"private\\10202be9\\101F876E.txt=src/{CUI}/uifw/AvKon/CenRep/101F876E.txt"]),
    "aknnotify": dict(mmp=f"{CUI}/uifw/AvKon/notifsrc/aknNotify.mmp"),
    "akncapserverclient": dict(mmp=f"{CUI}/uifw/AknGlobalUI/AknCapServer/group/AknCapServerClient.mmp"),
    "akncapserver": dict(mmp=f"{CUI}/uifw/AknGlobalUI/AknCapServer/group/AknCapServer.mmp", rtti=True),
    "aknanimdll": dict(mmp=f"{CUI}/uifw/AvKon/animdllsrc/AknAnimDll.mmp"),
    "akntransitionutils": dict(mmp=f"{CUI}/uifw/AvKon/AknTransitionUtils/group/akntransitionutils.mmp"),
    "aknphysics": dict(mmp=f"{CUI}/uifw/AvKon/aknphysics/group/aknphysics.mmp"),
    "gfxtrans": dict(mmp=f"{CUI}/lafagnosticuifoundation/graphicseffects/group/GfxTransEffect.mmp"),
    "servicehandler": dict(mmp=f"{CUI}/applicationinterworkingfw/ServiceHandler/group/ServiceHandler.mmp"),
    "hlplch": dict(mmp=f"{CUI}/uiutils/hlplch/group/hlplch.mmp"),
    "findutil": dict(mmp=f"{CUI}/uiutils/Findutil/group/FindUtil.mmp", flags=FINDUTIL_INC),
    "cdlengine": dict(mmp="oss.FCL.sf.mw.uiresources/layouts/cdl/CdlEngine/group/CdlEngine.mmp"),
    "cdlserver": dict(mmp="oss.FCL.sf.mw.uiresources/layouts/cdl/CdlServer/group/CdlServer.mmp"),
    "aknlayout2": dict(mmp="oss.FCL.sf.mw.uiresources/layouts/aknlayout2/group/AknLayout2.mmp"),
    "aknlayout2scalable": dict(mmp="oss.FCL.sf.mw.uiresources/layouts/aknlayout2/group/AknLayout2Scalable.mmp"),
    "layoutinst": dict(mmp="oss.FCL.sf.mw.uiresources/layouts/aknlayout2/group/../generated/layoutinst.mmp", rom="101fe2aa.dll"),
    # one resolution's layout data: nHD (360x640 / 640x360) -- boot with SCREEN=360x640
    "layoutinst_nhd4": dict(mmp="oss.FCL.sf.mw.uiresources/layouts/aknlayout2/generated/Nhd4_akn_app/layoutinst_nhd4.mmp",
                            rom="2001cb93.dll"),
    "aknskins": dict(mmp="oss.FCL.sf.mw.uiresources/skins/AknSkins/group/AknSkins.mmp"),
    "aknskinsrv": dict(mmp="oss.FCL.sf.mw.uiresources/skins/AknSkins/group/AknSkinSrv.mmp", defs=["AKNS_TRACING_ENABLED_ERROR"], rom_data=[   # Personalisation (skins), Themes (from its .crml)
        "private\\10202be9\\101F876F.txt=src/oss.FCL.sf.mw.uiresources/skins/AknSkins/CenRep/101F876F.txt",
        "private\\10202be9\\102818E8.txt=emitter/cenrep/102818E8.txt"]),
    "aknskinsrvexe": dict(mmp="oss.FCL.sf.mw.uiresources/skins/AknSkins/group/AknSkinSrvMain.mmp", rom="aknskinsrv.exe"),
    "aknskinrenderlib": dict(mmp="oss.FCL.sf.mw.uiresources/skins/AknSkins/group/AknSkinRenderLib.mmp", flags=["-U__MARM_ARMV5__"]),
    "aknicon": dict(mmp="oss.FCL.sf.mw.uiresources/uigraphics/AknIcon/group/AknIcon.mmp", rtti=True),
    "akniconsrv": dict(mmp="oss.FCL.sf.mw.uiresources/uigraphics/AknIcon/group/AknIconSrvMain.mmp"),
    "fontprovider": dict(mmp="oss.FCL.sf.mw.uiresources/fontsupport/fontprovider/Group/FontProvider.mmp"),
    "fontutils": dict(mmp="oss.FCL.sf.mw.uiresources/fontsupport/fontutils/FontUtils/group/FontUtils.mmp"),
    "aknpictograph": dict(mmp="oss.FCL.sf.mw.uiresources/pictographs/AknPictograph/group/AknPictograph.mmp"),
    "ptiengine": dict(mmp="oss.FCL.sf.mw.inputmethods/textinput/ptienginev2/group/ptienginev2.mmp"),
    "touchfeedback": dict(mmp="oss.FCL.sf.mw.hapticsservices/tactilefeedback/tactilefeedbackclient/group/touchfeedback.mmp"),
    "aknnotifyplugin2": dict(mmp=f"{CUI}/uifw/AknGlobalUI/group/AknNotifyPlugin2.mmp"),
    "aknnotifyplugin": dict(mmp=f"{CUI}/uifw/AvKon/AknNotifyPlugin_dll/group/AknNotifyPlugin.mmp"),   # eiksrvui's first call
    "aknnotifierwrapper": dict(mmp=f"{CUI}/uifw/AknGlobalUI/NotifierWrapper/group/aknnotifierwrapper.mmp"),
    "findutilimpl": dict(mmp=f"{CUI}/uiutils/Findutil/group/FindUtilImpl.mmp", flags=FINDUTIL_INC),
    # the FEP's resources only (avkon's character map includes aknfep.rsg); the FEP itself is not built
    "aknfep": dict(mmp="oss.FCL.sf.mw.inputmethods/fep/aknfep/group/AknFep.mmp", rsc_only=True),
    # --- the legacy GUI apps ---
    "perfmon": dict(mmp="oss.FCL.sf.app.rndtools/perfmon/group/perfmon.mmp"),
    # --- the 3-DLL locale (SYMBIAN_DISTINCT_LOCALE_MODEL): from uiresources master (BRANCH_RCL_3 has no loce32) ---
    "elocl_language_en_gb": dict(
        mmp="oss.FCL.sf.mw.uiresources@master/locales/loce32/language/group/elocl_language_en_gb.mmp", rom="elocl_lan.001"),
    "elocl_region_gb": dict(
        mmp="oss.FCL.sf.mw.uiresources@master/locales/loce32/region/group/elocl_region_gb.mmp", rom="elocl_reg.826",
        flags=["-finput-charset=ISO-8859-1"]),
    "elocl_collation_en": dict(
        mmp="oss.FCL.sf.mw.uiresources@master/locales/loce32/collation/group/elocl_collation_en.mmp", rom="elocl_col.001"),
}


def rom_name(key: str, targettype: str = "dll") -> str:
    c = COMPONENTS[key]
    if "rom" in c:
        return c["rom"]
    return key + (".exe" if targettype in ("exe", "exexp", "stdexe") else ".dll")
