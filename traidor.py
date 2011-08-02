#!/usr/bin/python
          
# maybe alternative for /code/getTrades.php before websocket is back
# http://bitcoincharts.com/t/trades.csv?symbol=mtgoxUSD&start=$UNIXTIME
# http://www.google.com/fusiontables/DataSource?dsrcid=1058017

import simplejson as json
import urllib, urllib2 #, httplib2
import sys, os
import time
import subprocess
from threading import *
from ConfigParser import SafeConfigParser
from pywsc.websocket import WebSocket
#import pygame

from common import *
from bot import *
from wxgui import *
#from img import *

PRICE_PREC = D('0.00001')
VOL_PREC = D('0.1')
VOL2_PREC = D('0')
MYVOL_PREC = D('0.01')

def convert_certain_json_objects_to_decimal(dct):
  for k in ('amount', 'price', 'btcs', 'usds', 'volume'):
    if k in dct: dct[k] = D(dct[k])
  for k in ('asks', 'bids'):
    if k in dct: 
      for idx in range(len(dct[k])):
        for i in (0,1): 
          dct[k][idx][i] = D(dct[k][idx][i]) 
  return dct

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
    S.auto_update_depth = True
    S.auto_update_trade = True
    S.depth_invalid_counter = 0
#    S.connection = httplib2.HTTPSConnectionWithTimeout("mtgox.com:443", strict=False, timeout=10)
    S.display_height=15
    S.orders = {'btcs': -1, 'usds': -1}
    S.trades = []

    S.do_img = False
    if S.do_img:
      S.img = Img(1280,720)
      S.img.set_bar(0,0.3,0.1)

    # parse configfile
    parser = SafeConfigParser()
    parser.read('traidor.conf')
    S.mtgox_account_name = parser.get('mtgox', 'account_name')
    S.mtgox_account_pass = parser.get('mtgox', 'account_pass')
    S.donated = parser.getboolean('main', 'donated')
    S.use_ws = parser.getboolean('main', 'use_websockets')
    S.debug_ws = parser.getboolean('main', 'debug_websockets')
    S.debug = parser.getboolean('main', 'debug')
    S.bots = list()


    t = Thread(target = S)
    t.start()
    
    t_show_depth = Thread(target = S.show_depth_run)
    t_show_depth.start()

    if S.use_ws:
      S.ws = WebSocket('ws://websocket.mtgox.com:80/mtgox')
      S.ws.setEventHandlers(S.onOpen, S.onMessage, S.onClose)  

  # --- bot handling ---------------------------------------------------------------------------------------------------------
  
  def addBot(S, bot):
    S.bots.append(bot)

  def removeBot(S, bot):
    S.bots.remove(bot)

  # --- bot support ----------------------------------------------------------------------------------------------------------
  
  def getBTC(S): return S.orders['btcs']
  def getUSD(S): return S.orders['usds']

  def get_order(S, oid):
    # woah, friggin linear search, do something !! ^^
    for o in S.orders['orders']: 
      if o['oid'] == oid: return o

  def get_orders(S):
    #"""unclear if this should be in the bot api because of the json-deriven format of orders"""
    return S.orders['orders']

  def do_trade(S, type, vol, price):
    result = S.request_json_authed('/code/' + type + 'BTC.php', params = {'amount': vol, 'price': price})
    print '{%s}: %s' % (result['oid'], result['status'])
    S.orders['orders'] = result['orders']
    return result['oid']

  def do_cancel_order(S, oid):
    print 'CANCELLING order {%s}' % oid
    o = S.get_order(oid)
    result = S.request_json_authed('/code/cancelOrder.php', {'oid': o['oid'], 'type': o['type']})
    S.orders['orders'] = result['orders']
    
  def do_cancel_all_orders(S):
    oids = list()
    for o in S.get_orders():
      oids.append(o['oid'])
    for oid in oids:
      S.do_cancel_order(oid)


  # --- websocket callbacks --------------------------------------------------------------------------------------------------
  
  def onOpen(S):
    if S.debug_ws: print "websocket open"
      
  def onMessage(S, message):
    #try:
    #print "-onMessage:", message
    update = False
    m = json.loads(message, use_decimal=True)
    if S.debug_ws: print m #json.dumps(m, sort_keys=True, indent=2)
    channel = m['channel']
    op = m['op']
    #print 'message in channel ', channel, ' op: ', op
    
#    if channel == 'd5f06780-30a8-4a48-a2f8-7ed181b4a13f': # ticker
#      S.prompt('tick')

    S.datalock.acquire()
    
    # trades
    if op == 'private' and channel == 'dbf1dee9-4f2e-4a08-8cb7-748919a71b21': 
      trade = m['trade']
      if (trade['type'] != 'trade'): print m
      #s = '%s: [trade %s]: %5.1f for %.4f' % (trade['date'], trade['tid'], float(trade['amount']), float(trade['price']))
      depth_type = None
      type = 'unknown'
      
      #S.trades.append([trade['date'], trade['tid'], trade['amount'], trade['price'], type])
      #S.img.write("test/%s.png" % trade['date'])
      
      trade = Trade(trade['date'], trade['amount'], trade['price'], trade['trade_type'])
      S.trades.append(trade)
      update = S.auto_update_depth
      
      # bots 
      S.datalock.release()
      S.request_orders() # hmmmgrl, really? why is this so extremely fast to call?
      S.last_price = trade.price
      for bot in S.bots:
        bot.trade(trade)
      S.datalock.acquire()

    # depth: {u'volume': 7.7060600456200001, u'price': 6.4884000000000004, u'type': 1}
    if op == 'private' and channel == '24e67e0d-1cad-4cc0-9e7a-f8523ef460fe': 
      #print m
      depth_msg = m['depth']
      if depth_msg['currency'] == 'USD':
        type = depth_msg['type_str'] + 's'
        price = D(depth_msg['price']).quantize(PRICE_PREC)
        volume = D(depth_msg['volume']);
        if not S.depth[type].has_key(price): 
          S.depth[type][price] = D('0')
        S.depth[type][price] += volume
        if S.depth[type][price] <= D('0'): 
          S.depth[type].pop(price)
        #S.dmz_width = sorted(S.depth['asks'])[0] - sorted(S.depth['bids'], reverse=True)[0]
        update = False
        S.last_depth_update = time.time()
        S.depth_invalid_counter += 1

        S.cmd('ps gligg.wav')
        time.sleep(0.05)
        
        if S.do_img: S.img_depth()

    S.datalock.release()
    
    if update:
      S.show_depth()
      S.prompt()
        
  def onClose(S):
    print "websocket closed"

  # --- json stuff ----------------------------------------------------------------------------------------------------------------------
  
  def request_json_old(S, url, params={}):
    headers = {"Content-type": "application/x-www-form-urlencoded", "Accept": "application/json"}
    success = False;
    S.connection.set_debuglevel(100)
    while not success:
      try:
        print "loading url: ", url, " params: ", params
        S.connection.request('POST', url, urllib.urlencode(params), headers)
        success = True
      except:
        print 'CONNECTION fail, retrying after some time'
        time.sleep(5);
    try:
      response = S.connection.getresponse()
      print response.getheaders()
      return json.loads(response.read(), use_decimal=True)
    except (httplib2.httplib.HTTPException, httplib2.httplib.ResponseNotReady):
      print 'CONNECTION reestablishment -------------------------'
      S.connection.close()
      S.connection = httplib.HTTPSConnection("mtgox.com:443", strict=True, timeout=10)
      S.connection.request('POST', url, urllib.urlencode(params), headers)
      return json.loads(S.connection.getresponse().read(), use_decimal=True)


  def request_json(S, url, params={}):
    data = urllib.urlencode(params)
    req = urllib2.Request("https://mtgox.com:443" + url, data)
    response = urllib2.urlopen(req)
    #s = response.read()
    #print s
    return json.load(response, use_decimal=True, object_hook=convert_certain_json_objects_to_decimal)

  def request_json_authed(S, url, params={}):
    params['name'] = S.mtgox_account_name
    params['pass'] = S.mtgox_account_pass
    return S.request_json(url, params)

  def request_market(S):
    S.market = S.request_json('/code/data/getDepth.php')
    
    S.highest_bid = sorted(S.market['bids'], reverse=True)[0][0];
    S.lowest_ask = sorted(S.market['asks'])[0][0];
    S.highest_bid_vol = S.market['bids'][0][1];
    S.lowest_ask_vol = S.market['asks'][0][1];
    S.dmz_width = S.highest_bid - S.lowest_ask;

    # S.market (list) -> S.depth (dict)
    S.datalock.acquire()
    S.depth = {}
    for kind in ('bids', 'asks'):
      S.depth[kind] = {}
      for o in S.market[kind]:
        price = o[0].quantize(PRICE_PREC)
        if not S.depth[kind].has_key(price): S.depth[kind][price] = D(0)
        S.depth[kind][price] += o[1]
    S.depth_invalid_counter += 1
    S.datalock.release()

  def request_orders(S):
    S.datalock.acquire()
    S.orders = S.request_json_authed('/code/getOrders.php')
    S.datalock.release()

  def request_ticker(S):
    S.ticker = S.request_json_authed('/code/data/ticker.php')

  def request_trades(S):
    S.datalock.acquire()
    S.trades2 = S.request_json('/code/data/getTrades.php')
    S.trades = list()
    for trade in S.trades2[-200:]:
      S.trades.append(Trade(trade['date'], trade['amount'], trade['price'], '?'))
    S.last_price = S.trades[-1].price
    S.datalock.release()
    
  # --- show_* ----------------------------------------------------------------------------------------

  def show_orders(S):
    S.datalock.acquire()
    S.displaylock.acquire()
    #print S.orders
    print "\n"
    i = 0
    print "[IDX] {                id                  } | typ    volume   price    - status"
    print "                                             |"
    type = -1
    for o in sorted(S.orders['orders'], key=lambda ord: ord['price'], reverse=True):
      #print "{%s}: %s %s" % (o['oid'], o['amount'], o['price'])
      if abs(S.last_price - o['price']) < D('10'):
        if o['type'] == 2 and type == 'ask' and len(S.orders['orders']) > 2: print "                                             |"
        type = o['type']
        if type==1: type = 'ask'
        elif type==2: type = 'bid'
        else: type = 'unknown'
        print "[%3i] {%s} | %s %s %s - %i %s" % (i, o['oid'], type, dec(o['amount'], 4, 5), dec(o['price'], 3, 5), o['status'], o['real_status'])
      i += 1
    S.displaylock.release()
    S.datalock.release()

  # write market depth into a png (experimental)
  def img_depth(S):
    S.img.clear()
    max_price = D('30.0')
    for kind in ('bids', 'asks'):
      if kind == 'bids': c, dir, end_x = 0xff3080ff, -1, 0
      if kind == 'asks': c, dir, end_x = 0xff30ff00, 1, S.img.w
      akku = D('0');
      old_price = D('0')
      old_x = -1
      for price in sorted(S.depth[kind].keys(), reverse = (kind=='bids')):
        akku += S.depth[kind][price]
        if old_price != price:
          x = S.img.w/2 + int((old_price - (max_price/2)) * 100)
          h = int(akku / 100)
          if x>=0 and x<=S.img.w:
            #print('price %s: set_bar(%i, %i)' % (price, x, h))
            if old_x < 0: old_x = x
            for x2 in range(old_x, x, dir):
              if h>0: S.img.set_bar(c, x2, S.img.h - h)
          old_price = price
          old_x = x
      for x2 in range(old_x, end_x, dir):
        if h>0: S.img.set_bar(c, x2, S.img.h - h)
      
    tm = time.localtime()
    S.img.write('test/%s.png' % time.strftime('%Y%m%d-%H:%M:%S',tm))

  # lazy depth display update (calls show_depth())
  def show_depth_run(S):
    print 'show_depth()-thread started'
    S.last_depth_update = time.time()
    while S.run:
      time.sleep(0.17)
      age = time.time() - S.last_depth_update
      if S.auto_update_depth:
        # once enough time passed since last depth update msg (burst ceased) or a lot of update messages queued up, call show_depth()
        if (age >= 0.71 and S.depth_invalid_counter > 0) or S.depth_invalid_counter > 37:  
          #print 'show_depth_run(): calling show_depth()'
          S.show_depth()
          S.prompt()    

  # display depth data
  def show_depth(S):
    S.datalock.acquire()
    s = []
    my_orders = S.orders['orders']
    for kind in ('bids', 'asks'):
      akku = D(0);
        
      # bids
      if (kind=='bids'):
        for price in sorted(S.depth[kind].keys(), reverse = (kind=='asks'))[-S.display_height:]:
          akku += S.depth[kind][price]
        i = S.display_height # len(S.depth[kind]);
        for price in sorted(S.depth[kind].keys(), reverse = False)[-S.display_height:]:
          i -= 1
          vol = S.depth[kind][price]
          #str = "%.4f %5.0f   %5.0f" % (price, vol, akku)  
          str = "%s %s %5s" % (dec(price, 3, 5), dec(vol, 4, 1), akku.quantize(VOL2_PREC))  
          my_vol = D(0)
          for my_order in my_orders:
            if my_order['price'].quantize(PRICE_PREC) == price.quantize(PRICE_PREC): 
              my_vol += my_order['amount']
          if (my_vol > 0): str = '%6s %s' % (my_vol.quantize(MYVOL_PREC),str)
          else: str = '       ' + str
          str = "[%3i]" % i + str
          s.append(str)
          akku -= vol

      # asks
      if (kind=='asks'):
        s_i = len(s) - 1
        for price in sorted(S.depth[kind].keys())[:S.display_height]:
          vol = S.depth[kind][price]
          akku += vol
          str = "%-5s %s %s" % (akku.quantize(VOL2_PREC), dec(vol, 4, 1), dec(price, 3, 5))
          my_vol = D(0)
          for my_order in my_orders:
            if my_order['price'].quantize(PRICE_PREC) == price.quantize(PRICE_PREC): 
              my_vol += my_order['amount']
          if (my_vol > 0): str = str + ' %-6s ' % my_vol.quantize(MYVOL_PREC)
          else: str += '        '
          if s_i >= 0:
            s[s_i] += "  |  " + str
            s_i -= 1

    # trades (websocket trades)
    i = 0
    while i < S.display_height - len(S.trades):
      s[i] += '|'
      i += 1
    for t in S.trades[-S.display_height:]:
      tm = time.localtime(t.time)
      str = "|  %s %s for %s %s" % (time.strftime('%H:%M:%S',tm), dec(t.amount, 4, 5), dec(t.price, 3, 5), t.type)
      s[i] += str
      i += 1

    S.depth_invalid_counter = 0

    S.datalock.release()
    
    S.displaylock.acquire()
    print '\n\n       ------ BUYING BITCOIN ------ | ------- SELLING BITCOIN ------ | ----------- TRADES ------------'
    print '                                                                     |'
    print '[IDX]   YOU   bid        vol   accumulated      vol   ask       YOU  |  time        amount       price'
    print '                                                                     |'
    for str in s[-S.display_height:]:
      print str
    S.displaylock.release()
        
  # --- actions -------------------------------------------------------------------------------------------------------

  def trade(S, key):
    p = key.split(' ')
    type = 'unknown'
    if p[0][0] == 'b': type = 'buy'; m = 'bids'; air = S.order_distance
    if p[0][0] == 's': type = 'sell'; m = 'asks'; air = -S.order_distance
    vol = p[1]
    price_str = ''
    if len(p) >= 3: price_str = p[2]
    price = -1.0
    #print 'price_str ', price_str
    if price_str[0] != 'i' >= 0:
      price = float(price_str)
    else:
      if price_str == 'i': index = 0
      else: index = int(price_str[1:])
      if m == 'bids': index = -index - 1
      #print 'index: ', index, ' market: ', S.market[m][index]
      price = sorted(S.depth[m].keys())[index] + air
      #price = S.depth[m][market_index] + air
      #print 'market_index: ', market_index
      #price = S.market[m][index][0] + air
      
    # price = "%.4f" % price
    k = raw_input("\n%s %s BTC for %s USD [y]es [n]o #> " % (type, vol, price))
    if k[0] == 'y':
      result = S.do_trade(type, vol, price)
      S.show_orders()
      return result
    else:
      print 'ABORTED'
      return None
      
    S.show_orders()
    
  def cancel_order(S, key):
    p = key.split(' ')
    print p
    for idx in p[1:]:
      index = int(idx)
      o = sorted(S.orders['orders'], key=lambda ord: ord['price'], reverse=True)[index]
      #key = raw_input("\ncancel order oid={%s} [y]es [n]o #> " % (o['oid']))
      key = raw_input("\ncancel order {%s} | %s for %s ? [y]es [n]o #>  " % (o['oid'], o['amount'], o['price']))
      if key[0] == 'y':
        print 'CANCELLING order {%s}' % o['oid']
        S.do_cancel_order(o['oid'])

  # --- preliminary bot stuff (highly experimental, will be abstracted) -------------------------------

  def show_help(S):
    print "\n\
    h                     this help\n\
    <ret>                 show public order book, recent trades and your order book\n\
    r                     S.reload - S.reload public order book and trades\n\
    b <amount> <price>    enter order to buy <amount> btc at <price>\n\
    s <amount> <price>    enter order to sell <amount> btc at <price>\n\
    b <amount> i<index>     enter order to buy <amount> btc, price looked up from orderbook at <index>\n\
    s <amount> i<index>     enter order to sell <amount> btc, price looked up from orderbook at <index>\n\
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
  def getPrompt(S, infoline):
    if (S.orders['btcs'] != 0): 
      ratio = S.orders['usds'] / S.orders['btcs']
    else: ratio = -1
    #return "\n%s | span %.4f | %.2f BTC, %.2f USD | %.2f #> " % (infoline, S.dmz_width, S.orders['btcs'], S.orders['usds'], ratio)
    return "\n%s | %s BTC | %s USD | [h]elp #> " % (infoline, S.orders['btcs'], S.orders['usds'] )

  def prompt(S, infoline='mtgox'):
    S.displaylock.acquire()
    sys.stdout.write(S.getPrompt(infoline))
    sys.stdout.flush()
    S.displaylock.release()

  def cmd(S, cmd):
    global PRICE_PREC
    if (cmd.rfind(';') >= 0):
      for c in cmd.split(';'): S.cmd(c.strip())
    else:
      if cmd[:3] == 'dws': S.debug_ws = not S.debug_ws; print 'debug_ws=', S.debug_ws
      if cmd[:2] == 'ps': pygame.mixer.Sound(cmd[3:]).play()
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
      elif cmd[0] == 'q': S.run = False
      elif cmd[0] == 'h': S.show_help()
      elif cmd[0] == 'b' or cmd[0] == 's': S.trade(cmd)
      elif cmd[0] == 'c': S.cancel_order(cmd); S.show_orders()
      elif cmd[0] == 'a': S.auto_update_depth = not S.auto_update_depth; print 'auto_update_depth = ', S.auto_update_depth
      elif cmd[0] == 'r': S.reload = True;
      elif cmd[0] == 'o': S.request_orders(); S.show_orders()
      elif cmd[0] == 'e': S.show_depth()
      #elif cmd[0] == 't': 
      #  for x in S.ticker: print x
      #  print S.ticker
      elif cmd[0] == 'd': S.display_height = int(cmd[1:])
      elif cmd[0] == 'p': 
        p = int(cmd[1:])
        try:
          if p<2 or p>5: print 'precision must be 2..5'
          else: PRICE_PREC = D(10) ** -p; S.reload = True
        except: print 'exception parsing precision value: %s' % p
          
  def __call__(S): # mainloop
    global PRICE_PREC
    S.run = True
    S.reload = False
    
    # initial for bot, ned so wichtig auf dauer, kost zeit
    # abhilfe: unten bei initialize bots nen fake-trade reinschreiben
    # es geht glaub nur um S.last_trade? oder?
    #S.request_trades()

    if S.debug: print 'request_orders()'
    S.request_orders()
    if S.debug: print 'request_ticker()'
    S.request_ticker()
    S.last_price = S.ticker['ticker']['last']
    if S.debug: print 'request_market()'
    S.request_market();
    S.prompt()
    
    if S.debug: print 'initializing bots...'
    for bot in S.bots:
      bot.initialize()
    if S.debug: print 'ready'
      
    counter = 0
    while (S.run):
        
      #print "  dmz width: %.4f\n" % S.dmz_width
      if S.use_ws:
        while not S.ws.connected:
          if S.debug: print 'connecting websocket...'
          try:
            S.ws.connect();
            if S.debug: print 'websocket connected'
          except:
            print 'connection problem, retrying later...'
            time.sleep(1);
            
      if (S.reload): 
        #S.request_orders()
        S.request_ticker()
        if not S.use_ws: S.request_trades()
        S.show_depth()
        S.request_market()
        # load BTC/USD somewhere in above calls!
        #S.show_orders()
        
      #S.print_stuff();
      S.reload = False;
      key = raw_input(S.getPrompt('mtgox'));
      if (len(key) > 0):
        S.cmd(key)
      else: 
        S.show_depth();
      counter += 1
      if (counter % 31) == 13 and not S.donated:
        print '\n\n\n\n\nplease consider donating to 1Ct1vCN6idU1hKrRcmR96G4NgAgrswPiCn\n\n\n(to remove donation msg, put "donated=1" into configfile, section [main])\n'
        
    if S.use_ws: 
      try:
        S.ws.close()
      except:
        if S.debug: print 'websocket closing failed'

#pygame.init()
t = Traidor()
#t.addBot(BeepBot(t))

#t.addBot(EquilibriumBot(t, D('0.0'), D('0'), D('3.0'), D('0.2'))) # btc add, usd add, fund_multiplier, desired_amount
#t.cmd("tb >= 14.80 ps alarm.wav")
#t.cmd("tb <= 14.40 ps alarm2.wav")
#t.mainloop()
