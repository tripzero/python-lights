import asyncio
from photons import LightProtocol
from binascii import hexlify
from wss.wssserver import Server, server_main


class LightServerWss(Server):
	def __init__(self, leds=None, port=None, iface = "localhost", useSsl=False, sslCert = "server.crt", sslKey = "server.key", debug=False):
		self.leds = leds
		self.port = port
		self.iface = iface

		#Keep about 5 seconds worth of data
		self.queue = asyncio.Queue(maxsize = self.leds.fps * 5)

		self.parser = LightProtocol(leds = self.leds, debug = debug)

		Server.__init__(self, port = port, useSsl = useSsl, sslCert = sslCert, sslKey = sslKey)

		asyncio.get_event_loop().create_task(self._processQueue())


	def onBinaryMessage(self, msg, fromClient):
		data = bytearray()
		data.extend(msg)

		"""
		self.print_debug("message length: {}".format(len(data)))
		self.print_debug("message data: {}".format(hexlify(data)))
		"""

		try:
			self.queue.put_nowait(data)
		except asyncio.QueueFull:
			pass #drop message

	@asyncio.coroutine
	def _processQueue(self):
		while True:

			data = yield from self.queue.get()
			self.parser.parse(data)

			yield from asyncio.sleep(1/self.leds.fps)


class LightServer(asyncio.Protocol):

	def __init__(self, leds, port, iface = "localhost", debug=False, **kwargs):

		self.leds = leds
		self.port = port
		self.iface = iface
		self.debug = debug
		self.parser = LightProtocol(leds = self.leds, debug = debug)
		self.queue = asyncio.Queue(maxsize = self.leds.fps * 5)

		asyncio.get_event_loop().create_task(self._processQueue())

	def start(self):
		loop = asyncio.get_event_loop()

		factory = loop.create_server(lambda: self,
			host = self.iface, port = self.port)

		self.server = loop.run_until_complete(factory)


	def print_debug(self, msg):
		if self.debug:
			print(msg)

	def connection_made(self, transport):
		#we may have only one client
		try:
			self.print_debug("new connection!")

			self.client_writer = transport
		
		except:
			import traceback, sys
			exc_type, exc_value, exc_traceback = sys.exc_info()
			traceback.print_tb(exc_traceback, limit=1, file=sys.stdout)
			traceback.print_exception(exc_type, exc_value, exc_traceback,
	                      limit=8, file=sys.stdout)

	def data_received(self, data):
		self.print_debug("new data received")
		
		try:
			self.queue.put_nowait(bytearray(data))
		except asyncio.QueueFull:
			pass #drop message

	@asyncio.coroutine
	def _processQueue(self):
		while True:

			data = yield from self.queue.get()
			self.parser.parse(data)

			yield from asyncio.sleep(1/self.leds.fps)

	def close():
		self.server.close()
		asyncio.get_event_loop().run_until_complete(self.server.wait_closed())



if __name__ == "__main__":
	from photons import LightArray2, OpenCvSimpleDriver, DummyDriver
	
	import argparse

	parser = argparse.ArgumentParser()
	parser.add_argument('--wss', dest="wss", help="use wss.", action='store_true')

	args, unknown = parser.parse_known_args()

	num_lights = 200

	leds = LightArray2(num_lights, OpenCvSimpleDriver(opengl=True), fps=60)

	sc = LightServer

	if args.wss:
		sc = LightServerWss

	server = server_main(ServerClass=sc, leds=leds)

	server.start()

	asyncio.get_event_loop().run_forever()

	server.close()
