import string
#!/usr/bin/env python3
"""Client side executable for sshed.

This program needs to be running on the client machine and the SSH client needs
to be properly set up to allow sshed to function properly.
"""

import argparse
import logging
import os
import socketserver
import subprocess
import sys
import tempfile

import sshed

# TODO: Use modes from the stat library.
USER_ONLY_UMASK = 0o077
LOGGING_FORMAT = '%(levelname)s: %(message)s'


class SocketServer(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
	"""A threaded Unix stream socket server.
	By making the server multithreaded, we should be able to simultaneously
	edit multiple files from one or more SSH sessions.
	"""
	pass


class SocketClosedError(Exception):
	"""An error to be raised when a socket is unexpectedly closed."""
	pass


class SocketRequestHandler(socketserver.BaseRequestHandler):
	"""
	A socket request handler. Handles a single file edit request.
	"""

	def get_line(self):
		"""Get a line of data from the socket, excluding the ending newline."""
		try:
			line_length = self.buffer.find(b'\n')
		except AttributeError:
			self.buffer = b''
			line_length = -1
		while line_length == -1:
			self.buffer += self.request.recv(sshed.BUFFER_SIZE)
			line_length = self.buffer.find(b'\n')
		line, self.buffer = self.buffer.split(b'\n', 1)
		logging.debug('Received line: %s', line)
		return line

	def get_bytes(self, length, file=None):
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
					return
				return message + seg
			if file:
				file.write(self.buffer)
			else:
				message += self.buffer
			written += len(self.buffer)
			self.buffer = self.request.recv(sshed.BUFFER_SIZE)
			if len(self.buffer) == 0:
				raise SocketClosedError()
		raise Exception(
			'Please file a bug in sshed. '
			'sshed_client.SocketRequestHandler.get_bytes should never terminate'
			'its loop.')

	def handle(self):
		"""Handle the socket request."""
		protocol_version = self.get_line()
		if protocol_version != b'1':
			logging.error('Unknown protocol version. Dropping connection.')
			logging.error('Protocol version: %s' % protocol_version)
			return
		filename = self.get_line().decode()
		logging.debug('Filename to edit: %s', filename)
		length = self.get_line()
		try:
			self.length = int(length)
		except ValueError:
			# If we receive invalid data, simply drop the connection.
			logging.error('Length cannot be %s', length)
			return
		logging.debug('Length of file: %s', self.length)
		file = tempfile.NamedTemporaryFile(prefix='%s_' % filename, delete=False)
		filename = file.name
		self.get_bytes(self.length, file=file)
		file.close()
		# TODO: Any text editor.
		subprocess.call(['kate', '-b', filename])
		# TODO: Only report back modifications to the file.
		with open(filename, 'rb') as file:
			self.request.sendall(file.read())
		os.remove(filename)


def parse_arguments():
	"""Parse the arguments handed into the program. Returns a namespace."""
	parser = argparse.ArgumentParser()
	parser.add_argument(
		'-d', '--debug', action='store_const',
		dest='logging_level', const=logging.DEBUG, default=logging.WARNING,
		help='Run in debug mode.')
	# TODO: Daemonize sshed_client.
	parser.add_argument(
		'--shell',
		default=None,
		help='Generate commands for the chosen shell on stdout.')
	parser.add_argument(
		'-b', '--bash', action='store_const',
		dest='shell', const='bash',
		help='Generate bash commands on stdout.')
	parser.add_argument(
		'-a', '--socketaddress',
		help='Give the socket a specific filename.')
	return parser.parse_args()


def main(args):
	logging.basicConfig(format=LOGGING_FORMAT, level=args.logging_level)
	os.umask(USER_ONLY_UMASK)
	sshed_dir = tempfile.TemporaryDirectory(prefix='sshed-')
	# TODO: Allow manually setting the socket location.
	socket_address = args.socketaddress or sshed_dir.name
	print('export SSHED_SOCK=%s' % socket_address)
	if socket_address == sshed_dir.name:
		socket_address += '/socket'
	server = SocketServer(socket_address, SocketRequestHandler)
	logging.debug('Socket opened at %s. Serving requests.', socket_address)
	try:
		server.serve_forever()
	except KeyboardInterrupt:
		os.remove(socket_address)



if __name__ == '__main__':
	sys.exit(main(parse_arguments()))
