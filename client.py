#!/usr/bin/env python
import socket


def client(data):
    addr = ('94.23.183.33', 6969)
    s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
    s.sendto(data,addr)
    s.close()

def server():
    addr = ('172.17.169.47', 31111)
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(addr)
    while True:
        data,address = s.recvfrom(1024)
        print data

if __name__ ==  "__main__":
    server()
    pass