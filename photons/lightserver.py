import trollius as asyncio
from lightclient import LightProtocol
from binascii import hexlify


class LightServer():

	def __init__(self, leds, port, iface = "localhost", debug=False):

		self.leds = leds
		self.port = port
		self.iface = iface
		self.debug = debug

		loop = asyncio.get_event_loop()

		factory = asyncio.start_server(self.new_connection, host = iface, port = port)
		self.server = loop.run_until_complete(factory)

		self.parser = LightProtocol(self.leds)

		self.client_reader = None

	def print_debug(self, msg):
		if self.debug:
			print(msg)

	def new_connection(self, client_reader, client_writer):
		#we may have only one client
		try:
			self.print_debug("new connection!")

			self.client_reader = client_reader

			while True:

				self.print_debug("reading data...")
				data = yield asyncio.From(self.client_reader.read())

				if data:
					buff = bytearray()
					buff.extend(data)
					self.print_debug("can_has_data!!!")
					self.print_debug("length: {}".format(len(data)))
					self.print_debug("data: {}".format(hexlify(data)))
					self.parser.parse(buff)

				else:
					return

		except:
			import traceback, sys
			exc_type, exc_value, exc_traceback = sys.exc_info()
			traceback.print_tb(exc_traceback, limit=1, file=sys.stdout)
			traceback.print_exception(exc_type, exc_value, exc_traceback,
	                      limit=8, file=sys.stdout)

	def close():
		self.server.close()
		asyncio.get_event_loop().run_until_complete(self.server.wait_closed())



if __name__ == "__main__":
	from lights import LightArray2, OpenCvSimpleDriver
	
	num_lights = 10

	leds = LightArray2(num_lights, OpenCvSimpleDriver())
	server = LightServer(leds, 9099, debug=True)

	asyncio.get_event_loop().run_forever()

	server.close()