#!/usr/bin/env python
import socket
addr=('222.85.25.9',6060)
s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
while 1:
    data=raw_input()
    if not data:
        break
    s.sendto(data,addr)
s.close()