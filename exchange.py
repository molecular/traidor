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

import urllib, urllib2 #, httplib2
try: import simplejson as json
except ImportError: import json
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
    
    