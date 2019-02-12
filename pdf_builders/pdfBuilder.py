#! Copied from https://github.com/SublimeText/LaTeXTools
from __future__ import print_function
import sys
import os
from shlex import split
from six import string_types
import subprocess
import re
from pdf_builders.system import which
from subprocess import Popen, PIPE, STDOUT, CalledProcessError
if sys.version_info < (3,):
    from pipes import quote

    def expand_vars(texpath):
        return os.path.expandvars(texpath).encode(sys.getfilesystemencoding())

    def update_env(old_env, new_env):
        encoding = sys.getfilesystemencoding()
        old_env.update(
            dict((k.encode(encoding), v) for (k, v) in new_env.items())
        )

    # reraise implementation from 6
    exec("""def reraise(tp, value, tb=None):
    raise tp, value, tb
""")

else:
    from imp import reload
    from shlex import quote

    def expand_vars(texpath):
        return os.path.expandvars(texpath)

    def update_env(old_env, new_env):
        old_env.update(new_env)


FILE_NOT_FOUND_ERROR_REGEX = re.compile(
    r"! LaTeX Error: File `(.*)/([^/']*)'", re.MULTILINE)

TEXLIVEONFLY = os.path.normpath(os.path.dirname(os.path.abspath(__file__)) + os.pathsep + u'texliveonfly.py')
DEBUG = False


def get_platform():
    platforms = {
        'linux1': 'Linux',
        'linux2': 'Linux',
        'darwin': 'OS X',
        'win32': 'Windows'
    }
    if sys.platform not in platforms:
        return sys.platform

    return platforms[sys.platform].lower()


class PrintWrapper(object):
    def __call__(self, *args, **kwargs):
        print(*args, **kwargs)
# ---------------------------------------------------------------
# PdfBuilder class
#
# Build engines subclass PdfBuilder
# NOTE: this will have to be moved eventually.
#


class PdfBuilder(object):
    """Base class for build engines"""

    # Configure parameters here
    #
    # tex_root: the full path to the tex root file
    # output: object in main thread responsible for writing to the output panel
    # builder_settings : a dictionary containing the "builder_settings" from LaTeXTools.sublime-settings
    # platform_settings : a dictionary containing the "platform_settings" from LaTeXTools.sublime-settings
    #
    # E.g.: self.path = prefs["path"]
    #
    # Your __init__.py method *must* call this (via super) to ensure that
    # tex_root is properly split into the root tex file's directory,
    # its base name, and extension, etc.
    def __init__(self, tex_root, output, engine, options, aux_directory,
                 output_directory, job_name, tex_directives,
                 builder_settings, platform_settings):
        self.tex_root = tex_root
        self.tex_dir, self.tex_name = os.path.split(tex_root)
        self.base_name, self.tex_ext = os.path.splitext(self.tex_name)
        if output is None:
            self.output_callable = PrintWrapper()
        else:
            self.output_callable = output
        self.out = ""
        self.engine = engine
        if options is None:
            self.options = []
        else:
            self.options = options
        self.output_directory = self.output_directory_full = output_directory
        self.aux_directory = self.aux_directory_full = aux_directory
        self.job_name = job_name
        self.tex_directives = tex_directives
        self.builder_settings = builder_settings
        self.platform_settings = platform_settings

        # if output_directory and aux_directory can be specified as a path
        # relative to self.tex_dir, we use that instead of the absolute path
        # note that the full path for both is available as
        # self.output_directory_full and self.aux_directory_full
        if (
                self.output_directory and
                self.output_directory.startswith(self.tex_dir)
        ):
            self.output_directory = os.path.relpath(
                self.output_directory, self.tex_dir
            )

        if (
                self.aux_directory and
                self.aux_directory.startswith(self.tex_dir)
        ):
            self.aux_directory = os.path.relpath(
                self.aux_directory, self.tex_dir
            )

    # Send to callable object
    # Usually no need to override
    def display(self, data):
        self.output_callable(data)
        # print(data)

    # Save command output
    # Usually no need to override
    def set_output(self, out):
        if DEBUG:
            print("Setting out")
            print(out)
        self.out = out

    # This is where the real work is done. This generator must yield (cmd, msg) tuples,
    # as a function of the parameters and the output from previous commands (via send()).
    # "cmd" is the command to be run, as an array
    # "msg" is the message to be displayed (or None)
    # As of now, this function *must* yield at least *one* tuple.
    # If no command must be run, just yield ("","")
    # Remember that we are now in the root file's directory
    def commands(self):
        raise NotImplementedError()

    # Clean up after ourselves
    # Only the build system knows what to delete for sure, so give this option
    # Return True if we actually handle this, False if not
    #
    # NOTE: problem. Either we make the builder class persistent, or we have to
    # pass the tex root again. Need to think about this
    def cleantemps(self):
        return NotImplementedError()


# utilities
def get_texpath():
    """
    Returns the default texpath
    """
    platform = get_platform()
    if platform == 'OS X':
        return '/Library/TeX/texbin:/usr/texbin:/usr/local/bin:/opt/local/bin'
    elif platform == 'Linux':
        return '/usr/texbin'
    else:
        return ''


__sentinel__ = object()


# wrapper to handle common logic for executing subprocesses
def external_command(command, cwd=None, shell=False, env=None,
                     stdin=__sentinel__, stdout=__sentinel__,
                     stderr=__sentinel__, preexec_fn=None,
                     use_texpath=True, show_window=False):
    '''
    Takes a command object to be passed to subprocess.Popen.
    Returns a subprocess.Popen object for the corresponding process.
    Raises OSError if command not found
    '''
    if command is None:
        raise ValueError('command must be a string or list of strings')

    _env = dict(os.environ)

    if use_texpath:
        _env['PATH'] = get_texpath() or os.environ['PATH']

    if env is not None:
        update_env(_env, env)

    platform = get_platform()
    # if command is a string rather than a list, convert it to a list
    # unless shell is set to True on a non-Windows platform
    if (
        (shell is False or platform == 'windows') and
        isinstance(command, string_types)
    ):
        command = split(command, False, False)
    elif (
        shell is True and platform != 'windows' and
        (isinstance(command, list) or isinstance(command, tuple))
    ):
        command = u' '.join(command)

    # Windows-specific adjustments
    startupinfo = None
    if platform == 'windows':
        # ensure console window doesn't show
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        if show_window:
            startupinfo.wShowWindow = 1

        if not os.path.isabs(command[0]):
            _command = which(
                command[0], path=_env['PATH'] or os.environ['PATH']
            )

            if _command:
                command[0] = _command

    if stdin is __sentinel__:
        stdin = None

    if stdout is __sentinel__:
        stdout = STDOUT

    if stderr is __sentinel__:
        stderr = STDOUT

    try:
        print(u'Running "{0}"'.format(u' '.join([quote(s) for s in command])))
    except UnicodeError:
        try:
            print(u'Running "{0}"'.format(command))
        except:
            pass

    p = Popen(
        command,
        stdin=stdin,
        stdout=stdout,
        stderr=stderr,
        startupinfo=startupinfo,
        preexec_fn=preexec_fn,
        shell=shell,
        env=_env,
        cwd=cwd
    )

    return p


def execute_command(command, cwd=None, shell=False, env=None,
                    stdin=__sentinel__, stdout=__sentinel__,
                    stderr=__sentinel__, preexec_fn=None,
                    use_texpath=True, show_window=False):
    '''
    Takes a command to be passed to subprocess.Popen and runs it. This is
    similar to subprocess.call().
    Returns a tuple consisting of
        (return_code, stdout, stderr)
    By default stderr is redirected to stdout, so stderr will normally be
    blank. This can be changed by calling execute_command with stderr set
    to subprocess.PIPE or any other valid value.
    Raises OSError if the executable is not found
    '''
    def convert_stream(stream):
        if stream is None:
            return u''
        else:
            return u'\n'.join(
                re.split(r'\r?\n', stream.decode('utf-8', 'ignore').rstrip())
            )

    if stdout is __sentinel__:
        stdout = PIPE

    if stderr is __sentinel__:
        stderr = STDOUT

    p = external_command(
        command,
        cwd=cwd,
        shell=shell,
        env=env,
        stdin=stdin,
        stdout=stdout,
        stderr=stderr,
        preexec_fn=preexec_fn,
        use_texpath=use_texpath,
        show_window=show_window
    )

    stdout, stderr = p.communicate()
    return (
        p.returncode,
        convert_stream(stdout),
        convert_stream(stderr)
    )


def check_call(command, cwd=None, shell=False, env=None,
               stdin=__sentinel__, stdout=__sentinel__,
               stderr=__sentinel__, preexec_fn=None,
               use_texpath=True, show_window=False):
    '''
    Takes a command to be passed to subprocess.Popen.
    Raises CalledProcessError if the command returned a non-zero value
    Raises OSError if the executable is not found
    This is pretty much identical to subprocess.check_call(), but
    implemented here to take advantage of LaTeXTools-specific tooling.
    '''
    # since we don't do anything with the output, by default just ignore it
    if stdout is __sentinel__:
        stdout = open(os.devnull, 'w')
    if stderr is __sentinel__:
        stderr = open(os.devnull, 'w')

    returncode, stdout, stderr = execute_command(
        command,
        cwd=cwd,
        shell=shell,
        env=env,
        stdin=stdin,
        stderr=stderr,
        preexec_fn=preexec_fn,
        use_texpath=use_texpath,
        show_window=show_window
    )

    if returncode:
        e = CalledProcessError(
            returncode,
            command
        )
        raise e

    return 0


def check_output(command, cwd=None, shell=False, env=None,
                 stdin=__sentinel__, stderr=__sentinel__,
                 preexec_fn=None, use_texpath=True,
                 show_window=False):
    """
    Takes a command to be passed to subprocess.Popen.
    Returns the output if the command was successful.
    By default stderr is redirected to stdout, so this will return any output
    to either stream. This can be changed by calling execute_command with
    stderr set to subprocess.PIPE or any other valid value.
    Raises CalledProcessError if the command returned a non-zero value
    Raises OSError if the executable is not found
    This is pretty much identical to subprocess.check_output(), but
    implemented here since it is unavailable in Python 2.6's library.
    """
    returncode, stdout, stderr = execute_command(
        command,
        cwd=cwd,
        shell=shell,
        env=env,
        stdin=stdin,
        stderr=stderr,
        preexec_fn=preexec_fn,
        use_texpath=use_texpath,
        show_window=show_window
    )

    if returncode:
        e = CalledProcessError(
            returncode,
            command
        )
        e.output = stdout
        e.stderr = stderr
        raise e

    return stdout
