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

#!/usr/bin/python
          
# maybe alternative for /code/getTrades.php before websocket is back
# http://bitcoincharts.com/t/trades.csv?symbol=mtgoxUSD&start=$UNIXTIME
# http://www.google.com/fusiontables/DataSource?dsrcid=1058017

import sys, os
import time
import subprocess
from ConfigParser import SafeConfigParser
#from pywsc.websocket import WebSocket
try:
  import pygame
  pygame_enabled=True
except:
  pygame_enabled=False
from contextlib import closing
from threading import *

from common import *
import common
from bot import *
import traceback
#from wxgui import *
#from img import *

from mtgox import *

class Traidor:
  def __init__(S):
    S.displaylock = Lock()
    # S.auto_update_trade = True
    S.auto_update_depth = True

    # parse configfile
    parser = SafeConfigParser()
    parser.read('traidor.conf')

    S.exchange = None
    S.exchanges = []
    exchange = MtGox(S, parser)
    S.addExchange(exchange)
    
    S.donated = parser.getboolean('main', 'donated')
    S.debug = parser.getboolean('main', 'debug')
    S.continue_on_exception = parser.getboolean('main', 'continue_on_exception')
    S.display_height = int(parser.get('main','initial_depth_display_height'))
    S.autoexec = parser.get('main', 'autoexec')
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
  
  def addBot(S, bot, do_init):
    S.bots.append(bot)
    if do_init:
      bot.initialize()

  def removeBot(S, bot):
    S.bots.remove(bot)

  # --- json stuff ----------------------------------------------------------------------------------------------------------------------

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
  def prompt(S, print_before=""):
    S.displaylock.acquire()
    if len(print_before) > 0: sys.stdout.write("\n%s" % print_before)
    sys.stdout.write(S.exchange.getPrompt())
    sys.stdout.flush()
    S.displaylock.release()

  def cmd(S, cmd, is_bot=False):
    if (cmd.rfind(';') >= 0):
      for c in cmd.split(';'): S.cmd(c.strip())
    else:
      #debug_print('cmd("%s")' % cmd)
      if cmd[:4] == 'eval': 
        S.auto_update_depth = False
        base = D(cmd[4:])
        print 'evaluation based on %s BTC: %s USD' % (base.quantize(USD_PREC), S.eval(base).quantize(USD_PREC))
      elif cmd[:2] == 'ps': 
        if pygame_enabled: pygame.mixer.Sound(cmd[3:]).play()
      elif cmd[:2] == 'lb': 
        i=0
        for bot in S.bots: 
          print "[%2i]: %s" % (i, bot.getName())
          i += 1
      elif cmd[:2] == 'tb': # TriggerBot
        S.addBot(TriggerBot(t, cmd[2:]), True)
      elif cmd[:2] == 'vb': # ValueBot
        paras = cmd[3:].split(' ')
        print paras
        S.value_bot = ValueBot(t.exchange, float(paras[0]), float(paras[1]))
        S.addBot(S.value_bot, True)
      elif cmd[:2] == 'v': # ValueBot info()
        try: S.value_bot 
        except:
          S.cmd('vb 1000')
        print S.value_bot.info()
      elif cmd[:2] == 'wx' or cmd[:3] == 'gui':
        wx = TraidorApp(t)
        S.addBot(wx, True)
        wx.initialize()
      elif cmd[0] == 'q': 
        S.run = False
      elif cmd[0] == 'h': 
        S.auto_update_depth = False
        S.show_help()
      elif cmd[0] == 'a': S.auto_update_depth = not S.auto_update_depth; print 'auto_update_depth = ', S.auto_update_depth
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
          else: 
            common.PRICE_PREC = D(10) ** -p; 
        except: print 'exception parsing precision value: %s' % p
        S.exchange.reload_depth()
      else:
        S.exchange.cmd(cmd, is_bot);

  def __call__(S): # mainloop
    S.run = True
    
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
      
    # autoexec
    if S.debug: print 'running autoexec: "%s"...' % S.autoexec
    try:
      S.cmd(S.autoexec, True)
    except:
      traceback.print_exc()
      print 'autoexec failed'
      return
    
    if S.debug: print 'ready'
      

    counter = 0
    while (S.run):
      try:
        key = raw_input(S.exchange.getPrompt());
        if (len(key) > 0):
          S.cmd(key)
        else: 
          #S.request_info();
          S.exchange.show_depth();
        counter += 1
        if (counter % 31) == 13 and not S.donated:
          print '\n\n\n\n\nplease consider donating to 1Ct1vCN6idU1hKrRcmR96G4NgAgrswPiCn\n\n\n(to remove donation msg, put "donated=1" into configfile, section [main])\n'
      except:
        traceback.print_exc()
        if not S.continue_on_exception: 
          print 'exception, continue_on_exception = False => quitting'
          S.run = False
        else:
          print 'exception, continue_on_exception = True => ignoring'
        

    if S.debug: print 'stopping bots...'
    for bot in S.bots:
      bot.stop()
      
    if S.debug: print 'stopping exchanges...'
    for x in S.exchanges:
      x.stop()


t = Traidor()
if pygame_enabled: pygame.init()

#t.addBot(BeepBot(t.exchange), False)

#t.addBot(EquilibriumBot(t, D('0.0'), D('0'), D('3.0'), D('0.2'))) # btc add, usd add, fund_multiplier, desired_amount
#t.cmd("tb >= 14.80 ps alarm.wav")
#t.cmd("tb <= 14.40 ps alarm2.wav")
#t.mainloop()
