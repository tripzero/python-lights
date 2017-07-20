import photons
import numpy as np
import timeit
import binascii
from fakelightarray import FakeLightArray2

parser = photons.LightProtocol(leds=FakeLightArray2())

message = parser.writeHeader(bytearray(binascii.unhexlify(b'010a000000ffff00010081ff00020000ff920300007bff04006a00ff05006100000600b500000700ff00000800ff00000900ff7700')))

def do_test_parse():
	parser.parse(message)

def run_bm_parse():
	t = timeit.timeit(stmt="do_test_parse()", setup="from __main__ import do_test_parse", number=1000000)

	return t

if __name__ == "__main__":
	
	t = run_bm_parse()
	print("do_test_update: {}".format(t))