

import trollius as asyncio

import numpy as np
import struct
import binascii

#log.startLogging(sys.stdout)

class LightParser:
	
	commandsMap = {}

	@staticmethod
	def command(cmd):
		def make_command(func):
			LightParser.commandsMap[cmd] = func
			return func
		return make_command

class LightProtocol:
	"""
		Light protocol follows the following frame/payload structure:

		[Header] [Payload]

		Header:

		[Protocol_Version][Payload_Length]
		[1byte][2bytes]

		Payload:
		[Command][Data]
		[1byte]


	"""
	ledsDataCopy = None
	
	def __init__(self):
		pass

	def update(self, ledsData):

		if len(ledsData) == 1 or np.unique(ledsData).size == 1:
			self.setAllColor(ledsData[0])
			return

		if self.ledsDataCopy is None:
			self.ledsDataCopy = np.array(ledsData, copy=True)
			#self.setNumLeds(len(self.ledsDataCopy))
			diff = self.ledsDataCopy
		else:
			diff = np.bitwise_xor(ledsData, self.ledsDataCopy)

		ledsToChange = bytearray()
		for i in range(len(diff)):
			if not np.all(np.equal(diff[i], [0,0,0])):
				ledsToChange.extend(struct.pack('<H', i))
				ledsToChange.extend(ledsData[i])
				#self.setColor(i, ledsData[i])
				
		if not len(ledsToChange):
			print("no change")
			return

		header = bytearray()
		header.append(0x01)
		header.extend(struct.pack('<H', int(len(ledsToChange)/5)))
		ledsToChange = header + ledsToChange

		self.ledsDataCopy = np.array(ledsData, copy=True)

		self.send(ledsToChange)

	def setColor(self, id, color):
		"""
		Command 0x01
		sets the color of a specific light

		Data:
		
		[Command][Number_Lights_to_set][id_1][r][g][b][id_n][r][g][b]...
		"""
		header = bytearray()
		header.append(0x01)
		header.extend(struct.pack('<H', 1))

		light = bytearray()
		light.extend(struct.pack('<H', id))
		light.extend(color)

		buff = header + light
		self.send(buff)

	def setAllColor(self, color):
		"""
		Command: 0x06
		sets all colors in the array

		Data:
		[Command][r][g][b]
		"""

		header = bytearray()
		header.append(0x06)

		light = bytearray()
		light.extend(color)

		buff = header + light
		self.send(buff)


	def setNumLeds(self, numLeds):
		buff = bytearray()
		buff.append(0x02)
		buff.extend(struct.pack('<H', numLeds))
		self.send(buff)

	def setDebug(self, d):
		buff = bytearray()
		buff.append(0x05)
		buff.append(int(d))
		self.send(buff)

	def parse(self, msg):
		cmd = msg[0]
		if cmd in LightParser.commandsMap:
			LightParser.commandsMap[cmd](self, msg)
		else:
			print("command {0} not supported by this server".format(cmd))

	@LightParser.command(0x01)
	def parseSetColor(self, msg):
		cmd = msg[0]
		numlights = struct.unpack('<H', msg[1:3])[0]

		print("number of lights {0}".format(numlights))

		light = 3 #start at light at position 3 in the msg
		for i in range(numlights):
			id = struct.unpack('<H', msg[light:light+2])[0]
			r = msg[light+2]
			g = msg[light+3]
			b = msg[light+4]

			print("change light id {0} to ({1},{2},{3})".format(id, r, g, b))
			light += 5 #5 bytes per light


class LightClient(LightProtocol):
	debug = False
	onDisconnected = None
	onConnected = None
	reader = None
	writer = None

	def __init__(self, loop = asyncio.get_event_loop(), debug = False, onConnected = None, onDisconnected = None):
		LightProtocol.__init__(self)
		self.loop = loop
		self.debug = debug
		self.onConnected = onConnected
		self.onDisconnected = onDisconnected
		if self.debug:
			self.log = open("lightclient.log", "w")

	def connectTo(self, addy, port):
		self.addy = addy
		self.port = port

		@asyncio.coroutine
		def c():
			self.reader, self.writer = yield asyncio.From(asyncio.open_connection(addy, port))

		try:
			self.loop.run_until_complete(c())
			self.connected = True
			self._onConnected()
			return True
		except:
			print("connection failed!")
			self.connected = False
			self._onDisconnected()
			return False

	def send(self, msg):

		if not self.connected:
			return

		if self.debug:
			self.log.write(msg)

		#write header:

		header = bytearray([0x01]) #protocol version 1.0
		header.extend(struct.pack('<H', len(msg)))

		msg = header + msg

		#print("writing to {}: {}".format(self.addy, binascii.hexlify(msg)))

		#@asyncio.coroutine
		def s():
			try:
				#print("writing for realz")
				self.writer.write(msg)
				self.writer.drain()
				#yield asyncio.From (self.writer.drain())
			except TimeoutError:
				self.connected = False
				self._onDisconnected()
			except:
				import traceback, sys
				exc_type, exc_value, exc_traceback = sys.exc_info()
				traceback.print_tb(exc_traceback, limit=1, file=sys.stdout)
				traceback.print_exception(exc_type, exc_value, exc_traceback,
		                      limit=8, file=sys.stdout)
		
		s()
		#self.loop.create_task(s())
		
	def _onConnected(self):
		if self.onConnected:
			self.onConnected()

	def _onDisconnected(self):
		if self.reader:
			self.reader.close()
		if self.writer:
			self.writer.close()
		if self.onDisconnected:
			self.onDisconnected()

if __name__ == "__main__":
	import argparse
	parser = argparse.ArgumentParser()
	parser.add_argument('--debug', dest="debug", help="turn on debugging.", action='store_true')
	parser.add_argument('--test', dest="test", help="self test", action="store_true")
	parser.add_argument('--num', dest="numLeds", help="number of leds", type=int)
	parser.add_argument('address', help="address", default="localhost", nargs="?")
	parser.add_argument('port', help="port", default=1888, nargs="?")
	args = parser.parse_args()

	client = LightClient()

	if not args.test:
		if not client.connectTo(args.address, args.port):
			quit()
	else:
		server = LightProtocol()
		client.send = server.parse


	#client.setNumLeds(args.num)

	client.setAllColor((0, 0, 100))

	#for i in range(20):
	#	client.setColor(0, (100, 0, 0))

	client.loop.run_forever()
	client.loop.close()
