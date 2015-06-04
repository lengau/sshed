#!/usr/bin/env python3
"""Client side executable for sshed.

This program needs to be running on the client machine and the SSH client needs
to be properly set up to allow sshed to function properly.
"""

import argparse
import difflib
import logging
import os
import shutil
import socketserver
import subprocess
import sys
import tempfile
import time

from sshed import packethandler, sshed

FOUR_MEGS = 4*2**20


class SocketServer(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
	"""A threaded Unix stream socket server.
	By making the server multithreaded, we should be able to simultaneously
	edit multiple files from one or more SSH sessions.
	"""
	pass


class SocketRequestHandler(socketserver.BaseRequestHandler,
	                       packethandler.PacketHandler):
	"""
	A socket request handler. Handles a single file edit request.
	"""
	PROTOCOL_VERSIONS = range(1,2)
	"""Accepted (known) protocol versions.

	A more detailed description of protocol versions is found in the PROTOCOL.md
	file in the top level source directory of sshed.
	"""

	def setup(self):
		packethandler.PacketHandler.__init__(self, self.request)

	def send_diff(self, original_filename, editing_filename):
		"""Get the different between to files and send it over the socket."""
		with open(original_filename, 'rb') as original:
			original_lines = original.readlines()
		with open(editing_filename, 'rb') as edited:
			edited_lines = edited.readlines()
		diff = difflib.ndiff(original_lines, edited_lines)
		self.request.sendall()

	def simple_respond(self, original_name, editing_name):
		"""Generate a response replying with the entire file.

		This is how protocol version 1 works, and is also used for smaller files
		when appropriate.
		"""
		original_mtime = os.path.getmtime(original_name)
		os.remove(original_name)
		if original_mtime >= os.path.getmtime(editing_name):
			# If it's not edited, we don't need to bother sending anything.
			os.remove(editing_name)
			return
		with open(editing_name, 'rb') as file:
			self.request.sendall(file.read())
		os.remove(editing_name)

	def duplicate_file(self, original, filetype=tempfile.NamedTemporaryFile,
		               **kwargs):
		"""Return a file that duplicates the file passed in.

		Positional arguments:
			original: a file-like object containing the original file.
		Keyword arguments:
			filetype: The class of file object to create.
			**kwargs: Keyword arguments to pass to the object constructor.

		Returns: An object of the time passed in filetype that uses the file
			interface to duplicate the original.
		"""
		location = original.tell()
		original.seek(0)
		copy = filetype(**kwargs)
		shutil.copyfileobj(original, copy)
		copy.seek(0)
		original.seek(location)
		return copy

	def wait_until_edit_or_exit(self, filename, modified_time, process,
		                        sleep_time=0.1):
		"""Wait until a file is edited or a process exits.

		Positional arguments:
			filename: The path to the file to check.
			modified_time: The last modified time against which to check.
			process: The process whose termination we're awaiting.
		Keyword arguments:
			sleep_time: Amount of time in seconds to sleep between checks.
		Returns:
			True if the file is edited; False if the process exits.
		"""
		while True:
			if process.poll() is not None:
				return
			if os.path.getmtime(filename) > modified_time:
				return
			time.sleep(sleep_time)


	def handle(self):
		"""Handle the socket request."""
		original = tempfile.SpooledTemporaryFile(max_size=FOUR_MEGS)
		headers = self.get(file=original)
		if headers.get('Version') not in self.PROTOCOL_VERSIONS:
			logging.error('Unknown protocol version. Dropping connection.')
			logging.error('Protocol version requested: %s', headers['Version'])
			return
		self.version = headers.get('Version')
		self.differential = headers.get('Differential')
		editing = self.duplicate_file(original, prefix=headers['Filename'],
				delete=False)
		editing.close()
		logging.debug('File to edit: %s', headers['Filename'])
		logging.debug('Text editor will open: %s', editing.name)
		editor = sshed.choose_editor()
		logging.debug('Text editor: %s', editor)
		last_modified = os.path.getmtime(editing.name)
		editor = subprocess.Popen(editor + [editing.name])

		repeat = True
		while repeat:
			self.wait_until_edit_or_exit(editing.name, last_modified, editor)
			if last_modified >= os.path.getmtime(editing.name):
				break
			last_modified = os.path.getmtime(editing.name)
			with open(editing.name, 'rb') as editing:
				temporary_file = self.duplicate_file(
					editing, filetype=tempfile.SpooledTemporaryFile,
					max_size=FOUR_MEGS)
			original.seek(0)
			original_lines = original.readlines()
			edited_lines = temporary_file.readlines()
			if original_lines == edited_lines:
				continue
			logging.debug('File has changed.')
			logging.debug('New file: %s', edited_lines)
			# TODO: differential editing
			if (not self.differential or
			    not self.send_diff(original_lines, edited_lines)):
				self.send({'Differential': 'False'}, temporary_file)
			original = temporary_file
		os.remove(editing.name)

	def send_diff(self, original, edited):
		"""Differential-aware file sender.

		NOTE: send_diff will always generate a diff, but may send the file
		without a diff if that ends up being shorter.

		Positional arguments:
			original: An array of bytes objects, each containing a line.
			edited: Like original, but for the edited file.
		"""
		original_strings = [line.decode() for line in original]
		edited_strings = [line.decode() for line in edited]
		edited_length = sum([len(line) for line in edited])
		diff = difflib.unified_diff(original_strings, edited_strings)
		logging.debug('Diff object: %s', diff)
		diff_list = list(diff)
		logging.debug('Diff list: %s', diff_list)
		diff_bytes = ''.join(diff_list).encode('utf-8')
		logging.debug('Diff bytes: %s', diff_bytes)
		logging.debug('Generated diff:\n%s', diff_bytes.decode())
		if len(diff_bytes) > edited_length:
			logging.debug('Diff is longer than edited file. '
			              'Sending file instead.')
			return False
		else:
			headers = dict(
				Differential=True,
				Filesize=edited_length
				# TODO: Add checksum of edited here.
				)
			self.send(headers, diff_bytes)
		return True



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
				raise ValueError('Unknown shell: %s' % shell)
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


def main(args=None):
	if args == None:
		args = parse_arguments()
	logging.basicConfig(format=sshed.LOGGING_FORMAT, level=args.logging_level)
	os.umask(sshed.USER_ONLY_DIRECTORY_UMASK)
	sshed_dir = tempfile.TemporaryDirectory(prefix='sshed-')
	os.umask(sshed.USER_ONLY_UMASK)
	socket_address = args.socket_address or (sshed_dir.name + '/socket')
	socket_var = EnvironmentVarible('SSHED_SOCK', socket_address)
	print(socket_var.generate(args.shell))
	server = SocketServer(socket_address, SocketRequestHandler)
	logging.debug('Socket opened at %s. Serving requests.', socket_address)
	try:
		server.serve_forever()
	except KeyboardInterrupt:
		os.remove(socket_address)



if __name__ == '__main__':
	sys.exit(main(parse_arguments()))
