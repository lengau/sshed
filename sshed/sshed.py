#!/usr/bin/env python3
"""Host side sshed script.

Designed to be run as "sshed" on the host side in place of a text editor.
"""

import argparse
import logging
import os
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


def parse_arguments(args=None):
    """Parse the arguments in the script and return an argument namespace."""
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
    return parser.parse_args(args=args)


def choose_editor():
    """Choose an editor to use."""
    editor = (
        os.environ.get('EDITOR') or os.environ.get('VISUAL') or
        os.environ.get('SUDO_EDITOR'))
    if not editor or 'sshed' in editor:
        editor = (
            shutil.which('sensible-editor') or shutil.which('xdg-open') or
            shutil.which('nano') or shutil.which('ed'))
    logging.debug('Chosen editor: %s', editor)
    return editor.split()

# TODO: Detect a Mir session.
# TODO (issue 2): Detect a graphical session in Windows.
GRAPHICAL_VARIABLES = [
    'DISPLAY',  # X11
    'WAYLAND_DISPLAY',  # Wayland
    'TERM_PROGRAM', ]  # OS X


def graphical_session():
    """Return whether the current session is graphical."""
    graphical_variable_data = [
        bool(os.environ.get(variable)) for variable in GRAPHICAL_VARIABLES]
    return True in graphical_variable_data


class SocketNotFoundError(Exception):
    """Raised if a socket address cannot be found."""
    pass


# pylint: disable=too-many-return-statements
def find_socket(socket_address=None):
    """Return the path to the socket file to use, or None if unable."""
    if not socket_address:
        try:
            socket_address = os.environ['SSHED_SOCK']
        except KeyError:
            # TODO: Raise this as an error rather than logging.
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
            # TODO: Raise this as an error rather than logging.
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
    if not stat.S_IMODE(file_stats.st_mode) == (stat.S_IRUSR | stat.S_IWUSR):
        logging.error(
            'Socket permissions are not valid. '
            'Socket should be readable and writeable only by its owner.')
        return None
    logging.debug('Socket found: %s', socket_address)
    return socket_address
# pylint: enable=too-many-return-statements


class MalformedDiff(Exception):
    """The diff file handed to Patcher isn't valid."""


class Patcher(object):  # pylint: disable=too-few-public-methods
    """A patcher to patch a diff onto a file."""

    def __init__(self, original, diff):
        """Initialise a Patcher.

        Positional arguments:
            original: A file-like object or iterable of lines with the
                original text
            diff: A list of strings containing the unidiff difference.
        """
        self.original = original
        """The original file as a file-like object."""
        self.hunks = self._get_hunks(diff)
        """The difference as a list of hunks. Each hunk is a list of lines."""
        super().__init__()

    @classmethod
    def _get_hunks(cls, diff):
        """Get a list of hunks from a list of unidiff lines.

        Each hunk is a list of lines in the hunk.
        Each line is a unicode string containing a line from a diff file.

        Positional arguments:
            diff: A list of lines in a unidiff format.

        Returns:
            A list of hunks as defined above.
        """
        hunk = []
        hunks = []
        while len(diff) > 0:
            if diff[0].startswith((b'---', b'+++')):
                diff.pop(0)
                continue
            if diff[0].startswith(b'@@'):
                if hunk != []:
                    hunks.append(hunk)
                    hunk = []
            hunk.append(diff.pop(0))
        if hunk != []:
            hunks.append(hunk)
        return hunks

    def patch(self, output=None):
        """Patch the original file to the output.

        Named arguments:
            output: A file-like object to write the output to or None.

        Returns:
            The post-diff file as a single string if output is None
        """
        # TODO: Rewrite function. Too much indentation.
        if output is None:
            return_data = True
            output = tempfile.SpooledTemporaryFile(max_size=2 ** 20)
        else:
            output.seek(0)
            return_data = False
        line_number = 1
        logging.debug('Hunks: %s', self.hunks)
        for hunk in self.hunks:
            header = hunk[0]
            start_line = header.split()[1][1:]
            if b',' in start_line:
                start_line = start_line.split(b',')[0]
            start_line = int(start_line)
            logging.debug('Start line: %s', start_line)
            while line_number < start_line:
                line = self.original.readline()
                line_number += 1
                logging.debug('Unchanged line: %s', line)
                output.write(line)
            for line in hunk[1:]:
                logging.debug('Handling diff line: %s', line)
                if line.startswith(b'-'):
                    original_line = self.original.readline()
                    line_number += 1
                    if original_line != line[1:]:
                        raise MalformedDiff(
                            'Removed a line from the wrong location.\n'
                            'Original line: %s'
                            'Diff line: %s' % (original_line, line))
                    logging.debug('Removed line: %s', original_line)
                    continue
                if line.startswith(b' '):
                    original_line = self.original.readline()
                    line_number += 1
                    if original_line != line[1:]:
                        raise MalformedDiff(
                            'Claimed same line (line %d) was not the same.\n'
                            'Original line: %s'
                            'Diff line: %s' % (
                                line_number, original_line, line))
                    logging.debug('Identical line: %s', original_line)
                    output.write(original_line)
                    continue
                if line.startswith(b'+'):
                    logging.debug('Added line: %s', line[1:])
                    output.write(line[1:])
        output.writelines(self.original.readlines())
        output.truncate()
        if return_data:
            output.seek(0)
            return output.read()


def main():
    """Entry point for sshed command."""
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
                    diff = edited.splitlines(keepends=True)
                    logging.debug('Diff:\n%s', diff)
                    patcher = Patcher(file, diff)
                    logging.debug('Hunks:\n%s', patcher.hunks)
                    # TOOD: Handle the original and updated file better.
                    with tempfile.NamedTemporaryFile() as output:
                        patcher.patch(output=output)
                        output.seek(0)
                        logging.debug('Updated file: %s', output.read())
                        file.seek(0)
                        output.seek(0)
                        file.write(output.read())
                    file.truncate()
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
