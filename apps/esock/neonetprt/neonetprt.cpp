// SPDX-License-Identifier: Apache-2.0
// neonetprt.cpp -- NEONET.PRT: ESOCK's KAfInet protocol module (TCP, UDP, the host resolver) over NeoNet, the
// phone's IP stack in NEONET.EXE (docs wifi.md W5a). No TCPIP6, no NIF: every socket call becomes a NeoNet call
// through NEONET.DLL, and ESOCK's own connection stack is NEOTIER.DLL's always-up one. The module runs in ESOCK's
// IP data thread, so nothing here blocks: each waiting NeoNet call is an active object (CNeoOp) whose completion
// becomes an MSocketNotify up-call. A socket's waiting calls are cancelled by closing its NeoNet socket (NEONET then
// completes them with KErrCancel).
#include "neonetprt.h"

// ---- the session
CNeoSession* CNeoSession::NewL()
	{
	CNeoSession* s = new (ELeave) CNeoSession;
	CleanupStack::PushL(s);
	User::LeaveIfError(s->iNet.Connect());
	CleanupStack::Pop(s);
	s->iRefs = 1;
	return s;
	}

// ---- one waiting call
CNeoOp::CNeoOp(CNeoSap& aSap, TKind aKind) : CActive(EPriorityStandard), iSap(aSap), iKind(aKind)
	{
	CActiveScheduler::Add(this);
	}

void CNeoOp::RunL()
	{
	iSap.Done(iKind, iStatus.Int());
	}

void CNeoOp::DoCancel()
	{
	iSap.Cancelled(iKind);
	}

// ---- a socket
CNeoSap* CNeoSap::NewL(TUint aSockType, CNeoSession* aSession)
	{
	CNeoSap* s = new (ELeave) CNeoSap(aSockType);
	CleanupStack::PushL(s);
	s->ConstructL(aSession);
	CleanupStack::Pop(s);
	return s;
	}

CNeoSap::CNeoSap(TUint aSockType) : iSockType(aSockType), iId(-1), iRxPtr(NULL, 0), iTxPtr(NULL, 0)
	{
	}

void CNeoSap::ConstructL(CNeoSession* aSession)
	{
	if (aSession)
		(iSession = aSession)->Open();							// an accepted connection: the listener's session
	else
		iSession = CNeoSession::NewL();
	iRx = HBufC8::NewL(KNeoNetMaxIo);
	iRxPtr.Set(iRx->Des());
	iTx = HBufC8::NewL(KNeoNetMaxIo);
	iTxPtr.Set(iTx->Des());
	iConnectOp = new (ELeave) CNeoOp(*this, CNeoOp::EConnect);
	iRecvOp = new (ELeave) CNeoOp(*this, CNeoOp::ERecv);
	iSendOp = new (ELeave) CNeoOp(*this, CNeoOp::ESend);
	iAcceptOp = new (ELeave) CNeoOp(*this, CNeoOp::EAccept);
	iLocal.SetFamily(KAfInet);
	iRemote.SetFamily(KAfInet);
	}

CNeoSap::~CNeoSap()
	{
	delete iConnectOp;										// each cancels its call first
	delete iRecvOp;
	delete iSendOp;
	delete iAcceptOp;
	CloseSocket();
	if (iSession)
		iSession->Close();
	delete iRx;
	delete iTx;
	}

void CNeoSap::CloseSocket()
	{
	if (iId >= 0)
		{
		iSession->iNet.CloseSocket(iId);
		iId = -1;
		}
	}

// a cancelled call: make NEONET answer it (KErrCancel), so CActive::Cancel's wait ends
void CNeoSap::Cancelled(CNeoOp::TKind aKind)
	{
	if (aKind == CNeoOp::EConnect)
		iSession->iNet.Close();								// no id yet: the session goes, and its waits with it
	else
		CloseSocket();
	}

void CNeoSap::Start()
	{
	StartRecv();
	}

// an accepted connection receives from the start; what came before ESOCK gave it a notifier is announced now
void CNeoSap::SetNotify(MSocketNotify* aSocket)
	{
	CServProviderBase::SetNotify(aSocket);
	if (!aSocket)
		return;
	if (iRxReady)
		iSocket->NewData(Stream() ? iRxPtr.Length() - iRxPos : 1);
	else if (iEof)
		iSocket->NewData(KNewDataEndofData);
	}

void CNeoSap::LocalName(TSockAddr& aAddr) const
	{
	TInetAddr a(iLocal);
	if (a.Address() == 0 && iSession->iNet.Handle())
		{
		TBuf8<KNeoNetStatusSize> st;
		if (iSession->iNet.Status(st) == KErrNone && st[1] == ENeoNetUp)
			a.SetAddress(NeoNetIp(st.Mid(4, 4)));
		}
	aAddr = a;
	}

TInt CNeoSap::SetLocalName(TSockAddr& aAddr)
	{
	iLocal = aAddr;
	return !Stream() && iId < 0 ? OpenUdp() : KErrNone;		// a datagram socket binds now
	}

void CNeoSap::RemName(TSockAddr& aAddr) const
	{
	aAddr = iRemote;
	}

TInt CNeoSap::SetRemName(TSockAddr& aAddr)
	{
	iRemote = aAddr;
	return KErrNone;
	}

TInt CNeoSap::GetOption(TUint /*aLevel*/, TUint /*aName*/, TDes8& /*aOption*/) const
	{
	return KErrNotSupported;
	}

// shortcut: options are accepted and ignored (NeoNet has none yet); apps that set TCP_NODELAY and the like go on
TInt CNeoSap::SetOption(TUint /*aLevel*/, TUint /*aName*/, const TDesC8& /*aOption*/)
	{
	return KErrNone;
	}

void CNeoSap::Ioctl(TUint /*aLevel*/, TUint /*aName*/, TDes8* /*aOption*/)
	{
	iSocket->Error(KErrNotSupported, MSocketNotify::EErrorIoctl);
	}

void CNeoSap::CancelIoctl(TUint /*aLevel*/, TUint /*aName*/)
	{
	}

TInt CNeoSap::OpenUdp()
	{
	TInt r = iSession->iNet.UdpOpen(iLocal.Port());
	if (r < 0)
		return r;
	iId = r;
	StartRecv();
	return KErrNone;
	}

void CNeoSap::AutoBind()
	{
	if (!Stream() && iId < 0)
		OpenUdp();
	}

void CNeoSap::ActiveOpen()
	{
	if (!Stream())												// a "connected" datagram socket: a default peer
		{
		TInt r = iId < 0 ? OpenUdp() : KErrNone;
		if (r != KErrNone)
			{
			iSocket->Error(r, MSocketNotify::EErrorConnect);
			return;
			}
		iConnected = ETrue;
		iSocket->ConnectComplete();
		return;
		}
	iSession->iNet.TcpConnect(iRemote.Address(), iRemote.Port(), iConnectOp->Status());
	iConnectOp->Go();
	}

void CNeoSap::ActiveOpen(const TDesC8& /*aConnectionData*/)
	{
	ActiveOpen();
	}

TInt CNeoSap::PassiveOpen(TUint /*aQueSize*/)
	{
	if (!Stream())
		return KErrNotSupported;
	TInt r = iSession->iNet.TcpListen(iLocal.Port());			// shortcut: one waiting connection (NeoNet's backlog)
	if (r < 0)
		return r;
	iId = r;
	iSession->iNet.Accept(iId, iPeer, iAcceptOp->Status());
	iAcceptOp->Go();
	return KErrNone;
	}

TInt CNeoSap::PassiveOpen(TUint aQueSize, const TDesC8& /*aConnectionData*/)
	{
	return PassiveOpen(aQueSize);
	}

void CNeoSap::Shutdown(TCloseType aOption)
	{
	iConnectOp->Cancel();
	iAcceptOp->Cancel();
	iRecvOp->Cancel();
	iRxReady = EFalse;
	if (aOption != EStopOutput && aOption != EImmediate && iSendOp->IsActive())
		{
		iClosing = ETrue;										// the queued bytes go first (Done ESend closes)
		return;
		}
	iSendOp->Cancel();
	CloseSocket();
	if (aOption != EImmediate)
		iSocket->CanClose();
	}

void CNeoSap::Shutdown(TCloseType aOption, const TDesC8& /*aDisconnectionData*/)
	{
	Shutdown(aOption);
	}

TUint CNeoSap::Write(const TDesC8& aDesc, TUint /*aOptions*/, TSockAddr* aAddr)
	{
	if (iSendOp->IsActive() || iClosing)
		return 0;												// CanSend follows once NEONET took the last write
	TInt n = Min(aDesc.Length(), KNeoNetMaxIo);
	if (Stream())
		{
		if (!iConnected || iId < 0)
			return 0;
		iTxPtr.Copy(aDesc.Left(n));
		iTxPos = 0;
		StartSend();
		return n;
		}
	if (iId < 0)
		{
		TInt r = OpenUdp();
		if (r != KErrNone)
			{
			iSocket->Error(r, MSocketNotify::EErrorSend);
			return 0;
			}
		}
	TInetAddr to(aAddr ? TInetAddr(*aAddr) : iRemote);
	iTxPtr.Copy(aDesc.Left(n));
	NeoNetEndpoint(iTo, to.Address(), to.Port());
	iSession->iNet.SendTo(iId, iTxPtr, iTo, iSendOp->Status());
	iSendOp->Go();
	return aDesc.Length();										// a datagram: all or nothing
	}

void CNeoSap::StartSend()
	{
	iTxRest.Set(iTxPtr.Mid(iTxPos));
	iSession->iNet.Send(iId, iTxRest, iSendOp->Status());
	iSendOp->Go();
	}

void CNeoSap::StartRecv()
	{
	if (iId < 0 || iRecvOp->IsActive() || iRxReady || !(iConnected || !Stream()))
		return;
	iRxPtr.Zero();
	iRxPos = 0;
	if (Stream())
		iSession->iNet.Recv(iId, iRxPtr, iRecvOp->Status());
	else
		iSession->iNet.RecvFrom(iId, iRxPtr, iPeer, iRecvOp->Status());
	iRecvOp->Go();
	}

void CNeoSap::GetData(TDes8& aDesc, TUint /*aOptions*/, TSockAddr* aAddr)
	{
	if (!iRxReady)
		{
		aDesc.Zero();
		return;
		}
	if (Stream())
		{
		// ESOCK sets the length it wants (at most what NewData announced) and we fill that much in place, as
		// commsfw's ipc.prt does; a zero length asks for what fits
		TInt avail = iRxPtr.Length() - iRxPos;
		TInt n = Min(aDesc.Length() ? aDesc.Length() : aDesc.MaxLength(), avail);
		Mem::Copy(const_cast<TUint8*>(aDesc.Ptr()), iRxPtr.Ptr() + iRxPos, n);
		aDesc.SetLength(n);
		iRxPos += n;
		if (iRxPos < iRxPtr.Length())
			return;
		}
	else
		{
		aDesc.Copy(iRxPtr.Left(Min(aDesc.MaxLength(), iRxPtr.Length())));	// the rest of the datagram is lost
		if (aAddr)
			{
			TInetAddr from(NeoNetIp(iPeer), NeoNetPort(iPeer));
			*aAddr = from;
			}
		}
	iRxReady = EFalse;
	StartRecv();
	}

void CNeoSap::Done(CNeoOp::TKind aKind, TInt aResult)
	{
	switch (aKind)
		{
	case CNeoOp::EConnect:
		if (aResult < 0)
			{
			iSocket->Error(aResult, MSocketNotify::EErrorConnect);
			return;
			}
		iId = aResult;
		iConnected = ETrue;
		iSocket->ConnectComplete();
		StartRecv();
		return;
	case CNeoOp::EAccept:
		{
		if (aResult < 0)
			{
			iSocket->Error(aResult, MSocketNotify::EErrorConnect);
			return;
			}
		CNeoSap* conn = NULL;
		TRAPD(r, conn = CNeoSap::NewL(KSockStream, iSession));
		if (r != KErrNone)
			{
			iSession->iNet.CloseSocket(aResult);
			iSocket->Error(r, MSocketNotify::EErrorConnect);
			return;
			}
		conn->iId = aResult;
		conn->iConnected = ETrue;
		conn->iLocal = iLocal;
		conn->iRemote = TInetAddr(NeoNetIp(iPeer), NeoNetPort(iPeer));
		iSession->iNet.Accept(iId, iPeer, iAcceptOp->Status());		// the next one
		iAcceptOp->Go();
		conn->StartRecv();
		iSocket->ConnectComplete(*conn);							// ESOCK owns it now
		return;
		}
	case CNeoOp::ERecv:
		if (aResult == KErrCancel)
			return;
		if (Stream() && aResult == 0)
			iEof = ETrue;											// the peer closed
		else if (aResult >= 0)
			iRxReady = ETrue;
		else if (aResult == KErrOverflow && !Stream())
			{
			StartRecv();											// a datagram too big for us: dropped
			return;
			}
		if (!iSocket)
			return;													// SetNotify announces it
		if (aResult < 0)
			iSocket->Error(aResult, MSocketNotify::EErrorRecv);
		else if (iEof)
			iSocket->NewData(KNewDataEndofData);
		else
			iSocket->NewData(Stream() ? aResult : 1);
		return;
	case CNeoOp::ESend:
		if (aResult < 0)
			{
			if (aResult != KErrCancel)
				iSocket->Error(aResult, MSocketNotify::EErrorSend);
			return;
			}
		if (Stream() && (iTxPos += aResult) < iTxPtr.Length())
			{
			StartSend();											// NEONET took part of it: the rest
			return;
			}
		iTxPtr.Zero();
		if (iClosing)
			{
			CloseSocket();
			iSocket->CanClose();
			return;
			}
		iSocket->CanSend();
		return;
		}
	}

TInt CNeoSap::SecurityCheck(MProvdSecurityChecker* /*aChecker*/)
	{
	return KErrNone;
	}

// ---- the resolver
CNeoResolver* CNeoResolver::NewL()
	{
	CNeoResolver* r = new (ELeave) CNeoResolver;
	CleanupStack::PushL(r);
	r->iOp = new (ELeave) COp(*r);
	CleanupStack::Pop(r);
	return r;
	}

CNeoResolver::~CNeoResolver()
	{
	delete iOp;
	iNet.Close();
	}

void CNeoResolver::GetByName(TNameRecord& aName)
	{
	iQuery = &aName;
	iName.Copy(aName.iName.Left(iName.MaxLength()));
	if (iName == iAnswered && TInetAddr::Cast(aName.iAddr).Address() == NeoNetIp(iIp))
		{
		iAnswered.Zero();										// Next() after the one answer: no more
		iNotify->QueryComplete(KErrNotFound);
		return;
		}
	TInt r = iNet.Handle() ? KErrNone : iNet.Connect();
	if (r != KErrNone)
		{
		iNotify->QueryComplete(r);
		return;
		}
	iIp.Zero();
	iNet.Resolve(iName, iIp, iOp->Status());
	iOp->Go();
	}

void CNeoResolver::Resolved(TInt aResult)
	{
	if (aResult == KErrNone && iIp.Length() == 4)
		{
		TInetAddr a(NeoNetIp(iIp), 0);
		iQuery->iAddr = a;
		iAnswered = iName;
		}
	iNotify->QueryComplete(aResult == KErrNone && iIp.Length() != 4 ? KErrNotFound : aResult);
	}

void CNeoResolver::GetByAddress(TNameRecord& /*aName*/)
	{
	iNotify->QueryComplete(KErrNotSupported);				// shortcut: no reverse lookups in NeoNet
	}

void CNeoResolver::SetHostName(TDes& aNameBuf)
	{
	iHostName = aNameBuf.Left(iHostName.MaxLength());
	}

void CNeoResolver::GetHostName(TDes& aNameBuf)
	{
	_LIT(KDefault, "neosymbian");
	aNameBuf = (iHostName.Length() ? TPtrC(iHostName) : TPtrC(KDefault)).Left(aNameBuf.MaxLength());
	}

void CNeoResolver::CancelCurrentOperation()
	{
	iOp->Cancel();
	}

TInt CNeoResolver::SecurityCheck(MProvdSecurityChecker* /*aChecker*/)
	{
	return KErrNone;
	}

// ---- the protocols and the family
static void Describe(TServerProtocolDesc& aDesc, TUint aSockType)
	{
	TBool tcp = aSockType == KSockStream;
	_LIT(KTcp, "tcp");
	_LIT(KUdp, "udp");
	aDesc.iName = tcp ? KTcp() : KUdp();
	aDesc.iAddrFamily = KAfInet;
	aDesc.iSockType = aSockType;
	aDesc.iProtocol = tcp ? KProtocolInetTcp : KProtocolInetUdp;
	aDesc.iVersion = TVersion(1, 0, 0);
	aDesc.iByteOrder = EBigEndian;
	aDesc.iServiceInfo = tcp ? (KSIStreamBased | KSIInOrder | KSIReliable | KSIGracefulClose)
		: (KSIConnectionLess | KSIDatagram | KSIGracefulClose);
	aDesc.iNamingServices = KNSNameResolution;					// RHostResolver opens on either
	aDesc.iSecurity = KSocketNoSecurity;
	aDesc.iMessageSize = tcp ? KSocketMessageSizeIsStream : 4096;	// NeoNet's UDP buffer
	aDesc.iServiceTypeInfo = ESocketSupport | ECantProcessMBufChains;
	aDesc.iNumSockets = KUnlimitedSockets;
	}

CServProviderBase* CNeoProtocol::NewSAPL(TUint aSockType)
	{
	return CNeoSap::NewL(aSockType);
	}

CHostResolvProvdBase* CNeoProtocol::NewHostResolverL()
	{
	return CNeoResolver::NewL();
	}

void CNeoProtocol::Identify(TServerProtocolDesc* aDesc) const
	{
	Describe(*aDesc, iSockType);
	}

CProtocolBase* CNeoFamily::NewProtocolL(TUint aSockType, TUint /*aProtocol*/)
	{
	return new (ELeave) CNeoProtocol(aSockType);
	}

TUint CNeoFamily::ProtocolList(TServerProtocolDesc*& aList)
	{
	aList = new TServerProtocolDesc[2];							// index 1 = tcp, 2 = udp (ip.neonet.esk)
	if (!aList)
		return 0;
	Describe(aList[0], KSockStream);
	Describe(aList[1], KSockDatagram);
	return 2;
	}

// ordinal 1: ESOCK's entry point into a protocol module
extern "C"
	{
	IMPORT_C CProtocolFamilyBase* InstallNeoNet();
	EXPORT_C CProtocolFamilyBase* InstallNeoNet()
		{
		return new CNeoFamily;
		}
	}
