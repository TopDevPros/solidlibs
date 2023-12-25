'''
    Coroutine classes and utilties.

    Portions Copyright 2012-2022 TopDevPros
    Last modified: 2022-11-19

    Simple replacements for overly complex threading, generators, Queues, etc.

    See the doctests for examples. Warning: The doctests are a mess and
    sinks are buggy. But some of these functions and classes are
    working in production.

    These functions and classes, especially Pump and Coroutine, hide
    the obscure python linkages between iterables and generators. In
    most cases you don't need threading at all. They also add optional
    common functionality such as filters and one time processing. Very
    memory efficient implementation.

    Some functions are from:
      * Dave Beazley's Generator Tricks for System Programers
        http://www.dabeaz.com/generators-uk/
      * Pipe Fitting with Python Generators
        http://paddy3118.blogspot.com/2009/05/pipe-fitting-with-python-generators.html

    This file is open source, licensed under GPLv3 <http://www.gnu.org/licenses/>.
'''

import collections.abc
import os.path
from queue import Queue
from tempfile import gettempdir
from threading import Thread

from solidlibs.os.command import background
from solidlibs.python.iter import iter
from solidlibs.os.lock import synchronized
from solidlibs.python.log import Log
from solidlibs.python.utils import last_exception, object_name

DEBUG = False # don't set this to True
if DEBUG:
    sys.exit('setting DEBUG to True locks up the machine')


log = Log()

def consumer(func):
    ''' Co-routine consumer decorator.

        Thanks to Dave Beazley. '''

    def start(*args,**kwargs):
        c = func(*args,**kwargs)
        next(c)
        return c
    return start

def pipe(source, *gennies):
    ''' Pipe data from generators a() to b() to c() to d() ...

        pipe(a,b,c,d, ...) -> yield from ...d(c(b(a())))

        The source is an iterator. A pump is any callable that takes a
        single generator parameter and returns a generator, such as a
        function or coroutine.Pump instance.

        In practice as of 2012-02-12 we've never used this, but had a need for a simpler:
            pipeline = source()
            for pump in pumps:
                pipeline = pump(pipeline)
            return pipeline

        See Pump.build_pipeline().

        See Pipe Fitting with Python Generators
            http://paddy3118.blogspot.com/2009/05/pipe-fitting-with-python-generators.html

        >>> # this count function is unrelated to our Count pump.
        >>> # it just provides a source of ints.
        >>> from itertools import count

        >>> def sqr(x):
        ...     for val in x:
        ...         yield val*val

        >>> def half(x):
        ...     for val in x:
        ...         yield val/2.0

        >>> p = pipe(count(), sqr, half)
        >>> [next(p) for i in range(5)]
        [0.0, 0.5, 2.0, 4.5, 8.0]
    '''

    if DEBUG: log(f'in pipe() source: {repr(source)}')
    if DEBUG: log(f'in pipe() source type: {type(source)}')
    if DEBUG: log(f'in pipe() source as list: {list(source)}')

    pipe_gen = source
    for genny in gennies:
        pipe_gen = genny(pipe_gen)

    for x in pipe_gen:
        if DEBUG: log(f'in pipe() item type: {type(x)}')
        yield x

def pull(iterator):
    ''' Used e.g. on a pipe(), a Pump, or the last Pump at the end of a pipe to pull items
        through the pipeline.

        Simply traverses iterator. '''

    if DEBUG: log(f'in pull() iterator: {object_name(iterator)} {repr(iterator)}')
    if DEBUG: log(f'in pull() iterator type: {type(iterator)}')
    for item in iterator:
        if DEBUG: log(f'in pull() item type: {type(item)}')
        pass

class Pump(object):
    ''' A Pump is a unix pipeline in python.

        It is a data processsing station on a python pipeline.
        A pump can filter and modify data items. It can do one
        time processing both before and after pumping.

        This class abstracts encapsulating an iterator, yield, filters,
        and one time processing before and after.

        This is a superclass for classes that process data from one pipe
        which is an iterable, and output that data as another iterable.
        The data may be filtered or otherwise processed by overiding methods.

        Pump is implemented as a generator for memory and speed efficiency.

        Standard map() and reduce() are not suitable for pipes because
        reduce() consumes the iterable, and the pipe stops.
        You can think of this as map-reduce without consuming the iterable.
        See coroutine.Count for an example. A Pump can also filter both
        input and output data, and perform one time processing before and
        after pumping.

        Subclass this class and supply your own methods to change default
        behavior.

        The rough equivalent of map-reduce is the method process(object).
        process() must return an object.  The default process(self, object)
        just returns the same object unchanged.

        Use before_filter() to filter objects before process().
        Use after_filter() to filter afterwards.
        If you only want your Pump to process certain objects,
        but pass all objects downstream, use an "if" in process().
        The ...filter() methods filter objects going downstream.


        One time setup goes in before(). The default before() does nothing.
        Any final processing goes in after(), which also does nothing by default.

        It's generally a good idea to only subclass Pump directly. If you
        subclass another subclass of Pump, you have to keep track of when to
        call super(). Instead try to pass one Pump as the iterator of the other
        Pump, or use multiple inheritance.

        >>> class Printer(Pump):
        ...     def process(self, object):
        ...         print(object)
        ...         return object

        >>> class Adder(Pump):
        ...
        ...     def before(self, *args, **kwargs):
        ...         self.total = 0
        ...
        ...     def process(self, object):
        ...         self.total += object
        ...         return object

        >>> log('test Pump()')
        >>> a = [1, 2, 3]

        Pump list --> Printer --> Adder --> Count --> len(list())
        >>> p1 = Printer(a)
        >>> p2 = Adder(p1)
        >>> p3 = Count(p2)
        >>> count = len(list(p3))
        1
        2
        3

        <<< assert p2.total == sum(a), f'total should be {sum(a)}, is {p2.total}'
        <<< assert p3.count == count, f'count should be {count}, is {p3.count}'
        <<< print(f'{p3.count} items total to {p2.total}')
        3 items total to 6
        '''

    def __init__(self, iterable, *args, **kwargs):
        ''' Initialize the pipe. Call before() before all other processsing. '''

        self.done = False
        if DEBUG: log(f'iterable type: {type(iterable)}')
        if not isinstance(iterable, collections.abc.Iterable):
            iterable = iter(iterable)
        self.source = iterable
        if DEBUG: log(f'iterable: {iterable}, self.source: {repr(source)}')
        self.before(*args, **kwargs)

    def __iter__(self):
        return self

    def __next__(self):
        ''' Get and process the next item. '''

        if DEBUG: log(f'{object_name(self)} __next__()')
        try:
            # get objects until one passes both before_filter() and
            # after_filter(), or there are no more objects
            if DEBUG: log(f'self.source: {repr(source)}')
            object = next(iter(self.source))

            if DEBUG: log(f'process: {object_name(self.process)}, object: {object_name(object)}')
            if self.before_filter(object):
                if DEBUG: log(f'calling {object_name(self.process)}({object_name(object)})')
                object = self.process(object)
                #if DEBUG: log(f'after calling {object_name(self.process)} object is {object_name(object)}')
                #if DEBUG: assert isinstance(object, Person) and hasattr(object, 'experienced_event'), object_name(self.process)
                self.after_filter(object)

        # any exception before raise will hide StopIteration
        except (StopIteration, GeneratorExit):
            self.done = True
            try:
                if DEBUG: log(exception_only())
                self.after()
            except StopIteration:
                # after StopIteration is raised,
                # it should be raised again on every call to __next()
                pass
            except:
                log(last_exception())

        except:
            log(last_exception())
            raise

        if self.done:
            raise StopIteration

        #if DEBUG: assert isinstance(object, Person) and hasattr(object, 'experienced_event'), object_name(self.process)
        return object

    def before(self, *args, **kwargs):
        ''' Initial one time setup.

            Do most of the things you'd ordinarily do in __init__ here.
            This function gets all the __init__() args except for the first,
            which is an iterable of items into the Pump.

            The input iterable is available as self.source. Other positional and
            keyword instantiation arguments are passed as *args and **kwargs. '''
        pass

    def after(self):
        ''' Final one time processing.

            Any exception that may have occured is available using the
            usual python calls. '''
        pass

    def before_filter(self, object):
        ''' Returns True if the object passes this filter. Otherwise returns False.

            Only objects that pass before_filter() are sent to process().
            The default is to pass all objects. '''

        return True

    def after_filter(self, object):
        ''' Returns True if the object passes this filter.  Otherwise returns False.

            Only objects that pass after_filter() after processing are returned
            from instances of this iterator.  The default is to pass all objects. '''

        return True

    def process(self, object):
        ''' Perform any processing on an object.

            If you only want your Pump to process certain objects,
            but pass all objects downstream, use an "if" here.
            The ...filter() methods filter objects going downstream.

            The defaut is to return the object unchanged. '''

        if DEBUG: log('default process()')
        return object

    def __getattr__(self, name):
        ''' Pass anything else to the iterable. '''

        getattr(self.source, name)

    @staticmethod
    def build_pipeline(source, *pumps):
        ''' Connect a series of pump functions to a source. The source is an iterator.
            A pump function is a generator function that takes an iterator argument.

            Returns a generator.

            Examples::

        >>> source = iter([1, 2])

        >>> def double(iterator):
        ...     for item in iterator:
        ...                yield item * 2

        >>> def counter(iterator):
        ...     return Count(iterator)

        >>> # E.g. to feed from source through the generator functions double and counter:
        >>> pipeline = Pump.build_pipeline(source, double, counter)
        >>> # 'pipeline' is a generator (counter(double(source))).

        >>> for item in pipeline:
        ...     print(item)
        2
        4
        >>> print(pipeline.count)
        2

        '''

        #if DEBUG: log(f'build_pipeline({repr(source)}, {repr(pumps)})')

        if pumps:
            for pump in pumps:
                genny = pump(source)
                source = genny
        else:
            # if no pumps, return source
            genny = source

        return genny

class Count(Pump):
    ''' Adds a count attribute to an iterable.

        The count is the number of items iterated over so far.
        If an object already has a way to count its items, such as len(),
        it may be better to use that.

        >>> log('test Count()')
        >>> a = [2, 4, 8]
        >>> b = Count(a)
        >>> for x in b:
        ...     print(x)
        2
        4
        8
        >>> b.count
        3
        >>> log('test Count() done')

        '''

    def before(self, attr_name=None, *args, **kwargs):
        ''' Initialize the counter.

            'attr_name' is the count attribute name, by default 'count'. '''

        self.attr_name = attr_name or 'count'
        setattr(self, self.attr_name, 0)

    def process(self, object):
        ''' Count. '''

        if DEBUG: log(f'{self.attr_name} was {getattr(self, self.attr_name)}') # DEBUG
        setattr(self, self.attr_name, getattr(self, self.attr_name) + 1)
        if DEBUG: log(f'{self.attr_name} is {getattr(self, self.attr_name)}') # DEBUG
        return object

    """ without attr_name
    def before(self, *args, **kwargs):
        self.count = 0

    def process(self, object):
        self.count += 1
        return object
    """

class Coroutine(object):
    ''' Generator based coroutine with piping, broadcasting, and aggregating.

        Gennerators are very memory efficient, but complex to use. This class
        abstracts away the magic "while True", "(yield)", and superfluous "next()".
        Adds piping, broadcasting, and receiving from multiple sources.
        Includes an optional filter and one time processing before and after.

        Pass objects to a Coroutine subclass using the co-routine's send().
        You can also specify another Coroutine as a data source.
        Override receive() to process received data.
        (not working: Calls to receive() are synchronized to avoid races in
        python implementations that don't lock access properly.)

        If you try to send() back to a Coroutine that is currently sending
        to you, send() raises a ValueError.

        When a Coroutine receives from multiple sources, the order of
        sources is undefined. Data from each source is processed in order
        for that source.

        When a Coroutine sends to multiple sinks, the order of sinks
        is undefined. Data sent to a Coroutine sink is processed in the order
        received.

        >>> class NoTrueScotsmanFilter(Coroutine):
        ...     # Filter out 'No true Scotsman...' definitions
        ...
        ...     def filter(self, definition):
        ...         return definition != 'No true Scotsman...'
        ...
        ...     def receive(self, object):
        ...         print(object)
        ...         return object

        >>> coroutine = NoTrueScotsmanFilter()
        >>> coroutine.send('No true Scotsman...') # no response expected
        >>> coroutine.send('True Scotsman')
        True Scotsman

        >>> class Test(Coroutine):
        ...
        ...     def before(self):
        ...         self.value = 0
        ...
        ...     def receive(self, object):
        ...         if self.name() == 'e': log.stacktrace(f'e receiving {object}') # DEBUG
        ...         log(f'before Test.receive: {self.name()}.value: {self.value}, object: {object}') # DEBUG
        ...         self.value = self.value + object
        ...         log(f'after Test.receive: {self.name()}.value: {self.value}') # DEBUG
        ...         return self.value

        # these tests may depend on calling sequence

        >>> log('test: 1 -> a -> b -> c')
        >>> a = Test('a')
        >>> b = Test('b', sources=a)
        >>> c = Test('c', sources=b)
        >>> a.send(1)
        >>> a.value
        1
        >>> b.value
        1
        >>> c.value
        1

        >>> log('test: 1 -> a -> b -> c, b + c -> d -> e')
        >>> a = Test('a')
        >>> b = Test('b', sources=a)
        >>> c = Test('c', sources=b)
        >>> e = Test('e')
        >>> d = Test('d', sources=[b, c], sinks=e)
        >>> a.send(1)
        >>> a.value
        1
        >>> b.value
        1
        >>> c.value
        1
        >>> d.value
        2
        >>> e.value
        2

        >>> log('test a, b, c, d, e with a.send(3)')
        >>> a = Test('a')
        >>> b = Test('b', sources=a)
        >>> c = Test('c', sources=b)
        >>> e = Test('e')
        >>> d = Test('d', sources=[b, c], sinks=e)
        >>> a.send(3)
        >>> a.value
        3
        >>> b.value
        3
        >>> c.value
        3
        >>> d.value
        6
        >>> e.value
        6

        >>> d = Test('d', sources=[b, c], sinks=[a, b]) # doctest: +ELLIPSIS
        Traceback (most recent call last):
        ...
        ValueError: infinite loop from sink to self...

        '''

    def __init__(self, name=None, sources=None, sinks=None, *args, **kwargs):
        ''' A source is another coroutine which sends its output to this coroutine.
            The arg 'sources' may be a single source.

            A sink is another coroutine which gets its input from this coroutine.
            The arg 'sinks' may be a single sink.

            Initialize the receiver loop. Call before() before all other processsing. '''

        self._name = name

        self.sinks = set()
        for sink in iter(sinks):
            self.add_sink(sink)

        for source in iter(sources):
            source.add_sink(self)

        self.before(*args, **kwargs)

        self.running = True
        self._c_loop = self._loop()
        next(self._c_loop)

    def _loop(self):
        ''' Receive, filter, and process each item.
            Call after() after all other processsing. '''

        try:
            while self.running:
                obj = (yield)
                if self.filter(obj):
                    if DEBUG: log(f'DEBUG {self.name()} received {obj}') # DEBUG
                    obj = self.receive(obj)
                    for sink in self.sinks:
                        if DEBUG: log(f'DEBUG {self.name()}->{sink.name()} {obj}') # DEBUG
                        sink.send(obj)

        # except (StopIteration, GeneratorExit):
        # any exception before raise will hide StopIteration
        #     pass

        finally:
            try:
                # if DEBUG: log(exception_only())
                self.after()
            except:
                log(last_exception())
            finally:
                raise

    def name(self):
        return self._name or 'unknown'

    def send(self, object):
        ''' Called to send an object to this Coroutine. '''

        self._c_loop.send(object)

    def before(self, *args, **kwargs):
        ''' Override this function to perform any one time setup.

            Do what you'd ordinarily do in __init__. '''
        pass

    def after(self):
        ''' Override this function to perform any one time cleanup.

            Any exception that may have occured is available using the
            usual python calls. '''
        pass

    def filter(self, object):
        ''' Returns True if the object passes this filter. Otherwise returns False.

            Only objects that pass filter() are sent to receive().
            The default is to pass all objects. '''

        return True

    @synchronized # this doesn't appear to work, so _loop() calls receive() directly
    def _receive(self, object):
        ''' Perform any processing on an object. Synchronized wraper for receive(). '''

        self.receive(object)

    def receive(self, object):
        ''' Override this function to perform any processing on an object. '''

        return object

    def stop(self):
        ''' Stop running. '''

        self.running = False

    def add_sink(self, sink):
        ''' Add a sink safely.

            Looped data pipes raise a ValueError. '''

        def check(sinks):
            for sink in sinks:
                path.append(sink.name())
                if sink == self:
                    raise ValueError(f'infinite loop from sink to self: -> {path}')
                else:
                    check(sink.sinks)

        if sink == self:
            raise ValueError(f'sink for {self.name()} is self')
        else:
            path = [self.name(), sink.name()]
            check(sink.sinks)

        self.sinks.add(sink)

def Coiterator(Coroutine):
    ''' Coroutine that is an iterator.

        The items you send() to a Coiterator are produced as
        iterator items. '''

    def before(self, block=False, *args, **kwargs):
        ''' One time setup. '''

        self.q = Queue()
        self.block = block
        self.done = False

    def after(self):
        ''' One time cleanup. '''

        self.done = True

    def receive(self, object):
        ''' Receive an object.

            If 'block=True' then wait for space in the queue. Otherwise
            if the queue is full raise Queue.Full. '''

        self.q.put(object, self.block)
        return object

    def __iter__(self):
        return self

    def next(self):
        ''' Get and process the next item.
            Block until an object is available.
            Raise StopIteration if the source is done. '''

        if self.done:
            raise StopIteration
        else:
            return self.q.get(True)


if __name__ == "__main__":

    import doctest
    doctest.testmod()
