# SPDX-License-Identifier: Apache-2.0
"""comms_components -- the 2010 socket server (ESOCK) without TCPIP6 or a NIF (docs wifi.md W5a/W7, the gate in
"W5a: ESOCK over NeoNet"): the comms process (c32start, c32exe and the root server), the comms framework elements,
ESOCK with the core providers, CommsDat and the commdb shim, insock, and their non-comms dependencies. Our own parts:
neonet.prt (KAfInet: TCP, UDP and the resolver over NEONET.EXE), neotier.dll (the always-up tier manager and MCPR),
the .cmi/.esk configuration and the CommsDat repository (apps/esock/). Merged into components.py's registry.
"""
import os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CF = 'oss.FCL.sf.os.commsfw'
CE = f'{CF}/commsfwsupport/commselements'
ES = f'{CF}/datacommsserver/esockserver'
NS = 'oss.FCL.sf.os.networkingsrv'
PDATA = 'oss.FCL.sf.os.persistentdata'
C32CFG = 'private\\101f7988'            # c32start's private directory: the .cmi files

COMPONENTS = {
    # --- the comms process: c32start reads the .cmi files and starts c32exe, which runs the ESOCK threads
    'c32start': dict(mmp=f'{CF}/commsprocess/commsrootserverconfig/configurator/group/c32start.mmp', rom_data=[
        f'{C32CFG}\\c32start.ini=src/{CF}/commsprocess/commsrootserverconfig/etc/c32start.ini',
        f'{C32CFG}\\esock.cmi=src/{ES}/etc/esock_main.cmi',
        f'{C32CFG}\\esock_tr.cmi=src/{ES}/etc/esock_tr.cmi',
        f'{C32CFG}\\esock_mip.cmi=src/{ES}/etc/esock_mip.cmi',
        f'{C32CFG}\\esock_dip.cmi=src/{ES}/etc/esock_dip.cmi']),
    'c32exe': dict(mmp=f'{CF}/commsprocess/commsrootserverconfig/group/C32EXE.MMP'),
    'c32root': dict(mmp=f'{CF}/commsprocess/commsrootserverconfig/group/c32root.mmp'),
    'procroot': dict(mmp=f'{CE}/rootserver/group/procroot.mmp'),
    'procrootsrv': dict(mmp=f'{CE}/rootserver/group/rootserver.mmp'),
    # --- the comms framework elements
    'commsfw': dict(mmp=f'{CE}/commsfw/group/commsfw.mmp'),
    'netmeta': dict(mmp=f'{CE}/NetMeta/group/NetMeta.mmp'),
    'netinterfaces': dict(mmp=f'{CE}/NetInterfaces/group/NetInterfaces.mmp'),
    'netmessages': dict(mmp=f'{CE}/NetMessages/group/NetMessages.mmp'),
    'netsm': dict(mmp=f'{CE}/StateMachine/group/NETSM.mmp'),
    'netstsrv': dict(mmp=f'{CE}/StartServer/group/NETStSrv.mmp'),
    'netmsg': dict(mmp=f'{CE}/MsgParser/group/NETMSG.mmp'),
    'netsubscribe': dict(mmp=f'{CE}/NetSubscribe/group/NetSubscribe.MMP'),
    'responsemsg': dict(mmp=f'{CE}/ResponseMsg/group/ResponseMsg.mmp'),
    'virtualconstructors': dict(mmp=f'{CE}/virtualconstructors/group/virtualconstructors.mmp'),
    'factories': dict(mmp=f'{CE}/factories/group/factories.mmp'),
    'meshmachine': dict(mmp=f'{CE}/meshmachine/group/meshmachine.mmp'),
    'nodemessages': dict(mmp=f'{CE}/nodemessages/group/nodemessages.mmp'),
    'serverden': dict(mmp=f'{CE}/serverden/group/serverden.mmp'),
    # --- comms buffers (zero-copy off: mbufmgrimpl uses a chunk heap, no shbuf LDD)
    'commsbufs': dict(mmp=f'{CF}/commsfwutils/commsbufs/group/commsbufs.mmp'),
    'mbufmgr': dict(mmp=f'{CF}/commsfwutils/commsbufs/group/mbufmgr.mmp'),
    'mbufmgrimpl': dict(mmp=f'{CF}/commsfwutils/commsbufs/group/mbufmgrimpl.mmp',
                        flags=['-I', os.path.join(REPO, 'apps', 'esock', 'mbufmgrimpl_inc')]),
    # --- ESOCK
    'esock': dict(mmp=f'{ES}/group/ESOCK.MMP'),
    'esocksvr': dict(mmp=f'{ES}/group/ESockSvr.MMP'),
    'esockmessages': dict(mmp=f'{ES}/esock_messages/group/ESockMessages.mmp'),
    'esockmessagesimpl': dict(mmp=f'{ES}/esock_messages/group/ESockMessagesImpl.mmp'),
    'esock_api_ext': dict(mmp=f'{ES}/api_ext/group/api_ext.mmp'),
    'esock_params': dict(mmp=f'{ES}/esock_params/group/esock_params.mmp'),
    'subconparams': dict(mmp=f'{ES}/subcon_params/group/subconparams.mmp'),
    'connservparams': dict(mmp=f'{ES}/connserv_params/group/connservparams.mmp'),
    'commsdataobjects': dict(mmp=f'{ES}/commsdataobjects/group/commsdataobjects.mmp'),
    'commsdataobjectsecom': dict(mmp=f'{ES}/commsdataobjects/group/commsdataobjectsecom.mmp'),
    'coreproviders': dict(mmp=f'{ES}/CoreProviders/group/coreproviders.mmp'),
    'coreprovidersecom': dict(mmp=f'{ES}/CoreProviders/group/coreprovidersecom.mmp'),
    'simpleselectorbase': dict(mmp=f'{ES}/simpleselectorbase/group/simpleselectorbase.mmp'),
    'mobilitycoreproviders': dict(mmp=f'{ES}/MobilityCoreProviders/group/mobilitycoreproviders.mmp'),
    'upscoreproviders': dict(mmp=f'{ES}/UpsCoreProviders/group/upscoreproviders.mmp'),
    'netups': dict(mmp=f'{NS}/networkcontrol/commsuserpromptmgr/group/netups.mmp'),
    'upsclient': dict(mmp='oss.FCL.sf.os.security/authorisation/userpromptservice/server/source/upsclient/upsclient.mmp'),
    'logwrap': dict(mmp=f'{PDATA}/loggingservices/eventlogger/group/LOGWRAP.MMP'),
    'insock': dict(mmp=f'{NS}/esockapiextensions/internetsockets/group/insock.mmp'),
    # --- CommsDat and the commdb shim esocksvr links
    # CommsDat (its repository: the 2010 empty one, policies only; NEOCDB.EXE writes our records at boot)
    'commsdat': dict(mmp=f'{CF}/commsfwtools/preparedefaultcommsdatabase/group/CommsDat.MMP', rom_data=[
        f'private\\10202be9\\cccccc00.txt=src/{CF}/commsfwtools/preparedefaultcommsdatabase/defaultcommdb/src/empty.txt']),
    'commdb': dict(mmp=f'{CF}/commsconfig/commsdatabaseshim/commdbshim/group/commdb.mmp'),
    'shimnotifiercli': dict(mmp=f'{CF}/commsconfig/commsdatabaseshim/commdbshim/Notifier/group/ShimNotifierCli.mmp'),
    'shimnotifiersvr': dict(mmp=f'{CF}/commsconfig/commsdatabaseshim/commdbshim/Notifier/group/ShimNotifierSvr.MMP'),
    # _FOFF with a run-time index (TDbBlob::CellSize)
    'edbms': dict(mmp=f'{PDATA}/persistentstorage/dbms/bmake/EDBMS.MMP', foff_dynamic=True),
    'dial': dict(mmp='oss.FCL.sf.os.cellularsrv/telephonyutils/dial/group/DIAL.MMP'),
    # --- ours (apps/esock): the always-up tier, the protocol module over NEONET.EXE, the CommsDat set-up, the test
    'neotier': dict(mmp='../apps/esock/neotier/neotier.mmp'),
    'neonetprt': dict(mmp='../apps/esock/neonetprt/neonetprt.mmp', rom='neonet.prt', rom_data=[
        'private\\101f7989\\esock\\ip.neonet.esk=apps/esock/ip.neonet.esk']),
    'neocdb': dict(mmp='../apps/esock/neocdb/neocdb.mmp'),
    'neosock': dict(mmp='../apps/esock/neosock/neosock.mmp'),
}
