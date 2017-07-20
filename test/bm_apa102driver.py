import photons
import numpy as np
import timeit

leds = np.zeros((1000, 3), np.uint8)
apadriver = photons.Apa102Driver()

def do_test_update():
	apadriver.update(leds)


def run_bm_update():
	t = timeit.timeit(stmt="do_test_update()", setup="from __main__ import do_test_update", number=10000)

	return t

if __name__ == "__main__":
	
	t = run_bm_update()
	print("do_test_update: {}".format(t))

