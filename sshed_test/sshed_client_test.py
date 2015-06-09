#!/usr/bin/env python3
"""Tests for sshed.sshed_client"""

import logging
import os
import socket
import stat
import tempfile
import unittest
try:
	from unittest import mock
except ImportError:
	import mock

from sshed import sshed_client


class TestDuplicateFile(unittest.TestCase):
	"""Tests for sshed.parse_arguments."""

	# Patch stderr so as not to clutter the test output
	@mock.patch('sys.stderr')
	def testRunsSuccessfully(self, _):
		"""Run duplicate_file and check that it succeeds."""
		with open(os.path.join(
			os.path.dirname(os.path.realpath(__file__)),
			'data/diff1_original.txt'), mode='rb') as original_file:
			copy = sshed_client.duplicate_file(original_file)
			self.assertEqual(original_file.read(), copy.read())
