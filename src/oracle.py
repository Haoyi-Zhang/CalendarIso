"""Independent exact finite oracle; does not import or call the admission test.

For each displaced tenant, enumerate all legal arrival amounts at every slot,
merging identical (queue, token, service) states. Product independence is
separately validated by the joint oracle in the test suite.
"""
from __future__ import annotations
from typing import Any

def exhaustive(state: dict[str, Any], borrower: int, length: int) -> tuple[bool, int]:
    cal, phase = state['calendar'], state['phase']
    explored = 0
    for i, t in enumerate(state['tenants']):
        if i == borrower:
            continue
        frontier = {(t['backlog'] + t['lead'], t['tokens'], 0)}
        for s in range(length):
            nxt = set()
            for q, x, done in frontier:
                if s:
                    if s >= t['refill'] and (s - t['refill']) % t['period'] == 0:
                        x = min(t['bucket'], x + 1)
                    choices = range(min(x, t['capacity'] - q) + 1)
                else:
                    choices = (0,)
                for a in choices:
                    explored += 1
                    q2, x2, done2 = q + a, x - a, done
                    if cal[(phase + s) % len(cal)] == i and q2 > 0:
                        q2 -= 1
                        done2 += 1
                    if done2 > t['lead']:
                        return False, explored
                    nxt.add((q2, x2, done2))
            frontier = nxt
    return True, explored


def one_arrival_check(state: dict[str, Any], borrower: int, length: int) -> tuple[bool, int | None]:
    """Replay zero/one arrival at EVERY offset; different implementation from producer.

This reduced checker relies on the general single-arrival theorem. The exhaustive
oracle above does not rely on that theorem. Return earliest violating offset.
"""
    bad = []
    for i, t in enumerate(state['tenants']):
        if i == borrower:
            continue
        for release in [None, *range(1, length)]:
            q, x, served = t['backlog'] + t['lead'], t['tokens'], 0
            legal = True
            earliest = None
            for s in range(length):
                if s and s >= t['refill'] and (s - t['refill']) % t['period'] == 0:
                    x = min(t['bucket'], x + 1)
                if s == release:
                    if not x or q == t['capacity']:
                        legal = False
                        break
                    q += 1
                    x -= 1
                if state['calendar'][(state['phase'] + s) % len(state['calendar'])] == i and q:
                    q -= 1
                    served += 1
                if served > t['lead'] and earliest is None:
                    earliest = s
            if legal and earliest is not None:
                bad.append(earliest)
    return (not bad, min(bad) if bad else None)


def replay_witness(state: dict[str, Any], certificate: dict[str, Any]) -> bool:
    """Validate a rejected certificate's explicit legal path and first failure."""
    w = certificate['witness']
    if not isinstance(w, dict):
        return False
    i = w.get('tenant')
    if type(i) is not int or not 0 <= i < len(state['tenants']) or i == certificate['borrower']:
        return False
    t = state['tenants'][i]
    arr = w.get('arrivals')
    if type(arr) is not list or len(arr) > 1:
        return False
    if arr:
        if (type(arr[0]) is not list or len(arr[0]) != 3 or
                any(type(v) is not int for v in arr[0]) or arr[0][1:] != [i, 1] or
                not 1 <= arr[0][0] < certificate['length']):
            return False
    q, x, done = t['backlog'] + t['lead'], t['tokens'], 0
    for s in range(certificate['length']):
        if s and s >= t['refill'] and (s - t['refill']) % t['period'] == 0:
            x = min(t['bucket'], x + 1)
        if arr and arr[0][0] == s:
            if not x or q >= t['capacity']:
                return False
            q += 1
            x -= 1
        if state['calendar'][(state['phase'] + s) % len(state['calendar'])] == i and q:
            q -= 1
            done += 1
        if done > t['lead']:
            return s == w.get('violation_offset')
    return False
