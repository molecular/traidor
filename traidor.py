#!/usr/bin/python
          
# maybe alternative for /code/getTrades.php before websocket is back
# http://bitcoincharts.com/t/trades.csv?symbol=mtgoxUSD&start=$UNIXTIME
# http://www.google.com/fusiontables/DataSource?dsrcid=1058017

import sys, os
import time
import subprocess
from ConfigParser import SafeConfigParser
#from pywsc.websocket import WebSocket
import pygame
from contextlib import closing
from threading import *

from common import *
from bot import *
from wxgui import *
#from img import *

from mtgox import *

PRICE_PREC = D('0.00001')
VOL_PREC = D('0.1')
VOL2_PREC = D('0')
MYVOL_PREC = D('0.01')


class Trade:
  def __init__(S, time, amount, price, type):
    (S.time, S.amount, S.price, S.type) = (time, D(amount), D(price), type)
    
  def str(S):
    "{%s} | %s for %s - %i %s" % (S['oid'], o['amount'], o['price'], o['status'], o['real_status'])

class Traidor:
  def __init__(S):
    S.datalock = Lock()
    S.displaylock = Lock()
    S.order_distance = D('0.00001')
    S.auto_update_trade = True

    S.do_img = False
    if S.do_img:
      S.img = Img(1280,720)
      S.img.set_bar(0,0.3,0.1)

    # parse configfile
    parser = SafeConfigParser()
    parser.read('traidor.conf')

    S.exchange = None
    S.exchanges = []
    exchange = MtGox(S, parser)
    S.addExchange(exchange)
    
    S.donated = parser.getboolean('main', 'donated')
    S.debug = parser.getboolean('main', 'debug')
    S.display_height = int(parser.get('main','initial_depth_display_height'))
    #lines = os.environ['LINES']
    #print "lines: ", lines
    S.bots = list()

    # start command mainloop
    t = Thread(target = S)
    t.start()
    

  # --- exchange handling ----------------------------------------------------------------------------------------------------
  
  def addExchange(S, exchange):
    S.exchange = exchange
    S.exchanges.append(exchange)

  # --- bot handling ---------------------------------------------------------------------------------------------------------
  
  def addBot(S, bot):
    S.bots.append(bot)

  def removeBot(S, bot):
    S.bots.remove(bot)



  # --- json stuff ----------------------------------------------------------------------------------------------------------------------
  

    
  def eval(S, base):
    delta = S.getBTC() - base
    corrected_usd = S.getUSD() + (S.last_price * delta * (D('1.0') - S.trading_fee))
    return corrected_usd

  # --- preliminary bot stuff (highly experimental, will be abstracted) -------------------------------

  def show_help(S):
    print "\n\
    h                     this help\n\
    a                     toggle auto_update on/off\n\
    <ret>                 show public order book, recent trades and your order book\n\
    r                     S.reload - S.reload public order book and trades\n\
    b <amount> <price>    enter order to buy <amount> btc at <price>\n\
    s <amount> <price>    enter order to sell <amount> btc at <price>\n\
    b <amount> i<index>   enter order to buy <amount> btc, price looked up from orderbook at <index>\n\
    s <amount> i<index>   enter order to sell <amount> btc, price looked up from orderbook at <index>\n\
    o                     view your order book\n\
    c <index> <index> ... cancel order at <index> from orderbook (list of <index>s possible)\n\
    d <lines>             set height of depth display\n\
    ws                    toggle websockets updates\n\
    dws                   toggle websocket debugging output\n\
    p <1..5>              set display precision\n\
    ps <file.wav>         play sound from wav\n\
    lb                    list active bots\n\
    wx | gui              start gui\n\
    q                     quit\n\
"
  def prompt(S):
    S.displaylock.acquire()
    sys.stdout.write(S.exchange.getPrompt(infoline))
    sys.stdout.flush()
    S.displaylock.release()

  def cmd(S, cmd, is_bot=False):
    global PRICE_PREC
    if (cmd.rfind(';') >= 0):
      for c in cmd.split(';'): S.cmd(c.strip())
    else:
      if cmd[:3] == 'dws': S.debug_ws = not S.debug_ws; print 'debug_ws=', S.debug_ws
      elif cmd[:4] == 'eval': 
        S.auto_update_depth = False
        base = D(cmd[4:])
        print 'evaluation based on %s BTC: %s USD' % (base.quantize(USD_PREC), S.eval(base).quantize(USD_PREC))
      elif cmd[:2] == 'ps': pygame.mixer.Sound(cmd[3:]).play()
      elif cmd[:3] == 'ws': S.use_ws = not S.use_ws; print 'use_ws=', S.use_ws
      elif cmd[:2] == 'lb': 
        i=0
        for bot in S.bots: 
          print "[%2i]: %s" % (i, bot.getName())
          i += 1
      elif cmd[:2] == 'tb': # TriggerBot
        S.addBot(TriggerBot(t, cmd[2:]))
      elif cmd[:2] == 'wx' or cmd[:3] == 'gui':
        wx = TraidorApp(t)
        S.addBot(wx)
        wx.initialize()
      elif cmd[0] == 'q': 
        S.run = False
      elif cmd[0] == 'h': 
        S.auto_update_depth = False
        S.show_help()
      elif cmd[0] == 'b' or cmd[0] == 's': 
        S.auto_update_depth = False
        S.trade(cmd, is_bot)
      elif cmd[0] == 'c': 
        S.auto_update_depth = False
        S.cancel_order(cmd, is_bot); 
        S.show_orders()
      elif cmd[0] == 'a': S.auto_update_depth = not S.auto_update_depth; print 'auto_update_depth = ', S.auto_update_depth
      elif cmd[0] == 'r': S.reload = True;
      elif cmd[0] == 'o': 
        S.auto_update_depth = False
        rc = S.request_orders(); 
        S.datalock.acquire()
        S.orders = rc
        S.datalock.release()
        S.show_orders()
      elif cmd[0] == 'e': S.show_depth()
      #elif cmd[0] == 't': 
      #  for x in S.ticker: print x
      #  print S.ticker
      elif cmd[0] == 'd': 
        S.displaylock.acquire()
        S.display_height = int(cmd[1:])
        S.displaylock.release()
      elif cmd[0] == 'p': 
        p = int(cmd[1:])
        try:
          if p<1 or p>5: print 'precision must be 2..5'
          else: PRICE_PREC = D(10) ** -p; S.reload = True
        except: print 'exception parsing precision value: %s' % p

  def websocket_thread(S):
    if S.use_ws:
      print 'websocket_thread() started'
      while S.run:
        print 'connecting websocket'
        try:
          S.ws = WebSocket('ws://websocket.mtgox.com/mtgox', version=6)
          msg = S.ws.recv(2**16-1)
          while msg is not None and S.run:
              S.onMessage(msg)
              msg = S.ws.recv(2**16-1)
        except:
          print 'exception connecting websocket: ', sys.exc_info()[0], " will retry..."
          time.sleep(3)
          
      print 'websocket_thread() exit'

  def __call__(S): # mainloop
    global PRICE_PREC
    S.run = True
    S.reload = False
    
    # initial for bot, ned so wichtig auf dauer, kost zeit
    # abhilfe: unten bei initialize bots nen fake-trade reinschreiben
    # es geht glaub nur um S.last_trade? oder?
    #S.request_trades()

    if S.debug: print 'starting exchanges...'
    for x in S.exchanges:
      x.start()

    if S.debug: print 'initializing bots...'
    for bot in S.bots:
      bot.initialize()
      
    if S.debug: print 'ready'
      

    counter = 0
    while (S.run):
        
                
      #if S.use_ws:
      #  while not S.ws.connected:
      #    if S.debug: print 'connecting websocket...'
      #    try:
      #      S.ws.connect();
      #      if S.debug: print 'websocket connected'
      #    except:
      #      print 'connection problem, retrying later...'
      #      time.sleep(1);
            
      if (S.reload): 
        #S.request_ticker()
        if not S.use_ws: S.request_trades()
        S.request_market()
        # trigger show_depth() thread
        S.last_depth_update = time.time()
        S.depth_invalid_counter += 1
        
      #S.print_stuff();
      S.reload = False;
      key = raw_input(S.exchange.getPrompt());
      if (len(key) > 0):
        S.cmd(key)
      else: 
        #S.request_info();
        S.show_depth();
      counter += 1
      if (counter % 31) == 13 and not S.donated:
        print '\n\n\n\n\nplease consider donating to 1Ct1vCN6idU1hKrRcmR96G4NgAgrswPiCn\n\n\n(to remove donation msg, put "donated=1" into configfile, section [main])\n'

    if S.debug: print 'stopping exchanges...'
    for x in S.exchanges:
      x.start()


pygame.init()
t = Traidor()
t.addBot(BeepBot(t))

#t.addBot(EquilibriumBot(t, D('0.0'), D('0'), D('3.0'), D('0.2'))) # btc add, usd add, fund_multiplier, desired_amount
#t.cmd("tb >= 14.80 ps alarm.wav")
#t.cmd("tb <= 14.40 ps alarm2.wav")
#t.mainloop()
