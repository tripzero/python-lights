from photons import LightFpsController
import numpy as np

def invert_rows(img):
		r = 1
		height, width, layers = img.shape

		inverted_img = img.copy()

		while r < height:
			inverted_img[r] = img[r, ::-1]
			r+=2

		return inverted_img

class Matrix(LightFpsController):

	def __init__(self, driver=None, width=16, height=9, fps=30, invert_rows_on_update = False):
		LightFpsController.__init__(self, driver = driver, fps = fps)
		self.height = height
		self.width = width
		self.ledsData = np.zeros((height*width, 3), np.uint8)
		self.ledArraySize = width * height
		self.invert_rows_on_update = invert_rows_on_update

	def update(self, frame=None):
		if frame is not None:
			h, w, l = frame.shape
			frame = np.reshape(frame, (h*w, 3))
			self.ledsData = frame

		if self.invert_rows_on_update:
			frame = invert_rows(self.ledsData)

		LightFpsController.update(self, frame)

	def color(self, led_index):
		return self.ledsData[led_index]

	def colorMatrix(self, x, y):
		return self.ledsData[x + (y * self.width) - 1]

	def changeColor(self, led_index, color):
		self.ledsData[led_index] = color
		self.update()

	def changeColorMatrix(self, x, y, color):
		pos = x + (y * self.width) - 1
		self.ledsData[pos] = color
		self.update()

	def clear(self):
		self.ledsData[:] = [0, 0, 0]
		self.update()