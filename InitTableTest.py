# *-* coding : utf-8 *-*

import os
import sys
import json
from khashmir.utkhashmir import UTKhashmir
from khashmir import const
from BitTorrent.RawServer_twisted import RawServer
from BTL import BTFailure, InfoHashType
from BTL.bencode import bencode
from BTL.hash import sha
from twisted.internet import reactor


class InitTableTest:
	def __init__(self):
		self.config,self.metainfo = self._load_settings()
		self.rawserver = RawServer(self.config)
		self.dht = UTKhashmir(self.config['bind'],self.config['port'],self.config['dumpDir'],self.rawserver)


	def _load_settings(self):
		f = open('config/MyNodes.json')
		settings = json.load(f)
		return settings["config"],settings["metainfo"]
		

	def start_init(self):
		if self.dht:
			infohash = InfoHashType(sha(bencode(self.metainfo['value'].encode('ascii'))).digest())
			nodes = self.dht.table.findNodes(infohash,invalid=False)
			
			if len(nodes) < const.K:
				for node in self.metainfo['nodes']:
					host = node['host']
					port = node['port']
					self.dht.addContact(host,port)
					# df = self.rawserver.gethostbyname(host)
					# print type(df)
					# df.addCallback(self.dht.addContact,port)
                # self.rawserver.listen_forever()
				self.rawserver.add_task(30,self.show_table)

			self.dht.announcePeer(infohash,self.metainfo['value'].encode('ascii'))
			ret = self.dht.getPeers(infohash,self.show_value)
			print ret

	def show_value(self,*arg):
		print arg[0]

	def show_table(self):
		for bucket in self.dht.table.buckets:
			for node in bucket.l:
				print node.host,node.port,node.num



if __name__ == '__main__':
	itt = InitTableTest()
	itt.start_init()
	itt.show_table()
	reactor.run()



