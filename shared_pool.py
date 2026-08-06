# Persistent shared batch pool for the whole run.

import asyncio
import time

from openai import AsyncOpenAI

from api_config import load_api_configs, REQUEST_INTERVAL


class _Job:
    __slots__ = ("batch_num", "batch", "func", "ctx", "fut", "retried")

    def __init__(self, batch_num, batch, func, ctx, fut):
        self.batch_num = batch_num
        self.batch = batch
        self.func = func
        self.ctx = ctx
        self.fut = fut
        self.retried = False


class SharedBatchPool:
    # Persistent shared batch pool.
    # One pool per run owns all API configs, clients, semaphores and 429 state.
    # Contract for process functions:
    #   - success -> return the result (pool resolves the future)
    #   - 429     -> call pool.retry(job) then return None (job is requeued)
    #   - error   -> raise (pool sets exception on the future)

    def __init__(self, api_configs=None):
        self.api_configs = api_configs if api_configs is not None else load_api_configs()
        self._queue = asyncio.Queue()
        self._worker_states = []
        self._workers = []
        self._closed = False
        self._loop = None

    async def start(self):
        self._loop = asyncio.get_running_loop()
        active = [c for c in self.api_configs if not c.is_permanently_disabled]
        if not active:
            raise RuntimeError("no available API")
        for cfg in active:
            self._worker_states.append({
                "cfg": cfg,
                "client": AsyncOpenAI(api_key=cfg.key, base_url=cfg.base_url),
                "sem": asyncio.Semaphore(cfg.parallel_limit),
                "rate_lock": asyncio.Lock(),
                "last_request": 0.0,
                "active_count": 0,
            })
        # 每個 API 建立 parallel_limit 個 worker，才能真正並行處理多個批次
        self._workers = [
            asyncio.create_task(self._worker_loop(ws))
            for ws in self._worker_states
            for _ in range(ws["cfg"].parallel_limit)
        ]

    async def submit(self, batch_num, batch, func, ctx=None):
        fut = self._loop.create_future()
        job = _Job(batch_num, batch, func, ctx, fut)
        await self._queue.put(job)
        return await fut

    def retry(self, job):
        job.retried = True
        self._queue.put_nowait(job)

    async def close(self):
        self._closed = True
        for w in self._workers:
            w.cancel()
        if self._workers:
            await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers = []

    async def _fail_all_queued(self, message):
        while True:
            try:
                job = self._queue.get_nowait()
            except asyncio.QueueEmpty:
                return
            if not job.fut.done():
                job.fut.set_exception(RuntimeError(message))

    async def _worker_loop(self, ws):
        cfg = ws["cfg"]
        while not self._closed:
            if cfg.is_cooling_down or cfg.is_permanently_disabled:
                await asyncio.sleep(1)
                continue
            try:
                job = self._queue.get_nowait()
            except asyncio.QueueEmpty:
                await asyncio.sleep(0.2)
                continue
            job.retried = False
            async with ws["sem"]:
                async with ws["rate_lock"]:
                    now = time.monotonic()
                    gap = REQUEST_INTERVAL - (now - ws["last_request"])
                    if gap > 0:
                        await asyncio.sleep(gap)
                    ws["last_request"] = time.monotonic()
                ws["active_count"] += 1
                try:
                    result = await job.func(ws, job)
                except Exception as e:
                    if not job.retried:
                        job.fut.set_exception(e)
                else:
                    if not job.retried:
                        job.fut.set_result(result)
                finally:
                    ws["active_count"] -= 1
                if self._queue.qsize() > 0 and all(c.is_permanently_disabled for c in self.api_configs):
                    await self._fail_all_queued("all APIs permanently disabled")
