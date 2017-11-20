import PyQt5.QtCore as qcore
from PyQt5.QtGui import QColor
import asyncio
import sys

from quamash import QEventLoop

from photons import BaseAnimation

import signal

def sigint_handler(*args):
	qcore.QCoreApplication.quit()
	sys.exit(0)


def init_event_loop(app = qcore.QCoreApplication(sys.argv)):
	loop = QEventLoop(app)
	asyncio.set_event_loop(loop)
	signal.signal(signal.SIGINT, sigint_handler)

	return loop


class QColorObject(qcore.QObject):
	def __init__(self, index, leds):
		qcore.QObject.__init__(self)
		self.leds = leds
		self.index = index
		self._color = QColor(0, 0, 0)

	@qcore.pyqtProperty(QColor)
	def color(self):
		return self._color

	@color.setter
	def color(self, value):
		self._color = value
		self.leds.changeColor(self.index, [self._color.red(), self._color.green(), self._color.blue()])


class QColorTransform(BaseAnimation):

	_static_animation_tracker = []

	def __init__(self, leds, debug=False):
		BaseAnimation.__init__(self)
		self.leds = leds
		self.debug = debug
		self.animations = qcore.QParallelAnimationGroup()

		QColorTransform._static_animation_tracker.append(self)
		self.animations.finished.connect(self.finished)
		self.animations.finished.connect(lambda: QColorTransform._static_animation_tracker.remove(self))


	def addAnimation(self, led, color, time, fromColor = []):

		if  not len(fromColor):
			prevColor = self.leds.color(led)[:]
		else:
			prevColor = fromColor

		color_animation = QColorObject(led, self.leds)

		animation = qcore.QPropertyAnimation(color_animation, bytes("color", 'utf-8'))
		animation.setDuration(time)
		animation.setStartValue(QColor(prevColor[0], prevColor[1], prevColor[2]))
		animation.setEndValue(QColor(color[0], color[1], color[2]))

		self.animations.addAnimation(animation)


	def start(self):
		self.animations.start()
		return self.promise


	def finished(self):
		self.promise.call()


if __name__ == "__main__":

	import photons as lights

	init_event_loop()

	driver = lights.DummyDriver()
	leds = lights.LightArray2(10, driver)

	def transform():
		xform = QColorTransform(leds)

		xform.addAnimation(0, [255, 255, 255], 10000)

		xform.start().then(lambda: print("final color: {}".format(leds.color(0)))).then(sys.exit, 0)

	transform()

	asyncio.get_event_loop().run_forever()


