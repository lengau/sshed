#!/usr/bin/env python3
"""Tests for sshed.sshed"""

import unittest

from sshed import sshed


class TestChooseEditor(unittest.TestCase):
	def setUp(self):
		# Called before the first testfunction is executed
		pass

	def tearDown(self):
		# Called after the last testfunction was executed
		pass

	def testFail(self):
		assert 1 == 1

	def testChooseEditor(self):
		sshed.choose_editor()

if __name__ == "__main__":
	unittest.main()
