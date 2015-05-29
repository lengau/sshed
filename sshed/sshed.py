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

import packethandler


# TODO: Use modes from the stat library.
USER_ONLY_UMASK = 0o177
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
		Filesize=os.path.getsize(args.file))
	with open(args.file, mode='r+b') as file:
		packet_handler.send(headers, file)
		while True:
			file.seek(0)
			try:
				logging.debug('Waiting for response from client')
				packet_handler.get(file)
				logging.debug('Response written to file.')
			except packethandler.SocketClosedError:
				logging.debug('Socket closed. Exiting.')
				return 0


if __name__ == '__main__':
	sys.exit(main())
