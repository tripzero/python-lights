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

	def __init__(self, driver=None, width=16, height=9):
		LightFpsController.__init__(self, driver=driver)
		self.height = height
		self.width = width
		self.ledsData = np.zeros((height*width, 3), np.uint8)

	def update(self, frame=None):
		if frame is not None:
			h, w, l = frame.shape
			frame = np.reshape(frame, (h*w, 3))
			LightFpsController.update(self, frame)

		LightFpsController.update(self)

	def changeColor(self, x, y, color):
		self.ledsData[x*y] = color

	def clear(self):
		self.ledsData[:] = [0, 0, 0]
		self.update()