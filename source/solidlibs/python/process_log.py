#! /usr/bin/python3
'''
    Process log

    Provides a comprehensive status log for all processes logged by a specific user.

    Usage:
        from solidlibs.python.status import ProcessLog
        ...
        status_log = ProcessLog(PROCESS_NAME)

    A status log summarizes the runtime history and current state of system processes:
      * When significant processes start, succeed, and fail
        * "start: ..."
        * "running: ..."
        * "success: ..."
        * "failed: ..."
      * Mitigation of significant errors
        * "recovery: ..."
      * Unrecoverable errors
        * "unrecoverable: ...:"

    Because we use our log server to syncronize log messages, you can
    re-initialize ProcessLog wherever convenient. It all goes to the
    same log for each user.

    Last modified: 2023-11-03
'''

from solidlibs.python.log import Log

class ProcessLog():

    '''
        A comprehensive status log for all processes logged by a specific user.

        >>> plog = ProcessLog()
        >>> def procedure():
        ...     plog.start('just beginning')
        ...     plog.running('processing')
        ...     plog.success('worked')
    '''

    def __init__(self, name=None):
        self.log = Log(name)

    def start(self, msg):
        ''' Attempt to start a process '''

        msg = f'start: {msg}'
        self.log.debug(msg)

    def running(self, msg):
        ''' Process is running '''

        msg = f'running: {msg}'
        self.log.debug(msg)

    def success(self, msg):
        ''' Process succeeded '''

        msg = f'success: {msg}'
        self.log.debug(msg)

    def failed(self, msg):
        ''' Process failed '''

        msg = f'failed: {msg}'
        self.log.error(msg)

    def recovery(self, msg):
        ''' Process attempting recovery. '''

        msg = f'recovery: {msg}'
        self.log.error(msg)

    def unrecoverable(self, msg):
        ''' Unrecoverable error. '''

        msg = f'unrecoverable: {msg}'
        self.log.error(msg)


if __name__ == "__main__":

    import doctest
    doctest.testmod()
