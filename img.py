import numpy
from PIL import Image


__all__ = ["Img"]

black = 0xff000000

class Img:
  def __init__(S, w, h):
    S.w, S.h = w, h
    S.img = numpy.empty((S.w, S.h), numpy.uint32)
    S.img.shape = S.h, S.w
    
  def clear(S):
    S.img[0:S.h, 0:S.w] = black
    
  def set_bar(S, c, x, h):
    S.img[0:h, x] = black
    S.img[h:S.h, x] = c
      
  def write(S, filename):
    pilImage = Image.frombuffer('RGBA', (S.w, S.h), S.img, 'raw', 'RGBA', 0, 1)
    pilImage.save(filename)