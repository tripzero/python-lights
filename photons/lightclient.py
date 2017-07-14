

import trollius as asyncio
from wss.wssclient import ReconnectAsyncio, Client
from collections import deque
import binascii

from photons import LightProtocol

try:
	range = xrange
except:
	pass


class LightClientWss(Client, LightProtocol):

	def __init__(self, host=None, port=None, retry = False, loop = None, debug = False, fps = 60):
		Client.__init__(self, retry = retry, loop = loop)
		LightProtocol.__init__(self, debug = debug)

		self.fps = fps
		self.send_queue = asyncio.Queue()

		self.debug = debug

		if host and port:
			self.connectTo(host, port, useSsl=False)

		self.loop.create_task(self._process_send())

	def send(self, msg):
		self.send_queue.put_nowait(msg)

	@asyncio.coroutine
	def _process_send(self):
		while True:

			if self.send_queue.qsize():
				msg = bytearray()

				while self.send_queue.qsize() > 0:
					i = self.send_queue.get_nowait()
					msg.extend(i)

				msg = self.writeHeader(msg)
				self.sendBinaryMsg(bytes(msg))

			yield asyncio.From(asyncio.sleep(1.0 / self.fps))

class LightClient(LightProtocol, ReconnectAsyncio):


	def __init__(self, loop = asyncio.get_event_loop(), debug = False, onConnected = None, onDisconnected = None, usingAsynioEventLoop=True):
		LightProtocol.__init__(self)
		ReconnectAsyncio.__init__(self, retry=True)
		self.reader = None
		self.writer = None
		self.loop = loop
		self.debug = debug
		self.connected = False

		self.onConnected = onConnected
		self.onDisconnected = onDisconnected
		self.usingAsynioEventLoop = usingAsynioEventLoop
		if self.debug:
			self.log = open("lightclient.log", "w")

	@asyncio.coroutine
	def _connect(self):
		self.reader, self.writer = yield asyncio.From(asyncio.open_connection(self.addy, self.port))
		protocol = self.writer.transport._protocol
		protocol.connection_lost = self._onDisconnected
		self.connected=True
		if self.onConnected:
			self.onConnected()

	def connectTo(self, addy, port):
		self.addy = addy
		self.port = port

		self.debug_print("trying to connect to {}:{}".format(addy, port))

		self._do_connect()

	def debug_print(self, msg):
		if self.debug:
			self.log.write(msg)
			self.log.write("\n")

	def send(self, msg):

		if not self.connected:
			self.debug_print("not connected")
			return
		
		msg = self.writeHeader(msg)

		#self.debug_print("writing to {}: {}".format(self.addy, binascii.hexlify(msg)))

		@asyncio.coroutine
		def s2():
			try:
				#print("writing for realz")
				self.writer.write(msg)
				yield asyncio.From(self.writer.drain())
			except TimeoutError:
				self.connected = False
				self._onDisconnected()
			except:
				import traceback, sys
				exc_type, exc_value, exc_traceback = sys.exc_info()
				traceback.print_tb(exc_traceback, limit=1, file=sys.stdout)
				traceback.print_exception(exc_type, exc_value, exc_traceback,
		                      limit=8, file=sys.stdout)

		def s():
			try:
				self.writer.write(msg)
				yield asyncio.From(self.writer.drain())
			
			except TimeoutError:
				self.connected = False
				self._onDisconnected()
			except:
				import traceback, sys
				exc_type, exc_value, exc_traceback = sys.exc_info()
				traceback.print_tb(exc_traceback, limit=1, file=sys.stdout)
				traceback.print_exception(exc_type, exc_value, exc_traceback,
		                      limit=8, file=sys.stdout)
		
		if self.usingAsynioEventLoop:
			s()
		else:
			self.loop.run_until_complete(s2())
		
	def _onConnected(self):
		if self.onConnected:
			self.onConnected()

	def _onDisconnected(self, reason=None):
		self.connected = False

		if self.writer:
			self.writer.close()

		if self.onDisconnected:
			self.onDisconnected()


def test_protocol(debug=False):

	class TestClient(LightProtocol):
		def __init__(self, num_lights=10):

			LightProtocol.__init__(self)

			from lights import LightArray2, OpenCvSimpleDriver
			self.leds = LightArray2(num_lights, OpenCvSimpleDriver())
			self.server = LightProtocol(self.leds, debug = debug)

		def send(self, buffer):

			self.server.parse(self.writeHeader(buffer))


	num_lights = 10
	c = TestClient(num_lights)

	#set all colors to red, green, than blue
	@asyncio.coroutine
	def test_set_color():
		print("test_set_color")
		print("============\n")

		print("setColor: red")
		for i in range(num_lights):
			c.setColor(i, (255, 0, 0))

		yield asyncio.From (asyncio.sleep(5))

		print("setColor: green")
		for i in range(num_lights):
			c.setColor(i, (0, 255, 0))

		yield asyncio.From (asyncio.sleep(5))

		print("setColor: blue")
		for i in range(num_lights):
			c.setColor(i, (0, 0, 255))

		yield asyncio.From (asyncio.sleep(5))

	@asyncio.coroutine
	def test_clear():
		print("test_clear")
		print("==========\n")

		c.clear()
		yield asyncio.From (asyncio.sleep(5))

	@asyncio.coroutine
	def test_set_all():
		print("test_set_all")
		print("============\n")

		print("setAllColor: red")
		c.setAllColor((255, 0 , 0))

		yield asyncio.From (asyncio.sleep(5))

		print("setAllColor: green")
		c.setAllColor((0, 255 , 0))

		yield asyncio.From (asyncio.sleep(5))

		print("setAllColor: blue")
		c.setAllColor((0, 0 , 255))
		yield asyncio.From (asyncio.sleep(5))

	@asyncio.coroutine
	def test_set_series():
		print("test_set_series")
		print("===============\n")
		# first and last led = red

		c.setColor(0, (255, 0, 0))
		c.setColor(num_lights-1, (255, 0, 0))

		#all leds in between = blue

		c.setSeries(1, num_lights-2, (0, 0, 255))

		print("red, blue, red")

		yield asyncio.From (asyncio.sleep(5))

	@asyncio.coroutine
	def test_multimsg():
		print("test_multimsg")
		print("============\n")

		#this message has clear [0x03] and set_all_colors [0x06]
		msg = b'0306000064'
		msg = bytearray(binascii.unhexlify(msg))

		print("should be blueish...")

		c.send(msg)

		yield asyncio.From (asyncio.sleep(5))

		print("should be a rainbow")

		msg = b'010a000000ffff00010081ff00020000ff920300007bff04006a00ff05006100000600b500000700ff00000800ff00000900ff7700'
		msg = bytearray(binascii.unhexlify(msg))

		c.send(msg)
		yield asyncio.From (asyncio.sleep(5))


		msg = b'0301010001008a006c0101000200170000010100040050003f0101000800c300000101000900e70000'
		msg = bytearray(binascii.unhexlify(msg))

		c.send(msg)
		yield asyncio.From (asyncio.sleep(5))


	def test_debug():
		print("test_debug")
		print("============\n")

		to_set=1

		if debug:
			to_set = 0

		c.setDebug(to_set)
		assert(c.server.debug == to_set)

		print("pass")

		#teardown:
		c.setDebug(debug)

	def test_setNumLeds():
		print("test_setNumLeds")
		print("===============\n")
		c.setNumLeds(1)
		assert(c.leds.ledArraySize == 1)
		c.setNumLeds(num_lights)
		assert(c.leds.ledArraySize == num_lights)

		print("pass")


	asyncio.get_event_loop().run_until_complete(test_clear())
	asyncio.get_event_loop().run_until_complete(test_multimsg())
	asyncio.get_event_loop().run_until_complete(test_set_series())
	asyncio.get_event_loop().run_until_complete(test_set_color())
	asyncio.get_event_loop().run_until_complete(test_clear())
	asyncio.get_event_loop().run_until_complete(test_set_all())
	asyncio.get_event_loop().run_until_complete(test_clear())
	test_debug()
	test_setNumLeds()



if __name__ == "__main__":
	import argparse
	parser = argparse.ArgumentParser()
	parser.add_argument('--debug', dest="debug", help="turn on debugging.", action='store_true')
	parser.add_argument('--test', dest="test", help="self test", action="store_true")
	parser.add_argument('--num', dest="numLeds", help="number of leds", type=int)
	parser.add_argument('--wss', dest="wss", help="use wss socket", action="store_true")
	parser.add_argument('address', help="address", default="localhost", nargs="?")
	parser.add_argument('port', help="port", default=1888, nargs="?")
	args = parser.parse_args()

	if args.test:
		test_protocol(debug=args.debug)
		quit()

		
	client = None
	if not args.wss:
		client = LightClient(debug=args.debug)
	else:
		client = LightClientWss(debug=args.debug)

	def onConnected():
		print("client onConnected:")
		client.clear()
		client.setAllColor((0, 0, 100))

	if args.wss:
		client.setOpenHandler(onConnected)
		client.connectTo(args.address, args.port, useSsl=False)
	else:
		client.onConnected = onConnected
		client.connectTo(args.address, args.port)


	client.loop.run_forever()
	client.loop.close()
