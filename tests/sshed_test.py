#!/usr/bin/env python3
"""Tests for sshed.sshed"""

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

from sshed import sshed

from data import diff1
from data import hunks_data
from data import malformed_diffs

class TestParseArguments(unittest.TestCase):
	"""Tests for sshed.parse_arguments."""

	# Patch stderr so as not to clutter the test output
	@mock.patch('sys.stderr')
	def testRequiresFile(self, _):
		"""Try with no arguments."""
		with self.assertRaises(SystemExit):
			sshed.parse_arguments([])

	def testSucceedsWithFile(self):
		"""Test settings when a file is passed in."""
		args = sshed.parse_arguments(args=['filename'])
		self.assertEqual(args.file, 'filename')
		self.assertEqual(args.logging_level, logging.WARNING)
		self.assertIsNone(args.socket_address)

	def testSucceedsWithFileAndDebug(self):
		args = sshed.parse_arguments(args=['-d', 'filename'])
		self.assertEqual(args.logging_level, logging.DEBUG)
		self.assertEqual(args.file, 'filename')
		self.assertIsNone(args.socket_address)

	def testSucceedsWithFileAndSocket(self):
		args = sshed.parse_arguments(args=['-a', 'socket_address', 'filename'])
		self.assertEqual(args.logging_level, logging.WARNING)
		self.assertEqual(args.file, 'filename')
		self.assertEqual(args.socket_address, 'socket_address')

	def testSucceedsWithFileAndSocketAndDebug(self):
		args = sshed.parse_arguments(
			args=['-d', '-a', 'socket_address', 'filename'])
		self.assertEqual(args.logging_level, logging.DEBUG)
		self.assertEqual(args.file, 'filename')
		self.assertEqual(args.socket_address, 'socket_address')


class TestChooseEditor(unittest.TestCase):
	"""Test editor options."""

	def testEditorFromEditorVariable(self):
		"""Retrieve the editor from the EDITOR environment variable."""
		environment = {
			'EDITOR': 'editor',
			'VISUAL': 'visual',
			'SUDO_EDITOR': 'sudo_editor'
		}
		with mock.patch.dict(os.environ, values=environment, clear=True):
			self.assertEqual(sshed.choose_editor(), [environment['EDITOR']])

	def testEditorFromVisualVariable(self):
		"""Retrieve the editor from the VISUAL environment variable."""
		environment = {
			'VISUAL': 'visual',
			'SUDO_EDITOR': 'sudo_editor'
		}
		with mock.patch.dict(os.environ, values=environment, clear=True):
			self.assertEqual(sshed.choose_editor(), [environment['VISUAL']])

	def testEditorFromSudoEditorVariable(self):
		"""Retrieve the editor from the SUDO_EDITOR environment variable."""
		environment = {
			'SUDO_EDITOR': 'sudo_editor'
		}
		with mock.patch.dict(os.environ, values=environment, clear=True):
			self.assertEqual(sshed.choose_editor(), [environment['SUDO_EDITOR']])

	@mock.patch('shutil.which')
	def testEditorIsSensibleEditor(self, which):
		"""Use sensible-editor os the editor."""
		environment = {}
		which.side_effect = [str(number) for number in range(10)]
		with mock.patch.dict(os.environ, values=environment, clear=True):
			self.assertListEqual(sshed.choose_editor(), ['0'])
		which.assert_called_once_with('sensible-editor')

	@mock.patch('shutil.which')
	def testEditorIsXdgOpen(self, which):
		"""Use xdg-open os the editor."""
		environment = {}
		which.side_effect = [None] + [str(number) for number in range(1, 10)]
		with mock.patch.dict(os.environ, values=environment, clear=True):
			self.assertEqual(sshed.choose_editor(), ['1'])
		which.assert_has_calls([
			mock.call('sensible-editor'),
			mock.call('xdg-open')])

	@mock.patch('shutil.which')
	def testEditorIsNano(self, which):
		"""Use nano os the editor."""
		environment = {}
		which.side_effect = (
			[None] * 2 + [str(number) for number in range(2, 10)])
		with mock.patch.dict(os.environ, values=environment, clear=True):
			self.assertEqual(sshed.choose_editor(), ['2'])
		which.assert_has_calls([
			mock.call('sensible-editor'),
			mock.call('xdg-open'),
			mock.call('nano')])

	@mock.patch('shutil.which')
	def testEditorIsEd(self, which):
		"""Use ed os the editor."""
		environment = {}
		which.side_effect = (
			[None] * 3 + [str(number) for number in range(3, 10)])
		with mock.patch.dict(os.environ, values=environment, clear=True):
			self.assertEqual(sshed.choose_editor(), ['3'])
		which.assert_has_calls([
			mock.call('sensible-editor'),
			mock.call('xdg-open'),
			mock.call('nano'),
			mock.call('ed')])


class TestGraphicalSession(unittest.TestCase):
	"""Test finding a graphical session."""

	def testX11Session(self):
		"""In an X11 session."""
		environment = {'DISPLAY': ':0'}
		with mock.patch.dict(os.environ, values=environment, clear=True):
			self.assertTrue(sshed.graphical_session())

	def testWaylandSession(self):
		"""In a Wayland session."""
		environment = {'WAYLAND_DISPLAY': 'wayland-0'}
		with mock.patch.dict(os.environ, values=environment, clear=True):
			self.assertTrue(sshed.graphical_session())

	def testOSXSession(self):
		"""In an OS X session."""
		environment = {'TERM_PROGRAM': 'iTerm.App'}
		with mock.patch.dict(os.environ, values=environment, clear=True):
			self.assertTrue(sshed.graphical_session())

	def testMultipleSessions(self):
		"""Test within multiple sessions (e.g. XWayland or Wayland on X)."""
		environment = {
			'DISPLAY': ':0',
			'WAYLAND_DISPLAY': 'wayland-0',
		}
		with mock.patch.dict(os.environ, values=environment, clear=True):
			self.assertTrue(sshed.graphical_session())

	def testNonGraphicalSession(self):
		"""Not in a graphical session."""
		environment = {}
		with mock.patch.dict(os.environ, values=environment, clear=True):
			self.assertFalse(sshed.graphical_session())


class TestFindSocket(unittest.TestCase):
	"""Test finding the socket."""

	def setUp(self):
		self.temporary_dir = tempfile.TemporaryDirectory()
		self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
		self.socket.bind(self.temporary_dir.name + '/socket')
		os.chmod(self.socket.getsockname(), stat.S_IRUSR | stat.S_IWUSR)

	def tearDown(self):
		self.socket.close()
		self.temporary_dir.cleanup()

	@mock.patch('logging.error')
	def testAddressNotInEnvironment(self, error_log):
		"""Cannot find socket because environment doesn't contain it."""
		with mock.patch.dict(os.environ, values={}, clear=True):
			self.assertIsNone(sshed.find_socket(socket_address=None))
		error_log.assert_called_once_with(
			'No SSHED_SOCK environment variable and no socket address passed '
			'via command line.')

	def testValidAddressInEnvironment(self):
		"""Socket address in an environment variable"""
		values = {'SSHED_SOCK': self.socket.getsockname()}
		with mock.patch.dict(os.environ, values=values):
			self.assertEqual(
				sshed.find_socket(socket_address=None),
				self.socket.getsockname())

	def testValidAddressPassedIn(self):
		"""Valid socket, address passed in by argument."""
		self.assertEqual(
			sshed.find_socket(socket_address=self.socket.getsockname()),
			self.socket.getsockname())

	@mock.patch('logging.error')
	def testSocketNotFound(self, error_log):
		"""Socket does not exist."""
		self.assertIsNone(sshed.find_socket(
			socket_address=self.temporary_dir.name + '/nonexistent'))
		error_log.assert_called_once_with(
			'SSHED_SOCK points to a nonexistent file.')

	@mock.patch('logging.warning')
	def testSocketIsValidDirectory(self, warning_log):
		"""SSHED_SOCK is a directory containing the (valid) socket."""
		self.assertEqual(
			sshed.find_socket(socket_address=self.temporary_dir.name),
			self.socket.getsockname())
		warning_log.assert_called_once_with(
			'SSHED_SOCK points to a directory, not a file.')

	@mock.patch('logging.warning')
	@mock.patch('logging.error')
	def testSocketIsInvalidDirectory(self, error_log, warning_log):
		"""SSHED_SOCK is a directory that does not contain the socket."""
		os.remove(self.socket.getsockname())
		self.assertIsNone(
			sshed.find_socket(socket_address=self.temporary_dir.name))
		warning_log.assert_called_once_with(
			'SSHED_SOCK points to a directory, not a file.')
		error_log.assert_called_once_with(
			'Specified socket directory (%s) does not contain a valid '
			'socket file.', self.temporary_dir.name)

	@mock.patch('logging.error')
	def testSocketIsRegularFile(self, error_log):
		"""SSHED_SOCK points to a regular file."""
		temporary_file = tempfile.NamedTemporaryFile()
		self.assertIsNone(
			sshed.find_socket(socket_address=temporary_file.name))
		error_log.assert_called_once_with(
			'SSHED_SOCK does not point to a socket.')

	@mock.patch('logging.error')
	@mock.patch('os.getuid')
	def testSocketIsOwnedByWrongUser(self, getuid, error_log):
		"""Socket owner doesn't match the current user."""
		getuid.return_value = os.stat(self.socket.getsockname()).st_uid + 1
		self.assertIsNone(
			sshed.find_socket(socket_address=self.socket.getsockname()))
		getuid.assert_called_once_with()
		error_log.assert_called_once_with(
			'Socket is not owned by the current user.')

	@mock.patch('logging.error')
	def testSocketHasWrongPermissions(self, error_log):
		"""Socket permissions are too broad (or too restrictive)."""
		os.chmod(
			self.socket.getsockname(),
			stat.S_IRUSR | stat.S_IWUSR | stat.S_IWGRP)
		self.assertIsNone(
			sshed.find_socket(socket_address=self.socket.getsockname()))
		error_log.assert_called_once_with(
			'Socket permissions are not valid. '
			'Socket should be readable and writeable only by its owner.')


class testPatcher(unittest.TestCase):
	"""Test Patcher's _get_hunks method."""

	def testGetHunks(self):
		"""Tests for Patcher._get_hunks."""
		hunks = sshed.Patcher._get_hunks(hunks_data.FIRST_DIFF)
		self.assertListEqual(hunks, hunks_data.FIRST_DIFF_HUNKS)

	def testPatch(self):
		"""Test full patches."""
		with open(os.path.join(
			os.path.dirname(os.path.realpath(__file__)),
			'data/diff1_original.txt'), mode='rb') as original_file:
			patcher = sshed.Patcher(original_file, diff1.DIFF)
			self.assertEqual(
				patcher.patch(),
				diff1.FINAL)

	def testMalformedRemove(self):
		"""Test patch() with a bad removal line."""
		with tempfile.SpooledTemporaryFile(max_size=8192) as original:
			original.write(malformed_diffs.ORIGINAL)
			original.seek(0)
			patcher = sshed.Patcher(
				original, malformed_diffs.MALFORMED_REMOVE_DIFF)
			with self.assertRaises(sshed.MalformedDiff):
				patcher.patch()

	def testMalformedSame(self):
		"""Test patch() with a bad removal line."""
		with tempfile.SpooledTemporaryFile(max_size=8192) as original:
			original.write(malformed_diffs.ORIGINAL)
			original.seek(0)
			patcher = sshed.Patcher(
				original, malformed_diffs.MALFORMED_SAME_DIFF)
			with self.assertRaises(sshed.MalformedDiff):
				patcher.patch()


if __name__ == "__main__":
	# logging.basicConfig(level=logging.DEBUG)
	unittest.main()
