from decimal import Decimal as D
import time

__all__ = ["D", "dec", "say", "debug_print", "timeout", "BTC_PREC", "USD_PREC"]

BTC_PREC = D('0.00000001')
USD_PREC = D('0.00001')

# talking
def say(text):
  print text
  #festival = subprocess.os.popen2("echo '(SayText \"" + text.replace("'", "") + "\")' | /usr/bin/festival --pipe")

# align D number at decimal point
def dec(dec, before, after):
  rc = dec.normalize().to_eng_string()
  if rc.find('.') >= 0:
    rc = "%*s" % (before-rc.find('.')+len(rc), rc)
  else: rc = "%*s" % (before, rc)
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
