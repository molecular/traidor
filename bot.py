#from traidor import Traidor
import pygame
from common import *
from decimal import Decimal as D

__all__ = ["Bot", "BeepBot", "TriggerBot", "EquilibriumBot"]

class Bot:
  def __init__(S, exchange):
    S.exchange = exchange
    
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
    S.exchange.cmd('ps click.wav')
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
      S.exchange.cmd(S.cmd)
      S.exchange.removeBot(S)

  def getName(S):
    return "TriggerBot(%s %s %s)" % (S.compare, S.price, S.cmd)
    
class EquilibriumBot(Bot):
  def __init__(S, exchange, fake_btc, fake_usd):
    Bot.__init__(S, exchange)
    S.fake_btc, S.fake_usd = fake_btc, fake_usd
    
  def initialize(S):
    S.exchange.do_cancel_all_orders()

  def trade(S, trade):
    ex = S.exchange

    desired_amount = D('2.0')
    
    # remove all orders I don't know about
    #for o in ex.get_orders():
    #  if o['oid'] not in (S.order['buy'], S.order['sell']):
        
    
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
    (btc, usd) = (ex.getBTC() + S.fake_btc, ex.getUSD() + S.fake_usd)
    my_ratio = (usd / btc).quantize(P)
    
    def d(x): return dec(x, 5, 5)
      
    new_rate = ex.last_price
    desired_usd = (usd + (new_rate * btc)) / 2
    desired_btc = (btc + (usd / new_rate)) / 2
    delta_usd = desired_usd - usd
    # trade sim
    delta_btc = -delta_usd / new_rate
    print "rate %s:\ncurrent %s BTC | %s USD | ratio %s \ndesire  %s USD | %s BTC -> \ndelta   %s USD | %s BTC" % (d(new_rate), d(btc), d(usd), d(my_ratio), d(desired_usd), d(desired_btc), d(delta_usd), d(delta_btc))

    if abs(delta_btc) > desired_amount:
      print 'delta_btc (%s) is > desired_amount (%s), refusing to trade bring me to equlibrium first.' % (delta_btc, desired_amount)
    else:
      buy_rate = usd / (btc + 2 * desired_amount)
      sell_rate = usd / (btc - 2 * desired_amount)

      buy_rate = buy_rate.quantize(BTC_PREC)
      sell_rate = sell_rate.quantize(BTC_PREC)

      print ' to buy %s BTC, I want rate %s' % (desired_amount, buy_rate)
      print 'to sell %s BTC, I want rate %s' % (desired_amount, sell_rate)
      
      # check orders
      #if S.orders['buy'] == None:
        
      
    
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
    return "EquilibriumBot()"
