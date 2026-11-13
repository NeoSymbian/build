// SPDX-License-Identifier: Apache-2.0
// neonet.h -- NEONET.DLL: the C++ client of NeoNet, the phone's IP stack over Wi-Fi (NEONET.EXE, docs wifi.md W5/W7),
// for 2010-style C++ programs and ESOCK's neonet.prt. One RNeoNet session serves any number of sockets; a socket is
// a small id owned by the session (closed with it). Every call maps 1:1 onto a NeoNet op (neolink crates/net
// proto.rs). The waiting ops complete their TRequestStatus with a count, an id or an error; closing a socket
// completes its waiting ops with KErrCancel, closing the session cancels everything.
#ifndef NEONET_H
#define NEONET_H

#include <e32std.h>

// The network's state (RNeoNet::Status): {version 1, state, prefix, 0, ip[4], gateway[4], dns1[4], dns2[4]}.
const TInt KNeoNetStatusSize = 20;
enum TNeoNetState { ENeoNetDown = 0, ENeoNetConfiguring = 1, ENeoNetUp = 2 };
// An IPv4 address and port as NeoNet carries it: {ip[4], port big-endian[2]}.
const TInt KNeoNetEndpointSize = 6;
typedef TBuf8<KNeoNetEndpointSize> TNeoNetEndpoint;
// Bytes one Send/Recv/SendTo/RecvFrom moves at most.
const TInt KNeoNetMaxIo = 8192;

// An IPv4 address as a number (192.168.3.1 = 0xC0A80301) from 4 bytes, and an endpoint's parts.
inline TUint32 NeoNetIp(const TDesC8& aIp4)
	{ return (TUint32)aIp4[0] << 24 | (TUint32)aIp4[1] << 16 | (TUint32)aIp4[2] << 8 | aIp4[3]; }
inline TUint NeoNetPort(const TDesC8& aEndpoint) { return (TUint)aEndpoint[4] << 8 | aEndpoint[5]; }
inline void NeoNetEndpoint(TDes8& aOut, TUint32 aIp, TUint aPort)
	{
	aOut.SetLength(KNeoNetEndpointSize);
	aOut[0] = (TUint8)(aIp >> 24); aOut[1] = (TUint8)(aIp >> 16); aOut[2] = (TUint8)(aIp >> 8); aOut[3] = (TUint8)aIp;
	aOut[4] = (TUint8)(aPort >> 8); aOut[5] = (TUint8)aPort;
	}

class RNeoNet : public RSessionBase
	{
public:
	// KErrNotFound until NEONET.EXE runs (SYSSTART starts it at boot)
	IMPORT_C TInt Connect();
	// the state and DHCP lease into aStatus (>= KNeoNetStatusSize); never waits
	IMPORT_C TInt Status(TDes8& aStatus) const;
	// the IPv4 address of aName (a host name or a dotted address) into aIp (4 bytes), by DNS
	IMPORT_C void Resolve(const TDesC8& aName, TDes8& aIp, TRequestStatus& aStatus) const;
	// a TCP connection to aIp:aPort: completes with its socket id once established (KErrCouldNotConnect, KErrNotReady
	// without an address)
	IMPORT_C void TcpConnect(TUint32 aIp, TUint aPort, TRequestStatus& aStatus) const;
	// listen on aPort: the listening socket's id (KErrInUse)
	IMPORT_C TInt TcpListen(TUint aPort) const;
	// the next connection to listener aId: completes with its socket id, the peer in aPeer (KNeoNetEndpointSize)
	IMPORT_C void Accept(TInt aId, TDes8& aPeer, TRequestStatus& aStatus) const;
	// a UDP socket on aPort (0: any): its id
	IMPORT_C TInt UdpOpen(TUint aPort) const;
	// TCP: queue some of aData (<= KNeoNetMaxIo): completes with the bytes taken, waiting while the buffer is full
	IMPORT_C void Send(TInt aId, const TDesC8& aData, TRequestStatus& aStatus) const;
	// TCP: completes with the bytes read into aData, 0 once the peer closed; waits until something arrives
	IMPORT_C void Recv(TInt aId, TDes8& aData, TRequestStatus& aStatus) const;
	// UDP: one datagram to aTo (an endpoint): completes with its length
	IMPORT_C void SendTo(TInt aId, const TDesC8& aData, const TDesC8& aTo, TRequestStatus& aStatus) const;
	// UDP: the next datagram into aData and its sender into aFrom: completes with its length (KErrOverflow: it didn't
	// fit and is gone)
	IMPORT_C void RecvFrom(TInt aId, TDes8& aData, TDes8& aFrom, TRequestStatus& aStatus) const;
	// close socket aId (TCP: its FIN goes after the queued data)
	IMPORT_C TInt CloseSocket(TInt aId) const;
	};

#endif
