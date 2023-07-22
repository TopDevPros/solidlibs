'''
    Abstract class to build virtualenv for one of our websites.

    Copyright 2013-2023 solidlibs
    Last modified: 2023-05-17

    This file is open source, licensed under GPLv3 <http://www.gnu.org/licenses/>.

    This module should probably be merged into build_venv
'''

from abc import ABCMeta, abstractmethod
import os
import sys
from subprocess import CalledProcessError
from traceback import format_exc

from solidlibs.os.command import run
#def run(*args, **kwargs): # DEBUG
#    print(f'run({args}, {kwargs})')
from solidlibs.python.log import Log
from solidlibs.python.ve import venv


class AbstractBuildVenv(metaclass=ABCMeta):
    ''' Build the virtualenv for a site.

        Each site should inherit from this abstract class with details about their environment.
    '''

    log = Log()

    def __init__(self):

        major, minor, _, _, _ = sys.version_info
        self.MAJOR_PYTHON_VERSION = major
        self.MINOR_PYTHON_VERSION = minor

        self.VIRTUAL_SUBDIR = 'virtualenv'

    def build(self):

        os.chdir(self.project_dirname())
        self.init_virtualenv()

        if self.virtualenv_dir_exists():

            self.log(f'building virtual environment in {self.project_dirname()}')
            os.chdir(self.virtualenv_dir())

            # activate the virtualenv
            with venv(dirname=self.virtualenv_dir()):

                # set up a link to the python lib for simplier config
                dirname = f'python{self.MAJOR_PYTHON_VERSION}.{self.MINOR_PYTHON_VERSION}'

                os.chdir('lib')
                run('ln', '-s', dirname, 'python')

                self.report('   installing requirements')
                try:
                    run(f'pip{self.MAJOR_PYTHON_VERSION}',
                        'install',
                        '-r',
                        self.get_requirements())

                except CalledProcessError as cpe:
                    self.log(format_exc())
                    if cpe.stdout: self.log(f'stdout: {cpe.stdout}')
                    if cpe.stderr: self.log(f'stderr: {cpe.stderr}')
                    sys.exit(
                      f'{cpe.stderr}. For more details see {self.log.pathname}')

                """ NOT USED
                with open(self.get_requirements()) as f:
                    for line in f.readlines():
                        if line.strip():
                            app = line.strip()
                            self.report(f'     {app}')
                            try:
                                run(f'pip{self.MAJOR_PYTHON_VERSION}', 'install', app)
                            except CalledProcessError as cpe:
                                self.log(format_exc())
                                if cpe.stdout: self.log(f'stdout: {cpe.stdout}')
                                if cpe.stderr: self.log(f'stderr: {cpe.stderr}')
                                sys.exit(
                                  f'{cpe.stderr}. For more details see {self.log.pathname}')
                """

            self.log('   linking packages')
            self.link_packages()

            self.log('   linking assets')
            self.link_assets()

            self.finish_build()
            self.log('   virtual environment built')
        else:
            self.log.error(f'!!!Error: Unable to create {self.virtualenv_dir()}')

    @abstractmethod
    def project_dirname(self):
        ''' Directory where virtualenv and other subdirs will be created. '''

    @abstractmethod
    def get_requirements(self):
        ''' Return the full path to the virtualenv requirements. '''

    @abstractmethod
    def link_packages(self):
        ''' Link packages to the site-packages directory. '''

    @abstractmethod
    def link_assets(self):
        ''' Link assets that are found in weird places. '''

    @abstractmethod
    def virtualenv_dir(self):
        ''' Returns the full path to the virtualenv directory. '''

    def virtual_subdir(self):

        return self.VIRTUAL_SUBDIR

    def init_virtualenv(self):
        '''
            Initialize the virtualenv.

            Overwrite this function if you want
            special switches used when running virtualenv.
        '''

        if os.path.exists(self.virtual_subdir()):
            run('rm', '-fr', self.virtual_subdir())

        if (os.path.exists(f'/usr/bin/python{self.MAJOR_PYTHON_VERSION}.{self.MINOR_PYTHON_VERSION}') or
            os.path.exists(f'/usr/local/bin/python{self.MAJOR_PYTHON_VERSION}.{self.MINOR_PYTHON_VERSION}') ):
            python_pgm = f'python{self.MAJOR_PYTHON_VERSION}.{self.MINOR_PYTHON_VERSION}'
        else:
            entries = os.scandir('/usr/bin')
            for entry in entries:
                if (entry.name.startswith(f'python{self.MAJOR_PYTHON_VERSION}') and
                    '-' not in entry.name):

                    python_pgm = entry.name
                    break

        run('virtualenv', '-p', f'/usr/bin/{python_pgm}', self.virtual_subdir())

    def virtualenv_dir_exists(self):
        ''' Return True if the virtualenv directory does exist. '''

        return os.path.exists(self.virtualenv_dir())

    def finish_build(self):
        ''' Overwrite if there are any final steps necessary to create the build.'''
        # do not remove the follow pass; when we strip comments, we need the pass
        pass

    def report(self, message):
        ''' Show and log the message. '''

        print(message)
        self.log(message)

    def fail(self, message):
        ''' Show and log the message. Exit. '''

        print(message)
        self.log(message)
        sys.exit(message)
