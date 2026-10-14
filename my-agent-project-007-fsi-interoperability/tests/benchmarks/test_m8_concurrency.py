"""Task 12 -- Tenant semaphore: 3 concurrent per tenant."""

import time

from m8_pipeline_engine.graph import (
    _TENANT_SEMAPHORES,
    _acquire_tenant_slot,
)


def test_semaphore_is_three_per_tenant():
    sem = _TENANT_SEMAPHORES["test-tenant-A"]
    acquired = []
    for _ in range(3):
        acquired.append(sem.acquire(timeout=1))
    assert all(acquired)
    assert sem.acquire(timeout=0.1) is False
    for _ in range(3):
        sem.release()


def test_semaphore_acquire_timeout_returns_false():
    tenant = "test-tenant-B"
    sem = _TENANT_SEMAPHORES[tenant]
    for _ in range(3):
        sem.acquire(timeout=1)
    start = time.perf_counter()
    ok = _acquire_tenant_slot(tenant, timeout_s=1)
    assert ok is False
    elapsed = time.perf_counter() - start
    assert 0.9 <= elapsed <= 1.5
    for _ in range(3):
        sem.release()
