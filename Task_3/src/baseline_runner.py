"""Baseline Task 1.3 con semillas configurables, sin alterar sus reglas.

Réplica fiel de anexo/task_1_3_baseline.py: intercambio al inicio de cada
ventana H, autoescalado solo en extremos de ventana (no localiza cruce
continuo), DES propio con warm 120 / end 720.
"""
from __future__ import annotations

import heapq

import numpy as np
from scipy.integrate import solve_ivp

p, q, M = 0.002, 0.35, 20_000
delta0, kW, kR, W_ok = 0.003, 1.0, 0.5, 0.75
a, mu, K = 0.0005, 2.0, 60
theta, k_pedido, D = 0.7, 2, 6
T_VENTANA, T_CALENT = 720.0, 120.0


def simular_des(lam, c, rng):
    if lam <= 0:
        return 1.0 / mu, 0.0
    t = rng.exponential(1.0 / lam)
    eventos = []
    cola = []
    en_servicio = 0
    llegadas = rechazos = 0
    suma_W, aceptadas = 0.0, 0
    while True:
        if eventos and eventos[0][0] <= t:
            ts, t_lleg = heapq.heappop(eventos)
            if ts > T_VENTANA:
                break
            if t_lleg >= T_CALENT:
                suma_W += ts - t_lleg
                aceptadas += 1
            en_servicio -= 1
            if cola:
                t_lleg2 = cola.pop(0)
                heapq.heappush(eventos, (ts + rng.exponential(1.0 / mu), t_lleg2))
                en_servicio += 1
        else:
            if t > T_VENTANA:
                break
            medir = t >= T_CALENT
            if medir:
                llegadas += 1
            if en_servicio + len(cola) >= K:
                if medir:
                    rechazos += 1
            elif en_servicio < c:
                heapq.heappush(eventos, (t + rng.exponential(1.0 / mu), t))
                en_servicio += 1
            else:
                cola.append(t)
            t += rng.exponential(1.0 / lam)
    W = suma_W / aceptadas if aceptadas > 0 else 1.0 / mu
    r = rechazos / llegadas if llegadas > 0 else 0.0
    return W, r


def dUdt(t, U, W, r):
    delta = delta0 + kW * max(0.0, W - W_ok) + kR * r
    return (p + q * U / M) * (M - U) - delta * U


def correr_hibrido(H=1.0, c0=4, horizonte=100.0, seed=42):
    """Misma lógica que el baseline; solo se parametriza la semilla del RNG."""
    rng = np.random.default_rng(seed)
    t, U, c = 0.0, 100.0, c0
    pedido_llega = None
    historial = []
    orders = []
    deliveries = []
    while t < horizonte - 1e-12:
        W, r = simular_des(a * U, c, rng)
        t_fin = min(t + H, horizonte)
        sol = solve_ivp(dUdt, (t, t_fin), [U], args=(W, r), rtol=1e-6, atol=1e-6)
        U = float(sol.y[0, -1])
        t = t_fin
        if pedido_llega is not None and t >= pedido_llega:
            c += k_pedido
            deliveries.append(t)
            pedido_llega = None
            if a * U / (c * mu) > theta:
                pedido_llega = t + D
                orders.append(t)
        elif pedido_llega is None and a * U / (c * mu) > theta:
            pedido_llega = t + D
            orders.append(t)
        historial.append((t, U, c, W, r))
    hist = np.array(historial)
    return dict(
        seed=seed,
        U100=float(hist[-1, 1]),
        c100=int(hist[-1, 2]),
        Wmax=float(hist[:, 3].max()),
        rmax=float(hist[:, 4].max()),
        first_order=orders[0] if orders else None,
        first_delivery=deliveries[0] if deliveries else None,
        n_orders=len(orders),
        historial=hist,
    )
