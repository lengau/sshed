#!/usr/bin/env python3
"""Client side executable for sshed.

This program needs to be running on the client machine and the SSH client needs
to be properly set up to allow sshed to function properly.
"""

import argparse
import os
import socketserver
import subprocess
import sys
import tempfile

import sshed

# TODO: Use modes from the stat library.
USER_ONLY_UMASK = 0o077


class SocketServer(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
	"""A threaded Unix stream socket server.
	By making the server multithreaded, we should be able to simultaneously
	edit multiple files from one or more SSH sessions.
	"""
	pass


class SocketRequestHandler(socketserver.BaseRequestHandler):
	"""
	A socket request handler. Handles a single file edit request.
	"""

	def get_line(self):
		"""Get a line of data from the socket."""
		try:
			line_length = self.data.find(b'\n')
		except AttributeError:
			self.data = b''
			line_length = -1
		while line_length == -1:
			self.data += self.request.recv(sshed.BUFFER_SIZE)
			line_length = self.data.find(b'\n')
		line, self.data = self.data.split(b'\n', 1)
		return line

	def handle(self):
		protocol_version = self.get_line()
		if protocol_version != b'1':
			sshed.print_err('Unknown protocol version.')
			return
		filename = self.get_line().decode()
		length = self.get_line()
		try:
			self.length = int(length)
		except ValueError:
			# If we receive invalid data, simply drop the connection.
			sshed.print_err('Length cannot be', length)
			return
		# TODO: Only report back modifications to the file.
		file = tempfile.NamedTemporaryFile(prefix='%s_' % filename, delete=False)
		filename = file.name
		file.write(self.data)
		while file.tell() < self.length:
			self.data = self.request.recv(sshed.BUFFER_SIZE)
			file.write(self.data)
		file.close()
		# TODO: Any text editor.
		subprocess.call(['kate', '-b', filename])
		with open(filename, 'rb') as file:
			self.request.sendall(file.read())
		os.remove(filename)


def parse_arguments():
	"""Parse the arguments handed into the program. Returns a namespace."""
	parser = argparse.ArgumentParser()
	parser.add_argument(
		'-d', '--debug', action='store_true',
		help=(
			'Run in debug mode. Currently does nothing as we cannot '
			'daemonize yet.'))
	# TODO: Daemonize sshed_client.
	parser.add_argument(
		'-a', '--socketaddress',
		help='Give the socket a specific filename.')
	return parser.parse_args()


def main(args):
	os.umask(USER_ONLY_UMASK)
	sshed_dir = tempfile.TemporaryDirectory(prefix='sshed-')
	# TODO: Allow manually setting the socket location.
	socket_address = args.socketaddress or sshed_dir.name
	print('export SSHEDIT_SOCK=%s' % socket_address)
	if socket_address == sshed_dir.name:
		socket_address += '/socket'
	server = SocketServer(socket_address, SocketRequestHandler)
	try:
		server.serve_forever()
	except KeyboardInterrupt:
		os.remove(socket_address)



if __name__ == '__main__':
	sys.exit(main(parse_arguments()))
