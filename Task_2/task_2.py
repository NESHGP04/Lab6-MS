"""Aula Abierta, grupo 4. Ejecutar: python task_2.py

Dependencias: numpy, scipy, matplotlib. Salidas junto al script.
Las unidades del DES son segundos; las del SD son días.
"""
from pathlib import Path
from collections import deque
import heapq
import json
import csv
import math
import numpy as np
from scipy.integrate import solve_ivp
from scipy.stats import t as student, chi2
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

OUT = Path(__file__).resolve().parent
P, Q, M, DELTA0 = .002, .35, 20000., .003
A, MU, D, THETA = .0005, 2., 6., .7
BASE_SEED = 20261022

def theory(lam, c=4, mu=MU, K=None):
    if K is not None:
        weights = [1.]
        for n in range(1, K+1):
            weights.append(weights[-1]*lam/(min(n,c)*mu))
        prob = np.array(weights)/sum(weights)
        r = float(prob[-1]); eff = lam*(1-r)
        L = float(np.dot(np.arange(K+1), prob))
        Lq = float(np.dot(np.maximum(np.arange(K+1)-c,0), prob))
        return dict(r=r, W=L/eff, Wq=Lq/eff, L=L, Lq=Lq,
                    util=float(np.dot(np.minimum(np.arange(K+1),c),prob)/c))
    load=lam/mu; rho=load/c
    if rho>=1: raise ValueError('M/M/c requiere rho < 1')
    tail=load**c/math.factorial(c)/(1-rho)
    C=tail/(sum(load**k/math.factorial(k) for k in range(c))+tail)
    Wq=C/(c*mu-lam)
    return dict(C=C,Wq=Wq,W=Wq+1/mu,util=rho,L=lam*(Wq+1/mu),Lq=lam*Wq)

def des(lam, c=4, K=60, seed=0, warm=120., end=720.):
    """FCFS M/M/c/K. Reinicio vacío y calentamiento en cada llamada.

    W y Wq: cohorte aceptada que llega en [warm,end). Se drena sin
    nuevas llegadas para observar tiempos completos, sin ampliar áreas ni conteos.
    Áreas N, cola y ocupación: solo [warm,end). Los balances usan todos
    los clientes, incluidos los que atraviesan el inicio de la medición.
    Dos flujos aleatorios por ventana; se sortea servicio aun si hay rechazo.
    """
    ss=np.random.SeedSequence(seed)
    arng,srng=[np.random.default_rng(s) for s in ss.spawn(2)]
    arrivals=[]; t=0.
    while True:
        t+=arng.exponential(1/lam)
        if t>=end: break
        arrivals.append(t)
    services=srng.exponential(1/MU,len(arrivals))
    heap=[]; queue=deque(); i=0; n=0; last=0.
    area=areaq=busy=0.; total_arr=total_rej=total_dep=0
    measured_arr=measured_rej=measured_dep=0; n0=None; nend=None
    ws=[]; wqs=[]; clipped=clippedq=0.
    while i<len(arrivals) or heap:
        at=arrivals[i] if i<len(arrivals) else math.inf
        dt=heap[0][0] if heap else math.inf
        now=min(at,dt)
        if n0 is None and now>=warm: n0=n
        if nend is None and now>=end: nend=n
        span=max(0.,min(now,end)-max(last,warm))
        area+=n*span; areaq+=len(queue)*span; busy+=len(heap)*span
        last=now
        if at<dt:
            service=float(services[i]); i+=1; total_arr+=1
            measured=warm<=now<end
            measured_arr+=int(measured)
            if n>=K:
                total_rej+=1; measured_rej+=int(measured)
            else:
                n+=1
                job=(now,service,measured)
                if len(heap)<c:
                    heapq.heappush(heap,(now+service,now,job))
                else: queue.append(job)
        else:
            _,start,job=heapq.heappop(heap)
            arrival,service,measured=job; n-=1
            if now<end: total_dep+=1
            if warm<=now<end: measured_dep+=1
            clipped+=max(0.,min(now,end)-max(arrival,warm))
            clippedq+=max(0.,min(start,end)-max(arrival,warm))
            if measured: ws.append(now-arrival); wqs.append(start-arrival)
            if queue:
                job=queue.popleft()
                heapq.heappush(heap,(now+job[1],now,job))
    if n0 is None: n0=0
    if nend is None: nend=0
    T=end-warm; accepted=measured_arr-measured_rej
    assert total_arr==total_dep+total_rej+nend
    assert n0+measured_arr==measured_dep+measured_rej+nend
    assert abs(area-clipped)<1e-7 and abs(areaq-clippedq)<1e-7
    return dict(W=float(np.mean(ws)) if ws else 1/MU,
                Wq=float(np.mean(wqs)) if wqs else 0.,
                r=measured_rej/measured_arr if measured_arr else 0.,
                util=busy/(c*T),L=area/T,Lq=areaq/T,lam_eff=accepted/T,
                generated=measured_arr,rejected=measured_rej,departed=measured_dep,
                initial=n0,final=nend,total_generated=total_arr,
                total_rejected=total_rej,total_departed=total_dep,
                balance=n0+measured_arr-measured_dep-measured_rej-nend,
                little_exact_error=abs(area-clipped)/max(area,1e-12))

def ci(values):
    values=np.asarray(values,float); mean=float(values.mean())
    half=float(student.ppf(.975,len(values)-1)*values.std(ddof=1)/np.sqrt(len(values)))
    return dict(mean=mean,low=mean-half,high=mean+half)

def rhs(u, delta=DELTA0):
    return (P+Q*u/M)*(M-u)-delta*u

def rk4(u,h,delta=DELTA0):
    k1=rhs(u,delta); k2=rhs(u+h*k1/2,delta)
    k3=rhs(u+h*k2/2,delta); k4=rhs(u+h*k3,delta)
    return u+h*(k1+2*k2+2*k3+k4)/6

def sd_verification():
    ref=solve_ivp(lambda t,y:[rhs(y[0])],[0,100],[100.],
                  method='DOP853',rtol=1e-10,atol=1e-10,dense_output=True)
    # Solución cerrada de la ecuación de Riccati: verificación adicional.
    b=Q-P-DELTA0; disc=np.sqrt(b*b+4*(Q/M)*(P*M))
    up=(b+disc)/(2*Q/M); un=(b-disc)/(2*Q/M)
    def analytic(t):
        z=(100-up)/(100-un)*np.exp(-disc*np.asarray(t))
        return (up-z*un)/(1-z)
    hs=[1.,.5,.25,.125,.0625]; rows=[]; trajectories={}
    for h in hs:
        times=np.linspace(0,100,round(100/h)+1); exact=ref.sol(times)[0]
        for method in ('Euler','RK4'):
            us=[100.]
            for _ in times[1:]:
                us.append(us[-1]+h*rhs(us[-1]) if method=='Euler' else rk4(us[-1],h))
            err=float(np.max(np.abs(np.array(us)-exact)))
            rows.append(dict(method=method,h=h,error=err))
            if h==.25: trajectories[method]=(times,np.array(us))
    orders={method:float(np.polyfit(np.log([r['h'] for r in rows if r['method']==method][-3:]),
                                       np.log([r['error'] for r in rows if r['method']==method][-3:]),1)[0])
            for method in ('Euler','RK4')}
    times=np.linspace(0,100,1001)
    fig,ax=plt.subplots(1,2,figsize=(10,3.7))
    ax[0].plot(times,ref.sol(times)[0],label='solve_ivp')
    ax[0].plot(*trajectories['RK4'],ls='--',label='RK4 h = 0.25')
    ax[0].plot(*trajectories['Euler'],ls=':',label='Euler h = 0.25')
    ax[0].set(xlabel='Tiempo (días)',ylabel='Usuarios activos'); ax[0].legend()
    for method in ('Euler','RK4'):
        rr=[r for r in rows if r['method']==method]
        ax[1].loglog([r['h'] for r in rr],[r['error'] for r in rr],'o-',label=f'{method}, orden {orders[method]:.2f}')
    ax[1].set(xlabel='Paso (días)',ylabel='Error máximo (usuarios)'); ax[1].legend()
    fig.tight_layout(); fig.savefig(OUT/'figuras/convergencia.png',dpi=170); plt.close(fig)
    return dict(rows=rows,orders=orders,U100=float(ref.y[0,-1]),
                reference_error=float(np.max(abs(ref.sol(times)[0]-analytic(times)))))

def hybrid(mode='exact', seed=BASE_SEED, H=1., horizon=100.):
    """Datos DES congelados entre intercambios; llegadas no fuerzan intercambio.

    En coincidencias: entrega y reorden, intercambio DES, revisión ingenua.
    La revisión ingenua se realiza en la malla global dt, no en pasos internos
    de solve_ivp. El integrador es idéntico para aislar el error de detección.
    """
    t=0.; u=100.; c=4; pending=None; orders=[]; deliveries=[]; windows=[]
    trajectory=[(t,u,c)]; step={'naive1':1.,'naive025':.25}.get(mode)
    next_check=step if step else math.inf; next_exchange=0.; delta=DELTA0
    while t<horizon-1e-9:
        if pending is not None and abs(t-pending)<1e-8:
            c+=2; deliveries.append((t,c)); pending=None
            if A*u/(c*MU)>THETA:
                orders.append(t); pending=t+D
        if abs(t-next_exchange)<1e-8:
            idx=round(t/H)
            met=des(A*u,c,seed=[seed,idx])
            windows.append(dict(t=t,U=u,c=c,**met))
            delta=DELTA0+max(0.,met['W']-.75)+.5*met['r']
            next_exchange+=H
        if step and abs(t-next_check)<1e-8:
            if pending is None and A*u/(c*MU)>THETA:
                orders.append(t); pending=t+D
            next_check+=step
        end=min(next_exchange,pending if pending is not None else math.inf,next_check,horizon)
        def crossing(tt,yy): return A*yy[0]/(c*MU)-THETA
        crossing.terminal=True; crossing.direction=1
        events=crossing if mode=='exact' and pending is None else None
        sol=solve_ivp(lambda tt,yy:[rhs(yy[0],delta)],(t,end),[u],
                      rtol=1e-10,atol=1e-10,max_step=.25,events=events)
        for tt,uu in zip(sol.t[1:],sol.y[0,1:]): trajectory.append((float(tt),float(uu),c))
        t=float(sol.t[-1]); u=float(sol.y[0,-1])
        assert 0<=u<=M
        if events is not None and len(sol.t_events[0]):
            orders.append(t); pending=t+D
    # Una entrega exactamente en el horizonte cuenta en c(100).
    if pending is not None and abs(pending-horizon)<1e-8:
        c+=2; deliveries.append((horizon,c))
    return dict(mode=mode,seed=seed,U100=u,c100=c,first_order=orders[0] if orders else None,
                first_delivery=deliveries[0][0] if deliveries else None,
                Wmax=max(w['W'] for w in windows),rmax=max(w['r'] for w in windows),
                orders=orders,deliveries=deliveries,windows=windows,trajectory=trajectory)

def write_csv(name,rows):
    with (OUT/name).open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def main():
    (OUT/'figuras').mkdir(exist_ok=True)
    experiments={}
    for name,lam,K in [('stable',6,1000000),('overload',10,60),('interface',5,60)]:
        rows=[dict(rep=i+1,lam=lam,**des(lam,K=K,seed=[BASE_SEED,{'stable':1,'overload':2,'interface':3}[name],i])) for i in range(30)]
        write_csv(name+'.csv',rows)
        experiments[name]=dict(rows=rows,summary={key:ci([r[key] for r in rows]) for key in ['W','Wq','util','r','L','Lq','lam_eff','generated']})
    print('DES e interfaz completos',flush=True)
    sd=sd_verification(); write_csv('errores_sd.csv',sd['rows'])
    print('SD completo',flush=True)
    runs=[]
    for rep in range(30):
        for mode in ['exact','naive1','naive025']:
            run=hybrid(mode,BASE_SEED+rep); runs.append(run)
        if rep%5==0: print(f'Híbrido: {rep+1}/30 tríos',flush=True)
    metrics=['first_order','first_delivery','Wmax','rmax','U100','c100']
    write_csv('comparacion_eventos.csv',[dict(rep=i//3+1,mode=r['mode'],**{k:r[k] for k in metrics}) for i,r in enumerate(runs)])
    for r in runs[:3]:
        write_csv('ventanas_'+r['mode']+'.csv',r['windows'])
    paired={mode:{key:ci([runs[3*i+offset][key]-runs[3*i][key] for i in range(30)]) for key in ['first_order','Wmax','U100']}
            for mode,offset in [('naive1',1),('naive025',2)]}
    fig,axs=plt.subplots(3,1,figsize=(8,8),sharex=True)
    for run,label in zip(runs[:3],['Evento localizado','Revisión cada 1 día','Revisión cada 0.25 días']):
        tr=np.array(run['trajectory']); axs[0].plot(tr[:,0],tr[:,1],label=label)
        win=run['windows'];axs[1].step([w['t'] for w in win],[w['W'] for w in win],where='post')
        ts=[0]+[x[0] for x in run['deliveries']]+[100]
        cs=[4]+[x[1] for x in run['deliveries']]+[run['c100']]
        axs[2].step(ts,cs,where='post')
    axs[0].set_ylabel('Usuarios');axs[0].legend(fontsize=8)
    axs[1].set_ylabel('Latencia (s)');axs[1].axhline(.75,color='gray',ls='--')
    axs[2].set(ylabel='Servidores',xlabel='Tiempo (días)')
    fig.tight_layout();fig.savefig(OUT/'figuras/eventos.png',dpi=170);plt.close(fig)
    counts=np.array([r['generated'] for r in experiments['interface']['rows']]);var=counts.var(ddof=1)
    poisson=dict(mean=float(counts.mean()),variance=float(var),dispersion=float(var/counts.mean()),
                 dispersion_stat=float(29*var/counts.mean()),chi2_interval=[float(chi2.ppf(.025,29)),float(chi2.ppf(.975,29))])
    output=dict(parameters=dict(g=4,q=Q,D=D,H=1,seed=BASE_SEED),theory_stable=theory(6),
                theory_overload=theory(10,K=60),experiments=experiments,sd=sd,
                main_runs=runs[:3],paired=paired,poisson=poisson,
                all_summary={mode:{key:ci([r[key] for r in runs if r['mode']==mode]) for key in metrics} for mode in ['exact','naive1','naive025']})
    (OUT/'resultados.json').write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:output[k] for k in ['theory_stable','theory_overload','poisson','paired']},indent=2))
    print('Resultados guardados en',OUT,flush=True)

if __name__=='__main__': main()
