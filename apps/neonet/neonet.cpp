// SPDX-License-Identifier: Apache-2.0
// neonet.cpp -- NEONET.DLL, see neonet.h. The function numbers and arguments are NeoNet's (neolink crates/net
// proto.rs, API 1.1).
#include "neonet.h"

_LIT(KNeoNetServer, "NeoNet");
enum { EStatus = 1, EResolve, EConnect, ESend, ERecv, EClose, EUdpOpen, ESendTo, ERecvFrom, EListen, EAccept };

EXPORT_C TInt RNeoNet::Connect()
	{
	return CreateSession(KNeoNetServer, TVersion(1, 0, 0), -1);	// -1: the kernel's message pool (many waits at once)
	}

EXPORT_C TInt RNeoNet::Status(TDes8& aStatus) const
	{
	return SendReceive(EStatus, TIpcArgs(&aStatus));
	}

EXPORT_C void RNeoNet::Resolve(const TDesC8& aName, TDes8& aIp, TRequestStatus& aStatus) const
	{
	SendReceive(EResolve, TIpcArgs(&aName, &aIp), aStatus);
	}

EXPORT_C void RNeoNet::TcpConnect(TUint32 aIp, TUint aPort, TRequestStatus& aStatus) const
	{
	SendReceive(EConnect, TIpcArgs((TInt)aIp, (TInt)aPort), aStatus);
	}

EXPORT_C TInt RNeoNet::TcpListen(TUint aPort) const
	{
	return SendReceive(EListen, TIpcArgs((TInt)aPort));
	}

EXPORT_C void RNeoNet::Accept(TInt aId, TDes8& aPeer, TRequestStatus& aStatus) const
	{
	SendReceive(EAccept, TIpcArgs(aId, &aPeer), aStatus);
	}

EXPORT_C TInt RNeoNet::UdpOpen(TUint aPort) const
	{
	return SendReceive(EUdpOpen, TIpcArgs((TInt)aPort));
	}

EXPORT_C void RNeoNet::Send(TInt aId, const TDesC8& aData, TRequestStatus& aStatus) const
	{
	SendReceive(ESend, TIpcArgs(aId, &aData), aStatus);
	}

EXPORT_C void RNeoNet::Recv(TInt aId, TDes8& aData, TRequestStatus& aStatus) const
	{
	SendReceive(ERecv, TIpcArgs(aId, &aData), aStatus);
	}

EXPORT_C void RNeoNet::SendTo(TInt aId, const TDesC8& aData, const TDesC8& aTo, TRequestStatus& aStatus) const
	{
	SendReceive(ESendTo, TIpcArgs(aId, &aData, &aTo), aStatus);
	}

EXPORT_C void RNeoNet::RecvFrom(TInt aId, TDes8& aData, TDes8& aFrom, TRequestStatus& aStatus) const
	{
	SendReceive(ERecvFrom, TIpcArgs(aId, &aData, &aFrom), aStatus);
	}

EXPORT_C TInt RNeoNet::CloseSocket(TInt aId) const
	{
	return SendReceive(EClose, TIpcArgs(aId));
	}
