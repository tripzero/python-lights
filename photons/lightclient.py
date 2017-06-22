

import trollius as asyncio

import numpy as np
import struct
import binascii
from wss.wssclient import ReconnectAsyncio, Client

try:
	range = xrange
except:
	pass

#log.startLogging(sys.stdout)

class LightParser:
	
	commandsMap = {}

	@staticmethod
	def command(cmd):
		def make_command(func):
			LightParser.commandsMap[cmd] = func
			return func
		return make_command

class IncompatibleProtocolException(Exception):
	def __init__(self, protocol, should_be_protocol):
		Exception.__init__(self)
		print("protocol {} should be {}".format(protocol, should_be_protocol))

class BadMessageTypeException(Exception):
	def __init__(self):
		Exception.__init__(self)
		print("message type should be bytearray")

class InvalidCommandException(Exception):
	pass

class LightProtocol:
	"""
		Light protocol follows the following frame/payload structure:

		[Header] [Payload]

		Header:

		[Protocol_Version][Payload_Length]
		[1byte][2bytes]

		Payload:
		[Command][Data]
		[1byte][...]


	"""
	ledsDataCopy = None
	
	def __init__(self, leds=None, debug = 0):
		"""leds = LightArray2 handle.  This is only used when trying to parse."""
		self.leds = leds
		self.protocol_version = 0x01 #version 1.0
		self.debug = debug

	def debug_print(self, msg):
		if self.debug:
			print(msg)

	def updateCompress(self, ledsData):
		index = 0

		while index < len(ledsData):
			color = ledsData[index]
			startId = index
			length = 0
			for i in ledsData[index:]:
				if not np.array_equal(color, i):
					break
				
				length += 1

			if length < 4:
				"""if the length is less than 4, it's not worth the extra bits to send a setSeries"""
				for i in range(length):
					self.setColor(startId + i, color)
			else:
				self.setSeries(startId, length, color)

			index += length


	def update(self, ledsData):
		if len(ledsData) == 1 or np.unique(ledsData).size == 1:
			self.setAllColor(ledsData[0])
			return

		stdDev = np.std(ledsData)

		"""if stdDev < len(ledsData) / 4:
			" if there's a lot of common data, we can compress the stream and break up the packets "
			return self.updateCompress(ledsData)
		"""

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
			#print("no change")
			return

		header = bytearray()
		header.append(0x01)
		header.extend(struct.pack('<H', int(len(ledsToChange)/5)))
		ledsToChange = header + ledsToChange

		self.ledsDataCopy = np.array(ledsData, copy=True)

		#print ("sending {} update".format(len(ledsToChange)))
		self.send(self.writeHeader(ledsToChange))

	def writeHeader(self, msg):
		"""write header:
		[8bit][16bit]
		[protocol_version][msg_length]
		"""

		header = bytearray([self.protocol_version]) #protocol version 1.0
		header.extend(struct.pack('<H', len(msg)))

		msg = header + msg

		return msg

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
		return self.send(self.writeHeader(buff))

	def setSeries(self, startId, length, color):
		"""
		Command 0x07
		sets all lights in the series starting from "startId" to "endId" to "color"

		Data:
		[0x07][startId][length][r][g][b]		
		"""

		buff = bytearray()
		buff.append(0x07)
		buff.extend(struct.pack('<H', startId))
		buff.extend(struct.pack('<H', length))
		buff.extend(color)

		return self.send(self.writeHeader(buff))


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
		return self.send(self.writeHeader(buff))

	def clear(self):
		"""
		Command: 0x03
		clear all leds

		Data:
		[Command]
		"""

		header = bytearray()
		header.append(0x03)

		return self.send(self.writeHeader(header))

	def setNumLeds(self, numLeds):
		buff = bytearray()
		buff.append(0x02)
		buff.extend(struct.pack('<H', numLeds))
		return self.send(self.writeHeader(buff))

	def setDebug(self, d):
		buff = bytearray()
		buff.append(0x05)
		buff.append(int(d))
		return self.send(self.writeHeader(buff))

	def parse(self, msg):
		if not isinstance(msg, bytearray):
			raise BadMessageTypeException()

		protocol_version = msg[0]
		msg_length = struct.unpack('<H', msg[1:3])[0]

		if protocol_version != self.protocol_version:
			raise IncompatibleProtocolException(protocol_version, self.protocol_version)

		if self.debug:
					self.debug_print("message: {}".format(binascii.hexlify(msg)))

		while len(msg):
			
			cmd = msg[3]
			if cmd in LightParser.commandsMap:
				msg = LightParser.commandsMap[cmd](self, msg[3:])

				if self.debug:
					self.debug_print("remaining message: {}".format(binascii.hexlify(msg)))
			else:
				raise InvalidCommandException("command {0} not supported in {}".format(cmd, self.protocol_version))

	@LightParser.command(0x01)
	def parseSetColor(self, msg):
		cmd = msg[0]
		numlights = struct.unpack('<H', msg[1:3])[0]

		light = 3 #start at light at position 3 in the msg
		for i in range(numlights):
			id = struct.unpack('<H', msg[light:light+2])[0]

			r = msg[light+2]
			g = msg[light+3]
			b = msg[light+4]

			self.leds.changeColor(id, (r, g, b))

			light += 5 #5 bytes per light

		return msg[light:]

	@LightParser.command(0x03)
	def parseClear(self, msg):
		self.leds.clear()
		return msg[1:]

	@LightParser.command(0x02)
	def parseSetNumLeds(self, msg):
		numlights = struct.unpack('<H', msg[1:3])[0]

		self.leds.setLedArraySize(numlights)

		return msg[3:]

	@LightParser.command(0x06)
	def parseSetAllLeds(self, msg):

		assert(len(msg) > 3)

		pos = 1
		r = msg[pos]
		g = msg[pos+1]
		b = msg[pos+2]

		for led in xrange(self.leds.ledArraySize):
			self.leds.changeColor(led, (r, g, b))

		return msg[4:]

	@LightParser.command(0x07)
	def parseSetSeries(self, msg):
		start_id = struct.unpack('<H', msg[1:3])[0]
		numlights = struct.unpack('<H', msg[3:5])[0]

		r = msg[5]
		g = msg[6]
		b = msg[7]

		i = start_id
		while i < start_id + numlights:
			self.leds.changeColor(i, (r, g, b))
			i += 1

		return msg[8:]


	@LightParser.command(0x05)
	def parseSetDebug(self, msg):
		debug = msg[1]

		self.debug = debug

		return msg[2:]

class LightClientWss(Client, LightProtocol):

	def __init__(self, host=None, port=None, retry = False, loop = None, debug = False):
		Client.__init__(self, retry = retry, loop = loop)
		LightProtocol.__init__(self, debug=debug)

		self.debug = debug

		if host and port:
			self.connectTo(host, port, useSsl=False)

	def send(self, msg):
		self.sendBinaryMsg(bytes(msg))

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
		
		self.debug_print("writing to {}: {}".format(self.addy, binascii.hexlify(msg)))

		@asyncio.coroutine
		def s2():
			try:
				#print("writing for realz")
				self.writer.write(msg)
				yield asyncio.From (self.writer.drain())
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
				#self.writer.drain()
				yield asyncio.From (self.writer.drain())
			
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


def test_protocol():

	class TestClient(LightProtocol):
		def __init__(self, num_lights=10):

			LightProtocol.__init__(self)

			from lights import LightArray2, OpenCvSimpleDriver
			self.leds = LightArray2(num_lights, OpenCvSimpleDriver())
			self.server = LightProtocol(self.leds, debug=True)

		def send(self, buffer):
			self.server.parse(buffer)


	num_lights = 10
	c = TestClient(num_lights)

	#set all colors to red, green, than blue
	@asyncio.coroutine
	def test_set_color():
		print("test_set_color")
		print("============\n")

		print("setColor: red")
		for i in xrange(num_lights):
			c.setColor(i, (255, 0, 0))

		yield asyncio.From(asyncio.sleep(5))

		print("setColor: green")
		for i in xrange(num_lights):
			c.setColor(i, (0, 255, 0))

		yield asyncio.From(asyncio.sleep(5))

		print("setColor: blue")
		for i in xrange(num_lights):
			c.setColor(i, (0, 0, 255))

		yield asyncio.From(asyncio.sleep(5))

	@asyncio.coroutine
	def test_clear():
		print("test_clear")
		print("==========\n")

		c.clear()
		yield asyncio.From(asyncio.sleep(5))

	@asyncio.coroutine
	def test_set_all():
		print("test_set_all")
		print("============\n")

		print("setAllColor: red")
		c.setAllColor((255, 0 , 0))

		yield asyncio.From(asyncio.sleep(5))

		print("setAllColor: green")
		c.setAllColor((0, 255 , 0))

		yield asyncio.From(asyncio.sleep(5))

		print("setAllColor: blue")
		c.setAllColor((0, 0 , 255))
		yield asyncio.From(asyncio.sleep(5))

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

		yield asyncio.From(asyncio.sleep(5))

	@asyncio.coroutine
	def test_multimsg():
		print("test_multimsg")
		print("============\n")

		msg = '0101000301040006000064'
		msg = bytearray(msg.decode('hex'))

		print("should be blueish...")

		c.send(msg)

		yield asyncio.From(asyncio.sleep(5))

		print("should be a rainbow")

		msg = '013500010a000000ffff00010081ff00020000ff920300007bff04006a00ff05006100000600b500000700ff00000800ff00000900ff7700'
		msg = bytearray(msg.decode('hex'))

		c.send(msg)
		yield asyncio.From(asyncio.sleep(5))

	def test_debug():
		print("test_debug")
		print("============\n")

		c.setDebug(1)
		assert(c.server.debug)

		print("pass")

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
		test_protocol()
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
