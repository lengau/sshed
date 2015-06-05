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

SOCKET_THAT_CLOSES_PREMATURELY = [
	b'Some data here.',
	b'']

SOCKET_WITH_DATA = b'Some data that comes from the socket here.'

SOCKET_WITH_MULTIPLE_DATA = [
	b'First bit of data here.',
	b'Second bit of data...',
	b'Finally, our third bit of data.']
