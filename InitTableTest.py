# *-* coding : utf-8 *-*

import os
import sys
import json
from khashmir.utkhashmir import UTKhashmir
from khashmir import const
from BitTorrent.RawServer_twisted import RawServer
from twisted.internet import reactor
from khashmir import khash


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
			# infohash = sha(bencode(self.metainfo['value'])).digest()
			infohash = 0x0d0d7a9ef71434d31b893cec305264579b7cf262
			nodes = self.dht.table.findNodes(infohash)

			if len(nodes) < const.K:
				for node in self.metainfo['nodes']:
					host = node['host']
					port = node['port']
					self.dht.addContact(host,port)


			# self.rawserver.add_task(30,self.show_table)
			# self.rawserver.add_task(20, self.dht.getPeersAndAnnounce, infohash, self.metainfo['value'], self.show_value)
			# self.rawserver.add_task(10, self.dht.getPeerQuery,infohash,'176.31.225.184',8999)

			# self.rawserver.add_task(20,self.dht.announcePeer,infohash,self.metainfo['value'])

			self.rawserver.add_task(10,self.dht.getPeers,khash.stringify(infohash),self.show_value)


	def show_value(self,*arg):
		print "here!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
		print arg[0]

	def show_table(self):
		for bucket in self.dht.table.buckets:
			for node in bucket.l:
				print node.host,node.port,node.num



if __name__ == '__main__':
	itt = InitTableTest()
	itt.start_init()
	reactor.run()



