#from traidor import Traidor
#import pygame
from common import *
from decimal import Decimal as D

__all__ = ["Bot", "BeepBot", "TriggerBot", "EquilibriumBot"]

class Bot:
  def __init__(S, exchange):
    S.x = exchange
    
  def getName(S):
    return 'generic Bot'
    
  def trade(S, trade):
    print "baseclass function trade() called"

class BeepBot(Bot):
  def __init__(S, exchange):
    Bot.__init__(S, exchange)
    
  def initialize(S):
    pass
    
  def getName(S):
    return 'BeepBot'
    
  def trade(S, trade):
    S.x.cmd('ps click.wav')
    pass
    
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
      print '\nTRIGGER BOT %s TRIGGER %s\n' % (S.getName(), S.price)
      S.x.cmd(S.cmd)
      S.x.removeBot(S)

  def getName(S):
    return "TriggerBot(%s %s %s)" % (S.compare, S.price, S.cmd)
    
class EquilibriumBot(Bot):
  def __init__(S, exchange, fake_btc, fake_usd, funds_multiplier, desired_amount):
    Bot.__init__(S, exchange)
    S.fake_btc, S.fake_usd, S.funds_multiplier = fake_btc, fake_usd, funds_multiplier
    S.oid = {'buy': None, 'sell': None}
    S.desired_amount = desired_amount
    S.initial_usd, S.initial_btc = None, None
    
  def initialize(S):
    S.x.do_cancel_all_orders()
    S.do()

  def get_performance(S):
    ex = S.x
    if S.initial_usd == None:
      S.initial_btc = ex.getBTC()
      S.initial_usd = ex.getUSD()
    return (ex.getUSD() + ((ex.getBTC() - S.initial_btc) * ex.last_price)) - S.initial_usd

  def trade(S, trade):
    S.do()
  
  def do(S):
    ex = S.x

    # remove all orders I don't know about
    #for o in ex.get_orders():
    #  if o['oid'] not in (S.order['buy'], S.order['sell']):
    
    #ex.request_orders() deadlock?
    
    # find my trades
    my_highest_bid = D(0);
    my_lowest_ask = D('1E12');
    for o in sorted(ex.orders['orders'], key=lambda ord: ord['price'], reverse=True):
      #print "{%s}: %s %s" % (o['oid'], o['amount'], o['price'])
      type = o['type']
      if type==1: type = 'ask'
      elif type==2: type = 'bid'
      if type == 'ask' and o['price'] <= my_lowest_ask: my_lowest_ask = o['price']
      if type == 'bid' and o['price'] >= my_highest_bid: my_highest_bid = o['price']
    print 'my hi/lo: %.4f/%.4f' % (my_highest_bid, my_lowest_ask)

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
    if abs(delta_btc) > S.desired_amount * amount_mult:
      print 'delta_btc (%s) is > %s * desired_amount (%s), refusing to trade bring me to equlibrium first by %s at least %s BTC.' % (delta_btc, amount_mult, S.desired_amount, ('selling' if delta_btc<D('0') else 'buying'), ((abs(delta_btc) - S.desired_amount) / S.funds_multiplier).quantize(D('1.0')))
      ex.removeBot(S)  
    else:
      rate = {}
      amount = {}
      increment = D('0.01')
      max_amount = D('1.0')
      min_distance = D('0.0')
      
      amount['buy'] = S.desired_amount
      rate['buy'] = ex.last_price
      while (ex.last_price - rate['buy']) <= min_distance and amount['buy'] <= max_amount:
        rate['buy'] = usd / (btc + 2 * amount['buy'])
        amount['buy'] += increment
        
      amount['sell'] = S.desired_amount
      rate['sell'] = ex.last_price
      while (rate['sell'] - ex.last_price) <= min_distance and amount['sell'] <= max_amount:
        rate['sell'] = usd / (btc - 2 * amount['sell'])
        amount['sell'] += increment

      rate['buy'] = rate['buy'].quantize(BTC_PREC)
      rate['sell'] = rate['sell'].quantize(BTC_PREC)

      print ' to buy %s BTC, I want rate %s' % (amount['buy'], rate['buy'])
      print 'to sell %s BTC, I want rate %s' % (amount['sell'], rate['sell'])
      
      # check orders
      count_exist = 0
      for type in ('buy', 'sell'):
        if S.oid[type] != None or ex.get_order(S.oid[type]) != None: count_exist += 1

      print 'count_exist: ', count_exist
      if count_exist != 2:
        ex.cmd('ps alarm.wav')
        ex.do_cancel_all_orders()

      for type in ('buy', 'sell'):
        if S.oid[type] == None or ex.get_order(S.oid[type]) == None:
          if \
          (type == 'buy' and rate[type] < ex.last_price) or \
          (type == 'sell' and rate[type] > ex.last_price):
            print 'PLACING new order: %s %s %s' % (type, amount[type], rate[type])
            S.oid[type] = ex.do_trade(type, amount[type], rate[type])
        
      # check price, if wrong, change order
      for type in ('buy', 'sell'):
        o = ex.get_order(S.oid[type])
        if o != None and abs(o['price'] - rate[type]) > D('0.0001'):
          ex.cmd('ps alarm2.wav')
          print 'CANCELLING order {%s}' % S.oid[type]
          ex.do_cancel_order(S.oid[type])
          print 'PLACING new order: %s %s %s' % (type, amount[type], rate[type])
          S.oid[type] = ex.do_trade(type, amount[type], rate[type])

    print 'performance: %s' % S.get_performance()

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
