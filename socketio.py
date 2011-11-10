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
    response = urllib2.urlopen(req)
    r = response.read().split(':')
    if 'websocket' in r[3].split(','):
      print "good: transport 'websocket' supported by socket.io server ", S.url
      S.id = r[0]
      print "id: ", S.id

    S.thread = Thread(target = S.thread_func)
    S.thread.setDaemon(True)
    S.thread.start()

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
      #S.onMessage(msg)
      #print 'SocketIO msg: ', msg
      if msg[:10] == "3::/mtgox:":
        S.callback(msg[10:])
      else:
        print "dont know how to handle msg: ", msg
      msg = S.ws.recv()
      
  def keepalive_func(S):
    while S.run:
      time.sleep(10)
      S.ws.send('2::');
      
def test_callback(msg):
  print 'msg: ', msg

# testcase
if False:
  sio = SocketIO('socketio.mtgox.com/socket.io', test_callback)
  sio.connect()
  time.sleep(100)

