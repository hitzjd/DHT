# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from defer import Deferred
from BTL.bencode import bencode, bdecode
import socket
from BitTorrent.RawServer_twisted import Handler
from BTL.platform import bttime
from BTL.translation import _
import time
from math import log10
from client import client

import sys
from traceback import print_exc

from khash import distance
from BTL.cache import Cache
from KRateLimiter import KRateLimiter
from hammerlock import Hammerlock


from const import *

# commands
TID = 't'
REQ = 'q'
RSP = 'r'
TYP = 'y'
ARG = 'a'
ERR = 'e'

class KRPCFailSilently(Exception):
    pass

class KRPCProtocolError(Exception):
    pass

class KRPCServerError(Exception):
    pass

class KRPCSelfNodeError(Exception):
    pass

class hostbroker(Handler):       
    def __init__(self, server, addr, transport, call_later, max_ul_rate, config, rlcount):
        self.server = server         #khashmirbase
        self.addr = addr             #local address
        self.transport = transport   #listening udp socket(addr)
        self.rltransport = KRateLimiter(transport, max_ul_rate, call_later, rlcount, config['max_rate_period'])
        self.call_later = call_later  #rawserver.add_task
        self.connections = Cache(touch_on_access=True)
        self.hammerlock = Hammerlock(100, call_later)
        self.expire_connections(loop=True)
        self.config = config
        if not self.config.has_key('pause'):
            self.config['pause'] = False
        
    def expire_connections(self, loop=False):
        self.connections.expire(bttime() - KRPC_CONNECTION_CACHE_TIME)
        if loop:
            self.call_later(KRPC_CONNECTION_CACHE_TIME, self.expire_connections, True)

    '''receive data'''
    def data_came_in(self, addr, datagram):
        #if addr != self.addr:
        # print "recvfrom ",addr
        if not self.config['pause'] and self.hammerlock.check(addr):
            '''c == RRPC instance'''
            c = self.connectionForAddr(addr)
            c.datagramReceived(datagram, addr)

    def connection_lost(self, socket):
        ## this is like, bad
        print ">>> connection lost!", socket

    def connectionForAddr(self, addr):
        if addr == self.addr:
            raise KRPCSelfNodeError()
        if not self.connections.has_key(addr):
            conn = KRPC(addr, self.server, self.transport, self.rltransport, self.call_later)
            self.connections[addr] = conn
        else:
            conn = self.connections[addr]
        return conn


## connection
class KRPC(object):
    __slots__ = ('noisy','call_later','transport','rltransport','factory','addr','tids','mtid','pinging')
    noisy = 0
    def __init__(self, addr, server, transport, rltransport, call_later):
        self.call_later = call_later      #rawserver.add_task
        self.transport = transport        #udp socket
        self.rltransport = rltransport        
        self.factory = server             #UTKhashmirbase
        self.addr = addr                  #dst addr(ip,port)
        self.tids = {}
        self.mtid = 0
        self.pinging = False
        
    def sendErr(self, addr, tid, code, msg):
        ## send error
        out = bencode({TID:tid, TYP:ERR, ERR :(code, msg)})
        olen = len(out)
        self.rltransport.sendto(out, 0, addr)
        return olen                 

    ''' analyse krpc packet '''
    def datagramReceived(self, str, addr):
        # bdecode
        try:
            msg = bdecode(str)
        except Exception, e:
            if self.noisy:
                print "response decode error: " + `e`, `str`
        else:
            #if self.noisy:
            #    print msg
            # look at msg type
            if msg[TYP]  == REQ:
                ilen = len(str)
                # if request
                #	tell factory to handle
                '''here to call krpc_xxx in UTkhashmirBase'''
                f = getattr(self.factory ,"krpc_" + msg[REQ], None)
                msg[ARG]['_krpc_sender'] =  self.addr
                if f and callable(f):
                    try:
                        ret = apply(f, (), msg[ARG])
                    except KRPCFailSilently:
                        pass
                    except KRPCServerError, e:
                        olen = self.sendErr(addr, msg[TID], 202, "Server Error: %s" % e.args[0])
                    except KRPCProtocolError, e:
                        olen = self.sendErr(addr, msg[TID], 204, "Protocol Error: %s" % e.args[0])                        
                    except Exception, e:
                        print_exc(20)
                        olen = self.sendErr(addr, msg[TID], 202, "Server Error")
                    else:
                        if ret:
                            #	make response
                            out = bencode({TID : msg[TID], TYP : RSP, RSP : ret})
                        else:
                            out = bencode({TID : msg[TID], TYP : RSP, RSP : {}})
                        #	send response
                        olen = len(out)
                        self.rltransport.sendto(out, 0, addr)

                else:
                    if self.noisy:
                        #print "don't know about method %s" % msg[REQ]
                        pass
                    # unknown method
                    olen = self.sendErr(addr, msg[TID], *KERR_METHOD_UNKNOWN)
                if self.noisy:
                    try:
                        ndist = 10 * log10(2**160 * 1.0 / distance(self.factory.node.id, msg[ARG]['id']))
                        ndist = int(ndist)
                    except OverflowError:
                        ndist = 999

                    h = None
                    if msg[ARG].has_key('target'):
                        h = msg[ARG]['target']
                    elif msg[ARG].has_key('info_hash'):
                        h = msg[ARG]['info_hash']
                    else:
                        tdist = '-'

                    if h != None:
                        try:
                            tdist = 10 * log10(2**160 * 1.0 / distance(self.factory.node.id, h))
                            tdist = int(tdist)
                        except OverflowError:
                            tdist = 999

                    t = time.localtime()
                    t = "%2d-%2d-%2d %2d:%2d:%2d" % (t[0], t[1], t[2], t[3], t[4], t[5])
                    print "%s %s %s >>> %s - %s %s %s - %s %s" % (t,
                                                                  msg[ARG]['id'].encode('base64')[:4],
                                                                  addr,
                                                                  self.factory.node.port, 
                                                                  ilen,
                                                                  msg[REQ],
                                                                  olen,
                                                                  ndist,
                                                                  tdist)
            elif msg[TYP] == RSP:
                # if response
                # 	lookup tid
                ''' use TID to get request'''
                if self.tids.has_key(msg[TID]):
                    df = self.tids[msg[TID]]
                    # 	callback
                    del(self.tids[msg[TID]])
                    df.callback({'rsp' : msg[RSP], '_krpc_sender': addr})
                else:
                    # no tid, this transaction timed out already...
                    pass
                
            elif msg[TYP] == ERR:
                # if error
                # 	lookup tid
                if self.tids.has_key(msg[TID]):
                    df = self.tids[msg[TID]]
                    # 	callback
                    df.errback(msg[ERR])
                    del(self.tids[msg[TID]])
                else:
                    # day late and dollar short
                    pass
            else:
                # unknown message type
                df = self.tids[msg[TID]]
                # 	callback
                df.errback((KRPC_ERROR_RECEIVED_UNKNOWN, _("received unknown message type")))
                del(self.tids[msg[TID]])
                
    def sendRequest(self, method, args):
        # make message
        # send it
        msg = {TID : chr(self.mtid), TYP : REQ,  REQ : method, ARG : args}
        self.mtid = (self.mtid + 1) % 256
        s = bencode(msg)
        d = Deferred()
        self.tids[msg[TID]] = d
        self.call_later(KRPC_TIMEOUT, self.timeOut, msg[TID])
        self.call_later(0, self._send, s, d)
        return d
    #
    def timeOut(self, id):
        if self.tids.has_key(id):
            df = self.tids[id]
            del(self.tids[id])
            df.errback((KRPC_ERROR_TIMEOUT, _("timeout")))

    def _send(self, s, d):
        try:
            self.transport.sendto(s, 0, self.addr)
        except socket.error:
            d.errback((KRPC_SOCKET_ERROR, _("socket error")))
            
