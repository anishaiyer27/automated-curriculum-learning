"""
Algorithms at the continuum limit
"""

# <codecell>
from collections import namedtuple
import matplotlib as plt
import numpy as np
from scipy.stats import beta

import sys
sys.path.append('../')

from env import *

class UncertainCurriculumEnv(CurriculumEnv):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    
    def step(self, action):
        (self.N, _), reward, is_done, info = super().step(action)
        return (self.N, info['transcript']), reward, is_done, {}

def to_cont(N=3, eps=0, dn_per_interval=1000):
    prob = sig(eps) ** (1 / dn_per_interval)
    eps_cont = np.log(prob / (1 - prob))
    N_cont = N * dn_per_interval

    return N_cont, eps_cont


class TeacherUncertainOsc(Agent):
    def __init__(self, goal_length, tau=0.95, conf=0.75, max_m_factor=3, with_backtrack=False, bt_tau=0.05, bt_conf=0.75) -> None:
        super().__init__()
        self.goal_length = goal_length
        self.tau = tau
        self.conf = conf
        self.with_backtrack = with_backtrack
        self.bt_tau = bt_tau
        self.bt_conf = bt_conf

        self.trans_dict = defaultdict(list)
        self.n = 1

        p_eps = -np.log(tau)
        raw_min_m = np.log(1 - conf) / (-p_eps) - 1
        self.min_m = int(np.floor(raw_min_m))
        self.max_m = int(self.min_m * max_m_factor)

    def next_action(self, state):
        curr_n, trans = state
        self.trans_dict[curr_n].extend(trans)

        next_n = self.n
        if self.do_jump():
            self.n = min(self.n + 1, self.goal_length)
            next_n = self.n
        elif self.with_backtrack and self.do_dive():
            self.n = max(self.n - 1, 1)
            next_n = self.n
        elif next_n == curr_n:
            next_n = max(self.n - 1, 1)
        
        return next_n
    
    def do_jump(self):
        trans = self.trans_dict[self.n]
        for k in range(self.min_m, 1 + min(self.max_m, len(trans))):
            prob_good = self._get_prob_good(trans[-k:])
            if prob_good >= self.conf:
                return True

        return False

    def do_dive(self):
        if self.n == 1:
            return

        trans = self.trans_dict[self.n - 1]
        rev_trans = [not bit for bit in trans]
        for k in range(self.min_m, 1 + min(self.max_m, len(trans))):
            prob_good = self._get_prob_good(rev_trans[-k:], 1 - self.bt_tau)
            if prob_good >= self.bt_conf:
                return True
        
        return False
    
    def _get_prob_good(self, transcript, tau=None):
        if tau == None:
            tau = self.tau

        success = np.sum(transcript)
        total = len(transcript)
        prob_bad = beta.cdf(tau, a=success+1, b=total-success+1)
        return 1 - prob_bad

def run_incremental(eps=0, goal_length=3, T=3, max_steps=1000, lr=0.1):
    env = CurriculumEnv(goal_length=goal_length, student_reward=10, student_qe_dist=eps, train_iter=999, train_round=T, student_params={'lr': lr})
    env.reset()
    traj = [env.N]

    score = env._get_score(1, train=False)
    for _ in range(max_steps):
        if -score < env.p_eps:
            action = 2
        else:
            action = 1
        
        (_, score), _, is_done, _ = env.step(action)
        traj.append(env.N)

        if is_done:
            break
    
    return traj

def run_osc(eps=0, confidence=0.75, goal_length=3, T=3, max_steps=1000, lr=0.1, **teacher_kwargs):
    teacher = TeacherUncertainOsc(goal_length, conf=confidence, **teacher_kwargs)
    env = UncertainCurriculumEnv(goal_length=goal_length, student_reward=10, student_qe_dist=eps, train_iter=999, train_round=T, student_params={'lr': lr}, anarchy_mode=True)
    traj = [env.N]
    env.reset()

    obs = (1, [])
    for _ in range(max_steps):
        action = teacher.next_action(obs)
        obs, _, is_done, _ = env.step(action)
        traj.append(env.N)

        if is_done:
            break
    
    return traj

def run_incremental_with_backtrack(eps=0, goal_length=3, T=3, lr=0.1, max_steps=500):
    env = CurriculumEnv(goal_length=goal_length, student_reward=10, student_qe_dist=eps, train_iter=999, train_round=T, student_params={'lr': lr}, anarchy_mode=True)
    env.reset()
    traj = [env.N]

    for _ in range(max_steps):
        qs = np.array([eps + env.student.q_r[i] for i in range(goal_length)])
        while len(qs) > 0 and -np.sum(np.log(sig(qs))) > env.p_eps:
            qs = qs[:-1]
        
        action = min(len(qs) + 1, goal_length)
        _, _, is_done, _ = env.step(action)
        traj.append(env.N)

        if is_done:
            break
    
    return traj

# <codecell>
n_iters = 3
T = 5
lr = 0.01
max_steps = 10000

N_eff = 3
eps_eff = 0

N, eps = to_cont(N_eff, eps_eff, dn_per_interval=100)

Case = namedtuple('Case', ['name', 'run_func', 'run_params', 'runs'])

cases = [
    Case('Incremental', run_incremental, {'eps': eps, 'goal_length': N, 'lr': lr}, []),
    Case('Incremental (w/ BT)', run_incremental_with_backtrack, {'eps': eps, 'goal_length': N, 'lr': lr}, []),
]

for _ in tqdm(range(n_iters)):
    for case in cases:
        case.runs.append(case.run_func(**case.run_params, max_steps=max_steps, T=T))

# <codecell>
fig, axs = plt.subplots(1, 2, figsize=(10, 4))

for i, case in enumerate(cases):
    label = {'label': case.name}
    for run in case.runs:
        axs[0].plot(run, color=f'C{i}', alpha=0.7, **label)
        label = {}

axs[0].legend()
axs[0].set_xlabel('Iteration')
axs[0].set_ylabel('N')
# axs[0].set_yticks(np.arange(N) + 1)

# axs[0].set_ylim((25, 50))
# axs[0].set_xlim((100, 200))


all_lens = [[len(run) for run in case.runs] for case in cases]
all_means = [np.mean(lens) for lens in all_lens]
all_serr = [2 * np.std(lens) / np.sqrt(n_iters) for lens in all_lens]
all_names = [case.name for case in cases]

axs[1].bar(np.arange(len(cases)), all_means, tick_label=all_names, yerr=all_serr)
axs[1].set_ylabel('Iterations')

fig.suptitle(f'Epsilon = {eps}')
fig.tight_layout()
# plt.savefig(f'../fig/osc_ex_n_{N}_eps_{eps}.png')

# %%
