'''
    Iterator utilties.

    These classes are modeled after the ifunctions() in itertools and
    Dave Beasley's Generator Functions for System Programers.

    Portions Copyright 2011-2023 solidlibs
    Last modified: 2023-05-17

    This file is open source, licensed under GPLv3 <http://www.gnu.org/licenses/>.
'''

import os.path
import builtins
from itertools import takewhile
from tempfile import gettempdir

from solidlibs.python.log import Log

# log in non-standard dir because of concurrency issues
log = Log(os.path.join(gettempdir(), 'iter.log'))

def is_iterable(item):
    ''' Return True iff item is iterable.

        >>> print(is_iterable(3))
        False
    '''

    try:
        list(item)
    except TypeError:
        result = False
    else:
        result = True

    return result

def iter(items, sentinel=None):
    ''' A more flexible and tolerant iter().
        Accepts a single item. Treats None as an empty iterable. '''

    if items is not None:
        try:
            if sentinel:
                items = takewhile(lambda x: not sentinel(x), items)
            for item in builtins.iter(items):
                yield item
        except TypeError:
            # does this make any sense?
            # does it belong above inside "if sentinel:"?
            # 'items' may a sentinel. If so, it is just one item.
            if sentinel:
                if not sentinel(items):
                    yield items
            else:
                yield items

def count(iterable):
    ''' Count items in any iterable, or an object which can be made into an
        iterable.

        This is what you probably expected itertools.count() to do.

        Since count() works with any iterable, you don't have to remember
        when you can use len(). It can also be much more memory efficient
        than len(list(iterator)), since like generators it only requires
        one item in memory at a time.

        Traverses the iterable. This can result in side effects, such as
        exhausting a generator.

        If the iterable is a sequence (string, tuple or list) or a
        mapping (dictionary), the built-in function len() does not have side
        effects and may be more efficient. '''

    return sum(1 for item in iter(iterable))

def first(test, items):
    ''' Return first item for which test(item) is True. '''

    matches = list(filter(test, items))
    if matches:
        result = matches[0]
    else:
        result = None

    return result

def first_true(items):
    ''' Return first item in iterable that evaluates to True.
        If all items are False, return None.

        >>> print(first_true([0, None, '', 'yes', 'yes again', False]))
        yes
        >>> print(first_true([0, None, '', 'yes again', 'yes', False]))
        yes again
        >>> print(first_true([0, None, '', False]))
        None
    '''

    try:
        iterable = iter(items)
        item = next(iterable)
        while not item:
            item = next(iterable)
    except StopIteration:
        item = None
    return item

def last_true(iterable):
    ''' Return last item in iterable that evaluates to True.
        If all items are False, return None.

        Uses minimum memory, unlike "reverse(list(iterable))[0]".

        >>> print(last_true([0, None, '', 'yes', 'yes again', False]))
        yes again
    '''

    last_true_item = None
    for item in iterable:
        if item:
            last_true_item = item
    return last_true_item

def enqueue(q, *iterables):
    ''' Queue items from one or more iterables.

        You can enqueue() items in one thread, and dequeue() them from another.
        As of Python 2.5 Queue.task_done() and join() seem buggy, so use
        another way to let the dequeue thread run, such as threading.Event or
        if necessary time.sleep(). Set up the thread that calls dequeue(),
        then call enqueue(). See the doctest example.

        StopIteration can not be an item from one of the iterables, which is
        vanishingly unlikely anyway.

        Thanks to Dave Beasley.

        >>> from queue import Queue

        >>> iter1 = (1, 2)
        >>> iter2 = [3, 4]
        >>> q = Queue(0)

        >>> enqueue(q, iter1, iter2)
        >>> for item in dequeue(q):
        ...     print(item)
        1
        2
        3
        4

        >>> def dequeue_test(q, done_event):
        ...     for item in dequeue(q):
        ...         print(item)
        ...     done_event.set()
        >>> from threading import Event, Thread
        >>> done_event = Event()
        >>> thread = Thread(target=dequeue_test, args=(q, done_event))
        >>> thread.start()
        >>> enqueue(q, iter1, iter2)
        >>> done_event.wait()
        1
        2
        3
        4
        True
        '''

    for iterable in iterables:
        for item in iterable:
            q.put(item)
    # will this work across net links? python instances on a machine?
    q.put(StopIteration)

def dequeue(q):
    ''' Get items that were queued using enqueue().

        You can enqueue() items in one thread, and dequeue() them from another.

        Thanks to Dave Beasley. '''

    item = q.get()
    while item != StopIteration:
        yield item
        item = q.get()


if __name__ == "__main__":

    import doctest
    doctest.testmod()
