import os, sys
import subprocess

# Enables debugging of MksPython's commands
CMD_PYTHON_TRACE = os.environ.get("CMD_PYTHON_TRACE", False)

execute_kwargs = ('istream', 'with_keep_cwd', 'with_extended_output',
                  'with_exceptions', 'with_raw_output')

extra = {}
if sys.platform == 'win32':
    extra = {'shell': True}

def dashify(string):
    return string.replace('_', '-')

class CommanderError(Exception):
    """
    Thrown if execution of the command fails with non-zero status code.
    """
    def __init__(self, command, status, stderr=None):
        self.stderr = stderr
        self.status = status
        self.command = command

    def __str__(self):
        return repr("%s returned exit status %d" %
                    (str(self.command), self.status))

class Commander(object):
    def __init__(self, cmd, sep):
        super(Commander, self).__init__()
        self.cmd = cmd
        self.sep = sep

    def __getattr__(self, name):
        if name[:1] == '_':
            raise AttributeError(name)
        return lambda *args, **kwargs: self._call_process(name, *args, **kwargs)

    def execute(self, command,
                istream=None,
                with_keep_cwd=False,
                with_extended_output=False,
                with_exceptions=True,
                with_raw_output=False,
                ):
        if CMD_PYTHON_TRACE and not CMD_PYTHON_TRACE == 'full':
            print ' '.join(command)

        # Allow the user to have the command executed in their working dir.
        cwd = os.getcwd()

        # Start the process
        proc = subprocess.Popen(command,
                                cwd=cwd,
                                stdin=istream,
                                stderr=subprocess.PIPE,
                                stdout=subprocess.PIPE,
                                **extra
                                )

        # Wait for the process to return
        try:
            stdout_value = proc.stdout.read()
            stderr_value = proc.stderr.read()
            status = proc.wait()
        finally:
            proc.stdout.close()
            proc.stderr.close()

        # Strip off trailing white space by default
        if not with_raw_output:
            stdout_value = stdout_value.rstrip()
            stderr_value = stderr_value.rstrip()

        if with_exceptions and status != 0:
            raise CommanderError(command, status, stderr_value)

        if CMD_PYTHON_TRACE == 'full':
            if stderr_value:
              print "%s -> %d: '%s' !! '%s'" % (command, status, stdout_value, stderr_value)
            elif stdout_value:
              print "%s -> %d: '%s'" % (command, status, stdout_value)
            else:
              print "%s -> %d" % (command, status)

        # Allow access to the command's status code
        if with_extended_output:
            return (status, stdout_value, stderr_value)
        else:
            return stdout_value

    def transform_kwargs(self, **kwargs):
        """
        Transforms Python style kwargs into command line options.
        """
        args = []
        for k, v in kwargs.items():
            if len(k) == 1:
                if v is True:
                    args.append("-%s" % k)
                elif type(v) is not bool:
                    args.append("-%s%s" % (k, v))
            else:
                if v is True:
                    args.append("--%s" % dashify(k))
                elif type(v) is not bool:
                    if self.sep == '=':
                        args.append("--%s=%s" % (dashify(k), v))
                    else:
                        args.append("--%s" % dashify(k))
                        args.append("%s" % v)
        return args

    def _call_process(self, method, *args, **kwargs):
        # Handle optional arguments prior to calling transform_kwargs
        # otherwise these'll end up in args, which is bad.
        _kwargs = {}
        for kwarg in execute_kwargs:
            try:
                _kwargs[kwarg] = kwargs.pop(kwarg)
            except KeyError:
                pass

        # Prepare the argument list
        opt_args = self.transform_kwargs(**kwargs)
        ext_args = map(str, args)
        args = opt_args + ext_args

        call = [self.cmd, dashify(method)]
        call.extend(args)

        return self.execute(call, **_kwargs)
