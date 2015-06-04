# SSHEd

SSHEd is a small connector program that allows you to use a local text editor
or IDE to edit files on a remote server without having to manually copy the
file to the local machine. More importantly, sshedit gets run from the remote
machine.

This means it can be used as a drop-in replacement for ed, emacs, nano, vi, etc.
on remote machines over SSH.

## Installation
For right now, you'll need to do the following to use sshed:

1. Install it on both the client and host machine.
2. On the client machine, run sshed_client and copy the command given on stdout
   to the shell where you want to run ssh
3. On the client machine, SSH to the host using the edssh command.
4. On the host machine, you should now be able to use sshed as your editor,
   but only in the shell you connected via edssh.

## Editors
You should set your $EDITOR environment variable to be a graphical
editor that blocks the terminal until the file is closed. Some graphical text
editors don't block the terminal by default, so check for an option that'll
do so. For example, kate needs to be run with the -b argument to do so.
In bash, you can set your editor to kate by running:
export EDITOR='kate -b'
I would recommend adding that to your ~/.bashrc to keep it across sessions.

## Future Versions
Quite a few changes are planned before the 1.0 release. This section contains
some basic ideas of the vision for sshed.

### Installation
Eventually, the installation process will look similar to the following:

0. Extract the Python modules and binaries on the client.
1. On the remote host, modify the AcceptEnv line of /etc/ssh/sshd_config to
   include the text variable "SSHED_SOCK". This isn't required, but it helps.
2. In ~/.ssh/config, add a SendEnv line that sends "SSHED_SOCK".
   See the note below.
3. Add sshed_client to run like ssh-agent does.
4. If the host has sshed installed, simply ssh to the host and use sshed
5. If sshed is not installed on the host, use edssh to SSH in.

