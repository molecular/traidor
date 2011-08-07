#!/usr/bin/env python
# vim: set et sts=4 sw=4 fileencoding=utf-8:

# Only required for Python <= 2.5, but won't harm in newer versions
from __future__ import with_statement

from contextlib import closing
import json
import sys
from websocket import WebSocket

# Enable websocket protocol debugging
import websocket
websocket._debug = True

with closing(WebSocket('ws://websocket.mtgox.com/mtgox', version=6)) as s:
    msg = s.recv(2**16-1)
    while msg is not None:
        print >> sys.stderr, msg
        msg = s.recv(2**16-1)
