"""Motor híbrido SD+DES para Task 3.

Extraído y parametrizado a partir de Task_2/task_2.py (des, theory, hybrid)
sin modificar ese archivo. Conserva calentamiento 120 s, ventana 720 s,
drenaje, un pedido pendiente, entrega en t+D y detección exacta de umbral.
"""
from __future__ import annotations

from collections import deque
from pathlib import Path
import heapq
import math
import sys

import numpy as np
from scipy.integrate import solve_ivp
from scipy.stats import t as student

# ---------------------------------------------------------------------------
# Parámetros Grupo 4 (fuente: Task_2/task_2.py)
# ---------------------------------------------------------------------------
P, Q, M, DELTA0 = 0.002, 0.35, 20_000.0, 0.003
A, MU, D_DEFAULT, THETA_DEFAULT = 0.0005, 2.0, 6.0, 0.7
KAPPA_W, KAPPA_R, W_OK = 1.0, 0.5, 0.75  # delta = delta0 + kW*max(0,W-Wok) + kR*r
K_CAP = 60
BASE_SEED = 20261022
TASK2_DIR = Path(__file__).resolve().parents[2] / 'Task_2'


def theory(lam, c=4, mu=MU, K=None):
    if K is not None:
        weights = [1.0]
        for n in range(1, K + 1):
            weights.append(weights[-1] * lam / (min(n, c) * mu))
        prob = np.array(weights) / sum(weights)
        r = float(prob[-1])
        eff = lam * (1 - r)
        L = float(np.dot(np.arange(K + 1), prob))
        Lq = float(np.dot(np.maximum(np.arange(K + 1) - c, 0), prob))
        return dict(
            r=r, W=L / eff if eff > 0 else 1 / mu, Wq=Lq / eff if eff > 0 else 0.0,
            L=L, Lq=Lq,
            util=float(np.dot(np.minimum(np.arange(K + 1), c), prob) / c),
        )
    load = lam / mu
    rho = load / c
    if rho >= 1:
        raise ValueError('M/M/c requiere rho < 1')
    tail = load ** c / math.factorial(c) / (1 - rho)
    C = tail / (sum(load ** k / math.factorial(k) for k in range(c)) + tail)
    Wq = C / (c * mu - lam)
    return dict(C=C, Wq=Wq, W=Wq + 1 / mu, util=rho, L=lam * (Wq + 1 / mu), Lq=lam * Wq)


def des(lam, c=4, K=60, seed=0, warm=120.0, end=720.0):
    """FCFS M/M/c/K. Misma definición operacional que Task 2."""
    ss = np.random.SeedSequence(seed)
    arng, srng = [np.random.default_rng(s) for s in ss.spawn(2)]
    arrivals = []
    t = 0.0
    while True:
        t += arng.exponential(1 / lam)
        if t >= end:
            break
        arrivals.append(t)
    services = srng.exponential(1 / MU, len(arrivals))
    heap = []
    queue = deque()
    i = 0
    n = 0
    last = 0.0
    area = areaq = busy = 0.0
    total_arr = total_rej = total_dep = 0
    measured_arr = measured_rej = measured_dep = 0
    n0 = nend = None
    ws = []
    wqs = []
    clipped = clippedq = 0.0
    while i < len(arrivals) or heap:
        at = arrivals[i] if i < len(arrivals) else math.inf
        dt = heap[0][0] if heap else math.inf
        now = min(at, dt)
        if n0 is None and now >= warm:
            n0 = n
        if nend is None and now >= end:
            nend = n
        span = max(0.0, min(now, end) - max(last, warm))
        area += n * span
        areaq += len(queue) * span
        busy += len(heap) * span
        last = now
        if at < dt:
            service = float(services[i])
            i += 1
            total_arr += 1
            measured = warm <= now < end
            measured_arr += int(measured)
            if n >= K:
                total_rej += 1
                measured_rej += int(measured)
            else:
                n += 1
                job = (now, service, measured)
                if len(heap) < c:
                    heapq.heappush(heap, (now + service, now, job))
                else:
                    queue.append(job)
        else:
            _, start, job = heapq.heappop(heap)
            arrival, service, measured = job
            n -= 1
            if now < end:
                total_dep += 1
            if warm <= now < end:
                measured_dep += 1
            clipped += max(0.0, min(now, end) - max(arrival, warm))
            clippedq += max(0.0, min(start, end) - max(arrival, warm))
            if measured:
                ws.append(now - arrival)
                wqs.append(start - arrival)
            if queue:
                job = queue.popleft()
                heapq.heappush(heap, (now + job[1], now, job))
    if n0 is None:
        n0 = 0
    if nend is None:
        nend = 0
    T = end - warm
    accepted = measured_arr - measured_rej
    assert total_arr == total_dep + total_rej + nend
    assert n0 + measured_arr == measured_dep + measured_rej + nend
    assert abs(area - clipped) < 1e-7 and abs(areaq - clippedq) < 1e-7
    return dict(
        W=float(np.mean(ws)) if ws else 1 / MU,
        Wq=float(np.mean(wqs)) if wqs else 0.0,
        r=measured_rej / measured_arr if measured_arr else 0.0,
        util=busy / (c * T),
        L=area / T,
        Lq=areaq / T,
        lam_eff=accepted / T,
        generated=measured_arr,
        rejected=measured_rej,
        departed=measured_dep,
        initial=n0,
        final=nend,
        total_generated=total_arr,
        total_rejected=total_rej,
        total_departed=total_dep,
        balance=n0 + measured_arr - measured_dep - measured_rej - nend,
        little_exact_error=abs(area - clipped) / max(area, 1e-12),
    )


def ci(values):
    values = np.asarray(values, float)
    if len(values) == 0:
        return dict(mean=float('nan'), low=float('nan'), high=float('nan'), n=0)
    mean = float(values.mean())
    if len(values) == 1 or float(values.std(ddof=1)) == 0.0:
        return dict(mean=mean, low=mean, high=mean, n=len(values))
    half = float(student.ppf(0.975, len(values) - 1) * values.std(ddof=1) / np.sqrt(len(values)))
    return dict(mean=mean, low=mean - half, high=mean + half, n=len(values))


def rhs(u, delta=DELTA0):
    return (P + Q * u / M) * (M - u) - delta * u


def des_metrics(lam, c, seed, des_mode='stochastic'):
    """des_mode: 'stochastic' (Task 2) o 'theory' (M/M/c/K estacionario, sin ruido)."""
    if des_mode == 'theory':
        if lam <= 0:
            return dict(W=1 / MU, r=0.0, Wq=0.0, util=0.0, L=0.0, Lq=0.0, lam_eff=0.0)
        th = theory(lam, c=c, K=K_CAP)
        return dict(W=th['W'], r=th['r'], Wq=th['Wq'], util=th['util'], L=th['L'], Lq=th['Lq'],
                    lam_eff=lam * (1 - th['r']))
    return des(lam, c=c, K=K_CAP, seed=seed)


def hybrid(
    mode='exact',
    seed=BASE_SEED,
    H=1.0,
    horizon=100.0,
    theta=THETA_DEFAULT,
    k_order=2,
    D=D_DEFAULT,
    des_mode='stochastic',
    grid_dt=1.0,
):
    """Híbrido con detección exacta opcional y parámetros de política.

    Orden de coincidencias (Task 2 / LEAME): entrega y reorden, intercambio DES,
    revisión ingenua. W y r se congelan entre intercambios.
    Un solo pedido pendiente; entrega suma k_order servidores.
    """
    t = 0.0
    u = 100.0
    c = 4
    pending = None
    orders = []
    deliveries = []
    windows = []
    trajectory = [(t, u, c)]
    step = {'naive1': 1.0, 'naive025': 0.25}.get(mode)
    next_check = step if step else math.inf
    next_exchange = 0.0
    delta = DELTA0
    last_W, last_r = 1 / MU, 0.0

    while t < horizon - 1e-9:
        if pending is not None and abs(t - pending) < 1e-8:
            c += k_order
            deliveries.append((t, c))
            pending = None
            if A * u / (c * MU) > theta:
                orders.append(t)
                pending = t + D
        if abs(t - next_exchange) < 1e-8:
            idx = round(t / H)
            met = des_metrics(A * u, c, seed=[seed, idx], des_mode=des_mode)
            windows.append(dict(t=t, U=u, c=c, **{k: met[k] for k in ('W', 'r', 'Wq', 'util')}))
            last_W, last_r = met['W'], met['r']
            delta = DELTA0 + KAPPA_W * max(0.0, met['W'] - W_OK) + KAPPA_R * met['r']
            next_exchange += H
        if step and abs(t - next_check) < 1e-8:
            if pending is None and A * u / (c * MU) > theta:
                orders.append(t)
                pending = t + D
            next_check += step
        end = min(
            next_exchange,
            pending if pending is not None else math.inf,
            next_check,
            horizon,
        )

        def crossing(tt, yy):
            return A * yy[0] / (c * MU) - theta

        crossing.terminal = True
        crossing.direction = 1
        events = crossing if mode == 'exact' and pending is None else None
        sol = solve_ivp(
            lambda tt, yy: [rhs(yy[0], delta)],
            (t, end),
            [u],
            rtol=1e-10,
            atol=1e-10,
            max_step=0.25,
            events=events,
        )
        for tt, uu in zip(sol.t[1:], sol.y[0, 1:]):
            trajectory.append((float(tt), float(uu), c))
        t = float(sol.t[-1])
        u = float(sol.y[0, -1])
        assert 0 <= u <= M
        if events is not None and len(sol.t_events[0]):
            orders.append(t)
            pending = t + D

    if pending is not None and abs(pending - horizon) < 1e-8:
        c += k_order
        deliveries.append((horizon, c))

    grid = np.arange(0.0, horizon + 1e-12, grid_dt)
    U_grid, c_grid, W_grid, r_grid = _sample_grids(trajectory, windows, deliveries, c, grid, horizon)

    return dict(
        mode=mode,
        seed=seed,
        H=H,
        horizon=horizon,
        theta=theta,
        k_order=k_order,
        des_mode=des_mode,
        U100=float(U_grid[-1]) if abs(horizon - 100) < 1e-9 else float(u),
        U_end=float(u),
        c_end=int(c),
        c100=int(c) if abs(horizon - 100) < 1e-9 else int(c),
        first_order=orders[0] if orders else None,
        first_delivery=deliveries[0][0] if deliveries else None,
        Wmax=max((w['W'] for w in windows), default=1 / MU),
        rmax=max((w['r'] for w in windows), default=0.0),
        n_orders=len(orders),
        orders=orders,
        deliveries=deliveries,
        windows=windows,
        trajectory=trajectory,
        grid_t=grid,
        U_grid=U_grid,
        c_grid=c_grid,
        W_grid=W_grid,
        r_grid=r_grid,
    )


def _sample_grids(trajectory, windows, deliveries, c_final, grid, horizon):
    tr = np.array(trajectory)
    # U: interpolación lineal en la trayectoria continua
    U_grid = np.interp(grid, tr[:, 0], tr[:, 1])
    # c: escalón post-entregas (incluye c0=4)
    c_times = [0.0] + [d[0] for d in deliveries] + [horizon]
    c_vals = [4] + [d[1] for d in deliveries] + [c_final]
    c_grid = np.empty_like(grid)
    for i, tg in enumerate(grid):
        j = max(0, np.searchsorted(c_times, tg, side='right') - 1)
        c_grid[i] = c_vals[min(j, len(c_vals) - 1)]
    # W,r: escalón por ventana de intercambio (último valor conocido)
    W_grid = np.full_like(grid, 1 / MU)
    r_grid = np.zeros_like(grid)
    if windows:
        wt = [w['t'] for w in windows]
        ww = [w['W'] for w in windows]
        rr = [w['r'] for w in windows]
        for i, tg in enumerate(grid):
            j = max(0, np.searchsorted(wt, tg, side='right') - 1)
            W_grid[i] = ww[j]
            r_grid[i] = rr[j]
    return U_grid, c_grid, W_grid, r_grid


def rrmse(U_h, U_ref):
    """Error relativo cuadrático medio (sin porcentaje)."""
    U_h = np.asarray(U_h, float)
    U_ref = np.asarray(U_ref, float)
    den = math.sqrt(float(np.mean(U_ref ** 2)))
    if den == 0:
        return 0.0 if np.allclose(U_h, U_ref) else float('inf')
    return math.sqrt(float(np.mean((U_h - U_ref) ** 2))) / den


def net_income(U_daily, c_daily):
    """N = sum_{d=1}^{T} U_d - 40 * sum_{d=1}^{T} c_d.

    Convención: índices 1..T usan los valores en t=d (fin de cada día),
    es decir U_grid[1],...,U_grid[T] cuando grid_dt=1 y grid incluye 0..T.
    """
    U_daily = np.asarray(U_daily, float)
    c_daily = np.asarray(c_daily, float)
    return float(U_daily.sum() - 40.0 * c_daily.sum())


def wilson_ci(successes, n, z=1.959963984540054):
    """IC 95 % binomial de Wilson para proporción."""
    if n == 0:
        return dict(p=float('nan'), low=float('nan'), high=float('nan'))
    p = successes / n
    den = 1 + z ** 2 / n
    centre = (p + z ** 2 / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z ** 2 / (4 * n ** 2)) / den
    return dict(p=p, low=max(0.0, centre - half), high=min(1.0, centre + half))


def smoke_match_task2(seed=BASE_SEED):
    """Compara una réplica exacta H=1 con Task_2.hybrid si es importable."""
    ours = hybrid(mode='exact', seed=seed, H=1.0, horizon=100.0)
    out = {
        'ours': dict(
            first_order=ours['first_order'],
            U_end=ours['U_end'],
            c_end=ours['c_end'],
            Wmax=ours['Wmax'],
            rmax=ours['rmax'],
        )
    }
    if not TASK2_DIR.exists():
        out['task2'] = None
        out['ok'] = False
        out['note'] = 'Task_2 no encontrado'
        return out
    sys.path.insert(0, str(TASK2_DIR))
    try:
        import task_2 as t2  # noqa: WPS433
        ref = t2.hybrid(mode='exact', seed=seed, H=1.0, horizon=100.0)
        out['task2'] = dict(
            first_order=ref['first_order'],
            U_end=ref['U100'],
            c_end=ref['c100'],
            Wmax=ref['Wmax'],
            rmax=ref['rmax'],
        )
        out['ok'] = (
            abs(ours['first_order'] - ref['first_order']) < 1e-8
            and abs(ours['U_end'] - ref['U100']) < 1e-6
            and ours['c_end'] == ref['c100']
        )
    except Exception as exc:  # noqa: BLE001
        out['task2'] = None
        out['ok'] = False
        out['note'] = str(exc)
    finally:
        if sys.path and sys.path[0] == str(TASK2_DIR):
            sys.path.pop(0)
    return out
