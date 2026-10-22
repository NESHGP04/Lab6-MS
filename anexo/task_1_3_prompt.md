# Task 1.3 — Prompt utilizado (texto exacto)

Usted y su grupo forman el equipo asesor de Aula Abierta, una plataforma de video educativo que crece por el boca a boca. El director técnico debe decidir la política de crecimiento de la infraestructura de servidores: cuándo pedir más servidores y cuántos por pedido.

El modelo combina dos paradigmas. Los usuarios activos evolucionan con System Dynamics y el clúster de servidores se simula con eventos discretos. Ambos se acoplan en los dos sentidos.

Capa SD (usuarios activos, en unidades de usuarios, con el tiempo en días). Sea U(t) el número de usuarios activos:
dU/dt = (p + q·U/M)(M − U) − δ·U,   δ = δ0 + κW·max(0, W − Wok) + κR·r
El primer término es la adopción por innovación y por boca a boca, como en el modelo de Bass. El segundo es el abandono, que aumenta con la latencia W (en segundos) y con la fracción de solicitudes rechazadas r que percibe el usuario. Valores fijos: p = 0.002 por día, M = 20,000, U(0) = 100, δ0 = 0.003 por día, κW = 1.0 por día por segundo, κR = 0.5 por día y Wok = 0.75 segundos.

Capa DES (clúster de servidores en la hora pico). El clúster es una cola M/M/c/K. Las solicitudes llegan según un proceso de Poisson de tasa λ = a·U con a = 0.0005 solicitudes por segundo por usuario activo. Cada servidor atiende con tiempo exponencial de media 0.5 segundos, es decir μ = 2 solicitudes por segundo. El sistema admite como máximo K = 60 solicitudes simultáneas, y si está lleno la solicitud nueva es rechazada. Cada vez que el SD necesita datos del DES, este simula 720 segundos de hora pico con la tasa y los servidores vigentes, descarta los primeros 120 segundos como calentamiento y devuelve la latencia promedio W de las solicitudes aceptadas (tiempo en el sistema) y la fracción rechazada r.

Política de autoescalado (evento de estado en el SD). Sea ρpred(t) = a·U(t)/(c·μ) la utilización prevista. Cuando ρpred cruza hacia arriba el umbral θ = 0.7 y no hay un pedido pendiente, se ordenan 2 servidores que llegan D días después, que es un evento de tiempo. Si al llegar ρpred sigue por encima de θ, se ordena otro pedido de inmediato. Al inicio, c(0) = 4 servidores.

Acoplamiento. Cada H días la SD entrega al DES la tasa λ = a·U y el número de servidores c, y el DES devuelve W y r, que el SD mantiene constantes hasta el siguiente intercambio. El valor base es H = 1 día.

Parámetros de mi grupo (grupo 4): q = 0.35, D = 6 días.

Escribe en Python el modelo híbrido completo (SD + DES + autoescalado + acoplamiento). Corre una réplica con H = 1 y c(0) = 4 durante 100 días, y reporta U(100), el número final de servidores, la latencia máxima y la fracción máxima de solicitudes rechazadas.
