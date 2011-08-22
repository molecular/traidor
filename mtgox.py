from exchange import *
from common import *
from threading import *
from websocket import WebSocket
import sys, os
import time
import subprocess
import simplejson as json
import urllib, urllib2 #, httplib2

__all__ = ["MtGox"]

def convert_certain_json_objects_to_decimal(dct):
  for k in ('amount', 'price', 'btcs', 'usds', 'volume'):
    if k in dct: dct[k] = D(dct[k])
  for k in ('asks', 'bids'):
    if k in dct: 
      for idx in range(len(dct[k])):
        for i in (0,1): 
          dct[k][idx][i] = D(dct[k][idx][i]) 
  return dct

class MtGox (Exchange):
  def __init__(S, traidor, config):
    Exchange.__init__(S, traidor, config, 'mtgox')
    
    S.datalock = Lock()
    
    S.mtgox_account_name = config.get('mtgox', 'account_name')
    S.mtgox_account_pass = config.get('mtgox', 'account_pass')
    S.trading_fee = D(config.get('mtgox','trading_fee'))
    S.eval_base_btc = D(config.get('monetary','evaluation_base_btc'))
    S.eval_base_usd = D(config.get('monetary','evaluation_base_usd'))
    
    S.use_ws = config.getboolean('mtgox', 'use_websockets')
    S.debug_ws = config.getboolean('mtgox', 'debug_websockets')
    S.debug_request_timing = config.getboolean('mtgox', 'debug_request_timing')
    S.depth_invalid_counter = 0
    S.last_price = D('0.0')
    S.order_distance = D('0.00001')
#    S.connection = httplib2.HTTPSConnectionWithTimeout("mtgox.com:443", strict=False, timeout=10)
    S.orders = {'btcs': -1, 'usds': -1}
    S.trades = []
    
    t_show_depth = Thread(target = S.show_depth_run)
    t_show_depth.start()

  def start(S):
    #if S.debug: print 'request_info()'
    #S.request_info()
    if S.debug: print 'request_orders()'
    S.orders = S.request_orders() # DATALOCK?
    #if S.debug: print 'request_ticker()'
    #S.request_ticker()
    #S.last_price = S.ticker['ticker']['last']
    if S.debug: print 'request_market()'
    S.request_market();
#    S.prompt()
    
    # start request_thread() thread
    t_request = Thread(target = S.request_thread)
    t_request.setDaemon(True)
    t_request.start()

    # start websocket_thread
    if S.use_ws:
      S.t_websocket = Thread(target = S.websocket_thread)
      S.t_websocket.setDaemon(True)
      S.t_websocket.start()

  def stop(S):
    Exchange.stop(S)
    S.t_websocket.join(timeout=1)

  def websocket_thread(S):
    if S.use_ws:
      print 'websocket_thread() started'
      while S.run:
        print 'connecting websocket'
        try:
          S.ws = WebSocket('ws://websocket.mtgox.com/mtgox', version=6)
          msg = S.ws.recv()
          while msg is not None and S.run:
              S.onMessage(msg)
              msg = S.ws.recv()
        except:
          print 'exception connecting websocket: ', sys.exc_info()[0], " will retry..."
          time.sleep(3)
          
      print 'websocket_thread() exit'

  # --- bot support ----------------------------------------------------------------------------------------------------------
  
  def getBTC(S): 
    return S.orders['btcs']
    #return D(S.info['Wallets']['BTC']['Balance']['value'])
    
  def getUSD(S): 
    return S.orders['usds']
    #return D(S.info['Wallets']['USD']['Balance']['value'])

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

  def eval(S, base):
    delta = S.getBTC() - base
    corrected_usd = S.getUSD() + (S.last_price * delta * (D('1.0') - S.trading_fee))
    return corrected_usd
    
  # --- websocket callbacks --------------------------------------------------------------------------------------------------
  
  def onOpen(S):
    if S.debug_ws: print "websocket open"
      
  def onMessage(S, message):
    #try:
    #print "-onMessage:", message
    update = False
    m = json.loads(message, use_decimal=True)
    if S.debug_ws: 
      sys.stderr.write(str(m)) 
      sys.stderr.flush() #json.dumps(m, sort_keys=True, indent=2)
    channel = m['channel']
    op = m['op']
    #print 'message in channel ', channel, ' op: ', op
    
#    if channel == 'd5f06780-30a8-4a48-a2f8-7ed181b4a13f': # ticker
#      print m

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
      update = False
      S.last_depth_update = time.time()
      S.depth_invalid_counter += 1
      #update = S.auto_update_depth
      
      # bots 
      S.datalock.release()
      #S.orders = S.request_orders() # hmmmgrl, really? 
      S.last_price = trade.price
      for bot in S.traidor.bots:
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

        S.traidor.cmd('ps gligg.wav')
        time.sleep(0.05)
        
    S.datalock.release()
    
    if update:
      S.show_depth()
      S.traidor.prompt()
        
  def onClose(S):
    print "websocket closed"

  # --- api stuff --------------------------------------------------------------------------------------------------------
  
  def request_json(S, url, params={}):
    data = urllib.urlencode(params)
    req = urllib2.Request("https://mtgox.com:443" + url, data)
    success = False
    while not success:
      try:
        response = urllib2.urlopen(req)
        success = True
      except:
        print 'exception requesting "', url, '": ', sys.exc_info()[0]
        print 'retrying soon...'
        time.sleep(3)
    return json.load(response, use_decimal=True, object_hook=convert_certain_json_objects_to_decimal)
  
  def request_json_authed(S, url, params={}):
    start_time = time.time()
    params['name'] = S.mtgox_account_name
    params['pass'] = S.mtgox_account_pass
    rc = S.request_json(url, params);
    #json.load(S.request_json(url, params), use_decimal=True, object_hook=convert_certain_json_objects_to_decimal)
    duration = time.time() - start_time
    if S.debug_request_timing:
      debug_print('requesting https://mtgox.com:443%s took %s seconds' % (url, duration))
    return rc

  def request_market(S):
    global PRICE_PREC
    S.market = S.request_json('/api/0/data/getDepth.php')
    
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
    return S.request_json_authed('/api/0/getOrders.php')

  def request_info(S):
    S.info = S.request_json_authed('/api/0/info.php')
    #print 'S.info: ', S.info

  def request_ticker(S):
    S.ticker = S.request_json_authed('/api/0/data/ticker.php')

  def request_trades(S):
    S.datalock.acquire()
    S.trades2 = S.request_json('/api/0/data/getTrades.php')
    S.trades = list()
    for trade in S.trades2[-200:]:
      S.trades.append(Trade(trade['date'], trade['amount'], trade['price'], '?'))
    S.last_price = S.trades[-1].price
    S.datalock.release()
    
  # --- show_* ----------------------------------------------------------------------------------------

  def show_orders(S):
    S.datalock.acquire()
    S.traidor.displaylock.acquire()
    print "\n"
    i = 0
    print "[IDX] {                id                  } | typ    volume   price    - status"
    print "                                             |"
    type = -1
    for o in sorted(S.orders['orders'], key=lambda ord: ord['price'], reverse=True):
      #print "{%s}: %s %s" % (o['oid'], o['amount'], o['price'])
      if o['type'] == 2 and type == 'ask' and len(S.orders['orders']) > 2: print "                                             |"
      #print o
      type = o['type']
      if type==1: type = 'ask'
      elif type==2: type = 'bid'
      else: type = 'unknown'
      print "[%3i] {%s} | %s %s %s - %i %s" % (i, o['oid'], type, dec(o['amount'], 4, 5), dec(o['price'], 3, 5), o['status'], o['real_status'])
      i += 1
    S.traidor.displaylock.release()
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
    info_counter = 0
    S.last_depth_update = time.time()
    while S.run:
      time.sleep(0.17)
      age = time.time() - S.last_depth_update
      if S.traidor.auto_update_depth:
        # once enough time passed since last depth update msg (burst ceased) or a lot of update messages queued up, call show_depth()
        if (age >= 0.71 and S.depth_invalid_counter > 0) or S.depth_invalid_counter > 21:  
          #print 'show_depth_run(): calling show_depth()'
          S.show_depth()
          #S.orders = S.request_orders() DATALOCK
          info_counter += 1
          #if info_counter % 10 == 0: 
          #  S.request_info()
          #S.request_orders()
          S.should_request = True
          S.traidor.prompt()    
    print 'show_depth()-thread exit'
    
  # display depth data
  def show_depth(S):
    S.traidor.displaylock.acquire()
    S.datalock.acquire()
    s = []
    my_orders = S.orders['orders']
    for kind in ('bids', 'asks'):
      akku = D(0);
        
      # bids
      if (kind=='bids'):
        for price in sorted(S.depth[kind].keys(), reverse = (kind=='asks'))[-S.traidor.display_height:]:
          akku += S.depth[kind][price]
        i = S.traidor.display_height # len(S.depth[kind]);
        for price in sorted(S.depth[kind].keys(), reverse = False)[-S.traidor.display_height:]:
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
        for price in sorted(S.depth[kind].keys())[:S.traidor.display_height]:
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
    while i < S.traidor.display_height - len(S.trades) and i < len(s):
      s[i] += '|'
      i += 1
    for t in S.trades[-S.traidor.display_height:]:
      tm = time.localtime(t.time)
      str = "|  %s %s for %s %s" % (time.strftime('%H:%M:%S',tm), dec(t.amount, 4, 5), dec(t.price, 3, 5), t.type)
      try: s[i] += str 
      except: pass
      i += 1

    S.depth_invalid_counter = 0

    S.datalock.release()
    
    print '\n\n       ------ BUYING BITCOIN ------ | ------- SELLING BITCOIN ------ | ----------- TRADES ------------'
    print '                                                                     |'
    print '[IDX]   YOU   bid        vol   accumulated      vol   ask       YOU  |  time        amount       price'
    print '                                                                     |'
    for str in s[-S.traidor.display_height:]:
      print str
      
    S.traidor.displaylock.release()
        
  # --- actions -------------------------------------------------------------------------------------------------------

  def trade(S, key, is_bot=False):
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
    if not is_bot:
      k = raw_input("\n%s %s BTC for %s USD [y]es [n]o #> " % (type, vol, price))
    else:
      k = 'y'
    if k[0] == 'y':
      result = S.do_trade(type, vol, price)
      S.show_orders()
      return result
    else:
      print 'ABORTED'
      return None
          
  def cancel_order(S, key, is_bot):
    p = key.split(' ')
    print p
    
    # collect list of oids
    S.datalock.acquire()
    to_cancel = list()
    for idx in p[1:]:
      index = int(idx)
      to_cancel.append(sorted(S.orders['orders'], key=lambda ord: ord['price'], reverse=True)[index])

    S.traidor.displaylock.acquire()
    all_yes = is_bot
    for o in to_cancel:
      #o = sorted(S.orders['orders'], key=lambda ord: ord['price'], reverse=True)[index]
      #key = raw_input("\ncancel order oid={%s} [y]es [n]o #> " % (o['oid']))
      if not all_yes:
        type = o['type']
        if type==1: type = 'sell'
        elif type==2: type = 'buy'
        key = raw_input("\ncancel order {%s} | %s %s for %s ? [y]es [n]o [a]ll [c]ancel #>  " % (o['oid'], type, o['amount'], o['price']))
        if key[0] == 'a': all_yes = True
        elif key[0] == 'c': pass
      if all_yes or key[0] == 'y': S.do_cancel_order(o['oid'])
        
    S.traidor.displaylock.release()
    S.datalock.release()
    
  def request_thread(S):
    print 'request_thread() started'
    S.should_request = False
    while S.run:
      time.sleep(0.17)
      if S.should_request:
        timeout_secs = 15
        rc = timeout(S.request_orders, timeout_duration=timeout_secs)
        if rc != None:
          S.should_request = False
          S.datalock.acquire()
          S.orders = rc
          S.datalock.release()
        else:
          debug_print('request_orders() timeout (%ss)' % timeout_secs)
          
    print 'request_thread() exit'

  def reload_depth(S):
    #S.request_ticker()
    if not S.use_ws: S.request_trades()
    S.request_market() 
    # trigger show_depth() thread
    S.last_depth_update = time.time()
    S.depth_invalid_counter += 1

  def cmd(S, cmd, is_bot=False):
    if (cmd.rfind(';') >= 0):
      for c in cmd.split(';'): S.cmd(c.strip())
    else:
      if cmd[:3] == 'dws': S.debug_ws = not S.debug_ws; print 'debug_ws=', S.debug_ws
      elif cmd[:3] == 'ws': S.use_ws = not S.use_ws; print 'use_ws=', S.use_ws
      elif cmd[0] == 'b' or cmd[0] == 's': 
        S.traidor.auto_update_depth = False
        S.trade(cmd, is_bot)
      elif cmd[0] == 'c': 
        S.traidor.auto_update_depth = False
        S.cancel_order(cmd, is_bot); 
        S.show_orders()
      elif cmd[0] == 'o': 
        S.traidor.auto_update_depth = False
        rc = S.request_orders(); 
        S.datalock.acquire()
        S.orders = rc
        S.datalock.release()
        S.show_orders()
      elif cmd[0] == 'e': S.show_depth()
      elif cmd[0] == 'r': S.reload_depth();
      #elif cmd[0] == 't': 
      #  for x in S.ticker: print x
      #  print S.ticker

    