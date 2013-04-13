'''
    Copyright (C) Nicolas Fischer, molec@gmx.de
    
    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
'''

from threading import *
import urllib2, urllib
try: import simplejson as json
except ImportError: import json
import ssl, socket
import time
from websocket_client import create_connection
import traceback

class SocketIO:
  def __init__(S, url, callback):
    S.url = url
    S.callback = callback
    
  def connect(S):
    try:
      # data = urllib.urlencode({'Currency':'EUR,GBP'})
      data = urllib.urlencode({})
      req = urllib2.Request('https://' + S.url + "/1", data)
      print 'https://' + S.url + "/1"
      response = urllib2.urlopen(req)
      r = response.read().split(':')
      print 'response: ' + ':'.join(r)
      S.heartbeat_interval = int(float(r[1]) * .85)
      #print 'heartbeat: ', S.heartbeat_interval
      if 'websocket' in r[3].split(','):
        print "good: transport 'websocket' supported by socket.io server ", S.url
        S.id = r[0]
        print "id: ", S.id
      else:
        print "error: transport 'websocket' NOT supported by socket.io server ", S.url
        
      S.thread = Thread(target = S.thread_func)
      S.thread.setDaemon(True)
      S.thread.start()
    except:
      traceback.print_exc()      
      print "connection attempt aborted due to above exception, sleeping for a bit...";
      time.sleep(11)
      
  def unsubscribe(S, channel_id):
    S.ws.send('4::/mtgox:{"op":"unsubscribe","channel":"%s"}' % channel_id)
    
  def stop(S):
    S.run = False
    S.thread.join(timeout=1)
    S.keepalive_thread.join(timeout=1)


  def thread_func(S):
    print 'SocketIO: websocket thread started'
    
    my_url = 'wss://' + S.url + "/1/websocket/" + S.id
    
    S.ws = create_connection(my_url)
    
    #S.ws = WebSocket(my_url, version=0) 
    S.ws.send('1::/mtgox') #?Currency=USD,EUR,GBP,JPY')

    # start keepalive thread
    S.keepalive_thread = Thread(target = S.keepalive_func)
    S.keepalive_thread.setDaemon(True)
    S.run = True
    S.keepalive_thread.start()

    try:
      msg = S.ws.recv()
      while msg is not None and S.run:
        #print 'SocketIO msg: ', msg
        if msg[:10] == "4::/mtgox:":
          S.callback(msg[10:])
        elif msg[:3] == "2::":
        #  S.callback(msg[10:])
          True
        #else:
        #  print "SocketIO: dont know how to handle msg: ", msg
        msg = S.ws.recv()
    except:
      raise SystemExit
      
    S.ws.close()
      
  def keepalive_func(S):
    while S.run:
      try:
        S.ws.send('2::');
      except:
        if S.run:
          print 'error sending keepalive socket.io, trying reconnect after sleep...'
          S.ws.close()
          print '\ttrying to reconnect...'
          S.connect()
          raise SystemExit
        else:
          print 'exiting socket.io keepalive thread'
      time.sleep(S.heartbeat_interval)
      
def test_callback(msg):
  print 'msg: ', msg

# testcase
if False:
  sio = SocketIO('socketio.mtgox.com/socket.io', test_callback)
  sio.connect()
  time.sleep(100)

