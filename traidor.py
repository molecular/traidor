#!/usr/bin/python
          
# maybe alternative for /code/getTrades.php before websocket is back
# http://bitcoincharts.com/t/trades.csv?symbol=mtgoxUSD&start=$UNIXTIME
# http://www.google.com/fusiontables/DataSource?dsrcid=1058017

import simplejson as json
import urllib, urllib2 #, httplib2
import sys, os
import curses
import time
import subprocess
from threading import *
from ConfigParser import SafeConfigParser
from pywsc.websocket import WebSocket
from decimal import Decimal as D
import pygame

from bot import *

BTC_PREC = D('0.00000001')
USD_PREC = D('0.0001')
PRICE_PREC = D('0.00001')
VOL_PREC = D('0.1')
VOL2_PREC = D('0')
MYVOL_PREC = D('0.01')

def convert_certain_json_objects_to_decimal(dct):
  for k in ('amount', 'price', 'btcs', 'usds'):
    if k in dct: dct[k] = D(dct[k])
  for k in ('asks', 'bids'):
    if k in dct: 
      for idx in range(len(dct[k])):
        for i in (0,1): 
          dct[k][idx][i] = D(dct[k][idx][i]) 
  return dct

# align D number at decimal point
def dec(dec, before, after):
  rc = ''
  if dec.as_tuple().exponent >= 0:
    rc = "%i.0" % int(dec)
    rc = "%*s" % (before+1-len(rc), rc)
  else:
    rc = str(dec.normalize())
  #print dec, rc
  if rc.find('.') >= 0:
    rc = "%*s" % (before-rc.find('.')+len(rc), rc)
  rc += '                          '[:(after+before+1)-len(rc)]
  rc = rc[:(before+after+1)]
  return rc # rc.replace('0.', 'o.').replace('.0', '.o')

# talking
def say(text):
  print text
  #festival = subprocess.os.popen2("echo '(SayText \"" + text.replace("'", "") + "\")' | /usr/bin/festival --pipe")


class Trade:
  def __init__(S, time, amount, price, type):
    (S.time, S.amount, S.price, S.type) = (time, D(amount), D(price), type)
    
  def str(S):
    "{%s} | %s for %s - %i %s" % (S['oid'], o['amount'], o['price'], o['status'], o['real_status'])

class Traidor:
  def __init__(S):
    S.datalock = Lock()
    S.order_distance = D('0.0001')
    S.auto_update_depth = False
    S.auto_update_trade = True
#    S.connection = httplib2.HTTPSConnectionWithTimeout("mtgox.com:443", strict=False, timeout=10)
    S.display_height=20
    S.orders = {'btcs': -1, 'usds': -1}
    S.trades = []

    # parse configfile
    parser = SafeConfigParser()
    parser.read('traidor.conf')
    S.mtgox_account_name = parser.get('mtgox', 'account_name')
    S.mtgox_account_pass = parser.get('mtgox', 'account_pass')
    S.donated = parser.getboolean('main', 'donated')
    S.use_ws = parser.getboolean('main', 'use_websockets')
    S.debug_ws = parser.getboolean('main', 'debug_websockets')
    S.bots = list()

    t = Thread(target = S)
    t.start()

    if S.use_ws:
      S.ws = WebSocket('ws://websocket.mtgox.com:80/mtgox')
      S.ws.setEventHandlers(S.onOpen, S.onMessage, S.onClose)  

  # --- bot handling ---------------------------------------------------------------------------------------------------------
  
  def addBot(S, bot):
    S.bots.append(bot)

  def removeBot(S, bot):
    S.bots.remove(bot)

  # --- websocket callbacks --------------------------------------------------------------------------------------------------
  
  def onOpen(S):
    if S.debug_ws: print "websocket open"
      
  def onMessage(S, message):
    S.datalock.acquire()
    #print "-onMessage:", message
    update = False
    m = json.loads(message, use_decimal=True)
    if S.debug_ws: print m #json.dumps(m, sort_keys=True, indent=2)
    channel = m['channel']
    op = m['op']
    #print 'message in channel ', channel, ' op: ', op
    
#    if channel == 'd5f06780-30a8-4a48-a2f8-7ed181b4a13f': # ticker
#      S.prompt('tick')

    # trades
    if op == 'private' and channel == 'dbf1dee9-4f2e-4a08-8cb7-748919a71b21': 
      trade = m['trade']
      if (trade['type'] != 'trade'): print m
      #s = '%s: [trade %s]: %5.1f for %.4f' % (trade['date'], trade['tid'], float(trade['amount']), float(trade['price']))
      depth_type = None
      type = 'unknown'
      #if S.depth.has_key('bids'):
      #  #print '\nchecking for key: %.04f' % float(trade['price'])
      #  if S.depth['bids'].has_key("%.04f" % float(trade['price'])):
      #    type = 'sell' 
      #    depth_type = 'bids'
      #  if S.depth['asks'].has_key("%.04f" % float(trade['price'])): 
      #    type = 'buy' 
      #    depth_type = 'asks'
      #else: 
      #  type = 'no depth data'
      
      #S.trades.append([trade['date'], trade['tid'], trade['amount'], trade['price'], type])
      trade = Trade(trade['date'], trade['amount'], trade['price'], trade['trade_type'])
      S.trades.append(trade)
      update = S.auto_update_trade
      
      for bot in S.bots:
        bot.trade(trade)

      S.last_price = trade.price
      S.trade_happened()


      # adjust depth data
      #if depth_type != None:
      #  S.depth[depth_type]["%.04f" % float(trade['price'])] -= trade['amount']
        
      
      #S.prompt(s)

    # depth: {u'volume': 7.7060600456200001, u'price': 6.4884000000000004, u'type': 1}
    if op == 'private' and channel == '24e67e0d-1cad-4cc0-9e7a-f8523ef460fe': 
      print m
      depth_msg = m['depth']
      if S.auto_update_depth: print depth_msg
      if depth_msg['type'] == 2: type = 'bids'
      if depth_msg['type'] == 1: type = 'asks'
      if depth_msg['type'] == 1: othertype = 'bids'
      if depth_msg['type'] == 2: othertype = 'asks'
      price = float("%.04f" % float(depth_msg['price']))
      volume = float(depth_msg['volume']);
      if S.auto_update_depth: print '\nDEPTH EVENT: type %s: key %s, volume %f' % (type, price, volume)
      if not S.depth[type].has_key(price): 
        if S.auto_update_depth: print 'DEPTH MANAGMENT: type %s: added key %s, volume %f' % (type, price, volume)
        S.depth[type][price] = float(0)
      #if S.depth[othertype].has_key(price):
        #print 'DEPTH MANAGMENT: OTHERTYPE (%s) has_key(%s), trying to fix' % (othertype, price)
        # #if not S.depth[type].has_key(price): S.depth[type][price] = float(0)
        # #S.depth[type][price] += S.depth[type].pop(price)
        #type = othertype
      if S.auto_update_depth: print 'DEPTH MANAGMENT: type %s: %f -> %f' % (othertype, S.depth[type][price], S.depth[type][price] + volume)
      S.depth[type][price] += volume
      if S.depth[type][price] < 1E-4: 
        S.depth[type].pop(price)
        if S.auto_update_depth: print 'DEPTH MANAGMENT: type %s: removed key %s' % (type, price)
      S.dmz_width = sorted(S.depth['asks'])[0] - sorted(S.depth['bids'], reverse=True)[0]
      update = S.auto_update_depth
      #for x in sorted(S.depth[type]):
      #  print x, S.depth[type][x]

    S.datalock.release()
    if update:
      #S.request_stuff()
      S.show_depth()
      S.prompt('mtgox')
        
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
    S.datalock.release()
      
  def request_orders(S):
    S.datalock.acquire()
    S.orders = S.request_json_authed('/code/getOrders.php')
    S.datalock.release()

  def request_ticker(S):
    ticker = S.request_json_authed('/code/data/ticker.php')

  def request_trades(S):
    S.datalock.acquire()
    S.trades2 = S.request_json('/code/data/getTrades.php')
    S.trades = list()
    for trade in S.trades2[-200:]:
      S.trades.append(Trade(trade['date'], trade['amount'], trade['price'], '?'))
    S.last_price = S.trades[-1].price
    S.datalock.release()
    
  def request_stuff(S):
    #S.balance = S.request_json_authed('/code/getFunds.php')
    #print S.balance;
    #print 'orders';
    S.request_orders()
    #print 'ticker';
    S.request_ticker()
    #print 'trades2';
    if not S.use_ws: S.request_trades()
    #print 'market';
    #print S.trades2;
    S.request_market();
    #print 'request_stuff() done'


  def show_orders(S):
    S.datalock.acquire()
    #print S.orders
    print "\n"
    i = 0
    print "[IDX] {                id                  } | typ    volume   price    - status"
    print "                                             |"
    type = -1
    for o in sorted(S.orders['orders'], key=lambda ord: ord['price'], reverse=True):
      #print "{%s}: %s %s" % (o['oid'], o['amount'], o['price'])
      if abs(S.trades[-1].price - o['price']) < D('4'):
        if o['type'] == 2 and type == 'ask': print "                                             |"
        type = o['type']
        if type==1: type = 'ask'
        elif type==2: type = 'bid'
        else: type = 'unknown'
        print "[%3i] {%s} | %s %s %s - %i %s" % (i, o['oid'], type, dec(o['amount'], 4, 5), dec(o['price'], 3, 5), o['status'], o['real_status'])
      i += 1
    S.datalock.release()

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
        #i = len(S.depth[kind]) - 1
        #print 'i: ', i, ', s_i: ', s_i
        for price in sorted(S.depth[kind].keys())[:S.display_height]:
          #i -= 1
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
    #if i<0: i=0
    #print 'display_height: ', S.display_height, ', i:', i
    #if i > len(s): i = len(s)
    for t in S.trades[-S.display_height:]:
      #print i
      # str = "|  %s %9s for %s" % (time.strftime('%H:%M:%S',tm), t['amount'].quantize(VOL_PREC), t['price'].quantize(USD_PREC))
      tm = time.localtime(t.time)
      str = "|  %s %9s for %s %s" % (time.strftime('%H:%M:%S',tm), dec(t.amount, 4, 2), dec(t.price, 3, 5), t.type)
      s[i] += str
      i += 1

    # trades2 (trade API trades)
    #i = 0 #len(s)
    #for t in S.trades2[-S.display_height:]:
    #  tm = time.localtime(t['date'])
    #  #str = "| %s: %5.4f for %.4f" % (time.strftime('%H:%M:%S',tm), float(t['amount']), float(t['price']))
    #  str = "|  %s %9s for %s" % (time.strftime('%H:%M:%S',tm), t['amount'].quantize(VOL_PREC), t['price'].quantize(USD_PREC))
    #  s[i] += str
    #  i += 1
    
    S.datalock.release()

    print '\n       ------ BUYING BITCOIN ------ | ------- SELLING BITCOIN ------ | ----------- TRADES ------------'
    print '                                                                     |'
    print '[IDX]   YOU   bid        vol   accumulated      vol   ask       YOU  |  time        amount       price'
    print '                                                                     |'
    for str in s[-S.display_height:]:
      print str
        
  # --- actions -------------------------------------------------------------------------------------------------------

  def trade(S, key):
    p = key.split(' ')
    #print p
    type = 'unknown'
    if p[0][0] == 'b': type = 'buy'; m = 'bids'; air = S.order_distance
    if p[0][0] == 's': type = 'sell'; m = 'asks'; air = -S.order_distance
    vol = p[1]
    price_str = ''
    if len(p) >= 3: price_str = p[2]
    price = -1.0
    #print 'price_str ', price_str
    if price_str.find('.') >= 0:
      price = float(price_str)
    else:
      if price_str == '': index = 0
      else: index = int(price_str)
      if m == 'bids': index = -index - 1
      #print 'index: ', index, ' market: ', S.market[m][index]
      price = sorted(S.depth[m].keys())[index] + air
      #price = S.depth[m][market_index] + air
      #print 'market_index: ', market_index
      #price = S.market[m][index][0] + air
      
    # price = "%.4f" % price
    S.do_trade(type, vol, price)
    
  def do_trade(S, type, vol, price):
    key = raw_input("\n%s %s BTC for %s USD [y]es [n]o #> " % (type, vol, price))
    if key[0] == 'y':
      print 'TRADING'
      S.request_json_authed('/code/' + type + 'BTC.php', params = {'amount': vol, 'price': price})
      S.request_orders()
      S.show_orders()
    else:
      print 'ABORTED'
    
  def cancel_order(S, key):
    p = key.split(' ')
    print p
    for idx in p[1:]:
      index = int(idx)
      o = sorted(S.orders['orders'], key=lambda ord: ord['price'], reverse=True)[index]
      #key = raw_input("\ncancel order oid={%s} [y]es [n]o #> " % (o['oid']))
      key = raw_input("\ncancel order {%s} | %s for %s ? [y]es [n]o #>  " % (o['oid'], o['amount'], o['price']))
      if key[0] == 'y':
        print 'CANCELLING order: ', o
        S.request_json_authed('/code/cancelOrder.php', {'oid': o['oid'], 'type': o['type']})

  # --- preliminary bot stuff (highly experimental, will be abstracted) -------------------------------

  def bot_test(S):
    S.trade_happened()

  # bot callback
  def trade_happened(S):
    #print 'trade_happened()'
    #S.last_price = S.trades[-1].price
    
    return
    
    # find my trades
    S.my_highest_bid = D(0);
    S.my_lowest_ask = D('1E12');
    for o in sorted(S.orders['orders'], key=lambda ord: ord['price'], reverse=True):
      #print "{%s}: %s %s" % (o['oid'], o['amount'], o['price'])
      type = o['type']
      if type==1: type = 'ask'
      elif type==2: type = 'bid'
      if type == 'ask' and o['price'] <= S.my_lowest_ask: S.my_lowest_ask = o['price']
      if type == 'bid' and o['price'] >= S.my_highest_bid: S.my_highest_bid = o['price']
    print 'my hi/lo: %.4f/%.4f' % (S.my_highest_bid, S.my_lowest_ask)

#    S.ticker = S.request_json_authed('/code/data/ticker.php')

    # trade detector
    traded = False;
    #S.last_price = S.ticker['ticker']['last']
    print "last_price: %s" % S.last_price
    if S.last_price > S.my_lowest_ask:
      traded = True
    if S.last_price < S.my_highest_bid:
      traded = True
    if traded:
      say("a trade must have happened")
      
    # calc some stuff
    P = D(10) ** -8
    (usd, btc) = (S.orders['usds'], S.orders['btcs'])
    my_ratio = (usd / btc).quantize(P)
    min_amount = D('0.5')
    #min_amount_usd = D('5')
    min_distance = D('0.1')
    
    return;
    
    # daloop
    for kind in ('bids', 'asks'):
      orders = sorted(S.orders['orders'], key=lambda ord: ord['price'], reverse = (kind=='bids'))
      print orders
      depth = sorted(S.depth[kind].keys(), reverse = (kind=='bids'))
      i = 0
      print len(depth)
      
      def d(x): return dec(x, 5, 5)
      old_rate = new_rate = S.last_price #.quantize(D('0.1'))
      goon = True
      while goon:
        desired_usd = (usd + (new_rate * btc)) / 2
        delta_usd = desired_usd - usd
        # trade sim
        delta_btc = -delta_usd / new_rate
        do_trade = False
        
        #if delta_btc > min_amount and delta_usd < -min_amount:
        #print '%s' % d(old_rate / new_rate)
        if kind == 'bids': rate_change = ((old_rate / new_rate) - D('1.0'))
        if kind == 'asks': rate_change = ((new_rate / old_rate) - D('1.0'))
        if rate_change > D('0.01') and abs(delta_btc) > min_amount:
          do_trade = True
        if do_trade:
          usd += delta_usd
          btc += delta_btc
          old_rate = new_rate
          print "rate %s (+%s%%):  %s BTC | %s USD | ratio %s | desire %s USD -> delta %s USD | %s BTC | trading: %s" % (d(new_rate), dec(rate_change*D('100'), 5, 2), d(btc), d(usd), d(my_ratio), d(desired_usd), d(delta_usd), d(delta_btc), do_trade)
          
        if i < len(depth): # more depth data to look at?
          next_price = depth[i]
          new_rate = next_price #  + D('0.00001');
          i += 1
        else:
          if kind == 'bids':
            new_rate *= D('0.09');
            new_rate -= D('0.05');
          if kind == 'asks':
            new_rate *= D('1.1');
            new_rate += D('0.05');
          
        if new_rate <= D('1E-5'): goon = False
        if new_rate >= D('1E5'): goon = False
    


  def show_help(S):
    print "\n\
    h                     this help\n\
    <ret>                 show public order book, recent trades and your order book\n\
    r                     S.reload - S.reload public order book and trades\n\
    b <amount> <price>    enter order to buy <amount> btc at <price>\n\
    s <amount> <price>    enter order to sell <amount> btc at <price>\n\
    o                     view your order book\n\
    d <index>             delete order at <index> from orderbook\n\
    d <lines>             set height of depth display\n\
    ws                    toggle websockets updates\n\
    dws                   toggle websocket debugging output\n\
    p <1..5>              set display precision\n\
    q                     quit\n\
"
  def getPrompt(S, infoline):
    if (S.orders['btcs'] != 0): 
      ratio = S.orders['usds'] / S.orders['btcs']
    else: ratio = -1
    #return "\n%s | span %.4f | %.2f BTC, %.2f USD | %.2f #> " % (infoline, S.dmz_width, S.orders['btcs'], S.orders['usds'], ratio)
    return "\n%s | %s BTC | %s USD | [h]elp #> " % (infoline, S.orders['btcs'], S.orders['usds'] )

  def prompt(S, infoline):
    sys.stdout.write(S.getPrompt(infoline))
    sys.stdout.flush()

  def __call__(S): # mainloop
    global PRICE_PREC
    S.run = S.reload = True;
    
    # initial for bot, ned so wichtig auf dauer, kost zeit
    S.request_trades()
    
    counter = 0
    while (S.run):
      if (S.reload): 
        S.request_stuff()
        S.show_depth()
      #print "  dmz width: %.4f\n" % S.dmz_width
      if S.use_ws:
        while not S.ws.connected:
          try:
            S.ws.connect();
            if debug_ws: say("websocket connected")    
          except:
            print 'connection problem, retrying later...'
            time.sleep(1);
        
      #S.print_stuff();
      S.reload = False;
      key = raw_input(S.getPrompt('mtgox'));
      if (len(key) > 0):
        S.cmd(key)
      else: S.show_depth();
      counter += 1
      if (counter % 31) == 13 and not S.donated:
        print '\n\n\n\n\nplease consider donating to 1Ct1vCN6idU1hKrRcmR96G4NgAgrswPiCn\n\n\n(to remove donation msg, put "donated=1" into configfile, section [main])\n'
    if S.use_ws: S.ws.close()

  def cmd(S, cmd):
    if (cmd.rfind(';') >= 0):
      for c in cmd.split(';'): S.cmd(c.strip())
    else:
      if cmd[:3] == 'dws': S.debug_ws = not S.debug_ws; print 'debug_ws=', S.debug_ws
      if cmd[:2] == 'ps': pygame.mixer.Sound(cmd[3:]).play()
      elif cmd[:3] == 'ws': S.use_ws = not S.use_ws; print 'use_ws=', S.use_ws
      elif cmd[:2] == 'lb': 
        i=0
        for bot in S.bots: print "[%2i]: %s" % (i, bot.getName())
      elif cmd[:2] == 'tb': # BriggerBot
        S.addBot(TriggerBot(t, cmd[2:]))
      elif cmd[0] == 'q': S.run = False
      elif cmd[0] == 'h': S.show_help()
      elif cmd[0] == 'b' or cmd[0] == 's': S.trade(cmd)
      elif cmd[0] == 'c': S.cancel_order(cmd); S.request_orders(); S.show_orders()
      elif cmd[0] == 'a': S.auto_update_depth = not S.auto_update_depth
      elif cmd[0] == 'r': S.reload = True;
      elif cmd[0] == 'o': S.show_orders()
      elif cmd[0] == 'e': S.show_depth()
      #elif cmd[0] == 't': 
      #  for x in S.ticker: print x
      #  print S.ticker
      elif cmd[0] == 'd': S.display_height = int(cmd[1:])
      elif cmd[0] == 'x': S.bot_test()
      elif cmd[0] == 'p': 
        p = int(cmd[1:])
        try:
          if p<2 or p>5: print 'precision must be 2..5'
          else: PRICE_PREC = D(10) ** -p; S.reload = True
        except: print 'exception parsing precision value: %s' % p

pygame.init()
t = Traidor()
t.addBot(BeepBot(t))
t.addBot(EquilibriumBot(t))
t.cmd("tb >= 14.60 ps alarm.wav")
t.cmd("tb <= 14.40 ps alarm2.wav")
#t.mainloop()
