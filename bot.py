#from traidor import Traidor
import pygame
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
      print '\n\nTRIGGER BOT TRIGGER %s\n\n' % S.price
      S.exchange.cmd(S.cmd)
      S.exchange.removeBot(S)

  def getName(S):
    return "TriggerBot(%s %s %s)" % (S.compare, S.price, S.cmd)
    
class EquilibriumBot(Bot):
  def __init__(S, exchange):
    Bot.__init__(S, exchange)

  def trade(S, trade):
    ex = S.exchange

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


  def getName(S):
    return "EquilibriumBot()"
