# vim: set et sts=4 sw=4:
#
# This file is part of python-websocket
# Copyright (C) 2011  Giel van Schijndel
#
# python-websocket is free software: you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public License
# as published by the Free Software Foundation; either version 3 of
# the License, or (at your option) any later version.
#
# python-websocket is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from base64 import b64decode, b64encode
from hashlib import md5, sha1
from httplib import HTTPResponse
from os import urandom
import random
import re
from select import select
import socket
try:
    import socks
except ImportError:
    pass
try:
    import ssl
except ImportError:
    pass
import struct
import sys
import urllib
import urlparse

__all__ = ('WebSocket',)

# Wether to print protocol debugging messages to sys.stderr, default:
_debug = False

class _WebSocket(object):
    _default_ports = {
            'ws':  80,
            'wss': 443,
        }
    socket = None

    def __init__(self, url, version, origin, cookie, proxies):
        self.version = version
        self.origin = origin
        self.cookie = cookie
        self.proxies = proxies
        self._inmsgs = []
        self._indata = ''
        self._outdata = ''
        self._curmsg = ''

        if self.proxies is None:
            self.proxies = urllib.getproxies()

        if url:
            self.connect(url, self.proxies)

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.close()

    def connect(self, url, proxies=None):
        """Performs the necessary work to connect the WebSocket and perform the
        handshake."""
        if proxies is None:
            proxies = self.proxies

        if not 'ws' in urlparse.uses_netloc:
            urlparse.uses_netloc.append('ws')
        if not 'wss' in urlparse.uses_netloc:
            urlparse.uses_netloc.append('wss')
        urlParts = urlparse.urlparse(url)

        self.hostname = self.host = urlParts.hostname
        if urlParts.port is not None \
         and ((urlParts.scheme == 'ws'  and urlParts.port != 80) \
           or (urlParts.scheme == 'wss' and urlParts.port != 443)):
             self.host += ':%d' % (urlParts.port,)

        self.port = urlParts.port
        if self.port is None:
            self.port = self._default_ports[urlParts.scheme]

        self.username, self.password = urlParts.username, urlParts.password
        self.scheme = urlParts.scheme

        # optional proxy usage
        if self.scheme in proxies:
            proxyParts = urlparse.urlparse(proxies[self.scheme])

            if proxyParts.scheme == 'http':
                self.socket = socket.create_connection((proxyParts.hostname, proxyParts.port))
                request = "CONNECT %s:%d HTTP/1.0\r\n" \
                          "Host: %s\r\n" % (self.hostname, self.port, self.host)

                # TODO: Try without credentials first, only authenticate when we
                #       fail with a 407 (additionally allows digest auth)
                # CONNECT websocket.mtgox.com:80 HTTP/1.0
                # Host: websocket.mtgox.com:80
                # Connection: Keep-Alive
                #
                # HTTP/1.1 407 Proxy Authentication Required
                # Date: Wed, 13 Jul 2011 01:23:10 GMT
                # Proxy-Authenticate: Basic realm="Mortikia Proxy"
                # Vary: Accept-Encoding
                # Content-Length: 500
                # Keep-Alive: timeout=15, max=100
                # Connection: Keep-Alive
                # Content-Type: text/html; charset=iso-8859-1
                #
                # <!DOCTYPE HTML PUBLIC "-//IETF//DTD HTML 2.0//EN">
                # <html><head>
                # <title>407 Proxy Authentication Required</title>
                # </head><body>
                # <h1>Proxy Authentication Required</h1>
                # <p>This server could not verify that you
                # are authorized to access the document
                # requested.  Either you supplied the wrong
                # credentials (e.g., bad password), or your
                # browser doesn't understand how to supply
                # the credentials required.</p>
                # <hr>
                # <address>Apache/2.2.16 (Debian) Server at websocket.mtgox.com Port 80</address>
                # </body></html>
                # CONNECT websocket.mtgox.com:80 HTTP/1.0
                # Host: websocket.mtgox.com:80
                # Connection: Keep-Alive
                # Proxy-Authorization: Basic Z2llbDo1UUFXcEgydnBSVEZBdmxH
                #
                # HTTP/1.0 200 Connection Established
                # Proxy-agent: Apache/2.2.16 (Debian)
                #
                # Authenticate if required
                if proxyParts.username is not None:
                    request += "Proxy-Authorization: Basic %s\r\n" \
                            % b64encode('%s:%s' % (proxyParts.username, proxyParts.password or ''))

                # Finish request
                request += "\r\n"
                if _debug:
                    print >> sys.stderr, '\x1B[D\x1B[31m%s\x1B[m' % (request,),
                self.socket.sendall(request)

                # Process HTTP response
                response = HTTPResponse(self.socket)
                response.begin()

                if _debug:
                    print >> sys.stderr, '\x1B[D\x1B[34m%s' % ({9: 'HTTP/0.9', 10: 'HTTP/1.0', 11: 'HTTP/1.1'}[response.version],), response.status, response.reason
                    print >> sys.stderr, '%s\x1B[m' % (response.msg,)

                if response.status != 200:
                    self.socket.close()
                    raise socket.error("Tunnel connection failed: %d %s" % (response.status,
                                                                        response.reason))
            elif proxyParts.scheme == 'socks':
                try:
                    self.socket = socks.socksocket()
                    self.socket.setproxy(socks.PROXY_TYPE_SOCKS4, proxyParts.hostname, proxyParts.port)
                    self.socket.connect((self.hostname, self.port))
                except NameError:
                    raise NotImplementedError, "Using of SOCKS proxy functionality requires the 'socks' module, from /usr/share/pyshared/python_socksipy-1.0.egg-info"
        else:
            self.socket = socket.create_connection((self.hostname, self.port))

        if self.scheme == 'wss':
            try:
                self.socket = ssl.wrap_socket(self.socket)
            except NameError:
                raise NotImplementedError, "Using of wss:// (secure websockets) requires the 'ssl' module"

        self._do_handshake(url=url, version=self.version, origin=self.origin, cookie=self.cookie)

    def _do_handshake(self, url, version, origin, cookie):
        """Needs to be overridden by the subclass implementing the specific protocol version."""
        raise NotImplementedError, "WebSocket protocol version %d not implemented" % (version,)

    def _non_blocking_sendrcv(self):
        """Fills the TCP send buffer completely, but doesn't block to send
        everything in our own send buffer."""
        r, w, x = (self.socket,), (), ()
        if self._outdata:
            w = (self.socket,)
        r, w, x = select(r, w, x, 0)
        if r:
            self._indata += self.socket.recv(2**16-1)
        if w:
            sent = self.socket.send(self._outdata)
            self._outdata = self._outdata[sent:]

    def _do_recv(self):
        raise NotImplementedError

    def recv(self):
        try:
            # Block if there's *no* data whatsoever
            if not self._indata:
                self._indata += self.socket.recv(2**16-1)
            self._non_blocking_sendrcv()
            self._do_recv()
            try:
                msg = self._inmsgs.pop(0)
                if _debug:
                    print >> sys.stderr, '\x1B[34m%s\x1B[m' % (msg,)
                return msg
            except IndexError:
                return None
        finally:
            self._non_blocking_sendrcv()

    def _do_send(self, data):
        raise NotImplementedError

    def send(self, data):
        try:
            if _debug:
                print >> sys.stderr, '\x1B[31m%s\x1B[m' % (data,)
            return self._do_send(data)
        finally:
            self._non_blocking_sendrcv()

    def _ping_msg(self):
        raise NotImplementedError, 'Not all WebSocket versions implement the PING frame'

    def ping(self):
        try:
            return self._ping_msg()
        finally:
            self._non_blocking_sendrcv()

    def _close_msg(self):
        """Method to send the WebSocket CLOSE frame"""
        raise NotImplementedError

    def close(self):
        if self.socket is not None:
            try:
                if self._close_sent:
                    pass
            except AttributeError:
                self._close_msg()
                self._close_sent = True
            self.socket.sendall(self._outdata)
            self._outdata = ''
            self.socket.close()
            self.socket = None

class _WebSocket_0(_WebSocket):

    def _do_handshake(self, url, version=0, origin=None, cookie=None):
        """http://tools.ietf.org/html/draft-ietf-hybi-thewebsocketprotocol-00"""
        fields = [
                "Upgrade: WebSocket",
                "Connection: Upgrade",
                "Host: %s" % (self.host,),
                "Sec-WebSocket-Draft: 2",
            ]

        if origin is None:
            origin = self.host
        fields.append("Origin: %s" % (origin,))

        if cookie is not None:
            fields.append(cookie.output(header="Cookie:"))

        # Authenticate if required
        if self.username is not None:
            fields.append("Authorization: Basic %s"
                    % b64encode('%s:%s' % (self.username, self.password or '')))

        # What idiot invented this algorithm for key construction?
        spaces_1  = random.randint(1, 12)
        spaces_2  = random.randint(1, 12)
        max_1     = min(2**32-1 / spaces_1, 2**32-1)
        max_2     = min(2**32-1 / spaces_2, 2**32-1)
        number_1  = random.randint(0, max_1)
        number_2  = random.randint(0, max_2)
        product_1 = number_1 * spaces_1
        product_2 = number_2 * spaces_2
        key_1     = list(str(product_1))
        key_2     = list(str(product_2))

        ran_range = ''.join(map(chr, range(0x21, 0x30) + range(0x3a, 0x7f)))
        for n in xrange(random.randint(1, 12)):
            key_1.insert(random.randint(0, len(key_1)), random.choice(ran_range))
        for n in xrange(random.randint(1, 12)):
            key_2.insert(random.randint(0, len(key_1)), random.choice(ran_range))

        for n in xrange(spaces_1):
            key_1.insert(random.randint(1, len(key_1) - 1), ' ')
        for n in xrange(spaces_2):
            key_2.insert(random.randint(1, len(key_1) - 1), ' ')

        key_1 = ''.join(key_1)
        key_2 = ''.join(key_2)

        fields += [
                "Sec-WebSocket-Key1: %s" % (key_1,),
                "Sec-WebSocket-Key2: %s" % (key_2,),
            ]

        key_3 = urandom(8)
        fields.append("Content-Length: %d" % (len(key_3),))

        random.shuffle(fields)

        urlParts = urlparse.urlparse(url)

        # Finish request
        request = "GET %s HTTP/1.1\r\n" \
                  "%s\r\n" \
                  "\r\n" \
                  "%s" \
                % (urlParts.path, '\r\n'.join(fields), key_3)
        if _debug:
            print >> sys.stderr, '\x1B[D\x1B[31m%s\x1B[m' % (request,),
        self.socket.sendall(request)

        response = HTTPResponse(self.socket)
        response.begin()

        if _debug:
            print >> sys.stderr, '\x1B[D\x1B[34m%s' % ({9: 'HTTP/0.9', 10: 'HTTP/1.0', 11: 'HTTP/1.1'}[response.version],), response.status, response.reason
            print >> sys.stderr, '%s\x1B[m' % (response.msg,)

        if response.status != 101:
            self.socket.close()
            raise RuntimeError("WebSocket upgrade failed: %d %s" % (response.status, response.reason))

        # Hack to override httplib's setting it to 0 for 101's
        response.length = None

        expected_headers = ('upgrade', 'connection', 'sec-websocket-origin', 'sec-websocket-location')
        for header in expected_headers:
            if header not in response.msg:
                raise RuntimeError, "Expected WebSocket header not present: %s" % (header,)
        if response.msg['upgrade'].lower().strip() != 'websocket':
            raise RuntimeError, "Upgraded to wrong protocol, WebSocket expected: %s" % (response.msg['upgrade'],)
        if response.msg['connection'].lower().strip() != 'upgrade':
            raise RuntimeError, "Bad Connection header: %s" % (response.msg['connection'],)
        if response.msg['sec-websocket-origin'].lower().strip() != origin:
            raise RuntimeError, "Wrong WebSocket origin: %s" % (response.msg['sec-websocket-origin'],)

        if response.msg['sec-websocket-location'].lower().strip() != urlparse.urlunparse((self.scheme, self.host, urlParts.path, urlParts.params, urlParts.query, urlParts.fragment)):
            raise RuntimeError, "Bad WebSocket location: %s" % (response.msg['sec-websocket-location'],)

        assert 0 <= number_1 <= 4294967295
        assert 0 <= number_2 <= 4294967295
        challenge = struct.pack('>LL8s', number_1, number_2, key_3)
        expected = md5(challenge).digest()
        assert len(expected) == 16

        reply = response.read(len(expected))
        #if reply != expected:
        #    raise RuntimeError, "Invalid WebSocket challenge returned: %s %s %s" % (repr(challenge), repr(expected), repr(reply))

    def _do_recv(self):
        while self._indata:
            try:
                msg_end = self._indata.index('\xff')
                self._curmsg += self._indata[:msg_end+1]
                self._indata = self._indata[msg_end+1:]
            except ValueError:
                self._curmsg += self._indata
                self._indata = ''
            try:
                msg_start = self._curmsg.index('\x00')
                # ignore any invalid data preceding the message
                self._curmsg = self._curmsg[msg_start:]
            except ValueError:
                # entire message buffer is invalid, ditch it
                self._curmsg = ''

            # Add received messages to the queue
            if '\xff' in self._curmsg:
                msg_end = self._curmsg.index('\xff')
                msg = self._curmsg[1:msg_end]
                self._curmsg = self._curmsg[msg_end+1:]

                msg = msg.decode('utf-8', 'replace')
                self._inmsgs.append(msg)

    def _do_send(self, data):
        if not isinstance(data, basestring) \
            or re.search(r'[^\x00-\x7f]', data): # Detect non-ASCII, i.e. binary strings
            raise TypeError, "only text accepted (ASCII encoded 'str' or 'unicode')"

        # Encode unicode data as UTF-8
        if   isinstance(data, unicode):
            data = data.encode('utf-8', 'replace')

        self._outdata += '\x00%s\xff' % (data,)

    def _close_msg(self):
        self._outdata += '\xff\x00'

class _WebSocket_6(_WebSocket):
    def __init__(self, url, version, origin, cookie, proxies):
        super(_WebSocket_6, self).__init__(url=url, version=version, origin=origin, cookie=cookie, proxies=proxies)

        self._curop = 0x0

    def _do_handshake(self, url, version=6, origin=None, cookie=None):
        """http://tools.ietf.org/html/draft-ietf-hybi-thewebsocketprotocol-06"""
        urlParts = urlparse.urlparse(url)
        key = b64encode(urandom(16))
        request  = "GET %s HTTP/1.1\r\n" \
                   "Host: %s\r\n" \
                   "Upgrade: WebSocket\r\n" \
                   "Connection: Upgrade\r\n" \
                   "Sec-WebSocket-Key: %s\r\n" \
                   "Sec-WebSocket-Version: %d\r\n" \
                   % (urlParts.path, self.host, key, version)

        if origin is not None:
            request += "Sec-WebSocket-Origin: %s\r\n" % (origin,)

        if cookie is not None:
            request += cookie.output(header="Cookie:") + "\r\n"

        # Authenticate if required
        if self.username is not None:
            request += "Authorization: Basic %s\r\n" \
                    % b64encode('%s:%s' % (self.username, self.password or ''))

        # Finish request
        request += "\r\n"
        if _debug:
            print >> sys.stderr, '\x1B[D\x1B[31m%s\x1B[m' % (request,),
        self.socket.sendall(request)

        response = HTTPResponse(self.socket)
        response.begin()

        if _debug:
            print >> sys.stderr, '\x1B[D\x1B[34m%s' % ({9: 'HTTP/0.9', 10: 'HTTP/1.0', 11: 'HTTP/1.1'}[response.version],), response.status, response.reason
            print >> sys.stderr, '%s\x1B[m' % (response.msg,)

        if response.status != 101:
            self.socket.close()
            raise RuntimeError("WebSocket upgrade failed: %d %s" % (response.status, response.reason))

        expected = sha1(key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").digest()
        assert len(expected) == 20
        expected = b64encode(expected)

        if 'Sec-WebSocket-Accept' not in response.msg:
            raise RuntimeError, "Expected WebSocket header not present: Sec-WebSocket-Accept"

        if response.msg['Sec-WebSocket-Accept'].strip() != expected:
            raise RuntimeError, "Invalid WebSocket accept returned: %s %s %s" % (key, expected, response.msg['Sec-WebSocket-Accept'])

    def _do_recv(self):
        while self._indata:
            if len(self._indata) < 2:
                return
            header_flags = struct.unpack(r'!BB', self._indata[:2])
            pstart = 2
            fin  = bool(header_flags[0] & 0x80)
            rsv1 = bool(header_flags[0] & 0x40)
            rsv2 = bool(header_flags[0] & 0x20)
            rsv3 = bool(header_flags[0] & 0x10)
            opcode = header_flags[0] & 0x0f
            rsv4 = bool(header_flags[1] & 0x80)
            plen = header_flags[1] & 0x7f
            if   plen == 126:
                if len(self._indata) < 4:
                    return
                # '!' (network-byte order, aka big endian) should be
                # used, unfortunately MtGox wrongly sends the length
                # bytes as little-endian, hence the '<'
                #plen, = struct.unpack(r'!H', self._indata[pstart:pstart+2])
                plen, = struct.unpack(r'<H', self._indata[pstart:pstart+2])
                pstart += 2
            elif plen == 127:
                if len(self._indata) < 10:
                    return
                # '!' (network-byte order, aka big endian) should be
                # used, unfortunately MtGox wrongly sends the length
                # bytes as little-endian, hence the '<'
                #plen, = struct.unpack(r'!Q', self._indata[pstart:pstart+8])
                plen, = struct.unpack(r'<Q', self._indata[pstart:pstart+8])
                pstart += 8
            if len(self._indata) < pstart + plen:
                return

            data = self._indata[pstart:pstart+plen]
            self._indata = self._indata[pstart+plen:]
            if   opcode in (0x0, 0x4, 0x5): # continuation, text, binary
                if opcode != 0x0:
                    self._curop = opcode
                self._curmsg += data
                if fin:
                    if self._curop in (0x0, 0x4):
                        self._inmsgs.append(self._curmsg.decode('utf-8', 'replace'))
                    else:
                        self._inmsgs.append(self._curmsg)
                    self._curmsg = ''
            elif opcode == 0x1: # close
                header_flags = (0x80 | opcode, 0)
                self._outdata += struct.pack(r'!BB', *header_flags)
                self.close()
                self.socket.close()
            elif opcode == 0x2: # ping
                self._outdata += struct.pack(r'!B', 0x80 | opcode)
                if   len(data) < 126:
                    self._outdata += struct.pack(r'!B', len(data))
                elif len(data) < 2**16-1:
                    self._outdata += struct.pack(r'!BH', 126, len(data))
                elif len(data) < 2**64-1:
                    self._outdata += struct.pack(r'!BQ', 127, len(data))
                self._outdata += data
            elif opcode == 0x3: # pong
                if _debug:
                    print >> sys.stderr, "pong!"

    def _do_send(self, data):
        if not isinstance(data, basestring):
            raise TypeError, "only text or binary data accepted (basestring)"

        if   isinstance(data, unicode):
            data = data.encode('utf-8', 'replace')
            opcode = 0x04
        elif isinstance(data, str):
            opcode = 0x04
            # Consider data with non-printable characters to be binary
            if re.search(r'[^\x20-\x7e]', data):
                opcode = 0x05
        opcode = 0x0

        self._outdata += struct.pack(r'!B', 0x80 | opcode)
        if   len(data) < 126:
            self._outdata += struct.pack(r'!B', len(data))
        elif len(data) < 2**16-1:
            self._outdata += struct.pack(r'!BH', 126, len(data))
        elif len(data) < 2**64-1:
            self._outdata += struct.pack(r'!BQ', 127, len(data))
        self._outdata += data

    def _ping_msg(self):
        self._outdata += struct.pack(r'!BB', 0x80 | 0x02, 0)

    def _close_msg(self):
        self._outdata += struct.pack(r'!BB', 0x80 | 0x01, 0)

_WebSocket_versions = {
        0: _WebSocket_0,
        6: _WebSocket_6,
    }

def WebSocket(url=None, version=0, origin=None, cookie=None, proxies=None):
    """
    :type url:     str
    :type version: int
    :type origin:  str
    :type cookie:  Cookie.BaseCookie
    :type proxies: dict
    """
    try:
        WebSocket = _WebSocket_versions[version]
    except KeyError:
        raise NotImplementedError, "WebSocket protocol version %d not implemented" % (self.version,)
    return WebSocket(url=url, version=version, origin=origin, cookie=cookie, proxies=proxies)
