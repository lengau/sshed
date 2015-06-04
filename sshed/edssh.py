#!/usr/bin/env python3
"""Wrapper that enforces sshed usage in ssh.

This script was written to allow use of sshed without having to make system
modifications in order to pass an sshed tunnel through.
"""

# TODO: Check the resulting tunnelled socket.

from distutils.spawn import find_executable
import logging
import os
import subprocess
import sys

from sshed import sshed, sshed_client


class SshClient(object):
	"""An SSH client."""

	def __init__(self, executable='ssh'):
		super().__init__()
		self.executable = find_executable(executable)
		executables = ['ssh', 'dbclient']
		while self.executable is None:
			self.executable = find_executable(executables.pop(0))
		if self.executable is None:
			raise ValueError('Could not find your SSH client.')

	SSH_PROJECTS = {
		'OpenSSH': ['6.7'],
		'Dropbear': None,
	}

	@property
	def version(self):
		"""The version of the SSH client."""
		try:
			return self.__version
		except AttributeError:
			self.client_data()
			return self.__version

	@property
	def project(self):
		"""The project this client is attached to."""
		try:
			return self.__project
		except AttributeError:
			self.client_data()
			return self.__project

	def client_data(self):
		"""Return client executable, project, and version.

		Returns:
		A tuple containing the SSH client executable, the project it's from,
		and the version number.
		Examples:
			('/usr/bin/ssh', 'OpenSSH', '6.7p1')
			('/usr/bin/dbclient', 'Dropbear', 'v2014.65')
		"""
		version_data = subprocess.getoutput(' '.join([self.executable, '-V']))
		if version_data.startswith('OpenSSH'):
			self.__project = 'OpenSSH'
			self.__version = version_data.split()[0].split('_')[1]
		elif version_data.startswith('Dropbear'):
			self.__project = 'Dropbear'
			self.__version = version_data.split()[1]
		return (self.executable, self.__project, self.__version)

	def is_valid(self):
		"""Returns whether the SSH client is valid for use with sshed."""
		if self.SSH_PROJECTS.get(self.project) is None:
			return False
		for version in self.SSH_PROJECTS[self.project]:
			if self.version.startswith(version):
				return True
		return False

	def run(self, arguments):
		"""Run the SSH client in its own thread."""
		os.execv(
			#'/bin/echo',
			self.executable,
			[
				os.path.basename(self.executable),
				'-R', ':'.join((self.socket, self.socket)),
				'-t',
			] + arguments + [
				'SSHED_SOCK=%s ' % self.socket,
				os.environ.get('SHELL', 'bash'),
			])


def main():
	logging.basicConfig(format=sshed.LOGGING_FORMAT)
	if '--client' in sys.argv:
		client_index = sys.argv.index('--client')
		client_name = sys.argv[client_index + 1]
		for _ in range(2):
			sys.argv.pop(client_index)
	else:
		client_name = 'ssh'
	client = SshClient(executable=client_name)
	if not client.is_valid():
		logging.error(
			'Invalid SSH client version: %s %s', client.project, client.version)
		logging.error('Client executable was: %s', client.executable)
		sys.exit(1)
	client.socket = sshed.find_socket()
	if client.socket is None:
		# TODO: Open SSHEd client in another process.
		raise NotImplementedError("Can't find an existing sshed socket.")
	client.run(sys.argv[1:])
