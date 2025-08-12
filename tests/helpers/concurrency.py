"""Concurrency test utilities for multi-threaded integration tests.

Provides utilities to orchestrate concurrent test operations across distinct
SQLAlchemy sessions to validate race condition handling and transaction
isolation in the projection engine.
"""

from threading import Thread, Barrier
from typing import Callable, Optional, List


def run_in_threads(
    targets: List[Callable[[], None]], join_timeout: float = 10.0
) -> List[Optional[BaseException]]:
    """Execute multiple functions concurrently in separate threads.
    
    Args:
        targets: List of functions to execute concurrently
        join_timeout: Maximum time to wait for threads to complete
        
    Returns:
        List of exceptions (or None) aligned with targets
    """
    threads: List[Thread] = []
    errors: List[Optional[BaseException]] = [None] * len(targets)

    def wrap(i: int, fn: Callable[[], None]) -> None:
        try:
            fn()
        except BaseException as e:
            errors[i] = e

    for i, target in enumerate(targets):
        t = Thread(target=wrap, args=(i, target), daemon=True)
        threads.append(t)
        t.start()

    for t in threads:
        t.join(timeout=join_timeout)
        
    return errors


def session_worker(session_factory: Callable, fn: Callable) -> Callable[[], None]:
    """Wrap a function to run with its own SQLAlchemy session.
    
    Args:
        session_factory: Function that creates new Session instances
        fn: Function to execute, will receive Session as first argument
        
    Returns:
        Wrapped function that manages session lifecycle
    """
    def _inner():
        sess = session_factory()
        try:
            fn(sess)
        finally:
            sess.close()
    return _inner


def barrier_sync(n: int) -> Barrier:
    """Create a threading barrier for synchronizing n threads.
    
    Args:
        n: Number of threads to synchronize
        
    Returns:
        Threading barrier for coordinating starts
    """
    return Barrier(n)