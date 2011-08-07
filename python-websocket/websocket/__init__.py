# vim: set et sts=4 sw=4:

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
import struct
import sys
import urllib
import urlparse

__all__ = ('WebSocket',)

# Wether to print protocol debugging messages to sys.stderr, default:
_debug = False

class WebSocket(object):

    default_ports = {
            'ws':  80,
            'wss': 443,
        }

    def __init__(self, url, version=0, origin=None, cookie=None, proxies=None):
        """
        :type url:     str
        :type version: int
        :type origin:  str
        :type cookie:  Cookie.BaseCookie
        :type proxies: dict
        """
        if proxies is None:
            proxies = urllib.getproxies()

        self.url = url
        self.version = version
        self.inmsgs = []
        self.indata = ''
        self.curmsg = ''
        self.curop = 0x0
        self.outdata = ''

        urlparse.uses_netloc.append("ws")
        urlParts = urlparse.urlparse(self.url)

        self.hostname = self.host = urlParts.hostname
        if urlParts.port is not None \
         and ((urlParts.scheme == 'ws'  and urlParts.port != 80) \
           or (urlParts.scheme == 'wss' and urlParts.port != 443)):
             self.host += ':%d' % (urlParts.port,)

        self.port = urlParts.port
        if self.port is None:
            self.port = self.default_ports[urlParts.scheme]

        self.username, self.password = urlParts.username, urlParts.password
        self.scheme = urlParts.scheme

        # optional proxy usage
        if urlParts.scheme in proxies:
            proxyParts = urlparse.urlparse(proxies[urlParts.scheme])

            if proxyParts.scheme == 'http':
                #self.socket = socks.socksocket()
                #self.socket.setproxy(socks.PROXY_TYPE_SOCKS4, 'localhost', 9050)
                #self.socket.connect((proxyParts.hostname, proxyParts.port))
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

        try:
            handshake = self.handshakes[self.version]
        except KeyError:
            raise NotImplementedError, "WebSocket protocol version %d not implemented" % (self.version,)

        handshake(self, url=url, version=version, origin=origin, cookie=cookie)
    __doc__ = __init__.__doc__

    def _do_handshake_3(self, url, version=3, origin=None, cookie=None):
        """http://tools.ietf.org/html/draft-ietf-hybi-thewebsocketprotocol-03"""
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

        urlParts = urlparse.urlparse(self.url)

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

    def _do_handshake_6(self, url, version=6, origin=None, cookie=None):
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

    handshakes = {
            0: _do_handshake_3,
            1: _do_handshake_3,
            2: _do_handshake_3,
            3: _do_handshake_3,
            6: _do_handshake_6,
        }

    def recv(self, bufsize, flags=0):
        try:
            recv = self.recvs[self.version]
        except KeyError:
            raise NotImplementedError, "WebSocket protocol version %d not implemented" % (self.version,)
        return recv(self, bufsize, flags)

    def _non_blocking_send(self):
        """Fills the TCP send buffer completely, but doesn't block to send
        everything in our own send buffer."""
        if not self.outdata:
            return
        _, w, _ = select((), (self.socket,), (), 0)
        if not w:
            return
        sent = self.socket.send(self.outdata)
        self.outdata = self.outdata[sent:]

    def _do_recv_6(self, bufsize, flags=0):
        try:
            if not self.inmsgs:
                self.indata += self.socket.recv(bufsize, flags)
                while self.indata:
                    if len(self.indata) < 2:
                        try:
                            return self.inmsgs.pop(0)
                        except IndexError:
                            return None
                    header_flags = struct.unpack(r'!BB', self.indata[:2])
                    pstart = 2
                    fin  = bool(header_flags[0] & 0x80)
                    rsv1 = bool(header_flags[0] & 0x40)
                    rsv2 = bool(header_flags[0] & 0x20)
                    rsv3 = bool(header_flags[0] & 0x10)
                    opcode = header_flags[0] & 0x0f
                    rsv4 = bool(header_flags[1] & 0x80)
                    plen = header_flags[1] & 0x7f
                    if   plen == 126:
                        if len(self.indata) < 4:
                            try:
                                return self.inmsgs.pop(0)
                            except IndexError:
                                return None
                        # '!' (network-byte order, aka big endian) should be
                        # used, unfortunately MtGox wrongly sends the length
                        # bytes as little-endian, hence the '<'
                        #plen, = struct.unpack(r'!H', self.indata[pstart:pstart+2])
                        plen, = struct.unpack(r'<H', self.indata[pstart:pstart+2])
                        pstart += 2
                    elif plen == 127:
                        if len(self.indata) < 10:
                            try:
                                return self.inmsgs.pop(0)
                            except IndexError:
                                return None
                        # '!' (network-byte order, aka big endian) should be
                        # used, unfortunately MtGox wrongly sends the length
                        # bytes as little-endian, hence the '<'
                        #plen, = struct.unpack(r'!Q', self.indata[pstart:pstart+8])
                        plen, = struct.unpack(r'<Q', self.indata[pstart:pstart+8])
                        pstart += 8
                    if len(self.indata) < pstart + plen:
                        try:
                            return self.inmsgs.pop(0)
                        except IndexError:
                            return None

                    data = self.indata[pstart:pstart+plen]
                    self.indata = self.indata[pstart+plen:]
                    if   opcode in (0x0, 0x4, 0x5): # continuation, text, binary
                        if opcode != 0x0:
                            self.curop = opcode
                        self.curmsg += data
                        if fin:
                            if self.curop in (0x0, 0x4):
                                self.inmsgs.append(self.curmsg.decode('utf-8', 'replace'))
                            else:
                                self.inmsgs.append(self.curmsg)
                            self.curmsg = ''
                    elif opcode == 0x1: # close
                        header_flags = (0x80 | opcode, 0)
                        self.outdata += struct.pack(r'!BB', *header_flags)
                    elif opcode == 0x2: # ping
                        self.outdata += struct.pack(r'!B', 0x80 | opcode)
                        if   len(data) < 126:
                            self.outdata += struct.pack(r'!B', len(data))
                        elif len(data) < 2**16-1:
                            self.outdata += struct.pack(r'!BH', 126, len(data))
                        elif len(data) < 2**64-1:
                            self.outdata += struct.pack(r'!BQ', 127, len(data))
                        self.outdata += data
                    elif opcode == 0x3: # pong
                        if _debug:
                            print >> sys.stderr, "pong!"
            try:
                return self.inmsgs.pop(0)
            except IndexError:
                return None
        finally:
            self._non_blocking_send()

    recvs = {
            6: _do_recv_6,
        }

    def send(self, data, flags=0):
        try:
            send = self.sends[self.version]
        except KeyError:
            raise NotImplementedError, "WebSocket protocol version %d not implemented" % (self.version,)
        return send(self, data, flags)

    def _do_send_6(self, data, flags=0):
        try:
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

            self.outdata += struct.pack(r'!B', 0x80 | opcode)
            if   len(data) < 126:
                self.outdata += struct.pack(r'!B', len(data))
            elif len(data) < 2**16-1:
                self.outdata += struct.pack(r'!BH', 126, len(data))
            elif len(data) < 2**64-1:
                self.outdata += struct.pack(r'!BQ', 127, len(data))
            self.outdata += data
        finally:
            self._non_blocking_send()

    sends = {
            6: _do_send_6,
        }

    def _do_ping_6(self):
        try:
            self.outdata += struct.pack(r'!BB', 0x80 | 0x02, 0)
        finally:
            self._non_blocking_send()

    def ping(self):
        try:
            ping = self.pings[self.version]
        except KeyError:
            raise NotImplementedError, "WebSocket protocol version %d not implemented" % (self.version,)
        return ping(self)

    pings = {
            6: _do_ping_6,
        }

    def _do_close_6(self):
        self.outdata += struct.pack(r'!BB', 0x80 | 0x01, 0)
        self.sendall(self.outdata)
        self.outdata = ''

    def ping(self):
        try:
            close = self.closes[self.version]
        except KeyError:
            raise NotImplementedError, "WebSocket protocol version %d not implemented" % (self.version,)
        return close(self)

    closes = {
            6: _do_close_6,
        }
