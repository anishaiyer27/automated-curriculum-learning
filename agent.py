"""
Teacher and student agents

author: William Tong (wtong@g.harvard.edu)
"""

# <codecell>

from collections import defaultdict

import matplotlib.pyplot as plt
import numpy as np

def sigmoid(x):
    return 1 / (1 + np.exp(-x))


# TODO: figure out specifics to abstract
class Agent:
    def __init__(self) -> None:
        pass

    def next_action(state):
        raise NotImplementedError('next_action not implemented in Agent')

    def update(old_state, action, reward, next_state):
        raise NotImplementedError('update not implemented in Agent')
    
    def learn(self, env, max_iters=1000, post_hook=None, done_hook=None):
        state = env.reset()

        for _ in range(max_iters):
            action = self.next_action(state)
            next_state, reward, is_done, _ = env.step(action)
            self.update(state, action, reward, next_state)

            if post_hook != None:
                post_hook(self)

            if is_done:
                if done_hook != None:
                    done_hook(self)
                state = env.reset()
            else:
                state = next_state


class Student(Agent):
    def __init__(self, lr=0.1, gamma=1, q_e=None) -> None:
        super().__init__()
        self.lr = lr
        self.gamma = gamma

        # only track Q-values for action = 1, maps state --> value
        self.q_e = defaultdict(int) if q_e == None else q_e
        self.q_r = defaultdict(int)
    
    # softmax policy
    def policy(self, state) -> np.ndarray:
        q = self.q_e[state] + self.q_r[state]
        prob = sigmoid(q)
        return np.array([1 - prob, prob])

    def next_action(self, state) -> int:
        _, prob = self.policy(state)
        return np.random.binomial(n=1, p=prob)
    
    def update(self, old_state, _, reward, next_state):
        _, prob = self.policy(next_state)
        exp_q = prob * self.q_r[next_state]
        self.q_r[old_state] += self.lr * (reward + self.gamma * exp_q - self.q_r[old_state])

    def score(self, goal_state) -> float:
        qs = [self.q_e[s] + self.q_r[s] for s in range(goal_state)]
        log_prob = np.sum([-np.log(1 + np.exp(-q)) for q in qs])
        return log_prob


class Teacher(Agent):
    def __init__(self, lr=0.1, gamma=1, bins=20) -> None:
        super().__init__()

        self.lr = lr
        self.gamma = gamma
        self.q = defaultdict(int)
        self.bins = bins
    
    def _to_bin(self, state):
        bin_p = np.round(np.exp(state[1]) * self.bins) / self.bins
        return (state[0], bin_p)
    
    # softmax policy
    def policy(self, state_bin) -> np.ndarray:
        qs = np.array([self.q[(state_bin, a)] for a in [0, 1, 2]])
        probs = np.exp(qs) / np.sum(np.exp(qs))
        return probs
    
    def next_action(self, state):
        state = self._to_bin(state)
        probs = self.policy(state)
        return np.random.choice([0, 1, 2], p=probs)

    def update(self, old_state, action, reward, next_state):
        old_state = self._to_bin(old_state)
        next_state = self._to_bin(next_state)

        probs = self.policy(next_state)
        qs = np.array([self.q[next_state, a] for a in [0, 1, 2]])
        exp_q = np.sum(probs * qs)
        self.q[old_state, action] += self.lr * (reward + self.gamma * exp_q - self.q[old_state, action])

