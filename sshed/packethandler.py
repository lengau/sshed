#
# Packet handler for SSHed
# Copyright © 2015  Alex M. Lowe <lengau@gmail.com>
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import os

BUFFER_SIZE = 4096

class SocketClosedError(Exception):
	"""An error to be raised when a socket is unexpectedly closed."""
	pass


class PacketHandler(object):
	"""Handles incoming packets and generates outgoing packets."""
	STRING_TO_BOOL = {'True':True, 'False':False}

	def __init__(self, socket):
		self.socket = socket
		"""The socket on which the handler sends and receives packets."""
		self.buffer = b''

	def get(self, file=None):
		"""Get a packet from the socket.

		Returns:
			A dictionary containing the headers if file is set.
			If file is None, a tuple containing the headers dictionary and a
			bytes object containing the data.
		"""
		headers = self._get_headers()
		data = self._get_bytes(headers.get('Size', 0), file=file)
		if data is None:
			return headers
		return (headers, data)

	def _get_headers(self):
		"""Retrieve the headers of a packet.

		Returns:
			A dictionary containing the packet headers.
		"""
		headers_length = self.buffer.find('\n\n'.encode('utf-8'))
		while headers_length == -1:
			new_data = self.socket.recv(BUFFER_SIZE)
			self.buffer += new_data
			headers_length = self.buffer.find('\n\n'.encode('utf-8'))
			if headers_length == -1 and len(new_data) == 0:
				raise SocketClosedError(
					'Socket closed whilst retrieving headers. '
					'Raw packet data: %s', self.buffer)
		raw_headers, self.buffer = self.buffer.split('\n\n'.encode('utf-8'), 1)
		raw_headers = raw_headers.decode('utf-8').split('\n')
		headers = {}
		for header in raw_headers:
			name, contents = map(str.strip, header.split(':'))
			if name.startswith('"') and name.endswith('"'):
				name = name[1:-1]
			if contents.startswith('"') and contents.endswith('"'):
				contents = contents[1:-1]
			try:
				contents = int(contents)
			except ValueError:
				pass
			if contents in self.STRING_TO_BOOL:
				contents = self.STRING_TO_BOOL[contents]
			headers[name] = contents
		return headers

	def _get_bytes(self, length, file=None):
		"""Get the specified number of bytes from the socket.

		Return the specified number of bytes from the socket unless the file
		argument is set, in which case it writes to file and returns nothing.

		Positional arguments:
			length: The length (in bytes) of the expected output.

		Keyword arguments:
			file: A file-like object into which to place the bytes.
				Specific methods required are write and tell.

		Returns:
			A bytes object containing the socket data if no file is specified.
			Nothing if there is a file specified.

		Raises:
			SocketClosedError: If the socket is closed before the full message
				is received.
		"""
		written = 0
		message = b''
		while written < length:
			if len(self.buffer) >= (length - written):
				seg, self.buffer = (self.buffer[:length], self.buffer[length:])
				if file:
					file.write(seg)
					file.truncate()
					return
				return message + seg
			if file:
				file.write(self.buffer)
			else:
				message += self.buffer
			written += len(self.buffer)
			self.buffer = self.socket.recv(BUFFER_SIZE)
			if len(self.buffer) == 0:
				raise SocketClosedError()
		raise Exception(
			'Please file a bug in sshed. '
			'packethandler.PacketHandler._get_bytes should never terminate'
			'its loop.')

	def send(self, headers, file=None):
		"""Send data over the socket.

		If a Size header exists, it will be overwritten by the sensed size of
		the file.

		Positional arguments:
			headers: A dictionary containing the headers to send.
			file: A file-like object or a bytes object to send
		"""
		if isinstance(file, bytes):
			headers['Size'] = len(file)
		else:
			file.seek(0, os.SEEK_END)
			headers['Size'] = file.tell()
			file.seek(0, os.SEEK_SET)
		for header in headers:
			header_string = '%s: %s\n' % (header, headers[header])
			self.socket.sendall(header_string.encode('utf-8'))
		self.socket.sendall(b'\n')
		if isinstance(file, bytes):
			self.socket.sendall(file)
		else:
			self.socket.sendall(file.read())
