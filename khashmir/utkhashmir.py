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

import khashmir, knode
from actions import *
from khash import newID
from krpc import KRPCProtocolError, KRPCFailSilently
from BTL.cache import Cache
from sha import sha
from util import *
from BTL.stackthreading import Thread
from socket import gethostbyname
from const import *
from kstore import sample

TOKEN_UPDATE_INTERVAL = 5 * 60 # five minutes
NUM_PEERS = 50 # number of peers to return

class UTNode(knode.KNodeBase):
    def announcePeer(self, info_hash, port, khashmir_id):
        assert type(port) == type(1)
        assert type(info_hash) == type('')
        assert type(khashmir_id) == type('')
        assert len(info_hash) == 20
        assert len(khashmir_id) == 20

        try:
            token = self.table.tcache[self.id]
        except:
            token = None
        if token:
            assert type(token) == type(""), repr(token)
            # not true
            #assert len(token) == 20, repr(token)
            df = self.conn().sendRequest('announce_peer', {'info_hash':info_hash,
                                                         'port':port,
                                                         'id':khashmir_id,
                                                         'token':token})
        else:
            raise KRPCProtocolError("no write token for node")
        df.addErrback(self.errBack)
        df.addCallback(self.checkSender)
        return df



    def getPeers(self, info_hash, khashmir_id):
        df = self.conn().sendRequest('get_peers', {'info_hash':info_hash, 'id':khashmir_id})
        df.addErrback(self.errBack)
        df.addCallback(self.checkSender)
        return df

    def checkSender(self, dict):
        d = knode.KNodeBase.checkSender(self, dict)
        try:
            '''get_peer respond has token'''
            token = d['rsp']['token']
            assert type(token) == type(""), repr(token)
            # not true
            #assert len(token) == 20, repr(token)
            '''tcache:{queried_id : queried_return_token}'''
            self.table.tcache[d['rsp']['id']] = token
        except KeyError:
            pass
        return d
    
class UTStoreValue(StoreValue):
    def callNode(self, node, f):
        return f(self.target, self.value, node.token, self.table.node.id)
    
class UTKhashmir(khashmir.KhashmirBase):
    _Node = UTNode

    '''Just  a  Test'''
    def getPeerQuery(self,info_hash,host,port):
        n = self._Node(self.udp.connectionForAddr)
        n.table = self
        n = n.init(const.NULL_ID, host, port)
        df = n.conn().sendRequest('get_peers', {'info_hash':info_hash, 'id':self.table.node.id})
        def myErrorBack(*arg):
            print "error"
        def mySuccessBack(*arg):
            print "getPeer"
        df.addErrback(myErrorBack)
        df.addCallback(mySuccessBack)

    def pingQuery(self,host,port):
        n = self.Node().init(const.NULL_ID, host, port)
        self.sendPing(n)


    def setup(self, host, port, data_dir, rlcount, checkpoint=True):
        khashmir.KhashmirBase.setup(self, host, port,data_dir, rlcount, checkpoint)
        self.cur_token = self.last_token = sha('')
        self.tcache = Cache()
        self.gen_token(loop=True)
        self.expire_cached_tokens(loop=True)

    '''expire tokens in tcache'''
    def expire_cached_tokens(self, loop=False):
        self.tcache.expire(time() - TOKEN_UPDATE_INTERVAL)
        if loop:
            self.rawserver.external_add_task(TOKEN_UPDATE_INTERVAL,
                                             self.expire_cached_tokens, True)
                                
    def gen_token(self, loop=False):
        self.last_token = self.cur_token
        self.cur_token = sha(newID())
        if loop:
            self.rawserver.external_add_task(TOKEN_UPDATE_INTERVAL,
                                             self.gen_token, True)

    '''create token called by queried nodes'''
    def get_token(self, host, port):
        x = self.cur_token.copy()
        x.update("%s%s" % (host, port))
        h = x.digest()
        return h

    '''check token is valid or not'''
    def val_token(self, token, host, port):
        x = self.cur_token.copy()
        x.update("%s%s" % (host, port))
        a = x.digest()
        if token == a:
            return True

        x = self.last_token.copy()
        x.update("%s%s" % (host, port))
        b = x.digest()
        if token == b:
            return True

        return False

    def addContact(self, host, port, callback=None):
        # use dns on host, then call khashmir.addContact
        Thread(target=self._get_host, args=[host, port, callback]).start()
        # t = Thread(target=self._get_host, args=[host, port, callback])
        # t.start()

    def _get_host(self, host, port, callback):

        # this exception catch can go away once we actually fix the bug
        try:
            ip = gethostbyname(host)
        except TypeError, e:
            raise TypeError(str(e) + (": host(%s) port(%s)" % (repr(host), repr(port))))
        
        self.rawserver.external_add_task(0, self._got_host, ip, port, callback)
        # self._got_host(ip,port,callback)

    def _got_host(self, host, port, callback):
        khashmir.KhashmirBase.addContact(self, host, port, callback)

    '''send krpc::find_node first  return nodes closest to infohash'''
    '''then send krpc::announce_peer'''
    def announcePeer(self, info_hash, port, callback=None):
        """ stores the value for key in the global table, returns immediately, no status 
            in this implementation, peers respond but don't indicate status to storing values
            a key can have many values
        """
        def _storeValueForKey(nodes, key=info_hash, value=port, response=callback , table=self.table):
            if not response:
                # default callback
                def _storedValueHandler(sender):
                    pass
                response=_storedValueHandler
            action = UTStoreValue(self, key, value, response, self.rawserver.add_task, "announcePeer")
            '''nodes is a list of NodeWraps'''
            nodes = [node.node for node in nodes]
            '''now nodes is a list of UTNode'''
            self.rawserver.external_add_task(0, action.goWithNodes, nodes)
            
        # this call is asynch
        print "announcePeer"
        self.findNode(info_hash, _storeValueForKey)

    '''call when receive announce_peer krpc request'''
    def krpc_announce_peer(self, info_hash, port, id, token, _krpc_sender):
        sender = {'id' : id}
        sender['host'] = _krpc_sender[0]
        sender['port'] = _krpc_sender[1]
        if not self.val_token(token, sender['host'], sender['port']):
            raise KRPCProtocolError("Invalid Write Token")
        value = compact_peer_info(_krpc_sender[0], port)
        self.store[info_hash] = value
        n = self.Node().initWithDict(sender)
        self.insertNode(n, contacted=0)
        return {"id" : self.node.id}

    '''find infohash in self.store(KStore)'''
    """if find return store[infohash]"""
    """if not find return []"""
    def retrieveValues(self, key):
        try:
            l = self.store.sample(key, NUM_PEERS)
        except KeyError:
            l = []
        return l

    def getPeers(self, info_hash, callback, searchlocal = 1):
        """ returns the values found for key in global table
            callback will be called with a list of values for each peer that returns unique values
            final callback will be an empty list - probably should change to 'more coming' arg
        """
        print "getPeers"
        nodes = self.table.findNodes(info_hash, invalid=True)
        l = [x for x in nodes if x.invalid]
        if len(l) > 4:
            nodes = sample(l , 4) + self.table.findNodes(info_hash, invalid=False)[:4]
        
        # get locals
        if searchlocal:
            l = self.retrieveValues(info_hash)
            if len(l) > 0:
                self.rawserver.external_add_task(0, callback, [reducePeers(l)])
        else:
            l = []
        # create our search state
        state = GetValue(self, info_hash, callback, self.rawserver.add_task, 'getPeers')
        self.rawserver.external_add_task(0, state.goWithNodes, nodes, l)

    def getPeersAndAnnounce(self, info_hash, port, callback, searchlocal = 1):
        """ returns the values found for key in global table
            callback will be called with a list of values for each peer that returns unique values
            final callback will be an empty list - probably should change to 'more coming' arg
        """
        nodes = self.table.findNodes(info_hash, invalid=False)
        nodes += self.table.findNodes(info_hash, invalid=True)
        
        # get locals
        if searchlocal:
            l = self.retrieveValues(info_hash)
            if len(l) > 0:
                self.rawserver.external_add_task(0, callback, [reducePeers(l)])
        else:
            l = []
        # create our search state
        x = lambda a: a
        state = GetAndStore(self, info_hash, port, callback, x, self.rawserver.add_task, 'getPeers', "announcePeer")
        self.rawserver.external_add_task(0, state.goWithNodes, nodes, l)

    '''call when receive get_peer krpc request'''
    def krpc_get_peers(self, info_hash, id, _krpc_sender):
        sender = {'id' : id}
        sender['host'] = _krpc_sender[0]
        sender['port'] = _krpc_sender[1]        
        n = self.Node().initWithDict(sender)
        self.insertNode(n, contacted=0)
    
        l = self.retrieveValues(info_hash)
        if len(l) > 0:
            return {'values' : [reducePeers(l)],
                    "id": self.node.id,
                    "token" : self.get_token(sender['host'], sender['port'])}
        else:
            nodes = self.table.findNodes(info_hash, invalid=False)
            nodes = [node.senderDict() for node in nodes]
            return {'nodes' : packNodes(nodes),
                    "id": self.node.id,
                    "token" : self.get_token(sender['host'], sender['port'])}

