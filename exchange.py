import urllib, urllib2 #, httplib2
import simplejson as json
from common import *

__all__ = ["Exchange"]

class Exchange:
  def __init__(S, traidor, config, name):
    S.traidor = traidor
    S.name = name
    S.debug = config.getboolean(S.name, 'debug')
    S.run = True
    
  def getName(S):
    return S.name
    
  def getPrompt(S):
    if (S.getBTC() != 0): 
      ratio = S.getUSD() / S.getBTC()
    else: ratio = -1
    #return "\n%s | span %.4f | %.2f BTC, %.2f USD | %.2f #> " % (infoline, S.dmz_width, S.getBTC(), S.orders['usds'], ratio)
    rc = "\n%s | %s BTC | %s USD" % (S.getName(), S.getBTC(), S.getUSD() )
    if S.eval_base_btc > 0 and S.last_price != 0: rc += " | eval(%s BTC) = %s USD" % (S.eval_base_btc, (S.eval(S.eval_base_btc) - S.eval_base_usd).quantize(D('0.01')))
    rc += " | [h]elp #> "
    return rc
    
  def getTrades(S):
    pass
    
  def getTradeFee(S):
    return(D(10))
    
  def stop(S):
    S.run = False
    
    