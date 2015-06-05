#!/usr/bin/env python3
"""Tests for packethandler"""

import copy
import mock
import tempfile
import unittest

from sshed import packethandler

import packethandler_test_data as data


class TestGetHeaders(unittest.TestCase):
	"""Tests for PacketHandler._get_headers"""

	def setUp(self):
		self.socket = mock.Mock()
		self.handler = packethandler.PacketHandler(self.socket)

	def tearDown(self):
		pass

	def testSocketClosedNoHeaders(self):
		"""Raise a SocketClosedError when the socket is already closed."""
		self.socket.recv.return_value = data.CLOSED_SOCKET
		with self.assertRaises(packethandler.SocketClosedError):
			self.handler._get_headers()
		self.socket.recv.assert_called_once_with(4096)

	def testSocketClosedNoHeaders(self):
		"""Raise a SocketClosedError when the socket closes during headers."""
		self.socket.recv.side_effect = data.SOCKET_WITH_PARTIAL_HEADERS
		with self.assertRaises(packethandler.SocketClosedError):
			self.handler._get_headers()
		self.socket.recv.assert_called_with(4096)
		self.assertEqual(self.socket.recv.call_count, 2)

	def testNameWithQuotes(self):
		"""If the name of the header is surrounded in quotation marks"""
		self.socket.recv.return_value = data.SOCKET_WITH_QUOTED_NAME
		self.assertDictEqual(
			data.SOCKET_WITH_QUOTED_NAME_HEADERS, self.handler._get_headers())

	def testCastToNumbers(self):
		"""Successfully cast both floating point and integer numbers."""
		self.socket.recv.return_value = data.SOCKET_WITH_NUMBERS
		headers = self.handler._get_headers()
		self.assertDictEqual(data.SOCKET_WITH_NUMBERS_HEADERS, headers)

	def testCastToBoolean(self):
		"""Successfully cast to bool, but not to None."""
		self.socket.recv.return_value = data.SOCKET_WITH_BOOLEAN
		self.assertDictEqual(
			data.SOCKET_WITH_BOOLEAN_HEADERS, self.handler._get_headers())

	def testContentsWithColonAndSpaces(self):
		"""Test header contents surrounded by quotes and containing a colon."""
		self.socket.recv.return_value = data.SOCKET_WITH_QUOTED_CONTENTS
		self.assertDictEqual(
			data.SOCKET_WITH_QUOTED_CONTENTS_HEADERS,
			self.handler._get_headers())

	def testSplitHeaders(self):
		"""Socket contents have to be recv()'d twice to get all headers."""
		self.socket.recv.side_effect = data.SPLIT_HEADER_SOCKET
		self.assertDictEqual(
			data.SPLIT_HEADER_SOCKET_HEADERS,
			self.handler._get_headers())


class TestGetBytes(unittest.TestCase):
	"""Tests for PacketHandler._get_bytes"""

	def setUp(self):
		self.socket = mock.Mock()
		self.handler = packethandler.PacketHandler(self.socket)
		self.temporary_file = tempfile.SpooledTemporaryFile(max_size=8192)

	def tearDown(self):
		self.temporary_file.close()

	def testSocketAlreadyClosed(self):
		"""Raise a SocketClosedError when the socket is already Closed."""
		self.socket.recv.return_value = data.CLOSED_SOCKET
		with self.assertRaises(packethandler.SocketClosedError):
			self.handler._get_bytes(1)
		with self.assertRaises(packethandler.SocketClosedError):
			self.handler._get_bytes(1, data_file=self.temporary_file)

	def testSocketClosesUnexpectedly(self):
		"""Raise a SocketClosedError when the socket closes during transfer."""
		self.socket.recv.side_effect = data.SOCKET_THAT_CLOSES_PREMATURELY
		with self.assertRaises(packethandler.SocketClosedError):
			self.handler._get_bytes(
				len(data.SOCKET_THAT_CLOSES_PREMATURELY[0]) + 1)

		self.socket.recv.side_effect = data.SOCKET_THAT_CLOSES_PREMATURELY
		with self.assertRaises(packethandler.SocketClosedError):
			self.handler._get_bytes(
				len(data.SOCKET_THAT_CLOSES_PREMATURELY[0]) + 1,
				data_file=self.temporary_file)

	def testSocketExactData(self):
		"""Retrieve the complete data from the socket."""
		self.socket.recv.return_value = data.SOCKET_WITH_DATA
		self.assertEqual(
			data.SOCKET_WITH_DATA,
			self.handler._get_bytes(len(data.SOCKET_WITH_DATA)))

		self.handler._get_bytes(len(data.SOCKET_WITH_DATA), self.temporary_file)
		self.temporary_file.seek(0)
		self.assertEqual(data.SOCKET_WITH_DATA, self.temporary_file.read())

	def testSocketPartialData(self):
		"""Retrieve data from the socket, leaving some in the next packet."""
		self.socket.recv.return_value = data.SOCKET_WITH_DATA
		self.assertEqual(
			data.SOCKET_WITH_DATA[:-1],
			self.handler._get_bytes(len(data.SOCKET_WITH_DATA) - 1))

	def testSocketPartialDataToFile(self):
		"""Retrieve data from the socket, leaving some in the next packet."""
		self.socket.recv.return_value = data.SOCKET_WITH_DATA
		self.handler._get_bytes(
			len(data.SOCKET_WITH_DATA) - 1,
			self.temporary_file)
		self.temporary_file.seek(0)
		self.assertEqual(data.SOCKET_WITH_DATA[:-1], self.temporary_file.read())

	def testSocketMultipleRequests(self):
		"""Retrieve data from the socket using multiple requests."""
		self.socket.recv.side_effect = data.SOCKET_WITH_MULTIPLE_DATA
		self.assertEqual(
			b''.join(data.SOCKET_WITH_MULTIPLE_DATA),
			self.handler._get_bytes(
				len(b''.join(data.SOCKET_WITH_MULTIPLE_DATA))))
		self.assertEqual(
			len(data.SOCKET_WITH_MULTIPLE_DATA),
			self.socket.recv.call_count)

	def testSocketMultipleRequestsToFile(self):
		"""Retrieve data from the socket using multiple requests."""
		self.socket.recv.side_effect = data.SOCKET_WITH_MULTIPLE_DATA
		self.handler._get_bytes(
			len(b''.join(data.SOCKET_WITH_MULTIPLE_DATA)),
			data_file=self.temporary_file)
		self.temporary_file.seek(0)
		self.assertEqual(
			b''.join(data.SOCKET_WITH_MULTIPLE_DATA),
			self.temporary_file.read())
		self.assertEqual(
			len(data.SOCKET_WITH_MULTIPLE_DATA),
			self.socket.recv.call_count)


class TestGet(unittest.TestCase):
	"""Tests for PacketHandler.get"""

	def setUp(self):
		self.socket = mock.Mock()
		self.handler = packethandler.PacketHandler(self.socket)
		self.temporary_file = tempfile.SpooledTemporaryFile(max_size=8192)

	def tearDown(self):
		self.temporary_file.close()

	def testSocketInVariable(self):
		"""Get a packet from the socket once and put data into a variable."""
		self.socket.recv.return_value = data.SOCKET_WITH_EVERYTHING
		headers, socket_data = self.handler.get()
		self.assertDictEqual(data.SOCKET_WITH_EVERYTHING_HEADERS, headers)
		self.assertEqual(data.SOCKET_WITH_EVERYTHING_DATA, socket_data)

	def testSocketInVariableMultipleParts(self):
		"""Get a packet from the socket in multiple parts, to a variable."""
		self.socket.recv.side_effect = data.MULTI_PART_SOCKET_WITH_EVERYTHING
		headers, socket_data = self.handler.get()
		self.assertDictEqual(data.SOCKET_WITH_EVERYTHING_HEADERS, headers)
		self.assertEqual(data.SOCKET_WITH_EVERYTHING_DATA, socket_data)

	def testSocketInFile(self):
		"""Get a packet as a single part and put the data into a file."""
		self.socket.recv.return_value = data.SOCKET_WITH_EVERYTHING
		headers = self.handler.get(data_file=self.temporary_file)
		self.assertDictEqual(data.SOCKET_WITH_EVERYTHING_HEADERS, headers)
		self.temporary_file.seek(0)
		self.assertEqual(
			data.SOCKET_WITH_EVERYTHING_DATA, self.temporary_file.read())

	def testSocketInFileMultipleParts(self):
		"""Get a pcaket in multiple parts and put the data into a file."""
		self.socket.recv.side_effect = data.MULTI_PART_SOCKET_WITH_EVERYTHING
		headers = self.handler.get(data_file=self.temporary_file)
		self.assertDictEqual(data.SOCKET_WITH_EVERYTHING_HEADERS, headers)
		self.temporary_file.seek(0)
		self.assertEqual(
			data.SOCKET_WITH_EVERYTHING_DATA, self.temporary_file.read())


class TestSend(unittest.TestCase):
	"""Tests for sending a packet."""

	def setUp(self):
		self.socket = mock.Mock()
		self.handler = packethandler.PacketHandler(self.socket)
		self.temporary_file = tempfile.SpooledTemporaryFile(max_size=8192)

	def tearDown(self):
		self.temporary_file.close()

	def testGenerateHeaderBytes(self):
		"""Generate a set of bytes for the header."""
		for header in data.HEADER_BYTES_RAW_DATA:
			self.assertEqual(
				header[2],
				packethandler.PacketHandler._generate_header_bytes(
					header[0], header[1]))

	def testDataAsBytes(self):
		self.handler.send(
			data.SOCKET_WITH_EVERYTHING_BASE_HEADERS,
			contents=data.SOCKET_WITH_EVERYTHING_DATA)
		self.socket.sendall.assert_has_calls(
			[
				mock.call(line) for line in data.EVERYTHING_HEADER_LINES
			] + [
				mock.call(b'\n'),
				mock.call(data.SOCKET_WITH_EVERYTHING_DATA)
			],
			any_order=True)

	def testDataAsFile(self):
		self.temporary_file.write(data.SOCKET_WITH_EVERYTHING_DATA)
		self.temporary_file.seek(0)
		self.handler.send(
			data.SOCKET_WITH_EVERYTHING_BASE_HEADERS,
			contents=self.temporary_file)
		self.socket.sendall.assert_has_calls(
			[
				mock.call(line) for line in data.EVERYTHING_HEADER_LINES
			] + [
				mock.call(b'\n'),
				mock.call(data.SOCKET_WITH_EVERYTHING_DATA)
			],
			any_order=True)

	def testNoData(self):
		self.handler.send(data.SOCKET_WITH_EVERYTHING_BASE_HEADERS)
		header_lines = copy.copy(data.EVERYTHING_HEADER_LINES)
		header_lines[-1] = b'Size: 0\n'
		header_lines.append(b'\n')
		self.socket.sendall.assert_has_calls(
			[mock.call(line) for line in header_lines],
			any_order=True)


if __name__ == '__main__':
	unittest.main()
