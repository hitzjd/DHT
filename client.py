#!/usr/bin/env python
import socket


def client(data):
    addr = ('94.23.183.33', 6969)
    s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
    s.sendto(data,addr)
    s.close()

if __name__ ==  "__main__":
    pass