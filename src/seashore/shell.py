'''
Shell
-----
Running subprocesses with a shell-like interface.
'''
import copy
import contextlib
import os
import singledispatch
import subprocess
import sys
import urlparse
import time
import signal
import tempfile

import attr

class ProcessError(Exception):
    """
    A process has exited with non-zero status.
    """

@attr.s
class Shell(object):

    """
    Run subprocesses.

    Init arguments:
    
    :param cwd: current working directory (default is process's current working directory)
    :param env: environment variables dict (default is a copy of the process's environment)
    """

    _procs = attr.ib(init=False, default=attr.Factory(list))

    _cwd = attr.ib(init=False, default=attr.Factory(os.getcwd))

    _env = attr.ib(init=False, default=attr.Factory(lambda:dict(os.environ)))


    def batch(self, command, cwd=None):
        """
        Run a process, wait until it ends and return the output and error

        :param command: list of arguments
        :param cwd: current working directory (default is to use the internal working directory)
        :returns: pair of standard output, standard error
        :raises: :code:`ProcessError` with (return code, standard output, standard error)
        """
        with open('/dev/null') as stdin, \
             tempfile.NamedTemporaryFile() as stdout, \
             tempfile.NamedTemporaryFile() as stderr:
            proc = self.popen(command, stdin=subprocess.PIPE, stdout=stdout, stderr=stderr, cwd=cwd)
            proc.communicate('')
            retcode = proc.wait()
            self._procs.remove(proc)
            stdout.seek(0)
            stderr.seek(0)
            stdout_contents = stdout.read()
            stderr_contents = stderr.read()
            ## Log contents of stdout, stderr
            if retcode != 0:
                raise ProcessError(retcode, stdout_contents, stderr_contents)
            else:
                return stdout_contents, stderr_contents

    def interactive(self, command, cwd=None):
        """
        Run a process, while its standard output and error go directly to ours.

        :param command: list of arguments
        :param cwd: current working directory (default is to use the internal working directory)
        :raises: :code:`ProcessError` with (return code, standard output, standard error)
        """
        proc = self.popen(command, cwd=cwd)
        retcode = proc.wait()
        self._procs.remove(proc)
        if retcode != 0:
            raise ProcessError(retcode)

    def popen(self, command, **kwargs):
        """
        Run a process, giving direct access to the :code:`subprocess.Popen` arguments.

        :param command: list of arguments
        :param kwargs: keyword arguments passed to :code:`subprocess.Popen`
        :returns: a :code:`Process`
        """
        if kwargs.get('cwd') is None:
            kwargs['cwd'] = self._cwd
        if kwargs.get('env') is None:
            kwargs['env'] = self._env
        proc = subprocess.Popen(command, **kwargs)
        self._procs.append(proc)
        return proc

    def setenv(self, key, val):
        """
        Set internal environment variable.

        Changes internal environment in which subprocesses will be run.
        Does not change the process's own environment.

        :param key: name of variable
        :param value: value of variable
        """
        key = str(key)  # keys must be strings
        val = str(val)  # vals must be strings
        self._env[key] = val

    def getenv(self, key):
        """
        Get internal environment variable.

        Return value of variable in internal  environment in which subprocesses will be run.
 
        :param key: name of variable
        :returns: value of variable
        :raises: :code:`KeyError` if key is not in environment
        """
        return self._env[key]

    def cd(self, path):
        """
        Change internal current working directory.

        Changes internal directory in which subprocesses will be run.
        Does not change the process's own current working directory.

        :param path: new working directory
        """
        self._cwd = os.path.join(self._cwd, path)

    def reap_all(self):
        """
        Kill, as gently as possible, all processes.

        Loop through all processes and try to kill them with
        a sequence of :code:`SIGINT`, :code:`SIGTERM` and
        :code:`SIGKILL`.
        """
        for proc in self._procs:
            ret_code = proc.poll()
            if ret_code is None:
                proc.send_signal(signal.SIGINT)
                time.sleep(3)
            ret_code = ret_code or proc.poll()
            if ret_code is None: # pragma: no coverage
                proc.terminate()
                time.sleep(3)
            ret_code = ret_code or proc.poll() # pragma: no coverage
            if ret_code is None: # pragma: no coverage
                proc.kill()

    def clone(self):
        """
        Clone the shell object.

        :returns: a new Shell object with a copy of the environment dictionary
        """
        return attr.assoc(self, _env=dict(self._env), _procs=[])

@contextlib.contextmanager
def autoexit_code():
    """
    Context manager that translates :code:`ProcessError` to immediate process exit.
    """
    try:
        yield
    except ProcessError as pe:
        raise SystemExit(pe[0])
