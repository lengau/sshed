ORIGINAL = b"""\
Line one
2
THREE!
Four?
"""

MALFORMED_REMOVE_DIFF = [
	b'--- tmp 2015-05-29 16:46:52.722077075 -0400\n',
	b'+++ tmp2        2015-06-05 20:28:39.700598812 -0400\n',
	b'@@ -1,3 +1,4 @@\n',
	b'-First line\n',  # This line mismatches.
	b'+Line one\n'
	b' 2\n',
	b' THREE!\n',
	b'+3.5\n',
]

MALFORMED_SAME_DIFF = [
	b'--- tmp 2015-05-29 16:46:52.722077075 -0400\n',
	b'+++ tmp2        2015-06-05 20:28:39.700598812 -0400\n',
	b'@@ -1,3 +1,4 @@\n',
	b' Line one\n'
	b' 2\n',
	b' THREE?\n',  # This line mismatches.
	b'+3.5\n',
]
