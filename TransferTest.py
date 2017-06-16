# *-* coding : utf-8 *-*

import os
import threading
import logging
from BitTorrent.MultiDownload import MultiDownload
import BitTorrent.Download
from BitTorrent.Upload import Upload
from BitTorrent.ConnectionManager import ConnectionManager
import BitTorrent.Connector
import BitTorrent.PiecePicker
import BitTorrent.bitfield
from BitTorrent import configfile
from BitTorrent.defaultargs import get_defaults
from BTL.platform import decode_from_filesystem, encode_for_filesystem
from BitTorrent.platform import get_dot_dir
import BitTorrent.Rerequester
from BitTorrent.RequestManager import RequestManager
from BitTorrent.Storage import Storage,FilePool
from BitTorrent.StorageWrapper import StorageWrapper
from BTL.defer import DeferredEvent
from BitTorrent.RawServer_twisted import RawServer
from twisted.internet import reactor
from BitTorrent import PeerID
from BTL.exceptions import str_exc

class TransferTest:
    def __init__(self,config):
        self.config = config
        self.rawserver = RawServer(self.config)
        self.working_path = self.config['save_incomplete_in']
        self.destination_path = 'C:\\Users\\Administrator\\Desktop\\DHT\\data\\files\\dataFile.txt'
        self.data_dir = self.config['data_dir']
        self.myid = self._make_id()

        self.log_root = 'TrabsferTest'
        self.logger = logging.getLogger(self.log_root + '.' + repr(self.infohash))
        self.logger.setLevel(logging.DEBUG)

    def _init_storage(self):
        self.filepool_doneflag = DeferredEvent()
        self.doneflag = threading.Event()
        self.filepool = FilePool(self.filepool_doneflag,
                                 self.rawserver.add_task,
                                 self.rawserver.external_add_task,
                                 config['max_files_open'],
                                 config['num_disk_threads'])
        self.storage = Storage(self.config, self.filepool, self.working_path ,
                              [self.destination_path, 1], self.rawserver.add_task,
                               self.rawserver.external_add_task, self.doneflag)
        df = self.storage.startup_df

        piece_length = 1000
        is_batch = False

        resumefile = None
        if self.data_dir:
            filename = os.path.join(self.data_dir, 'resume',
                                    self.infohash.encode('hex'))
            if os.path.exists(filename):
                try:
                    resumefile = file(filename, 'rb')
                except Exception, e:
                    self._error(logging.WARNING,
                        _("Could not load fastresume data: %s") % str_exc(e)
                        + ' ' + _("Will perform full hash check."))
                    if resumefile is not None:
                        resumefile.close()
                    resumefile = None

        self.storagewrapper = StorageWrapper(self.storage, self.config, piece_length,self.doneflag,is_batch,
                                              self.working_path, self.destination_path, resumefile,
                                              self.rawserver.add_task, self.rawserver.external_add_task)

    def _init_connection_manager(self):
        md = MultiDownload(self.config, self._storagewrapper, self._rm,
                           self._urlage, self._picker, numpieces,
                           self.finished, self.got_exception, kickpeer, banpeer,
                           self._downmeasure.get_rate)

        def make_upload(connector):
            up = Upload(md, connector, self._storagewrapper, self.config['max_chunk_length'],
                        self.config['max_rate_period'],self.config['num_fast'])
            connector.add_sent_listener(self._upmeasure.update_rate)
            return up

        self.connection_manager = \
            ConnectionManager(make_upload, md, numpieces,
                              self.rawserver, self.config,self.myid, self.rawserver.add_task)



    def connect(self):
        addr1 = ('localhost', 8000)
        addr2 = ('localhost', 8001)

    def _make_id(self):
        return PeerID.make_id()

    def _error(self, level, text, exception=False, exc_info=None):
        if level > logging.WARNING:
            self.logger.log(level,
                            _('Error regarding "%s":\n') % self.metainfo.name + text,
                            exc_info=exc_info)



if __name__ == '__main__':
    uiname = 'bittorrent-console'
    defaults = get_defaults(uiname)
    # print defaults
    data_dir = [[name, value, doc] for (name, value, doc) in defaults
                if name == "data_dir"][0]
    defaults = [(name, value, doc) for (name, value, doc) in defaults
                if not name == "data_dir"]
    ddir = os.path.join(get_dot_dir(), "console")
    data_dir[1] = decode_from_filesystem(ddir)
    # print data_dir
    defaults.append(tuple(data_dir))
    config, args = configfile.parse_configuration_and_args(defaults,uiname)
    # print config
    test = TransferTest(config)
    reactor.run()

