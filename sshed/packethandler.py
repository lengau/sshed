# Packet handler for SSHed
# Copyright © 2015  Alex M. Lowe <lengau@gmail.com>
#
"""Parser and writer for sshed packets.
"""

import os

BUFFER_SIZE = 4096


class SocketClosedError(Exception):
    """An error to be raised when a socket is unexpectedly closed."""
    pass


class PacketHandler(object):
    """Handles incoming packets and generates outgoing packets."""
    STRING_TO_BOOL = {'True': True, 'False': False}

    def __init__(self, socket):
        self.socket = socket
        """The socket on which the handler sends and receives packets."""
        self.buffer = b''

    def get(self, data_file=None):
        """Get a packet from the socket.

        Named arguments:
            data_file: A file-like object into which to put the data.

        Returns:
            A dictionary containing the headers if data_file is set.
            If data_file is None, a tuple containing the headers dictionary and
            a bytes object containing the data.
        """
        headers = self._get_headers()
        data = self._get_bytes(headers.get('Size', 0), data_file=data_file)
        if data_file is None:
            return (headers, data)
        return headers

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
            name, contents = [str.strip(x) for x in header.split(':', 1)]
            if name.startswith('"') and name.endswith('"'):
                name = name[1:-1]
            try:
                contents = int(contents)
            except ValueError:
                pass
            else:
                headers[name] = contents
                continue
            try:
                contents = float(contents)
            except ValueError:
                pass
            else:
                headers[name] = contents
                continue
            if contents in self.STRING_TO_BOOL:
                contents = self.STRING_TO_BOOL[contents]
            else:
                if contents.startswith('"') and contents.endswith('"'):
                    contents = contents[1:-1]
            headers[name] = contents
        return headers

    def _get_bytes(self, length, data_file=None):
        """Get the specified number of bytes from the socket.

        Return the specified number of bytes from the socket unless the file
        argument is set, in which case it writes to file and returns nothing.

        Positional arguments:
            length: The length (in bytes) of the expected output.

        Keyword arguments:
            data: A file-like object into which to place the bytes.
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
                if data_file:
                    data_file.write(seg)
                    data_file.truncate()
                    return
                return message + seg
            if data_file:
                data_file.write(self.buffer)
            else:
                message += self.buffer
            written += len(self.buffer)
            self.buffer = self.socket.recv(BUFFER_SIZE)
            if len(self.buffer) == 0:
                raise SocketClosedError()

    @classmethod
    def _generate_header_bytes(cls, name, contents):
        """Generate a bytes object that is a line to send as headers.

        Positional arguments:
            name: The header name as a string.
            contents: The header contents.

        Returns:
            a bytes object containing a utf-8 encoded header line.
        """
        if name[0].isspace() or name[-1].isspace():
            name = '"%s"' % name
        if isinstance(contents, str):
            if contents[0].isspace() or contents[-1].isspace():
                contents = '"%s"' % contents
            try:
                float(contents)
            except ValueError:
                pass
            else:
                contents = '"%s"' % contents
            if contents in cls.STRING_TO_BOOL:
                contents = '"%s"' % contents
        else:
            contents = str(contents)
        return ('%s: %s\n' % (name, contents)).encode('utf-8')

    def send(self, headers, contents=None):
        """Send data over the socket.

        If a Size header exists, it will be overwritten by the sensed size of
        the file.

        Positional arguments:
            headers: A dictionary containing the headers to send.
            contents: A file-like object or a bytes object to send
        """
        if contents is None:
            headers['Size'] = 0
        elif isinstance(contents, bytes):
            headers['Size'] = len(contents)
        else:
            contents.seek(0, os.SEEK_END)
            headers['Size'] = contents.tell()
            contents.seek(0, os.SEEK_SET)
        for header in headers:
            self.socket.sendall(
                self._generate_header_bytes(header, headers[header]))
        self.socket.sendall(b'\n')
        if contents is None:
            return
        if isinstance(contents, bytes):
            self.socket.sendall(contents)
        else:
            self.socket.sendall(contents.read())
