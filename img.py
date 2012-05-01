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