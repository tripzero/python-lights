#!/usr/bin/env python

import photons
from photons.lightclient import LightClient
import random
import trollius as asyncio

leds = None

def done():
	print("done")

def p(msg):
	print(msg)

def wavelengthToRGB(wavelength):
	gamma = 0.80;
	intensityMax = 255;

	""" Taken from Earl F. Glynn's web page:
	* <a href="http://www.efg2.com/Lab/ScienceAndEngineering/Spectra.htm">Spectra Lab Report</a>
	"""

	factor = None
	r = None
	g = None
	b = None

	if((wavelength >= 380) and (wavelength<440)):
		r = -(wavelength - 440) / (440.0 - 380.0)
		g = 0.0
		b = 1.0
	elif((wavelength >= 440) and (wavelength<490)):
		r = 0.0
		g = (wavelength - 440) / (490.0 - 440.0)
		b = 1.0
	elif((wavelength >= 490) and (wavelength<510)):
		r = 0.0
		g = 1.0
		b = -(wavelength - 510) / (510.0 - 490.0)
	elif((wavelength >= 510) and (wavelength<580)):
		r = (wavelength - 510) / (580.0 - 510.0)
		g = 1.0
		b = 0.0
	elif((wavelength >= 580) and (wavelength<645)):
		r = 1.0
		g = -(wavelength - 645) / (645.0 - 580.0)
		b = 0.0
	elif((wavelength >= 645) and (wavelength<781)):
		r = 1.0
		g = 0.0
		b = 0.0
	else:
		r = 0.0
		g = 0.0
		b = 0.0

	# Let the intensity fall off near the vision limits
	if((wavelength >= 380) and (wavelength<420)):
	    factor = 0.3 + 0.7*(wavelength - 380) / (420.0 - 380.0)
	elif((wavelength >= 420) and (wavelength<701)):
	    factor = 1.0
	elif((wavelength >= 701) and (wavelength<781)):
	    factor = 0.3 + 0.7*(780 - wavelength) / (780.0 - 700.0)
	else:
	    factor = 0.0

	# Don't want 0^x = 1 for x != 0

	r = int(round(intensityMax * pow(r * factor, gamma)))
	g = int(round(intensityMax * pow(g * factor, gamma)))
	b = int(round(intensityMax * pow(b * factor, gamma)))

	return (r, g, b)

def mp(x, in_min, in_max, out_min, out_max):
	return (x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min

def wrap( kX, kLowerBound, kUpperBound):

	range_size = kUpperBound - kLowerBound + 1

	if (kX < kLowerBound):
		kX += range_size * ((kLowerBound - kX) / range_size + 1)

	return kLowerBound + (kX - kLowerBound) % range_size


@asyncio.coroutine
def rainbow():

	delay = 0.01

	offset = 0

	while True:
		if offset > leds.ledArraySize:
			offset = 0

		x = offset

		for led in range(leds.ledArraySize):

			if x >= leds.ledArraySize:
				x = 0

			wavelength = mp(led, 0, leds.ledArraySize, 780, 380)
			color = wavelengthToRGB(wavelength)
			leds.changeColor(x, color)

			#print("x={0}, offset={1}, color={2}".format(x, offset, color))

			x += 1

		offset += 1

		yield asyncio.From(asyncio.sleep(delay))

@asyncio.coroutine
def larsonScanner():

	length = 5
	led = 0
	led2 = leds.ledArraySize - 1
	side1 = 140

	direction = "forward"
	direction2 = "forward"

	delay = 0.02

	while True:

		leds.clear()

		for l in range(length):

			if led + length > side1:
				direction = "backwards"
				continue

			if led < 0:
				direction = "forward"
				continue

			leds.changeColor(led + l, (255, 0, 0))

		for l in range(length):
			if led2 - length < side1:
				direction2 = "backwards"
				break

			if led2 >= leds.ledArraySize:
				direction2 = "forward"
				break

			leds.changeColor(led2 - l, (255, 0, 0))

		if direction == "forward":
			led += 1
		else:
			led -= 1

		if direction2 == "forward":
			led2 -= 1
		else:
			led2 += 1


		yield asyncio.From(asyncio.sleep(delay))

@asyncio.coroutine
def larsonScanner2():

	length = 5
	led = 0
	led2 = leds.ledArraySize - 1
	side1 = 140

	direction = "forward"
	direction2 = "forward"

	delay = 0.05

	while True:

		#leds.clear()

		for l in range(length):

			if led + length > side1:
				direction = "backwards"
				continue

			if led < 0:
				direction = "forward"
				continue

			leds.transformColorTo(led + l, (255, 0, 0), 0.001).then(leds.transformColorTo, led + l, (0, 0, 0), 0.001)

		for l in range(length):
			if led2 - length < side1:
				direction2 = "backwards"
				break

			if led2 >= leds.ledArraySize:
				direction2 = "forward"
				break

			leds.transformColorTo(led2 - l, (255, 0, 0), 0.001).then(leds.transformColorTo, led2 - l, (0, 0, 0), 0.001)

		if direction == "forward":
			led += 1
		else:
			led -= 1

		if direction2 == "forward":
			led2 -= 1
		else:
			led2 += 1


		yield asyncio.From(asyncio.sleep(delay))



@asyncio.coroutine
def chaser():
	print ("doing chaser...")
	loop = asyncio.get_event_loop()

	leds.clear()
	animation = photons.SequentialAnimation()

	delay = 50
	time = leds.ledArraySize * delay

	r = random.randint(0, 255)
	g = random.randint(0, 255)
	b = random.randint(0, 255)

	print ("chase color: ", r, g, b)

	animation.addAnimation(leds.chase, (r, g, b), time, delay)

	animation.start().then(loop.create_task, chaser())

@asyncio.coroutine
def randomRainbowTransforms():
	print( "rainbow...")
	loop = asyncio.get_event_loop()

	concurrentTransform = photons.ConcurrentAnimation()

	r = random.randint(0, 255)
	g = random.randint(0, 255)
	b = random.randint(0, 255)
	for i in range(leds.ledArraySize):
		concurrentTransform.addAnimation(leds.transformColorTo, i, (r,g,b), 1000)

	concurrentTransform.start().then(loop.create_task, randomRainbowTransforms())


def pickRandomAnimation():
	animations = [randomRainbowTransforms, chaser]
	random.choice(animations)()

if __name__ == "__main__":
	import argparse
	import json

	parser = argparse.ArgumentParser()
	parser.add_argument('--debug', dest="debug", help="turn on debugging.", action='store_true')
	parser.add_argument('--num', dest="numLeds", help="number of leds", type=int, default=1)
	parser.add_argument('--fps', dest="fps", help="frames per second", type=int, default=5)
	parser.add_argument('--chase', dest="chase", help="do chase animation in a loop", action='store_true')
	parser.add_argument('--larson', dest="larson", help="do larson animation in a loop", action='store_true')
	parser.add_argument('--rainbow', dest="rainbow", help="do rainbow wave animation in a loop", action='store_true')
	parser.add_argument('--driver', dest="driver", help="driver to use", default=None)
	parser.add_argument('address', help="address", default="localhost", nargs="?")
	parser.add_argument('port', help="port", default=1888, nargs="?")
	parser.add_argument('--device', type=str, dest="device_name", default="", help="particle device name")
	parser.add_argument('--config', type=str, dest="config_name", default="config.json", help="config")
	args = parser.parse_args()

	loop = asyncio.get_event_loop()

	config = None

	try:
		with open(args.config_name,'r') as f:
			config = json.loads(f.read())
	except:
		print("not using config.json.  Not found or bad json")
		pass

	Driver = None
	driver = None
	driver_name = None

	if args.driver:
		driver_name = args.driver
		Driver = photons.getDriver(args.driver)

		if not Driver:
			raise Exception("failed to load driver: {}".format(args.driver))

	elif "driver" in config.keys():
		driver_name = config['driver']
		Driver = photons.getDriver(driver_name)
		if not Driver:
			raise Exception("{} driver not available.  Installed drivers: {}".format(config['driver'], ", ".join(photons.drivers)))

	else:
		raise Exception("No driver specified in config or arguments (--driver)")

	driver = Driver(debug=args.debug)

	if args.device_name:
		import spyrk

		key = config['particleKey']

		s = spyrk.SparkCloud(key)

		if "particleApiServer" in config.keys():
			apiServer = config["particleApiServer"]
			from hammock import Hammock
			s = spyrk.SparkCloud(key, spark_api=Hammock(apiServer))

		print("trying to get ip address and numLights from particle server...")

		args.address = s.devices[args.device_name].ip
		args.numLeds = s.devices[args.device_name].numLights
		print (args.address)

	if driver_name == "LightProtocol":
		driver.connectTo(args.address, args.port)
		driver.setNumLeds(args.numLeds)

	leds = photons.LightArray2(args.numLeds, driver, fps=args.fps)

	leds.clear()

	if args.chase:
		loop.create_task(chaser())
	elif args.rainbow:
		loop.create_task(rainbow())
	elif args.larson:
		loop.create_task(larsonScanner())
	else:
		loop.create_task(randomRainbowTransforms())

	print("running main loop")

	try:
		loop.run_forever()
	except:
		print("bork")
		import traceback, sys
		exc_type, exc_value, exc_traceback = sys.exc_info()
		traceback.print_tb(exc_traceback, limit=1, file=sys.stdout)
		traceback.print_exception(exc_type, exc_value, exc_traceback,
                      limit=8, file=sys.stdout)
