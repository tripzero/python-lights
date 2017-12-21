#/usr/bin/env python

import numpy as np
import asyncio
import copy
import math
from array import array

class Id:
	id = None
	staticId = 0
	def __init__(self):
		self.id = Id.staticId
		Id.staticId += 1

class Promise:
	
	_id_count = 0
	_promise_manager = []

	def __init__(self):
		self.success = None
		self.args = []
		self.promise = None
		self.id = Promise._id_count

		Promise._id_count += 1

		Promise._promise_manager.append(self)

		#print("({}) promise created: {}".format(self.id, self.success))


	def __del__(self):
		pass
		#print("({}) promise deleted: {}".format(self.id, self.success))

	def then(self, successCb, *args):

		self.success = successCb

		if len(args) > 0:
			self.args = args

		if not self.promise:
			self.promise = Promise()
		
		return self.promise

	def call(self):
		ret = None
		if self.success == None:
			return

		#print("({}) calling promise: {}".format(self.id, self.success))

		if len(self.args):
			ret = self.success(*self.args)
		else:
			ret = self.success()

		if ret and isinstance(ret, Promise) and self.promise:
			#print("promise future returned a promise.  Auto-attaching to chain")
			ret.then(self.promise.call)
		elif self.promise:
			#print("promise future return value not a promise")
			self.promise.call()

		#this queues up the cleanup after promise.call
		asyncio.get_event_loop().call_soon(Promise._promise_manager.remove, self)


class Chase(Id):
	steps = 0
	step = 0
	led = 0
	color = [0, 0, 0]
	forward = True
	promise = None
	prevColor = (0,0,0)

	def __init__(self, color, steps):
		Id.__init__(self)
		self.color = color
		self.steps = steps
		self.promise = Promise()

	def complete(self):
		self.promise.call()

class ColorTransform(Id):

	def __init__(self, led, targetColor, startColor, redStep, blueStep, greenStep, num_frames):
		Id.__init__(self)
		self.startColor = np.array([float(startColor[0]), float(startColor[1]), float(startColor[2])])
		self.led = led
		self.targetColor = targetColor
		self.redStep = redStep
		self.greenStep = greenStep
		self.blueStep = blueStep
		self.steps = [self.redStep, self.greenStep, self.blueStep]
		self.frame_index = 0
		self.num_frames = num_frames
		self.color = np.array([float(startColor[0]), float(startColor[1]), float(startColor[2])])

		self.promise = Promise()

	def color_as_int(self):
		return [int(math.floor(self.color[0])), int(math.floor(self.color[1])), int(math.floor(self.color[2]))]

	def complete(self):
		self.promise.call()

class TransformToColor(Id):

	def __init__(self, led, targetColor):
		Id.__init__(self)
		self.led = led
		self.targetColor = targetColor
		
		self.promise = Promise()

	def complete(self):
		self.promise.call()

class AnimationFunc:

	def __init__(self, func, args):
		self.func = func
		self.args = args

class BaseAnimation:

	def __init__(self):
		self.animations = []
		self.promise = Promise()
		self.running = False

	def addAnimation(self, animation, *args):
		if len(args) == 0:
			args = None

		self.animations.append(AnimationFunc(animation, args))

	def _do(self, animation):
		methodCall = animation.func
		args = animation.args

		if not methodCall:
			raise Exception("animation is not a method")

		if isinstance(methodCall, BaseAnimation):
			methodCall = methodCall.start

		if not args:
			return methodCall()
		else:
			return methodCall(*args)

	def start(self):
		self.running = True

class SequentialAnimation(BaseAnimation):

	def __init__(self):
		BaseAnimation.__init__(self)

	def start(self):
		if len(self.animations) == 0:
			self.promise.call()
		animation = self.animations.pop(0)
		self._do(animation).then(self._animationComplete)
		return self.promise

	def _animationComplete(self):
		if len(self.animations) == 0:
			self.promise.call()
			return

		animation = self.animations.pop(0)
		self._do(animation).then(self._animationComplete)


class ConcurrentAnimation(BaseAnimation):

	def __init__(self):
		BaseAnimation.__init__(self)

	def start(self):
		for animation in self.animations:
			self._do(animation).then(self._animationComplete, animation)

		return self.promise

	def _animationComplete(self, animation):
		self.animations.remove(animation)

		if len(self.animations) == 0:
			self.promise.call()

class Delay(BaseAnimation):
	def __init__(self, time):
		BaseAnimation.__init__(self)
		#time in miliseconds:
		self.time = time

	@asyncio.coroutine
	def do_sleep(self):
		yield from (asyncio.sleep(self.time / 1000.0))
		self.promise.call()

	def start(self):
		asyncio.get_event_loop().create_task(self.do_sleep())
		
		return self.promise

		
class ColorTransformAnimation(BaseAnimation):
	def __init__(self, leds, debug=False):
		BaseAnimation.__init__(self)
		self.leds = leds
		self.animations = []
		self.debug=debug

	def addAnimation(self, led, color, time, fromColor = []):

		if self._check_animation_already_added(led):
			if self.debug:
				print("Can only support one ColorTransformAnimation per light")
			return

		if  not len(fromColor):
			prevColor = self.leds.color(led)[:]
		else:
			prevColor = fromColor

		
		redDelta = color[0] - prevColor[0]
		greenDelta = color[1] - prevColor[1]
		blueDelta = color[2] - prevColor[2]
		numFrames = self.leds.fps * (time / 1000.0)


		if numFrames < 1.0:
			numFrames = 1.0


		redSteps = redDelta / numFrames
		greenSteps = greenDelta / numFrames
		blueSteps = blueDelta / numFrames

		if self.debug:
			print("color = {}, target = {}".format(prevColor, color))
			print("num frames = {}".format(numFrames))

		if redSteps == 0 and color[0] != prevColor[0]:
			redSteps = 1
		if greenSteps == 0 and color[1] != prevColor[1]:
			greenSteps = 1
		if blueSteps == 0 and color[2] != prevColor[2]:
			blueSteps = 1


		t = ColorTransform(led, color[:], prevColor, redSteps, blueSteps, greenSteps, math.floor(numFrames))
		self.animations.append(t)

	def _check_animation_already_added(self, led):
		for animation in self.animations:
			if animation.led == led:
				return True

		return False

	def start(self):
		BaseAnimation.start(self)
		#print("animation {} started".format(self))
		asyncio.get_event_loop().create_task(self._run())

		return self.promise

	def change_color(self, animation):
		color = animation.color

		steps = animation.steps

		ret = False

		if self.debug:
			print("color a: {}".format(color))
	
		for c in range(3):
			s = steps[c]
			color[c] += s
	
		if self.debug:
			print("color b: {}".format(color))

		animation.frame_index += 1

		if animation.frame_index >= animation.num_frames:
			color = animation.targetColor
			ret = True
			animation.complete()

		#animation.color = color
		self.leds.changeColor(animation.led, animation.color_as_int())

		if self.debug:
			print("led = {}, color = {}. target = {}".format(animation.led, color, animation.targetColor))
			print("start color: {}".format(animation.startColor))
			print("steps: {}".format(steps))
			print("{}/{} complete".format(animation.frame_index, animation.num_frames))

		return ret

	@asyncio.coroutine
	def _run(self):
		#print("trying to run animation for {}".format(self))
		try: 
			done_count = 0
			while done_count < len(self.animations):

				remove_list = []

				for animation in self.animations:
					if self.change_color(animation):
						done_count += 1

				yield from (asyncio.sleep(1.0/self.leds.fps))
		except KeyboardInterrupt:
			raise KeyboardInterrupt
		except:
			print("error in animation loop for {}".format(self))
			import sys, traceback
			exc_type, exc_value, exc_traceback = sys.exc_info()
			traceback.print_tb(exc_traceback, limit=1, file=sys.stdout)
			traceback.print_exception(exc_type, exc_value, exc_traceback, limit=6, file=sys.stdout)

		if self.debug:
			print("animation {} is complete. Calling promise".format(self))

		self.promise.call()
		self.running = False

class LightFpsController:

	def __init__(self, driver, fps=30, loop=asyncio.get_event_loop()):
		self.driver = driver
		self.loop = loop
		self.fps = fps
		self.needsUpdate = False
		self.loop.create_task(self._updateLoop())


	def update(self, data=None):
		if data is not None:
			self.ledsData = data

		self.needsUpdate = True

	def updateNow(self):
		self.driver.update(self.ledsData)

	@asyncio.coroutine
	def _updateLoop(self):
		while True:
			try:
				if self.needsUpdate == True:
					self.updateNow()
					self.needsUpdate = False
			except KeyboardInterrupt:
				raise KeyboardInterrupt
			except:
				print("bork in _doUpdate")
				import traceback, sys
				exc_type, exc_value, exc_traceback = sys.exc_info()
				traceback.print_tb(exc_traceback, limit=1, file=sys.stdout)
				traceback.print_exception(exc_type, exc_value, exc_traceback,
	                          limit=8, file=sys.stdout)

			yield from asyncio.sleep(1.0 / self.fps)

class LightArray2(LightFpsController):

	def __init__(self, ledArraySize, driver, fps=30, loop=asyncio.get_event_loop()):
		LightFpsController.__init__(self, driver, fps, loop)
		self.ledArraySize = 0
		self.ledsData = None
		self.setLedArraySize(ledArraySize)

		import threading

		self.locker = threading.Lock()

	def setLedArraySize(self, ledArraySize):
		self.ledArraySize = ledArraySize
		self.ledsData = np.zeros((ledArraySize, 3), np.uint8)

	def clear(self):
		self.ledsData[:] = [0, 0, 0]
		self.update()

	def changeColor(self, ledNumber, color):
		with self.locker:
			self.ledsData[ledNumber] = color
			self.update()

	def color(self, ledNumber):
		with self.locker:
			return self.ledsData[ledNumber]


	def transformColorTo(self, led, color, time):
		prevColor = self.ledsData[led]
		redSteps = abs(prevColor[0] - color[0])
		greenSteps = abs(prevColor[1] - color[1])
		blueSteps = abs(prevColor[2] - color[2])
		numFrames = int(self.fps * (time / 1000.0))

		redSteps = redSteps / numFrames
		blueSteps = blueSteps / numFrames
		greenSteps = greenSteps / numFrames

		t = TransformToColor(led, color)
		self.loop.create_task(self._doTransformColorTo(t, redSteps, greenSteps, blueSteps, numFrames))
		return t.promise

	@asyncio.coroutine
	def _doTransformColorTo(self, transform, redSteps, greenSteps, blueSteps, numFrames):
		color = self.ledsData[transform.led]

		steps = [redSteps, greenSteps, blueSteps]

		for i in range(numFrames):
			for c in range(3):
				if color[c] < transform.targetColor[c]:
					color[c] += steps[c]
				elif color[c] > transform.targetColor[c]:
					color[c] -= steps[c]

			self.changeColor(transform.led, color)

			yield from (asyncio.sleep(1.0/self.fps))

		transform.complete()


class Ws2801Driver:
	def __init__(self, freqs=800000, debug=None):
		try:
			import mraa
			self.spiDev = mraa.Spi(0)
			self.spiDev.frequency(freqs)
		except:
			print("Ws2801Driver: SPI not available.  Using FakeSPI")
			self.spiDev = FakeSpi()

	def update(self, ledsData):
		self.spiDev.write(bytearray(ledsData.tobytes()))

class PixelFormat:
	gbr = [1, 2, 0]
	bgr = [2, 1, 0]
	rbg = [0, 2, 1]

class FakeSpi:
	def write(self, data):
		pass

class Apa102Driver:

	def __init__(self, freqs=8000000, debug=None, brightness=100, pixel_order=PixelFormat.gbr):
		
		try:
			import mraa
			self.spiDev = mraa.Spi(0)
			self.spiDev.frequency(freqs)
		except:
			print("Apa102Driver: SPI not available.  Using FakeSPI")
			self.spiDev = FakeSpi()

		# Global brightness setting 0-100%
		self.brightness = brightness

		"""
		Set the color order of the lights.  This is used to convert
		RGB (the default format) to the right physical colors on the 
		light.
		"""
		self.pixel_order = pixel_order

		#Constant data structures:
		self.header = [0x00, 0x00, 0x00, 0x00]
		self.numLeds = None

	def _end_frame(self):
		return [0x00] * (self.numLeds + 15 // 16)

	@property
	def brightness(self):
		return self._brightness

	@brightness.setter
	def brightness(self, brightness):
		if brightness >= 0 and brightness <= 100:
			self._brightness = brightness
			self._brightness_5bit = self._calcGlobalBrightness(brightness)
		else:
			print("brightness is out of range (0-100)")

	def _calcGlobalBrightness(self, brightness):
		brightness = 31 * 0.01 * brightness
		brightness = int(brightness)
		msb = 0b11100000
		if brightness > 31:
			brightness = 31

		return msb | brightness

	def power(self, ledsData):
		return np.sum((ledsData / [255, 255, 255] * 0.2))

	def update(self, ledsData):
		if self.numLeds == None:
			self.numLeds = len(ledsData)

		data = bytearray()
		data.extend(self.header)
		po = self.pixel_order
		brightness = self._brightness_5bit

		for rgb in ledsData:
			data.append(brightness)
			# write pixel data
			data.extend([rgb[po[0]], rgb[po[1]], rgb[po[2]]])

		#endframe
		data.extend(self._end_frame())

		self.spiDev.write(data)


class OpenCvSimpleDriver:
	

	def __init__(self, debug=None, size=50, wrap=100, opengl=False):
		self.debug=debug
		self.image = None
		self.size = size
		self.wrap = wrap
		
		print("using size: {}".format(self.size))

		import cv2

		self.imshow = cv2.imshow
		self.waitKey = cv2.waitKey

		if opengl:
			cv2.namedWindow("output", cv2.WINDOW_OPENGL)

		asyncio.get_event_loop().create_task(self.process_cv2_mainloop())

	def update(self, ledsData):
		width = len(ledsData) * self.size
		height = self.size

		if len(ledsData) > self.wrap:
			width = int(self.wrap * self.size)
			height = int(self.size * len(ledsData) / self.wrap)


		if not isinstance(self.image, list):
			self.image = np.zeros((height, width, 3), np.uint8)
			self.imshow("output", self.image)

		x = 0
		i = 0
		y = 0

		for color in ledsData:
			#print("color = {}".format(color))
			self.image[y : y + self.size, x : x + self.size] = color[::-1]
			x += self.size
			i += 1
			if i > self.wrap:
				y += self.size
				x = 0
				i = 0

		self.imshow("output", self.image)

		if not asyncio.get_event_loop().is_running():
			self.waitKey(1)

	@asyncio.coroutine
	def process_cv2_mainloop(self):
		while True:
			self.waitKey(1)
			yield from asyncio.sleep(1.0/60.0) #60 fps...


class OpenCvDriver:
	image = None
	size = 50
	dimensions = None

	def __init__(self, debug=None):
		self.dimensions = (1, 1, 0, 0)

	def update(self, ledsData):
		import cv2

		bottom, right, top, left = self.dimensions
		height = max(right, left, 1)
		width = max(bottom, top, 1)
		if width == 1 and right and left:
			width = 2

		if height == 1 and bottom and top:
			height = 2

		width = width * self.size
		height = height * self.size

		if self.image == None:
			self.image = np.zeros((height, width, 3), np.uint8)

		yStep = height / 8
		xStep = width / 8

		if right != 0:
			yStep = height / (right)
		if bottom != 0:
			xStep = width / (bottom)

		#bottom
		y = height
		x = 0

		if bottom:
			pos = 0
			posEnd = bottom
			for color in ledsData[pos : posEnd]:
				self.image[height - self.size : height, x : x + xStep] = color
				x += xStep

		#right
		if right:
			pos = bottom
			posEnd = pos + right
			for color in ledsData[pos : posEnd]:
				self.image[y - yStep : y, width - self.size : width] = color
				y -= yStep

		#reset steps for top and left
		yStep = height / 8
		xStep = width / 8

		if left != 0:
			yStep = height / (left)
		if top != 0:
			xStep = width / (top)

		x = width

		#top
		if top:
			pos = bottom + right
			posEnd = pos + top
			for color in ledsData[pos : posEnd]:
				self.image[0 : self.size, x - xStep : x] = color
				x -= xStep

		y = 0

		#left
		if left:
			pos = bottom + right + top
			posEnd = pos + left
			for color in ledsData[pos : posEnd]:
				self.image[y : y + yStep, 0 : self.size] = color
				y += yStep

		cv2.imshow("output", self.image)

class DummyDriver:

	def __init__(self, debug=False, **kwargs):
		self.debug = debug

	def update(self, ledsData):
		if self.debug:
			print("DummyDriver -> update() called")

def getDriver(driverName = None):
	try:
		from lights.lightclient import LightClient, LightClientWss, LightClientUdp
	except ImportError:
		from photons import LightClient, LightClientWss, LightClientUdp

	drivers = { "Ws2801" : Ws2801Driver, "Apa102" : Apa102Driver, "OpenCV" : OpenCvDriver, "LightClient" : LightClient, 
				"OpenCVSimple" : OpenCvSimpleDriver, "Dummy" : DummyDriver , "LightClientWss" : LightClientWss,
				"LightClientUdp" : LightClientUdp}

	if driverName and driverName in drivers:
		return drivers[driverName]

	print("driver {} not supported".format(driverName))
	print("supported drivers:")

	for driver in drivers.keys():
		print("\t{}".format(driver))

	return None


if __name__ == "__main__":

	driver = getDriver("Dummy")()

	lights = LightArray2(10, driver)

	for i in range(10):
		lights.changeColor(i, (255, 255, 255))

	asyncio.get_event_loop().run_forever()
