pywsc - Python WebSocket Client
===============================

Experimental Python implementation of draft-ietf-hybi-thewebsocketprotocol-00.


Usage
-----

	from pywsc.websocket import WebSocket

	if __name__ == '__main__':
		ws = WebSocket('ws://localhost:8080/test')
		
		def onOpen():
			print "-onOpen"
			ws.send('Hello World!')
			
		def onMessage(message):
			print "-onMessage:", message
			
		def onClose():
			print "-onClose"
			
		ws.setEventHandlers(onOpen, onMessage, onClose)
		ws.connect()