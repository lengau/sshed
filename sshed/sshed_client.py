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
		with tempfile.NamedTemporaryFile(
			prefix='%s_' % filename, delete=False) as file:
			filename = file.name
			self.get_bytes(self.length, file=file)
		editor = sshed.choose_editor()
		subprocess.call(editor + [filename])
		# TODO: Only report back modifications to the file.
		with open(filename, 'rb') as file:
			self.request.sendall(file.read())
		os.remove(filename)


class EnvironmentVarible(object):
	"""Environment variable exporter.

	Generates specialised commands for exporting environment variables in a
	variety of shells.
	"""
	SHELL_FORMATS = {
		'csh': 'setenv {name} {contents}',
		'fish': 'setenv {name} {contents}',
		'bash': 'export {name}={contents}',
	}
	def __init__(self, name, contents):
		self.name = name
		self.contents = contents

	def generate(self, shell, smart=True):
		"""Generate a command string to set an environment variable.

		Positional arguments:
			shell: The name of the shell for which to generate the command.

		Keyword arguments:
			smart: Whether to use smart detection for unknown shells.

		Returns:
			A string containing the command string.
		"""
		if shell not in self.SHELL_FORMATS:
			if smart:
				if shell.endswith('csh'):
					shell = 'csh'
				else:
					shell = 'bash'
			else:
				raise ValueError('Unknown shell %s' % value)
		return self.SHELL_FORMATS[shell].format(
			name=self.name, contents=self.contents)


def parse_arguments():
	"""Parse the arguments handed into the program. Returns a namespace."""
	parser = argparse.ArgumentParser()
	parser.add_argument(
		'-d', '--debug', action='store_const',
		dest='logging_level', const=logging.DEBUG, default=logging.WARNING,
		help='Run in debug mode.')
	# TODO: Daemonize sshed_client.

	shell_group = parser.add_argument_group(
		title='Shell choice arguments',
		description=('Arguments that allow manually specifying the shell '
		             'for which to generate the commands to set environment '
		             'variables.'))
	shell = shell_group.add_mutually_exclusive_group()
	shell.add_argument(
		'--shell',
		default=None,
		help=('Specify the shell for which to write commands. Default is to '
		      'detect from the SHELL environment variable or (if undetected) '
		      'fall back to bash.'))
	shell.add_argument(
		'-b', '--bash', action='store_const',
		dest='shell', const='bash',
		help='Generate bash commands. Shortcut for "--shell bash".')
	shell.add_argument(
		'-c', '--csh', action='store_const',
		dest='shell', const='csh',
		help='Generate csh commands. Shortcut for "--shell csh".')
	shell.add_argument(
		'--fish', action='store_const',
		dest='shell', const='fish',
		help='Generate fish commands. Shortcut for "--shell fish".')

	parser.add_argument(
		'-a', '--socketaddress',
		dest='socket_address',
		help='Give the socket a specific filename.')
	args = parser.parse_args()
	if not args.shell:
		args.shell = os.path.basename(os.environ.get('SHELL')) or 'bash'
	return args


def main(args):
	logging.basicConfig(format=sshed.LOGGING_FORMAT, level=args.logging_level)
	os.umask(sshed.USER_ONLY_UMASK)
	sshed_dir = tempfile.TemporaryDirectory(prefix='sshed-')
	socket_address = args.socket_address or sshed_dir.name
	socket_var = EnvironmentVarible('SSHED_SOCK', socket_address)
	print(socket_var.generate(args.shell))
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
