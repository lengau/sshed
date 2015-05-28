# SSHed protocol

This is a quick, basic description of the communications protocol used on an
sshed pipe. The motivation behind this file is to allow others to implement
compatible sshed programs in the language of their choice.

Version numbers should be incremented whenever incompatible changes are made to
the way sshed passes a file over the socket. Protocol versions are integers
that are encoded as ASCII strings over the wire. Exceptions can be made for
protocol versions under development, but should never be used in release
software.

Versions marked as deprecated are no longer implemented by the most recent
versions of sshed.

## LANGUAGE
A brief note on the wording used:

The CLIENT refers to the machine running sshed_client, which would typically be
the machine with which the user is physically interacting. This is also
typically the machine on which the ssh command is run (with -R to create the
appropriate tunnel).

The HOST refers to the machine on which sshed is run, passing the name of a
file on the host's filesystem to sshed. Typically this machine is either remote
(e.g. a server in a datacentre or a VPS) or headless (e.g. an embedded device).
This is also typically the machine which is running the SSH server (sshd).

This gets a sort of backwards server-client relationship (with the user only
directly interacting with the host, but the client being the long-running
process), but the reason for this choice of terminology is to match names with
the running ssh process in what I would view to be the "normal" usage of sshed.
That is to say, the client running on the local machine and the user SSHing to
a remote machine and using the host software on the remote machine. I would
encourage anyone reading this to think about sshed (and the client and host)
in relation to which SSH application it pairs with (i.e. is on the same machine
as).

## BASIC PROTOCOL STRUCTURE:
All versions of the protocol should follow this basic structure.
Each side sends data as a frame that looks as follows:

    Header-1: Contents
    Header-2: Contents

    DATADATADATADATADATA

Each header should be UTF-8 text, with the name separated from the contents by
a colon and one header separated from another by a newline. Whitespace
surrounding (but not inside) the header and the contents will be ignored.
Should whitespace be required, the corresponding name or contents should be
encapsulated with double quote characters ("). Newlines are not allowed in the
header contents, and neither newlines nor colons are allowed in header names.

The last header should be immediately followed by two newline characters, which
signify the start of the data.
The receiving end MUST have a way to determine the end of the data. In most
cases, this is provided by a 'Size' header that provides the size in bytes.
However, it's possible that some future packets may use different methods,
such as a string end (\0) charater.

## Protocol versions
Hopefully once the version 1 protocol has been finalised there won't need to
be many changes. However, any incompatible changes should require a version
bump, and I don't want to require ugly workarounds to determine if version 1
of the protocol is being used. So instead I'm just making sshed protocol version
aware from day 1.

### Version 1
NOTE: Protocol version 1 is only set to be finalised in sshed version 0.5.
Until then this section is subject to change without notice, though most
changes will be documented in issues on the
[sshed bug tracker](https://github.com/lengau/sshed/issues).

Version 1 of the sshed protocol allows a file of a specific name (must be
passed from host to client) to be passed from the host to the client, edited
on the client, and then passed back to the host.

The host must begin the conversation by sending the following headers to the
client:

* protocol version ('Version')
* 'Filename'
* 'Filesize'

The 'Version' header should be set to '1'

The 'Filesize' header refers to the length of the file in bytes. This is
different from the 'Size' header, which measures the size (in bytes) of this
packet. A packet must always be completed. Although the 'Size' header isn't
limited (and thus allows for arbitrarily sized packets), in practice the
size of a packet should be small enough to only take a few milliseconds to
transmit or receive in its entirety (network latency not included).

The host immediately sends the full file to the client as the data in the same
packet as the original header.
NOTE: With [client side caching](https://github.com/lengau/sshed/issues/6), this
is likely to become more complex.

#### Saving changes

NOTE: The following has not yet been implemented. Currently, sshed_client only
responds when the text editor closes. When it responds, it either closes the
socket immediately (indicating no change to the file) or sends the entire file
back to the host.

When the client detects that the file has been saved, it should either send the
entire file or a diff. These packets look slightly different:

##### Non-differential
If the client is sending the entire file, it should send the following header:

    Differential: False

The full file follows in the same packet (the 'Filesize' and 'Size' headers
would therefore have identical contents, so the 'Size' header is all that
is necessary).

##### Differential
If the client is only sending a diff, it should send the following header:

    Differential: True
    Filesize: [size of the resulting file after the diff has been applied]
    Checksum: [checksum of the resulting file]

The diff then follows in a
[Unified diff](https://docs.python.org/3.4/library/difflib.html#difflib.unified_diff)
format.

The diff should be based on the result of the previously sent diff. That is to
say diffs are cumulative.

#### Exiting the editor.
Once the editor has terminated, one last check should be made for whether the
file has changed. If it has, a change packet should be sent to the host.

Once the change packet has been sent, the client can close the socket.

#### Abrupt exits
If the client closes the socket at any point, the host should exit as soon as
possible. If a partial save has been sent, the host should ignore this and write
only the last complete save to the file.

If the host closes the socket, the client should terminate (NOT KILL) the text
editor process immediately.

#### Checksums
Any time a checksum is referred to (e.g. in Checksum headers), the checksum is
to be a SHA256 digest of the data converted into hexadecimal. Using the hashlib
library in Python 3.4, one could use the line:

    checksum = hashlib.sha256(data).hexdigest()

to compute the checksum. This should always result in a 64-character unicode
string containing the checksum.
The checksum should ONLY be of the data, not the headers. We should consider
the socket over which sshed is communicating to be a reliable transport.
