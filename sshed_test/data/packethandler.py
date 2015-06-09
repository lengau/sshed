"""Data for packethandler tests."""

import copy

#
# Sample socket data.
#
CLOSED_SOCKET = b''

SOCKET_WITH_PARTIAL_HEADERS = [b"""\
Version: 1
Other-Header: Something
Partial-Heade""", b'']

SOCKET_WITH_QUOTED_NAME = b"""\
Version: 1
" Header with spaces all over ": Some text.

"""

SOCKET_WITH_QUOTED_NAME_HEADERS = {
	'Version': 1,
	' Header with spaces all over ': 'Some text.',
}

SOCKET_WITH_NUMBERS = b"""\
Integer: 255
Float: 3.1415927

"""

SOCKET_WITH_NUMBERS_HEADERS = {
	'Integer': int(255),
	'Float': float(3.1415927),
}

SOCKET_WITH_BOOLEAN = b"""\
True: True
False: False
None: None

"""

SOCKET_WITH_BOOLEAN_HEADERS = {
	'True': True,
	'False': False,
	'None': 'None',
}

SOCKET_WITH_QUOTED_CONTENTS = b"""\
Contents: " My name: Test String! "

"""

SOCKET_WITH_QUOTED_CONTENTS_HEADERS = {
	'Contents': ' My name: Test String! ',
}

SPLIT_HEADER_SOCKET = [
	b'Version: 1\nOthe',
	b'r-header: Thing\n\n']

SPLIT_HEADER_SOCKET_HEADERS = {
	'Version': 1,
	'Other-header': 'Thing',
}

SOCKET_THAT_CLOSES_PREMATURELY = [
	b'Some data here.',
	b'']

SOCKET_WITH_DATA = b'Some data that comes from the socket here.'

SOCKET_WITH_MULTIPLE_DATA = [
	b'First bit of data here.',
	b'Second bit of data...',
	b'Finally, our third bit of data.']

SOCKET_WITH_EVERYTHING_DATA = b'Some data goes here.\n'

SOCKET_WITH_EVERYTHING_HEADER_STRING = b"""\
Version: 1
" Header with spaces " :        "   Header contents with spaces  "
Integer: 0
Float: -2.7182818284
True:True
	False : False
False-String: "False"
None:None
Size: 21
"""

SOCKET_WITH_EVERYTHING = (
	SOCKET_WITH_EVERYTHING_HEADER_STRING +
	b'\n' +
	SOCKET_WITH_EVERYTHING_DATA)

MULTI_PART_SOCKET_WITH_EVERYTHING = [
	SOCKET_WITH_EVERYTHING[:10],
	SOCKET_WITH_EVERYTHING[10:35],
	SOCKET_WITH_EVERYTHING[35:-14],
	SOCKET_WITH_EVERYTHING[-14:]]

SOCKET_WITH_EVERYTHING_BASE_HEADERS = {
	'Version': 1,
	' Header with spaces ': '   Header contents with spaces  ',
	'Integer': 0,
	'Float': -2.7182818284,
	'True': True,
	'False': False,
	'False-String': 'False',
	'None': 'None'}

SOCKET_WITH_EVERYTHING_HEADERS = copy.copy(SOCKET_WITH_EVERYTHING_BASE_HEADERS)
SOCKET_WITH_EVERYTHING_HEADERS['Size'] = len(SOCKET_WITH_EVERYTHING_DATA)


EVERYTHING_HEADER_LINES = [
	b'Version: 1\n',
	b'" Header with spaces ": "   Header contents with spaces  "\n',
	b'Integer: 0\n',
	b'Float: -2.7182818284\n',
	b'True: True\n',
	b'False: False\n',
	b'False-String: "False"\n',
	b'None: None\n',
	b'Size: 21\n',
]

HEADER_BYTES_RAW_DATA = [
	['String', 'Some data', b'String: Some data\n'],
	[' Pre-spaced', ' pre-spaced', b'" Pre-spaced": " pre-spaced"\n'],
	['Post-spaced ', 'post-spaced ', b'"Post-spaced ": "post-spaced "\n'],
	[' Dual-spaced ', ' dual-spaced ', b'" Dual-spaced ": " dual-spaced "\n'],
	['Integer', 0, b'Integer: 0\n'],
	['Integer string', '0', b'Integer string: "0"\n'],
	['Float', 0.1, b'Float: 0.1\n'],
	['Float-as-string', '0.1', b'Float-as-string: "0.1"\n'],
	['True', True, b'True: True\n'],
	['True string', 'True', b'True string: "True"\n'],
	['False', False, b'False: False\n'],
]
