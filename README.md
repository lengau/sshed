# SSHEd

SSHEd is a small connector program that allows you to use a local text editor
or IDE to edit files on a remote server without having to manually copy the
file to the local machine. More importantly, sshedit gets run from the remote
machine.

This means it can be used as a drop-in replacement for ed, emacs, nano, vi, etc.
on remote machines over SSH.

## Installation Notes
sshed is currently WAY WAY pre-alpha software. I was even badly behaved and
haven't written any unit tests yet. (I know. Shame on me.) However, the
following should be enough to get a copy of sshed working from the source
directory.

1. On the remote host, modify the AcceptEnv line of /etc/ssh/sshd_config to
   include the text variable "SSHED_SOCK". This isn't required, but it helps.
2. In ~/.ssh/config, add a SendEnv line that sends "SSHED_SOCK".
2.5. See the note below.
3. Start sshed_client and copy the output variable-setting line to another
   shell.
4. In that shell, run:
   ssh -t -R $SSHED_SOCK:$SSHED_SOCK [remote_hostname]
5. Make sure sshed.py is on the client and run it.

NOTE: You should set your $EDITOR environment variable to be a graphical
editor that blocks the terminal until the file is closed. Some graphical text
editors don't block the terminal by default, so check for an option that'll
do so. For example, kate needs to be run with the -b argument to do so.
In bash, you can set your editor to kate by running:
export EDITOR='kate -b'
I would recommend adding that to your ~/.bashrc to keep it across sessions.
