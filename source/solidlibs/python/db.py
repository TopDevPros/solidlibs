'''
    Database utilities.

    Portions Copyright 2010-2023 TopDevPros
    Last modified: 2023-10-13
'''

import re
import time
from contextlib import contextmanager

from django.conf import settings
from django.db import connection, reset_queries, transaction, IntegrityError
from django.db.utils import OperationalError

from solidlibs.python.coroutine import Pump
from solidlibs.python.log import Log
from solidlibs.python.internals import caller
from solidlibs.python.elapsed_time import ElapsedTime, LogElapsedTime
from solidlibs.python.times import one_second, timestamp
from solidlibs.python.utils import object_name

log = Log()
slow_db_log = Log('slow.transactions.log')

CURSOR_UNION_REGEX = re.compile(r'^SELECT .*? FROM (.*)$', re.I)
TOO_LONG = one_second


class IterableQuerySet():
    ''' Allows iteration over a QuerySet breaking it off into smaller chunks.

        This is a workaround for django's QuerySet.iterator() bug.
        As of Django 1.2 QuerySet.iterator() eats memory, causing thrashing
        on large data sets.

        Author: David Cramer
        See "Large SQL Result Sets in Django", http://www.davidcramer.net/code/412/large-sql-result-sets-in-django.html '''

    def __init__(self, queryset, batch=10000):
        self.batch = batch
        self.queryset = queryset

    def __iter__(self):
        at = 0

        results = self.queryset[at:at+self.batch]
        while results:

            clear_query_cache()

            for result in results:
                yield result

            at += self.batch
            results = self.queryset[at:at+self.batch]

    def __getattr__(self, name):
        return getattr(self.queryset, name)

class QuerySetCursor():
    ''' Buffer QuerySet cursor for large data sets.

        Author: David Cramer
        See "Large SQL Result Sets in Django", http://www.davidcramer.net/code/412/large-sql-result-sets-in-django.html '''

    def __init__(self, connection, sql, params=None, model_class=None):
        self._result_cache = None
        self._offset = 0
        self._limit = None
        self._connection = connection
        self._sql = sql
        self._model_class = model_class
        if params is None:
            self.params = []
        else:
            self._params = params

    def __getitem__(self, k):
        if not isinstance(k, (slice, int)):
            raise TypeError
        assert (not isinstance(k, slice) and (k >= 0)) \
            or (isinstance(k, slice) and (k.start is None or k.start >= 0) and (k.stop is None or k.stop >= 0)), \
            "Negative indexing is not supported."
        if isinstance(k, slice):
            if self._offset < k.start or k.stop-k.start > self._limit:
                self._result_cache = None
        else:
            if k not in list(range(self._offset, self._limit+self._offset)):
                self._result_cache = None
        if self._result_cache is None:
            if isinstance(k, slice):
                self._offset = k.start
                self._limit = k.stop-k.start
                return self._get_results()
            else:
                self._offset = k
                self._limit = 1
                return self._get_results()[0]
        else:
            return self._result_cache[k]

    def __len__(self):
        return len(self._get_data())

    def __iter__(self):
        return iter(self._get_data())

    def _get_data(self):
        if self._result_cache is None:
            self._result_cache = list(self._get_results())
        return self._result_cache

    def _get_results(self):
        if self._limit:
            query = self._sql + ' LIMIT %s, %s'
            params = self._params + [self._offset, self._offset+self._limit]
        else:
            params = self._params
            query = self._sql

        cursor = self._connection.cursor()
        try:
            cursor.execute(query, params)
            results = cursor.fetchall()
            if self._model_class:
                results = [self._model_class(*r) for r in results]
        finally:
            cursor.close()
        return results

    def count(self):
        statements = self._sql.split(' UNION ')
        prepared = []
        for statement in statements:
            end_of_stmt = CURSOR_UNION_REGEX.match(statement)
            if not end_of_stmt:
                raise Exception("Error getting SQL")
            prepared.append(f"SELECT COUNT(1) FROM {end_of_stmt.group(1)}")
        query = f"SELECT ({') + ('.join(prepared)})"
        cursor = self._connection.cursor()
        try:
            cursor.execute(query, self._params)
            results = cursor.fetchone()[0]
        finally:
            cursor.close()
        return results

class DjangoCacheClearer(Pump):
    ''' Clear Django query cache in a pipeable Pump. '''

    def after(self):
        clear_query_cache()

def clear_query_cache():
    ''' Clear the Dango sql query cache.

        Django's SQL query cache can eat a lot of memory.
        The cache is only used if settings.DEBUG is True.

        The primary advantages of this function over calling
        django.db.reset_queries() directly are 1) to encapsulate the idiom
        and 2) increase readability of the code. '''

    reset_queries()

def big_query_set(connection, sql, params, model_class):
    return IterableQuerySet(QuerySetCursor(connection, sql, params, model_class))

def delete(query, verbose=False):
    ''' Delete items.

        Either Django or some DBMSes like SQLite have a limit on the number
        of items items deleted in a delete() call. This function loops as
        needed.

        To avoid memory thrashing, uses IterableQuerySet,
        clear_query_cache(), and deletes one by one. '''

    def delete():
        ''' There seems to be a limit on how many deletes at once, so set up to loop '''

        count_to_delete = iquery.count()
        if count_to_delete:

            if verbose: log(f'{count_to_delete:d} to delete')

            count = 0

            for item in iquery:
                item.delete()
                count += 1
                if verbose:
                    # every 10,000
                    if not (count % 10000):
                        log(f'deleted {count:d}/{count_to_delete:d} {name} items')

            count_after = iquery.count()
            if verbose: log(f'{count_after:d} left after deleting')

            clear_query_cache()
            return count_to_delete - count_after

    if isinstance(query, IterableQuerySet):
        iquery = query
    else:
        iquery = IterableQuerySet(query)

    if verbose:
        if iquery.model:
            name = object_name(iquery.model)
        else:
            name = ''
        total_count = iquery.count()
        #log(f'deleting {total_count:d} {name} items')

    count_left = delete()
    while count_left:
        count_left = delete()

    if verbose:
        log(f'deleted {count_left:d} {name} items')
        assert count_left == total_count

def first(query):
    ''' Get first item. '''

    return next(iter(IterableQuerySet(query)))

def last(query):
    ''' Get last item. '''

    return first(query.reverse())

def query_sql(query):
    ''' Get the sql generated by a query.

        Or to see the sql for all running queries:

            from django.db import connection
            connection.queries
    '''

    # this changes as django changes

    #cols, sql, args = query.query._get_sql_clause()
    #return "SELECT %s %s" % (', '.join(cols), sql % tuple(args))

    # works with django 1.2
    return str(query.query)


def access_db(transaction_function, *args, timeout=None, **kwargs):
    ''' Retry transaction until success or timeout.

        This is the preferred way to access a database.
        Use lock_db() if your database access needs to fail fast and not retry.
        Do not use lock() with a database unless you are really sure of what you are doing.

        Args:
            transaction_function:
                Function that accesses the database in this transaction.
            timeout: Timeout in seconds. Default is 20.

            All other arguments and keyword parameters are passed to the transaction function.

        Returns:
            The result from transaction_function().

        Usage::

            def my_transaction():
                ...

            access_db(my_transaction)
    '''

    def log_retry_time():
        log(f'{standard_caller_id} retried {retry_time} seconds')

    DEFAULT_TIMEOUT = 20 # seconds
    RETRY_DELAY = 0.1 # seconds

    if timeout is None:
        timeout = DEFAULT_TIMEOUT

    module_line = caller(ignore=[__file__, r'.*/contextlib.py'])
    standard_caller_id = f'{module_line} (access_db ({timestamp()})'
    #with LogElapsedTime(log, '{} total access time'.format(standard_caller_id)):

    done = False
    retry_time = 0 # seconds

    while not done:
        try:
            result = transaction_function(*args, **kwargs)
        except Exception as exc:
            """
            Or:

            except (OperationalError, IntegrityError) as db_error:
                if 'database locked' in str(db_error):
                    log('{} database locked; retrying'.format(standard_caller_id))
            """

            if retry_time < timeout:
                #log(f'{standard_caller_id} exception: {str(exc)}')
                time.sleep(RETRY_DELAY)
                retry_time = retry_time + RETRY_DELAY

            else:
                #log(f'{standard_caller_id} timed out: {exc}')
                log_retry_time()
                raise

        else:
            done = True

    return result

@contextmanager
def lock_db():
    ''' Wrap block in a django transaction and close the database connection.

        Use access_db() instead if you can. You should only use lock_db() if
        your database access needs to fail fast and not retry.

        Usage::

            with lock_db():
                ...
    '''

    # this could conceivably ignore extra files if __file__ contains '.' etc.
    standard_caller_id = caller(ignore=[__file__, r'.*/contextlib.py'])
    with ElapsedTime() as et:

        # do we want to close the connection inside the transaction, or outside()
        with transaction.atomic():
            with _close_db():
                yield

    # q&d
    if et.timedelta() > TOO_LONG:
        message = f'{standard_caller_id} slow transaction: {et.timedelta()}'
        slow_db_log.warning(message)
        log.warning(message)


@contextmanager
def _close_db():
    ''' Try to avoid "OperationalError database locked".

        Do not call _close_db() except inside solidlibs.python.db. Use access_db() instead.

        It's a good idea to use this on every db access, even reads.

        Postgres raises many exceptions unless the connection is
        explicitly closed.

        Usage::

            with _close_db():
                ...
    '''

    """
        References

            Search: django sqlite database locked solved

            class 'psycopg2.InterfaceError': connection already closed
            https://stackoverflow.com/questions/9427787/class-psycopg2-interfaceerror-connection-already-closed

            Django stops functioning when the database (PostgreSQL) closes the connection
            https://code.djangoproject.com/ticket/15802

            python - Django sqlite database is locked - Stack Overflow
            stackoverflow.com/questions/31547234/django-sqlite-database-is-locked

               But anyone familiar with databases knows that when you're using
               the "serializable" isolation level with many common database
               systems, then transactions can typically fail with a serialization
               error anyway. That happens in exactly the kind of situation
               this deadlock represents, and when a serialization error occurs,
               then the failing transaction must simply be retried. And, in fact,
               that works fine for me.

            Django ticket #29280 (Fix SQLite "database is locked" problems using "BEGIN ...
            code.djangoproject.com/ticket/29280

                (includes how to monkeypatch python, specifically django atomic transactions)

    """

    try:
        yield

    finally:
        try:
            if connection.connection is not None:
                try:
                    connnection.close()
                except:
                    # it doesn't matter if the close failed
                    # usually it's that the connection is already closed
                    pass

        except Exception as exc:
            # we need to know what happened
            log(f'exception in _close_db:\n{exc}')
