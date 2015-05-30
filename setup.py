from distutils.core import setup

setup(
	name='sshed',
	packages = ['sshed'],
	version = '0.1',
	description = 'Use a local text editor to edit remote files over SSH.',
	author = 'Alex M. Lowe',
	author_email = 'amlowe@ieee.org',
	url = 'https://github.com/lengau/sshed',
	keywords = ['ssh', 'editor', 'text'],
	classifiers = [
		'Development Status :: 3 - Alpha',
		'Environment :: Console',
		'Environment :: X11 Applications',
		'Intended Audience :: Developers',
		'Intended Audience :: End Users/Desktop',
		'Intended Audience :: System Administrators',
		'License :: OSI Approved :: GNU General Public License v2 or later (GPLv2+)',
		'Operating System :: Unix',
		'Programming Language :: Python',
		'Programming Language :: Python :: 3',
		'Topic :: Text Editors',
		],
	long_description = """\
Text editing over SSH helper
----------------------------

Allows the use of a local (graphical) text editor for editing remote files in
an SSH session.

Provides an agent process (similar to ssh-agent) on the client side and a
drop-in editor process on the host side.

NOTE: Right now, SSHEd requires a bit of manual work to install. Full
installation instructions are included in the README file distributed with
sshed.
"""
	)
