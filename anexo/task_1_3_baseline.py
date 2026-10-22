"""Modelo híbrido SD + DES para Aula Abierta (línea base generada por IA, Task 1.3).

SD  : dU/dt = (p + q U/M)(M - U) - delta U, con delta = delta0 + kW max(0, W - Wok) + kR r
DES : cola M/M/c/K simulada por eventos en ventanas de 720 s (calentamiento de 120 s)
Acoplamiento: cada H días se calcula (W, r) con el DES y se mantienen constantes en el SD.
Autoescalado: si rho_pred = a U / (c mu) supera theta y no hay pedido pendiente, se piden 2 servidores
que llegan D días después.
"""
import heapq

import numpy as np
from scipy.integrate import solve_ivp

# ---------------- Parámetros ----------------
p, q, M = 0.002, 0.35, 20_000          # q del grupo 4
delta0, kW, kR, W_ok = 0.003, 1.0, 0.5, 0.75
a, mu, K = 0.0005, 2.0, 60
theta, k_pedido, D = 0.7, 2, 6         # D del grupo 4
T_VENTANA, T_CALENT = 720.0, 120.0     # segundos
rng = np.random.default_rng(42)


# ---------------- Capa DES ----------------
def simular_des(lam, c):
    """Simula una cola M/M/c/K durante T_VENTANA segundos y devuelve (W, r)
    medidos sobre las solicitudes que llegan después del calentamiento."""
    if lam <= 0:
        return 1.0 / mu, 0.0
    t = rng.exponential(1.0 / lam)
    eventos = []                       # heap de salidas: (tiempo_salida, tiempo_llegada)
    cola = []                          # llegadas en espera (FIFO)
    en_servicio = 0
    llegadas = rechazos = 0
    suma_W, aceptadas = 0.0, 0
    while True:
        # próximo evento: llegada (t) o salida (eventos[0])
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


# ---------------- Capa SD ----------------
def dUdt(t, U, W, r):
    delta = delta0 + kW * max(0.0, W - W_ok) + kR * r
    return (p + q * U / M) * (M - U) - delta * U


# ---------------- Híbrido ----------------
def correr_hibrido(H=1.0, c0=4, horizonte=100.0):
    t, U, c = 0.0, 100.0, c0
    pedido_llega = None                # día de llegada del pedido pendiente (None = no hay)
    historial = []
    while t < horizonte - 1e-12:
        # intercambio: el SD entrega lambda y c al DES; el DES devuelve W y r
        W, r = simular_des(a * U, c)
        # el SD integra una ventana de H días con W y r constantes
        t_fin = min(t + H, horizonte)
        sol = solve_ivp(dUdt, (t, t_fin), [U], args=(W, r), rtol=1e-6, atol=1e-6)
        U = sol.y[0, -1]
        t = t_fin
        # llegada de servidores
        if pedido_llega is not None and t >= pedido_llega:
            c += k_pedido
            pedido_llega = None
            if a * U / (c * mu) > theta:      # sigue por encima del umbral: pedir otro de inmediato
                pedido_llega = t + D
        # autoescalado: revisar el umbral
        elif pedido_llega is None and a * U / (c * mu) > theta:
            pedido_llega = t + D
        historial.append((t, U, c, W, r))
    return np.array(historial)


if __name__ == '__main__':
    h = correr_hibrido(H=1.0, c0=4, horizonte=100.0)
    print(f'U(100)                     = {h[-1, 1]:.1f}')
    print(f'Servidores finales         = {int(h[-1, 2])}')
    print(f'Latencia máxima            = {h[:, 3].max():.4f} s')
    print(f'Fracción máx. rechazadas   = {h[:, 4].max():.4f}')
