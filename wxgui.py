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

from bot import *
from threading import *
from common import *
import wx
import sys
from wx.lib.mixins.listctrl import ListCtrlAutoWidthMixin

__all__ = ["TraidorApp"]

class OrderBookListCtrl(wx.ListCtrl,ListCtrlAutoWidthMixin):
  def __init__(S, parent):
    wx.ListCtrl.__init__(S, parent, -1, style=wx.LC_REPORT)
    ListCtrlAutoWidthMixin.__init__(S)

class TraidorFrame(wx.Frame):
  def __init__(S, exchange):
    S.x = exchange
    wx.Frame.__init__(S, None, title="traidor")

    # font
    S.mono_font = wx.Font(9, wx.FONTFAMILY_TELETYPE, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
    S.SetFont(S.mono_font)

    # menu
    file_menu = wx.Menu()
    menuBar = wx.MenuBar()
    menuBar.Append(file_menu, "&Help")
    S.SetMenuBar(menuBar)
    S.Bind(wx.EVT_MENU, S.OnAbout, file_menu.Append(wx.ID_ABOUT, "&About", "About Traidor"))
    file_menu.AppendSeparator()
    S.Bind(wx.EVT_MENU, S.OnQuit, file_menu.Append(wx.ID_EXIT, "&Quit", "Quit"))
    
    # order book
    hbox = wx.BoxSizer(wx.HORIZONTAL)
    panel = wx.Panel(S, -1)
    S.orderlist = OrderBookListCtrl(panel)
    S.orderlist.InsertColumn(0, 'id')
    S.orderlist.InsertColumn(1, 'type')
    S.orderlist.InsertColumn(2, 'amount', wx.LIST_FORMAT_RIGHT)
    S.orderlist.InsertColumn(3, 'price', wx.LIST_FORMAT_RIGHT)
    S.orderlist.InsertColumn(4, 'status')
    hbox.Add(S.orderlist, 1, wx.EXPAND)
    panel.SetSizer(hbox)
    S.fill_orders(S.orderlist, S.x.get_orders())
    
    S.Centre()
    S.Show(True)

  type_string = {1: 'sell', 2: 'buy'}
  status_string = {0: 'invalid', 1: 'open', 2: 'pending'}
  def fill_orders(S, list, orders):
    for o in sorted(orders, key=lambda ord: ord['price'], reverse=True):
      i = list.InsertStringItem(sys.maxint, o['oid'])
      list.SetStringItem(i, 1, TraidorFrame.type_string[o['type']])
      list.SetStringItem(i, 2, dec(o['amount'], 5, 8))
      list.SetStringItem(i, 3, dec(o['price'], 3, 5))
      list.SetStringItem(i, 4, TraidorFrame.status_string[o['status']])
      
  def OnAbout(S, e):
    dlg = wx.MessageDialog(S, "traidor", "About Traidor", wx.OK)
    dlg.ShowModal()
    dlg.Destroy()
    
  def OnQuit(S, e):
    S.Close(True)

class TraidorApp(wx.App, Thread, Bot):
  def __init__(S, exchange):
    Bot.__init__(S, exchange)
    wx.App.__init__(S, False)
    Thread.__init__(S)

  def initialize(S):
    S.frame = TraidorFrame(S.x)
    S.start()

  def run(S):
    S.MainLoop()
