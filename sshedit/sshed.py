#!/usr/bin/env python3

import argparse
import os
import shutil
import socket
import subprocess
import sys
import tempfile


# TODO: Use modes from the stat library.
USER_ONLY_UMASK = 0o077
BUFFER_SIZE = 4096


def print_err(*args, **kwargs):
	print('ERROR:', *args, file=sys.stderr, **kwargs)


def parse_arguments():
	parser = argparse.ArgumentParser()
	parser.add_argument('file')
	return parser.parse_args()


def choose_editor():
	"""Choose an editor to use."""
	editor = (os.environ.get('EDITOR') or os.environ.get('VISUAL') or
	          os.environ.get('SUDO_EDITOR'))
	if not editor or 'sshed' in editor:
		editor = (shutil.which('sensible-editor') or shutil.which('xdg-open') or
		          shutil.which('nano') or shutil.which('ed'))
	return editor


def main():
	args = parse_arguments()
	os.umask(USER_ONLY_UMASK)
	client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
	try:
		client.connect(os.environ['SSHED_SOCK'])
	except (FileNotFoundError, KeyError):
		print_err('Cannot open socket to local machine. Using remote editor.')
		subprocess.call([choose_editor(), args.file])
		return 1
	client.send(b'1\n')  # Protocol version
	client.send(os.path.basename(args.file).encode() + b'\n')
	client.send(str(os.path.getsize(args.file)).encode() + b'\n')
	with open(args.file, mode='r+b') as file:
		# TODO: Don't require loading the entire file into memory all at once.
		client.send(file.read())
		# TODO: Only receive the changes from the client.
		file.seek(0)
		buffer = b'\0'
		try:
			while len(buffer) > 0:
				buffer = client.recv(BUFFER_SIZE)
				file.write(buffer)
		except KeyboardInterrupt:
			return 2



if __name__ == '__main__':
	sys.exit(main())
