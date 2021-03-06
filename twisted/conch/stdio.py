# -*- test-case-name: twisted.conch.test.test_manhole -*-
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

"""Asynchronous local terminal input handling

API Stability: Unstable

@author: U{Jp Calderone<mailto:exarkun@twistedmatrix.com>}
"""

import os, tty, sys, termios

from twisted.internet import reactor, stdio, protocol, defer
from twisted.python import failure, reflect, log

from twisted.conch.insults.insults import ServerProtocol
from twisted.conch.manhole import ColoredManhole

class UnexpectedOutputError(Exception):
    pass

class TerminalProcessProtocol(protocol.ProcessProtocol):
    def __init__(self, proto):
        self.proto = proto
        self.onConnection = defer.Deferred()

    def connectionMade(self):
        self.proto.makeConnection(self)
        self.onConnection.callback(None)
        self.onConnection = None

    def write(self, bytes):
        self.transport.write(bytes)

    def outReceived(self, bytes):
        self.proto.dataReceived(bytes)

    def errReceived(self, bytes):
        self.transport.loseConnection()
        if self.proto is not None:
            self.proto.connectionLost(failure.Failure(UnexpectedOutputError(bytes)))
            self.proto = None

    def childConnectionLost(self, childFD):
        if self.proto is not None:
            self.proto.childConnectionLost(childFD)

    def processEnded(self, reason):
        if self.proto is not None:
            self.proto.connectionLost(reason)
            self.proto = None

class ConsoleManhole(ColoredManhole):
    def handle_QUIT(self):
        ColoredManhole.handle_QUIT(self)
        reactor.stop()

def runWithProtocol(klass):
    fd = sys.__stdin__.fileno()
    oldSettings = termios.tcgetattr(fd)
    tty.setraw(fd)
    try:
        p = ServerProtocol(klass)
        stdio.StandardIO(p)
        reactor.run()
    finally:
        termios.tcsetattr(fd, termios.TCSANOW, oldSettings)
        os.write(0, "\r\x1bc\r")

def main(argv=None):
    log.startLogging(file('child.log', 'w'))

    if argv is None:
        argv = sys.argv[1:]
    if argv:
        klass = reflect.namedClass(argv[0])
    else:
        klass = ConsoleManhole
    runWithProtocol(klass)

if __name__ == '__main__':
    main()
