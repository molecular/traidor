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

from common import *
from decimal import Decimal as D
from threading import *
from time import *
import math as m

__all__ = ["Bot", "BeepBot", "ValueBot", "TriggerBot", "EquilibriumBot"]

class Bot:
  def __init__(S, exchange):
    S.x = exchange
    
  def initialize(S):
    pass
    
  def getName(S):
    return 'generic Bot'

  def stop(S):
    pass
    
  def trade(S, trade):
    print "baseclass function trade() called"
    
  def output(S, str):
    S.x.traidor.prompt(str)

class ThreadedBot(Bot):
  def __init__(S, exchange, interval_s):
    Bot.__init__(S, exchange)
    S.thread_interval = interval_s
    
  def initialize(S):
    S.run = True
    S.thread = Thread(target = S)
    S.thread.start()
    
  def stop(S):
    S.run = False

  def __call__(S):
    while S.run:
      S.act()
      sleep(S.thread_interval)

  def act(S):
    print 'ThreadedBot act() called, implement subclass'
    
  def getName(S):
    return 'ThreadedBot'

class BeepBot(Bot):
  def __init__(S, exchange):
    Bot.__init__(S, exchange)
    S.last_price = S.x.last_price
    S.traidor = S.x.traidor
    
  def initialize(S):
    pass
    
  def getName(S):
    return 'BeepBot'
    
  def trade(S, trade):
    if ( S.x.last_price < S.last_price ):
      S.traidor.cmd('ps click.wav')
    else:
      S.traidor.cmd('ps click.wav')
    S.last_price = S.x.last_price

class ValueBot(ThreadedBot):
  def __init__(S, exchange, interval_s, interval):
    ThreadedBot.__init__(S, exchange, interval_s)
    S.last_price = S.x.last_price
    S.traidor = S.x.traidor
    S.direction = ''
    S.interval = interval
    S.vol = D('0')
    S.hotvol = 0.0
    
  def initialize(S):
    ThreadedBot.initialize(S)
    
  def getName(S):
    return 'ValueBot'
    
  def trade(S, trade):
    if ( S.x.last_price < S.last_price ):
      S.direction = 'down'
    elif ( S.x.last_price > S.last_price ):
      S.direction = 'up'
    else:
      S.direction = "onbalance"
    S.last_price = S.x.last_price

  def act(S):
    S.vol = D('0')
    S.hotvol = 0.0
    for t in S.x.getTrades():
      now = mktime(localtime())
      tm = mktime(localtime(t.time))
      diff = now - tm
      #print diff
      if diff < S.interval:
        #print t.str()
        S.vol += t.amount
        if float(diff) != 0.0: S.hotvol += m.pow(float(t.amount), 1.0/float(diff))
        else: S.hotvol = -0.0
    S.output(S.info())

  def info(S):
    rc = "ValueBot Info:\n"
    rc += "  direction: %s\n" % S.direction
    rc += "trading fee: %s%%\n" % (S.x.getTradeFee() * 100)
    rc += "   interval: %s\n" % (S.interval)
    rc += "     volume: %s\n" % (S.vol)
    rc += " hot volume: %f\n" % (S.hotvol)
    return rc

class TriggerBot(Bot):
  def __init__(S, exchange, trigger):
    Bot.__init__(S, exchange)
    p = trigger.split()
    S.compare = p[0]
    S.price = D(p[1])
    S.cmd = " ".join(p[2:])
    #S.initial_price = exchange.last_price
    
  def trade(S, trade):
    #print "%s: compare: %s, price: %s, cmd: %s" % (S.getName(), S.initial_price, S.trigger_price, trade.price)
    if \
    (S.compare == ">" and trade.price > S.price) or \
    (S.compare == ">=" and trade.price >= S.price) or \
    (S.compare == "<" and trade.price < S.price) or \
    (S.compare == "<=" and trade.price <= S.price):
      print '\nTRIGGER BOT %s TRIGGER %s, executing "%s"\n' % (S.getName(), S.price, S.cmd)
      S.x.cmd(S.cmd, is_bot=True)
      S.x.removeBot(S)

  def getName(S):
    return "TriggerBot(%s %s %s)" % (S.compare, S.price, S.cmd)
    
class EquilibriumBot(ThreadedBot):
  def __init__(S, exchange, fake_btc, fake_usd, funds_multiplier, desired_amount):
    ThreadedBot.__init__(S, exchange, 50) 
    S.fake_btc, S.fake_usd, S.funds_multiplier = fake_btc, fake_usd, funds_multiplier
    S.oid = {'bid': None, 'ask': None}
    S.desired_amount = desired_amount
    S.initial_usd, S.initial_btc = None, None
    
  def initialize(S):
    ThreadedBot.initialize(S)
    # S.x.do_cancel_all_orders()
    # S.do()

  def get_performance(S):
    ex = S.x
    if S.initial_usd == None:
      S.initial_btc = ex.getBTC()
      S.initial_usd = ex.getUSD()
    return (ex.getUSD() + ((ex.getBTC() - S.initial_btc) * ex.last_price)) - S.initial_usd

  def trade(S, trade):
    #S.do()
    print "trade: ", trade.str()

  def act(S):
    S.do()

  def do(S):
    ex = S.x

    # remove all orders I don't know about
    #for o in ex.get_orders():
    #  if o['oid'] not in (S.order['bid'], S.order['ask']):
    
    
    S.oid = {'bid': None, 'ask': None}
    ex.request_orders() # update orders
    ex.request_info() # update balance
    
    # find my orders
    my_highest_bid = D(0);
    my_lowest_ask = D('1E12');
    #print ex.orders
    for o in sorted(ex.orders, key=lambda ord: ord['price']['value_int'], reverse=True):
      #print "{%s}: %s %s" % (o['oid'], o['amount'], o['price'])
      type = o['type']
      price = o['price']['value']
      if type == 'ask' and price <= my_lowest_ask: 
        my_lowest_ask = price
        S.oid[type] = o['oid']
      if type == 'bid' and price >= my_highest_bid: 
        my_highest_bid = price
        S.oid[type] = o['oid']
      print 'order, type %s, price %s' % ( type, price ) 
    print 'my hi/lo: %s/%s' % (my_highest_bid, my_lowest_ask)

    '''# trade detector
    traded = False;
    #S.last_price = S.ticker['ticker']['last']
    print "last_price: %s" % S.last_price
    if S.last_price > S.my_lowest_ask:
      traded = True
    if S.last_price < S.my_highest_bid:
      traded = True
    if traded:
      say("a trade must have happened")
    '''  
    
    # calc some stuff
    P = D(10) ** -8
    (btc, usd) = ( (ex.getBTC() + S.fake_btc) * S.funds_multiplier, (ex.getUSD() + S.fake_usd) * S.funds_multiplier )
    my_ratio = (usd / btc).quantize(P)
    
    def d(x): return dec(x, 5, 5)
      
    new_rate = ex.last_price
    desired_usd = (usd + (new_rate * btc)) / 2
    desired_btc = (btc + (usd / new_rate)) / 2
    delta_usd = desired_usd - usd
    # trade sim
    delta_btc = -delta_usd / new_rate
    print "rate %s:\ncurrent %s BTC | %s USD | ratio %s \ndesire  %s BTC | %s USD -> \ndelta   %s BTC | %s USD" % (d(new_rate), d(btc), d(usd), d(my_ratio), d(desired_btc), d(desired_usd), d(delta_btc), d(delta_usd))

    amount_mult = D('10')
    if False and abs(delta_btc) > S.desired_amount * amount_mult:
      print 'delta_btc (%s) is > %s * desired_amount (%s), refusing to trade bring me to equlibrium first by %s at least %s BTC.' % (delta_btc, amount_mult, S.desired_amount, ('selling' if delta_btc<D('0') else 'buying'), ((abs(delta_btc) - S.desired_amount) / S.funds_multiplier).quantize(D('1.0')))
      ex.removeBot(S)  
    else:
      rate = {}
      amount = {}
      increment = D('0.01')
      max_amount = D('1.0')
      min_distance = D('-0.1')
      last_price = ex.last_price
      print 'last_price: %s' % (last_price)
      
      amount['bid'] = S.desired_amount
      rate['bid'] = last_price + D('1.0')
      while (ex.last_price - rate['bid']) <= min_distance and amount['bid'] <= max_amount:
        rate['bid'] = usd / (btc + 2 * amount['bid'])
        rate['bid'] *= (D('1.0') - D('0.003'))
        amount['bid'] += increment
        #print 'BID: rate %s amount %s' % (rate['bid'], amount['bid'])
        
      amount['ask'] = S.desired_amount
      rate['ask'] = last_price - D('1.0')
      while (rate['ask'] - ex.last_price) <= min_distance and amount['ask'] <= max_amount:
        rate['ask'] = usd / (btc - 2 * amount['ask'])
        rate['ask'] /= (D('1.0') - D('0.003'))
        amount['ask'] += increment
        #print 'ASK: rate %s amount %s  |   rate - last_price: %s, min_distance: %s' % (rate['ask'], amount['ask'], rate['ask'] - ex.last_price, min_distance)

      rate['bid'] = rate['bid'].quantize(BTC_PREC)
      rate['ask'] = rate['ask'].quantize(BTC_PREC)

      print ' to buy %s BTC, I want rate %s' % (amount['bid'], rate['bid'])
      print 'to sell %s BTC, I want rate %s' % (amount['ask'], rate['ask'])
      
      print 'S.oid: ', S.oid
    
      # check orders
      count_exist = 0
      for type in ('bid', 'ask'):
        if S.oid[type] != None or ex.get_order(S.oid[type]) != None: count_exist += 1

      print 'count_exist: ', count_exist
      if count_exist != 2:
        ex.cmd('ps alarm.wav')
        ex.do_cancel_all_orders()

      for type in ('bid', 'ask'):
        if S.oid[type] == None or ex.get_order(S.oid[type]) == None:
          #if \
          #(type == 'bid' and rate[type] < ex.last_price) or \
          #(type == 'ask' and rate[type] > ex.last_price):
          print 'PLACING new order: %s %s %s' % (type, amount[type], rate[type])
          S.oid[type] = ex.do_trade(type, amount[type], rate[type])
        
      # check price, if wrong, change order
      for type in ('bid', 'ask'):
        o = ex.get_order(S.oid[type])
        if o != None and abs(o['price']['value'] - rate[type]) > D('0.0001'):
          ex.cmd('ps alarm2.wav')
          print 'CANCELLING order {%s}' % S.oid[type]
          ex.do_cancel_order(S.oid[type])
          print 'PLACING new order: %s %s %s' % (type, amount[type], rate[type])
          S.oid[type] = ex.do_trade(type, amount[type], rate[type])
      

    #print 'performance: %s' % S.get_performance()


    '''    # daloop
    for kind in ('bids', 'asks'):
      orders = sorted(S.orders['orders'], key=lambda ord: ord['price'], reverse = (kind=='bids'))
      print orders
      depth = sorted(S.depth[kind].keys(), reverse = (kind=='bids'))
      i = 0
      print len(depth)
      
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
    '''    

  def getName(S):
    return "EquilibriumBot(performance: %s)" % (S.get_performance().quantize(D('0.001')))
