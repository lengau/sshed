#!/usr/bin/env python3

import argparse
import logging
import os
import platform
import shutil
import socket
import stat
import subprocess
import sys
import tempfile

from sshed import packethandler


# TODO: Use modes from the stat library.
USER_ONLY_UMASK = 0o177
USER_ONLY_DIRECTORY_UMASK = 0o077
LOGGING_FORMAT = '%(levelname)s: %(message)s'


def parse_arguments():
	parser = argparse.ArgumentParser()
	parser.add_argument('file')
	parser.add_argument(
		'-d', '--debug', action='store_const',
		dest='logging_level', const=logging.DEBUG, default=logging.WARNING,
		help='Run in debug mode.')
	parser.add_argument(
		'-a', '--socketaddress',
		dest='socket_address',
		help='Use a specific socket file.')
	return parser.parse_args()


def choose_editor():
	"""Choose an editor to use."""
	editor = (os.environ.get('EDITOR') or os.environ.get('VISUAL') or
	          os.environ.get('SUDO_EDITOR'))
	if not editor or 'sshed' in editor:
		editor = (shutil.which('sensible-editor') or shutil.which('xdg-open') or
		          shutil.which('nano') or shutil.which('ed'))
	logging.debug('Chosen editor: %s', editor)
	return editor.split()


def graphical_session():
	"""Return whether the current session is graphical."""
	#TODO: Detect a Mir session.
	#TODO (issue 2): Detect a graphical session in Windows.
	GRAPHICAL_VARIABLES = [
		'DISPLAY',  # X11
		'WAYLAND_DISPLAY',  # Wayland
		'TERM_PROGRAM',  # OS X
		]
	return True in map(bool, map(os.environ.get, GRAPHICAL_VARIABLES))


def find_socket(socket_address=None):
	"""Return the path to the socket file to use, or None if unable."""
	if not socket_address:
		try:
			socket_address = os.environ['SSHED_SOCK']
		except KeyError:
			logging.error(
				'No SSHED_SOCK environment variable and no socket address '
				'passed via command line.')
			return None
	try:
		file_stats = os.stat(socket_address)
	except FileNotFoundError:
		logging.error('SSHED_SOCK points to a nonexistent file.')
		return None
	if stat.S_ISDIR(file_stats.st_mode):
		logging.warning('SSHED_SOCK points to a directory, not a file.')
		try:
			file_stats = os.stat(socket_address + '/socket')
			socket_address += '/socket'
		except FileNotFoundError:
			logging.error(
				'Specified socket directory (%s) does not contain a valid '
				'socket file.', socket_address)
			return None
	if not stat.S_ISSOCK(file_stats.st_mode):
		logging.error('SSHED_SOCK does not point to a socket.')
		return None
	if not file_stats.st_uid == os.getuid():
		logging.error('Socket is not owned by the current user.')
		return None
	if not stat.S_IMODE(file_stats.st_mode) == (stat.S_IRUSR|stat.S_IWUSR):
		logging.error('Socket access is too permissive.')
		return None
	logging.debug('Socket found: %s', socket_address)
	return socket_address


def write_diff(headers, diff, file):
	"""Update a file using a diff.

	Positional arguments:
		headers: a dictionary containing the packet headers.
		diff: a bytes object containing the diff sent.
		file: a file containing the original data. Also where the changes are
			written.
	"""
	file.seek(0)
	filesize = headers.get('Filesize')
	logging.debug('Diff file repeated below:\n%s', diff)
	diff = diff.split('\n')
	diff.pop(0)
	diff.pop(0)
	output_lines = []
	while True:
		try:
			while not diff[0].startswith('@'):
				diff.pop(0)
		except IndexError:
			break
		starting_line = int(diff.pop(0)[4:-2].split()[0].split(',')[0])
		logging.debug('Moving to line %d.', starting_line)
		while len(output_lines) < starting_line-1:
			output_lines.append(file.readline())
		logging.debug('Diff line: %s', diff[0])
		if diff[0].startswith('+'):
			logging.debug('Inserting line: %s', diff[0])
			output_lines.append(diff.pop(0)[1:])
		elif diff[0].startswith(' '):
			logging.debug('Identical lines')
			diff.pop(0)
			output_lines.append(file.readline())
		elif diff[0].startswith('-'):
			logging.debug('Removing line: %s', diff[0])
			file.readline()
	output_lines.extend(file.readlines())
	file.seek(0)
	file.writelines(output_lines)


def main():
	args = parse_arguments()
	logging.basicConfig(format=LOGGING_FORMAT, level=args.logging_level)
	os.umask(USER_ONLY_UMASK)
	socket_file = find_socket(args.socket_address)
	if socket_file is None:
		logging.warning('Using a host side text editor instead.')
		return subprocess.call(choose_editor() + [args.file])
	client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
	client.connect(socket_file)
	packet_handler = packethandler.PacketHandler(client)
	headers = dict(
		Version=1,
		Filename=os.path.basename(args.file),
		Filesize=os.path.getsize(args.file),
		# TODO: Allow the user to disable differential editing.
		Differential=True)
	with open(args.file, mode='r+b') as file:
		packet_handler.send(headers, file)
		while True:
			file.seek(0)
			try:
				logging.debug('Waiting for response from client')
				headers, edited = packet_handler.get()
				logging.debug('Headers: %s', headers)
				if headers.get('Differential') is True:
					logging.debug('Differential editing enabled.')
					write_diff(headers, edited.decode(), file)
				else:
					logging.debug('Differential editing disabled.')
					file.write(edited)
					file.truncate()
				logging.debug('File updated.')
			except packethandler.SocketClosedError:
				logging.debug('Socket closed. Exiting.')
				return 0


if __name__ == '__main__':
	sys.exit(main())
