"""Parallel/sequential execution utility following fl_eval/execution/parallel_executor.py pattern."""

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, Iterable, TypeVar

import psutil
from tqdm import tqdm

R = TypeVar("R")

# Physical core count → semaphore limit
PHYSICAL_CORES = psutil.cpu_count(logical=False) or 1
SAFE_THREADS = max(1, PHYSICAL_CORES)
CPU_LIMITER = threading.BoundedSemaphore(SAFE_THREADS)

# Large management pool — sleeping threads are cheap
MAX_MANAGEMENT_THREADS = 5000
_SHARED_EXECUTOR = ThreadPoolExecutor(max_workers=MAX_MANAGEMENT_THREADS)
_EXECUTOR_SHUTDOWN = False


def _get_shared_executor() -> ThreadPoolExecutor:
    global _SHARED_EXECUTOR, _EXECUTOR_SHUTDOWN
    if _EXECUTOR_SHUTDOWN:
        _SHARED_EXECUTOR = ThreadPoolExecutor(max_workers=MAX_MANAGEMENT_THREADS)
        _EXECUTOR_SHUTDOWN = False
    return _SHARED_EXECUTOR


def shutdown_parallel_executor(wait: bool = True) -> None:
    global _SHARED_EXECUTOR, _EXECUTOR_SHUTDOWN
    if not _EXECUTOR_SHUTDOWN:
        _SHARED_EXECUTOR.shutdown(wait=wait)
        _EXECUTOR_SHUTDOWN = True


def run_parallel_or_seq(
    items: Iterable[Any],
    task_fn: Callable[..., R],
    desc: str = "",
    *task_args: Any,
    parallel: bool = True,
) -> list[R]:
    """Run task_fn over items in parallel (thread pool + semaphore) or sequentially.

    Args:
        items: Iterable of inputs.
        task_fn: Callable taking (item, *task_args) -> R.
        desc: tqdm progress bar description. Empty string disables bar label.
        *task_args: Extra positional args forwarded to task_fn.
        parallel: If True use ThreadPoolExecutor; else run sequentially.

    Returns:
        List of results (order not guaranteed when parallel).
    """
    results: list[Any] = []
    cdesc = desc + f" (Active Cores:{SAFE_THREADS})"

    def semaphore_task(item: Any) -> R:
        with CPU_LIMITER:
            return task_fn(item, *task_args)

    if parallel:
        executor = _get_shared_executor()
        futures = {executor.submit(semaphore_task, item): item for item in items}

        for future in tqdm(as_completed(futures), total=len(futures), desc=cdesc):
            item = futures[future]
            try:
                results.append(future.result())
            except Exception as e:
                print(f"[Warning] Error processing {item}: {e}")
    else:
        for item in tqdm(items, desc=f"{cdesc} (seq)", miniters=1, smoothing=0):
            try:
                with CPU_LIMITER:
                    results.append(task_fn(item, *task_args))
            except Exception as e:
                print(f"[Warning] Error processing {item}: {e}")

    return results
