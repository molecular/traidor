from threading import *
import urllib2, urllib
import simplejson as json
import ssl, socket
import time
from websocket import WebSocket


class SocketIO:
  def __init__(S, url, callback):
    S.url = url
    S.callback = callback
    
  def connect(S):
    data = urllib.urlencode({})
    req = urllib2.Request('https://' + S.url + "/1", data)
    print 'https://' + S.url + "/1"
    response = urllib2.urlopen(req)
    r = response.read().split(':')
    S.heartbeat_interval = int(r[1])
    print 'heartbeat: ', S.heartbeat_interval
    if 'websocket' in r[3].split(','):
      print "good: transport 'websocket' supported by socket.io server ", S.url
      S.id = r[0]
      print "id: ", S.id

    S.thread = Thread(target = S.thread_func)
    S.thread.setDaemon(True)
    S.thread.start()

  def stop(S):
    S.run = False
    S.thread.join(timeout=1)
    S.keepalive_thread.join(timeout=1)


  def thread_func(S):
    print 'SocketIO: websocket thread started'
    
    my_url = 'wss://' + S.url + "/1/websocket/" + S.id
    
    S.ws = WebSocket(my_url, version=0) 
    S.run = True
    S.ws.send('1::/mtgox')

    # start keepalive thread
    S.keepalive_thread = Thread(target = S.keepalive_func)
    S.keepalive_thread.setDaemon(True)
    S.keepalive_thread.start()
    
    msg = S.ws.recv()
    while msg is not None and S.run:
      #print 'SocketIO msg: ', msg
      if msg[:10] == "4::/mtgox:":
        S.callback(msg[10:])
      #elif msg[:3] == "2::":
      #  True
      #else:
      #  print "SocketIO: dont know how to handle msg: ", msg
      msg = S.ws.recv()
      
  def keepalive_func(S):
    while S.run:
      time.sleep(S.heartbeat_interval)
      try:
        S.ws.send('2::');
      except:
        print 'error sending keepalive socket.io, trying reconnect'
        S.connect()
      
def test_callback(msg):
  print 'msg: ', msg

# testcase
if False:
  sio = SocketIO('socketio.mtgox.com/socket.io', test_callback)
  sio.connect()
  time.sleep(100)
