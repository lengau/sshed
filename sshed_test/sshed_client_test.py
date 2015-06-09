#!/usr/bin/env python3
"""Tests for sshed.sshed_client"""

import logging
import os
import socket
import stat
import tempfile
import timeit
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


class TestWaitUntilEditOrExit(unittest.TestCase):
	"""Test the logic in wait_until_edit_or_exit."""

	def setUp(self):
		"""Create mock objects for testing wait_until_edit_or_exit."""
		self.process = mock.Mock()

	@mock.patch('time.sleep')
	@mock.patch('os.path.getmtime')
	def testAlreadyExited(self, getmtime, sleep):
		"""Test immediate return when the process has already exited."""
		self.process.poll.return_value = 0
		getmtime.return_value = 0
		self.assertIsNone(sshed_client.wait_until_edit_or_exit(
			'filename', 0, self.process, sleep_time=0.001))
		self.process.poll.assert_called_once_with()
		self.assertEqual(0, getmtime.call_count)
		self.assertEqual(0, sleep.call_count)

	@mock.patch('time.sleep')
	@mock.patch('os.path.getmtime')
	def testAlreadyModified(self, getmtime, sleep):
		"""Test immediate return when the file has already been modified."""
		self.process.poll.return_value = None
		getmtime.return_value = 1
		self.assertIsNone(sshed_client.wait_until_edit_or_exit(
			'filename', 0, self.process, sleep_time=0.001))
		self.process.poll.assert_called_once_with()
		getmtime.assert_called_once_with('filename')
		self.assertEqual(0, sleep.call_count)

	@mock.patch('time.sleep')
	@mock.patch('os.path.getmtime')
	def testSleepCorrectly(self, getmtime, sleep):
		"""Test that wait_until_edit_or_exit sleeps as expected."""
		self.process.poll.side_effect = [None, None, 0]
		getmtime.return_value = 0
		self.assertIsNone(sshed_client.wait_until_edit_or_exit(
			'filename', 0, self.process, sleep_time=0.001))
		self.assertEqual(3, self.process.poll.call_count)
		self.assertEqual(2, getmtime.call_count)
		self.assertEqual(2, sleep.call_count)
		sleep.assert_called_with(0.001)


class TestSocketRequestHandler(unittest.TestCase):
	# TODO: Tests for SocketRequestHandler
	pass


class TestEnvironmentVariable(unittest.TestCase):
	"""Tests for EnvironmentVariable."""

	def setUp(self):
		self.var = sshed_client.EnvironmentVarible('var_name', 'var_contents')

	def testGenerateShellInFormats(self):
		"""Generate when the shell has a known format."""
		self.var.SHELL_FORMATS = {
			'known_shell': 'name={name}, contents={contents}'}
		self.assertEqual(
			self.var.generate('known_shell'),
			'name=var_name, contents=var_contents')

	def testGenerateRaisesValueErrorWhenNotSmart(self):
		"""Raise a ValueError when in an unknown shell."""
		self.var.SHELL_FORMATS = {}
		with self.assertRaises(ValueError):
			self.var.generate('unknown_shell', smart=False)

	def testGenerateCshOption(self):
		"""Generate a setenv command for csh-like shells."""
		self.var.SHELL_FORMATS['csh'] = 'name={name}, contents={contents}'
		self.assertEqual(
			self.var.generate('some_sort_of_csh'),
			'name=var_name, contents=var_contents')

	def testGenerateBashOption(self):
		"""Generate an export command for bash-like shells."""
		self.var.SHELL_FORMATS['bash'] = 'name={name}, contents={contents}'
		self.assertEqual(
			self.var.generate('some_sort_of_bash'),
			'name=var_name, contents=var_contents')


class TestParseArguments(unittest.TestCase):
	"""Tests for parse_arguments."""

	@mock.patch('os.environ')
	@mock.patch('os.path.basename')
	def testWithShell(self, basename, environ):
		"""Parse arguments with a shell set."""
		args = sshed_client.parse_arguments(['-b'])
		self.assertEqual('bash', args.shell)

		args = sshed_client.parse_arguments(['-c'])
		self.assertEqual('csh', args.shell)

		args = sshed_client.parse_arguments(['--fish'])
		self.assertEqual('fish', args.shell)

		args = sshed_client.parse_arguments(['--shell', 'custom_shell'])
		self.assertEqual('custom_shell', args.shell)

	@mock.patch('os.environ')
	def testShellInEnvironment(self, environ):
		"""Parse arguments and get shell from the environment."""
		environ.get.return_value = '/bin/shell_from_environment'
		args = sshed_client.parse_arguments([])
		environ.get.assert_called_with('SHELL', '')
		self.assertEqual('shell_from_environment', args.shell)

	@mock.patch('os.environ')
	def testFallbackToBash(self, environ):
		"""Parse arguments and fall back to bash."""
		environ.get.return_value = ''
		args = sshed_client.parse_arguments([])
		environ.get.assert_called_with('SHELL', '')
		self.assertEqual('bash', args.shell)


if __name__ == '__main__':
	unittest.main()
