"""Task 1.2 – Equilibrio del lazo con capacidad fija (c = 4, sin rechazos, r = 0).

(a) Latencia de la fila M/M/c en función de U (Erlang C) y su dominio de validez.
(b) Ecuación del equilibrio U* del SD acoplado, resuelta numéricamente; se reportan U*, rho y W.
(c) La explicación escrita va en el documento; aquí se genera la figura que la respalda.

Parámetros del grupo g = 4:  q = 0.20 + 0.05((g-1) mod 4) = 0.35,  D = 3 + ((g-1) mod 4) = 6 días
(D no interviene en este task: sin autoescalado).
"""
import os

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from scipy.optimize import brentq

# ---------------- Parámetros ----------------
g = 4
q = 0.20 + 0.05 * ((g - 1) % 4)        # coeficiente de boca a boca
p = 0.002                              # innovación (por día)
M = 20_000                             # mercado potencial (usuarios)
delta0, kappa_W, W_ok = 0.003, 1.0, 0.75   # abandono base, sensibilidad a latencia, latencia tolerada
a = 0.0005                             # solicitudes/s por usuario activo
mu = 2.0                               # solicitudes/s que atiende un servidor
c = 4                                  # servidores (fijos)

U_max_valido = c * mu / a              # estabilidad de la fila: a·U < c·mu  ->  U < 16 000


# ---------------- (a) Latencia M/M/c ----------------
def erlang_c(c, A):
    """Probabilidad de esperar C(c, A). Se calcula con la recursión de Erlang B (estable
    numéricamente) y C = B / (1 - (A/c)(1 - B)). Válida para A < c."""
    B = 1.0
    for k in range(1, c + 1):
        B = A * B / (k + A * B)
    return B / (1.0 - (A / c) * (1.0 - B))


def latencia(U):
    """W(U) = C(c, A)/(c·mu - a·U) + 1/mu, con A = a·U/mu. Válida para 0 <= U < c·mu/a."""
    A = a * U / mu
    return erlang_c(c, A) / (c * mu - a * U) + 1.0 / mu


# ---------------- (b) Equilibrio del SD acoplado ----------------
def adopcion(U):
    """Adopción: (p + q U/M)(M - U)."""
    return (p + q * U / M) * (M - U)


def abandono(U):
    """Abandono con la latencia de equilibrio (r = 0): [delta0 + kW max(0, W - Wok)] U."""
    W = latencia(U)
    return (delta0 + kappa_W * max(0.0, W - W_ok)) * U


def f(U):
    """dU/dt evaluado en el lazo cerrado; el equilibrio cumple f(U*) = 0."""
    return adopcion(U) - abandono(U)


if __name__ == '__main__':
    # Se barre el dominio válido buscando todos los cambios de signo (puede haber más de un equilibrio).
    grid = np.linspace(1.0, U_max_valido - 1e-6, 20_000)
    vals = np.array([f(u) for u in grid])
    raices = [brentq(f, grid[i], grid[i + 1], xtol=1e-10)
              for i in range(len(grid) - 1) if vals[i] * vals[i + 1] < 0]
    assert len(raices) >= 1, 'no se encontró equilibrio en el dominio válido'

    print(f'Grupo {g}: q = {q:.2f}   |   dominio válido de W(U): 0 <= U < {U_max_valido:.0f}')
    print(f'Equilibrios encontrados: {len(raices)}')
    for U_star in raices:
        A = a * U_star / mu
        rho = A / c
        W = latencia(U_star)
        print(f'  U* = {U_star:10.3f}   rho = {rho:.5f}   W = {W:.5f} s   '
              f'(residuo f(U*) = {f(U_star):.2e})')
        print(f'  penalización de latencia kW·max(0, W-Wok) = {kappa_W * max(0, W - W_ok):.5f} /día')

    # ---------------- Figura: adopción vs abandono ----------------
    us = np.linspace(1.0, U_max_valido - 1e-6, 2000)
    fig, ax = plt.subplots(1, 2, figsize=(12, 4.2))
    ax[0].plot(us, [adopcion(u) for u in us], label='adopción  $(p+qU/M)(M-U)$')
    ax[0].plot(us, [abandono(u) for u in us], label='abandono  $\\delta(W(U))\\,U$')
    for U_star in raices:
        ax[0].axvline(U_star, color='k', ls=':', lw=1)
    ax[0].set_xlabel('U (usuarios)'); ax[0].set_ylabel('usuarios/día'); ax[0].legend()
    ax[0].set_title('Equilibrio con c = 4 fijo')
    ax[1].plot(us, [latencia(u) for u in us])
    ax[1].axhline(W_ok, color='r', ls='--', lw=1, label='$W_{ok}$ = 0.75 s')
    ax[1].set_ylim(0, 5); ax[1].set_xlabel('U (usuarios)'); ax[1].set_ylabel('W (s)')
    ax[1].set_title('Latencia M/M/4 en función de U'); ax[1].legend()
    fig.tight_layout()
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'figuras', 'task_1_2_equilibrio.png')
    fig.savefig(out, dpi=150)
    print('Figura:', out)
