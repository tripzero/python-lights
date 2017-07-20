from photons import LightClient, LightServer
from fakelightarray import FakeLightArray2
import asyncio
import numpy as np

set_color = [255, 0, 0]

class LA(FakeLightArray2):
	def __init__(self):
		self.fps = 60
		self.got_it = False

	def changeColor(self, index, color):
		print("changeColor({}, {})".format(index, color))
		self.got_it = True

leds = LA()

server = LightServer(leds=leds, port=1888, debug=True)

server.start()

client = LightClient(debug=True, onConnected=set_color)

def set_color():
	print("sending set color...")
	client.setColor(0, [255, 0, 0])

def check_got_message():
	assert(leds.got_it)
	asyncio.get_event_loop().stop()

asyncio.get_event_loop().call_later(2.0, check_got_message)

asyncio.get_event_loop().run_forever()
server.close()

