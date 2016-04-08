#!/usr/bin/env python

from setuptools import setup, Extension

classifiers = """\
Development Status :: 4 - Beta
Intended Audience :: Developers
License :: OSI Approved :: GNU Lesser General Public License v2 (LGPLv2)
Programming Language :: Python
Topic :: System :: Hardware
Topic :: Software Development :: Libraries :: Python Modules
Operating System :: Unix
Operating System :: POSIX :: Linux
"""

setup(name='lights',
      version='1.0',
      description='Python Light module for working with color LEDs',
      author='Kevron Rees',
      author_email='tripzero.kev@gmail.com',
      url='https://github.com/tripzero/python-lights',
      packages=["lights"],
      install_requires=["trollius"],
      classifiers = filter(None, classifiers.split("\n"))
      )
