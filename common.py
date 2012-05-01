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

from decimal import Decimal as D
import time


__all__ = ["D", "Trade", "dec", "say", "debug_print", "timeout", "BTC_PREC", "USD_PREC", "PRICE_PREC", "VOL_PREC", "VOL2_PREC", "MYVOL_PREC"]

BTC_PREC = D('0.00000001')
USD_PREC = D('0.00001')

PRICE_PREC = D('0.00001')
VOL_PREC = D('0.1')
VOL2_PREC = D('0')
MYVOL_PREC = D('0.01')

# class Trade
class Trade:
  def __init__(S, tid, time, amount, price, type):
    (S.tid, S.time, S.amount, S.price, S.type) = (tid, time, D(amount), D(price), type)
    
  def str(S):
    return "%s: {%s} | %s for %s - %s" % (time.strftime('%H:%M:%S',time.localtime(S.time)), S.tid, S.amount, S.price, S.type)

# talking
def say(text):
  print text
  #festival = subprocess.os.popen2("echo '(SayText \"" + text.replace("'", "") + "\")' | /usr/bin/festival --pipe")

# align D number at decimal point
def dec(dec, before, after):
  rc = dec.normalize().to_eng_string()
  if rc.find('.') >= 0:
    rc = "%*s" % (before-rc.find('.')+len(rc), rc)
  else: rc = "%*s.0" % (before, rc)
  rc += '                          '[:(after+before+1)-len(rc)]
  rc = rc[:(before+after+1)]
  return rc # rc.replace('0.', 'o.').replace('.0', '.o')

debug_log = open('debug.log', 'w')
def debug_print(str):
  tm = time.localtime()
  debug_log.write( '%s: %s\n' % (time.strftime('%Y/%m/%d-%H:%M:%S',tm), str) )
  debug_log.flush()

def timeout(func, args=(), kwargs={}, timeout_duration=1, default=None):
  import threading
  class InterruptableThread(threading.Thread):
    def __init__(self):
      threading.Thread.__init__(self)
      self.result = None

    def run(self):
      try:
        self.result = func(*args, **kwargs)
      except:
        self.result = default

  it = InterruptableThread()
  it.start()
  it.join(timeout_duration)
  if it.isAlive():
    return default
  else:
    return it.result

