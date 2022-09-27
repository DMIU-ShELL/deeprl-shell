#######################################################################
# Copyright (C) 2017 Shangtong Zhang(zhangshangtong.cpp@gmail.com)    #
# Permission given to modify the code as long as you keep this        #
# declaration at the top                                              #
#######################################################################

'''
lifelong (continual) learning experiments using supermask
superpostion algorithm in RL.
https://arxiv.org/abs/2006.14769
'''

import json
import copy
import shutil
import matplotlib
matplotlib.use("Pdf")
from deep_rl import *
import os
import argparse

import multiprocess as mp
import pickle
import time
import dis

##### (Meta)CT-graph environment
'''
ppo, baseline (no lifelong learning), task boundary (oracle) given
'''
def ppo_baseline_mctgraph(name, args):
    env_config_path = args.env_config_path

    config = Config()
    config.env_name = name
    config.env_config_path = env_config_path
    config.lr = 0.00015
    config.cl_preservation = 'baseline'
    config.seed = 8379
    random_seed(config.seed)
    exp_id = '-seed-{0}'.format(config.seed)
    log_name = name + '-ppo' + '-' + config.cl_preservation + exp_id
    config.log_dir = get_default_log_dir(log_name)
    config.num_workers = 4

    # get num_tasks from env_config
    with open(env_config_path, 'r') as f:
        env_config_ = json.load(f)
    num_tasks = env_config_['num_tasks']
    del env_config_

    task_fn = lambda log_dir: MetaCTgraphFlatObs(name, env_config_path, log_dir)
    config.task_fn = lambda: ParallelizedTask(task_fn, config.num_workers, log_dir=config.log_dir)
    eval_task_fn = lambda log_dir: MetaCTgraphFlatObs(name, env_config_path, log_dir)
    config.eval_task_fn = eval_task_fn
    config.optimizer_fn = lambda params, lr: torch.optim.RMSprop(params, lr=lr)
    config.network_fn = lambda state_dim, action_dim, label_dim: CategoricalActorCriticNet_CL(
        state_dim, action_dim, label_dim, 
        phi_body=FCBody_CL(state_dim, task_label_dim=label_dim, hidden_units=(200, 200, 200)),
        actor_body=DummyBody_CL(200),
        critic_body=DummyBody_CL(200))
    config.policy_fn = SamplePolicy
    config.state_normalizer = ImageNormalizer()
    config.discount = 0.99
    config.use_gae = True
    config.gae_tau = 0.99
    config.entropy_weight = 0.1
    config.rollout_length = 128
    config.optimization_epochs = 8
    config.num_mini_batches = 64
    config.ppo_ratio_clip = 0.1
    config.iteration_log_interval = 1
    config.gradient_clip = 5
    config.max_steps = args.max_steps
    config.evaluation_episodes = 10
    config.logger = get_logger(log_dir=config.log_dir, file_name='train-log')
    config.cl_requires_task_label = True

    config.eval_interval = 25
    config.task_ids = np.arange(num_tasks).tolist()

    agent = BaselineAgent(config)
    config.agent_name = agent.__class__.__name__
    tasks = agent.config.cl_tasks_info
    config.cl_num_learn_blocks = 1
    shutil.copy(env_config_path, config.log_dir + '/env_config.json')
    with open('{0}/tasks_info.bin'.format(config.log_dir), 'wb') as f:
        pickle.dump(tasks, f)
    run_iterations_w_oracle(agent, tasks)
    with open('{0}/tasks_info_after_train.bin'.format(config.log_dir), 'wb') as f:
        pickle.dump(tasks, f)
    # save config
    with open('{0}/config.json'.format(config.log_dir), 'w') as f:
        dict_config = vars(config)
        for k in dict_config.keys():
            if not isinstance(dict_config[k], int) \
            and not isinstance(dict_config[k], float) and dict_config[k] is not None:
                dict_config[k] = str(dict_config[k])
        json.dump(dict_config, f)

'''
ppo, supermask lifelong learning, task boundary (oracle) given
'''
def ppo_ll_mctgraph(name, args):
    env_config_path = args.env_config_path

    config = Config()
    config.env_name = name
    config.env_config_path = env_config_path
    config.lr = 0.00015
    config.cl_preservation = 'supermask'
    config.seed = 8379
    random_seed(config.seed)
    exp_id = '-seed-{0}'.format(config.seed)
    log_name = name + '-ppo' + '-' + config.cl_preservation + exp_id
    config.log_dir = get_default_log_dir(log_name)
    config.num_workers = 4
    # get num_tasks from env_config
    with open(env_config_path, 'r') as f:
        env_config_ = json.load(f)
    num_tasks = env_config_['num_tasks']
    del env_config_

    task_fn = lambda log_dir: MetaCTgraphFlatObs(name, env_config_path, log_dir)
    config.task_fn = lambda: ParallelizedTask(task_fn, config.num_workers, log_dir=config.log_dir)
    eval_task_fn = lambda log_dir: MetaCTgraphFlatObs(name, env_config_path, log_dir)
    config.eval_task_fn = eval_task_fn
    config.optimizer_fn = lambda params, lr: torch.optim.RMSprop(params, lr=lr)
    config.network_fn = lambda state_dim, action_dim, label_dim: CategoricalActorCriticNet_SS(
        state_dim, action_dim, label_dim, 
        phi_body=FCBody_SS(state_dim, task_label_dim=label_dim, hidden_units=(200, 200, 200), num_tasks=num_tasks), 
        actor_body=DummyBody_CL(200),
        critic_body=DummyBody_CL(200),
        num_tasks=num_tasks)
    config.policy_fn = SamplePolicy
    config.state_normalizer = ImageNormalizer()
    config.discount = 0.99
    config.use_gae = True
    config.gae_tau = 0.99
    config.entropy_weight = 0.1
    config.rollout_length = 128
    config.optimization_epochs = 8
    config.num_mini_batches = 64
    config.ppo_ratio_clip = 0.1
    config.iteration_log_interval = 1
    config.gradient_clip = 5
    config.max_steps = args.max_steps
    config.evaluation_episodes = 10
    config.logger = get_logger(log_dir=config.log_dir, file_name='train-log')
    config.cl_requires_task_label = True

    config.eval_interval = 25
    config.task_ids = np.arange(num_tasks).tolist()

    agent = LLAgent(config)
    config.agent_name = agent.__class__.__name__
    tasks = agent.config.cl_tasks_info
    config.cl_num_learn_blocks = 1
    shutil.copy(env_config_path, config.log_dir + '/env_config.json')
    with open('{0}/tasks_info.bin'.format(config.log_dir), 'wb') as f:
        pickle.dump(tasks, f)
    run_iterations_w_oracle(agent, tasks)
    with open('{0}/tasks_info_after_train.bin'.format(config.log_dir), 'wb') as f:
        pickle.dump(tasks, f)
    # save config
    with open('{0}/config.json'.format(config.log_dir), 'w') as f:
        dict_config = vars(config)
        for k in dict_config.keys():
            if not isinstance(dict_config[k], int) \
            and not isinstance(dict_config[k], float) and dict_config[k] is not None:
                dict_config[k] = str(dict_config[k])
        json.dump(dict_config, f)

##### Minigrid environment
'''
ppo, baseline (no lifelong learning), task boundary (oracle) given
'''
def ppo_baseline_minigrid(name, args):
    env_config_path = args.env_config_path

    config = Config()
    config.env_name = name
    config.env_config_path = env_config_path
    config.lr = 0.00015
    config.cl_preservation = 'baseline'
    config.seed = 8379
    random_seed(config.seed)
    exp_id = '-seed-{0}'.format(config.seed)
    log_name = name + '-ppo' + '-' + config.cl_preservation + exp_id
    config.log_dir = get_default_log_dir(log_name)
    config.num_workers = 4

    # get num_tasks from env_config
    with open(env_config_path, 'r') as f:
        env_config_ = json.load(f)
    num_tasks = len(env_config_['tasks'])
    del env_config_

    task_fn = lambda log_dir: MiniGridFlatObs(name, env_config_path, log_dir, config.seed, False)
    config.task_fn = lambda: ParallelizedTask(task_fn, config.num_workers, log_dir=config.log_dir)
    eval_task_fn = lambda log_dir: MiniGridFlatObs(name, env_config_path, log_dir, config.seed, True)
    config.eval_task_fn = eval_task_fn
    config.optimizer_fn = lambda params, lr: torch.optim.RMSprop(params, lr=lr)
    config.network_fn = lambda state_dim, action_dim, label_dim: CategoricalActorCriticNet_CL(
        state_dim, action_dim, label_dim, 
        phi_body=FCBody_CL(state_dim, task_label_dim=label_dim, hidden_units=(200, 200, 200)),
        actor_body=DummyBody_CL(200),
        critic_body=DummyBody_CL(200))
    config.policy_fn = SamplePolicy
    #config.state_normalizer = ImageNormalizer()
    # rescale state normaliser: suitable for grid encoding of states in minigrid
    config.state_normalizer = RescaleNormalizer(1./10.)
    config.discount = 0.99
    config.use_gae = True
    config.gae_tau = 0.99
    config.entropy_weight = 0.1 #0.75
    config.rollout_length = 128
    config.optimization_epochs = 8
    config.num_mini_batches = 64
    config.ppo_ratio_clip = 0.1
    config.iteration_log_interval = 1
    config.gradient_clip = 5
    config.max_steps = args.max_steps
    config.evaluation_episodes = 10
    config.logger = get_logger(log_dir=config.log_dir, file_name='train-log')
    config.cl_requires_task_label = True

    config.eval_interval = 25
    config.task_ids = np.arange(num_tasks).tolist()

    agent = BaselineAgent(config)
    config.agent_name = agent.__class__.__name__
    tasks = agent.config.cl_tasks_info
    config.cl_num_learn_blocks = 1
    shutil.copy(env_config_path, config.log_dir + '/env_config.json')
    with open('{0}/tasks_info.bin'.format(config.log_dir), 'wb') as f:
        pickle.dump(tasks, f)
    run_iterations_w_oracle(agent, tasks)
    with open('{0}/tasks_info_after_train.bin'.format(config.log_dir), 'wb') as f:
        pickle.dump(tasks, f)
    # save config
    with open('{0}/config.json'.format(config.log_dir), 'w') as f:
        dict_config = vars(config)
        for k in dict_config.keys():
            if not isinstance(dict_config[k], int) \
            and not isinstance(dict_config[k], float) and dict_config[k] is not None:
                dict_config[k] = str(dict_config[k])
        json.dump(dict_config, f)

'''
ppo, supermask lifelong learning, task boundary (oracle) given
'''
def ppo_ll_minigrid(name, args):
    env_config_path = args.env_config_path

    config = Config()
    config.env_name = name
    config.env_config_path = env_config_path
    config.lr = 0.00015
    config.cl_preservation = 'supermask'
    config.seed = 8379
    random_seed(config.seed)
    exp_id = '-seed-{0}'.format(config.seed)
    log_name = name + '-ppo' + '-' + config.cl_preservation + exp_id
    config.log_dir = get_default_log_dir(log_name)
    config.num_workers = 4
    # get num_tasks from env_config
    with open(env_config_path, 'r') as f:
        env_config_ = json.load(f)
    num_tasks = len(env_config_['tasks'])
    del env_config_

    task_fn = lambda log_dir: MiniGridFlatObs(name, env_config_path, log_dir, config.seed, False)
    config.task_fn = lambda: ParallelizedTask(task_fn, config.num_workers, log_dir=config.log_dir)
    eval_task_fn = lambda log_dir: MiniGridFlatObs(name, env_config_path, log_dir, config.seed, True)
    config.eval_task_fn = eval_task_fn
    config.optimizer_fn = lambda params, lr: torch.optim.RMSprop(params, lr=lr)
    config.network_fn = lambda state_dim, action_dim, label_dim: CategoricalActorCriticNet_SS(
        state_dim, action_dim, label_dim,
        phi_body=FCBody_SS(state_dim, task_label_dim=label_dim, hidden_units=(200, 200, 200), num_tasks=num_tasks),
        actor_body=DummyBody_CL(200),
        critic_body=DummyBody_CL(200),
        num_tasks=num_tasks)
    config.policy_fn = SamplePolicy
    #config.state_normalizer = ImageNormalizer()
    # rescale state normaliser: suitable for grid encoding of states in minigrid
    config.state_normalizer = RescaleNormalizer(1./10.)
    config.discount = 0.99
    config.use_gae = True
    config.gae_tau = 0.99
    config.entropy_weight = 0.1 #0.75
    config.rollout_length = 128
    config.optimization_epochs = 8
    config.num_mini_batches = 64
    config.ppo_ratio_clip = 0.1
    config.iteration_log_interval = 1
    config.gradient_clip = 5
    config.max_steps = args.max_steps
    config.evaluation_episodes = 10
    config.logger = get_logger(log_dir=config.log_dir, file_name='train-log')
    config.cl_requires_task_label = True

    config.eval_interval = 25
    config.task_ids = np.arange(num_tasks).tolist()

    agent = LLAgent(config)
    config.agent_name = agent.__class__.__name__
    tasks = agent.config.cl_tasks_info
    config.cl_num_learn_blocks = 1
    shutil.copy(env_config_path, config.log_dir + '/env_config.json')
    with open('{0}/tasks_info.bin'.format(config.log_dir), 'wb') as f:
        pickle.dump(tasks, f)
    run_iterations_w_oracle(agent, tasks)
    with open('{0}/tasks_info_after_train.bin'.format(config.log_dir), 'wb') as f:
        pickle.dump(tasks, f)
    # save config
    with open('{0}/config.json'.format(config.log_dir), 'w') as f:
        dict_config = vars(config)
        for k in dict_config.keys():
            if not isinstance(dict_config[k], int) \
            and not isinstance(dict_config[k], float) and dict_config[k] is not None:
                dict_config[k] = str(dict_config[k])
        json.dump(dict_config, f)

##### ContinualWorld environment
'''
ppo, baseline (no lifelong learning), task boundary (oracle) given
'''
def ppo_baseline_continualworld(name, args):
    env_config_path = args.env_config_path

    config = Config()
    config.env_name = name
    config.env_config_path = env_config_path
    config.lr = 5e-4
    config.cl_preservation = 'baseline'
    config.seed = 8379
    random_seed(config.seed)
    exp_id = '-seed-{0}'.format(config.seed)
    log_name = name + '-ppo' + '-' + config.cl_preservation + exp_id
    config.log_dir = get_default_log_dir(log_name)
    config.num_workers = 1

    # get num_tasks from env_config
    with open(env_config_path, 'r') as f:
        env_config_ = json.load(f)
    num_tasks = len(env_config_['tasks'])
    del env_config_

    task_fn = lambda log_dir: ContinualWorld(name, env_config_path, log_dir, config.seed)
    config.task_fn = lambda: ParallelizedTask(task_fn, config.num_workers, log_dir=config.log_dir)
    eval_task_fn = lambda log_dir: ContinualWorld(name, env_config_path, log_dir, config.seed)
    config.eval_task_fn = eval_task_fn
    config.optimizer_fn = lambda params, lr: torch.optim.Adam(params, lr=lr)
    config.network_fn = lambda state_dim, action_dim, label_dim: GaussianActorCriticNet_CL(
        state_dim, action_dim, label_dim,
        phi_body=DummyBody_CL(state_dim, task_label_dim=label_dim),
        actor_body=FCBody_CL(state_dim + label_dim, hidden_units=(128, 128), gate=torch.tanh),
        critic_body=FCBody_CL(state_dim + label_dim, hidden_units=(128, 128), gate=torch.tanh))
    config.policy_fn = SamplePolicy
    #config.state_normalizer = RescaleNormalizer(1.) # no rescaling
    config.state_normalizer = RunningStatsNormalizer()
    config.reward_normalizer = RewardRunningStatsNormalizer()
    config.discount = 0.99
    config.use_gae = True
    config.gae_tau = 0.97
    config.entropy_weight = 5e-3
    config.rollout_length = 512 * 10
    config.optimization_epochs = 16
    config.num_mini_batches = 160 # with rollout of 5120, 160 mini_batch gives 32 samples per batch
    config.ppo_ratio_clip = 0.2
    config.iteration_log_interval = 1
    config.gradient_clip = 5
    config.max_steps = args.max_steps
    config.evaluation_episodes = 10
    config.logger = get_logger(log_dir=config.log_dir, file_name='train-log')
    config.cl_requires_task_label = True

    config.eval_interval = 200
    config.task_ids = np.arange(num_tasks).tolist()

    agent = BaselineAgent(config)
    config.agent_name = agent.__class__.__name__
    tasks = agent.config.cl_tasks_info
    config.cl_num_learn_blocks = 1
    shutil.copy(env_config_path, config.log_dir + '/env_config.json')
    with open('{0}/tasks_info.bin'.format(config.log_dir), 'wb') as f:
        pickle.dump(tasks, f)
    run_iterations_w_oracle(agent, tasks)
    with open('{0}/tasks_info_after_train.bin'.format(config.log_dir), 'wb') as f:
        pickle.dump(tasks, f)
    # save config
    with open('{0}/config.json'.format(config.log_dir), 'w') as f:
        dict_config = vars(config)
        for k in dict_config.keys():
            if not isinstance(dict_config[k], int) \
            and not isinstance(dict_config[k], float) and dict_config[k] is not None:
                dict_config[k] = str(dict_config[k])
        json.dump(dict_config, f)
'''
ppo, supermask lifelong learning, task boundary (oracle) given
'''
def ppo_ll_continualworld(name, args):
    env_config_path = args.env_config_path

    config = Config()
    config.env_name = name
    config.env_config_path = env_config_path
    config.lr = 5e-4
    config.cl_preservation = 'supermask'
    config.seed = 8379
    random_seed(config.seed)
    exp_id = '-seed-{0}'.format(config.seed)
    log_name = name + '-ppo' + '-' + config.cl_preservation + exp_id
    config.log_dir = get_default_log_dir(log_name)
    config.num_workers = 1

    # get num_tasks from env_config
    with open(env_config_path, 'r') as f:
        env_config_ = json.load(f)
    num_tasks = len(env_config_['tasks'])
    del env_config_

    task_fn = lambda log_dir: ContinualWorld(name, env_config_path, log_dir, config.seed)
    config.task_fn = lambda: ParallelizedTask(task_fn, config.num_workers, log_dir=config.log_dir)
    eval_task_fn = lambda log_dir: ContinualWorld(name, env_config_path, log_dir, config.seed)
    config.eval_task_fn = eval_task_fn
    config.optimizer_fn = lambda params, lr: torch.optim.Adam(params, lr=lr)
    config.network_fn = lambda state_dim, action_dim, label_dim: GaussianActorCriticNet_SS(
        state_dim, action_dim, label_dim,
        phi_body=DummyBody_CL(state_dim, task_label_dim=label_dim),
        actor_body=FCBody_SS(state_dim + label_dim, hidden_units=(128, 128), \
            discrete_mask=False, gate=torch.tanh, num_tasks=num_tasks),
        critic_body=FCBody_SS(state_dim + label_dim, hidden_units=(128, 128), \
            discrete_mask=False, gate=torch.tanh, num_tasks=num_tasks),
        num_tasks=num_tasks)
    config.policy_fn = SamplePolicy
    #config.state_normalizer = RescaleNormalizer(1.) # no rescaling
    config.state_normalizer = RunningStatsNormalizer()
    config.reward_normalizer = RewardRunningStatsNormalizer()
    config.discount = 0.99
    config.use_gae = True
    config.gae_tau = 0.97
    config.entropy_weight = 5e-3
    config.rollout_length = 512 * 10
    config.optimization_epochs = 16
    config.num_mini_batches = 160 # with rollout of 5120, 160 mini_batch gives 32 samples per batch
    config.ppo_ratio_clip = 0.2
    config.iteration_log_interval = 1
    config.gradient_clip = 5
    config.max_steps = args.max_steps
    config.evaluation_episodes = 10
    config.logger = get_logger(log_dir=config.log_dir, file_name='train-log')
    config.cl_requires_task_label = True

    config.eval_interval = 200
    config.task_ids = np.arange(num_tasks).tolist()

    agent = LLAgent(config)
    config.agent_name = agent.__class__.__name__
    tasks = agent.config.cl_tasks_info
    config.cl_num_learn_blocks = 1
    shutil.copy(env_config_path, config.log_dir + '/env_config.json')
    with open('{0}/tasks_info.bin'.format(config.log_dir), 'wb') as f:
        pickle.dump(tasks, f)
    run_iterations_w_oracle(agent, tasks)
    with open('{0}/tasks_info_after_train.bin'.format(config.log_dir), 'wb') as f:
        pickle.dump(tasks, f)
    # save config
    with open('{0}/config.json'.format(config.log_dir), 'w') as f:
        dict_config = vars(config)
        for k in dict_config.keys():
            if not isinstance(dict_config[k], int) \
            and not isinstance(dict_config[k], float) and dict_config[k] is not None:
                dict_config[k] = str(dict_config[k])
        json.dump(dict_config, f)


'''
META CTGRAPH WITH SUPERMASKS AND MULTIPROCESSING
'''
def ppo_ll_mctgraph_mp(name, args):
    env_config_path = args.env_config_path

    config = Config()
    config.env_name = name
    config.env_config_path = env_config_path
    config.lr = 0.00015
    config.cl_preservation = 'supermask'
    config.seed = 8379
    random_seed(config.seed)
    exp_id = '-seed-{0}'.format(config.seed)
    log_name = name + '-ppo' + '-' + config.cl_preservation + exp_id
    config.log_dir = get_default_log_dir(log_name)
    config.num_workers = 4
    # get num_tasks from env_config
    with open(env_config_path, 'r') as f:
        env_config_ = json.load(f)
    num_tasks = env_config_['num_tasks']
    del env_config_

    task_fn = lambda log_dir: MetaCTgraphFlatObs(name, env_config_path, log_dir)
    config.task_fn = lambda: ParallelizedTask(task_fn, config.num_workers, log_dir=config.log_dir)
    eval_task_fn = lambda log_dir: MetaCTgraphFlatObs(name, env_config_path, log_dir)
    config.eval_task_fn = eval_task_fn
    config.optimizer_fn = lambda params, lr: torch.optim.RMSprop(params, lr=lr)
    config.network_fn = lambda state_dim, action_dim, label_dim: CategoricalActorCriticNet_SS(
        state_dim, action_dim, label_dim, 
        phi_body=FCBody_SS(state_dim, task_label_dim=label_dim, hidden_units=(200, 200, 200), num_tasks=num_tasks), 
        actor_body=DummyBody_CL(200),
        critic_body=DummyBody_CL(200),
        num_tasks=num_tasks)
    config.policy_fn = SamplePolicy
    config.state_normalizer = ImageNormalizer()
    config.discount = 0.99
    config.use_gae = True
    config.gae_tau = 0.99
    config.entropy_weight = 0.1
    config.rollout_length = 128
    config.optimization_epochs = 8
    config.num_mini_batches = 64
    config.ppo_ratio_clip = 0.1
    config.iteration_log_interval = 1
    config.gradient_clip = 5
    config.max_steps = args.max_steps
    config.evaluation_episodes = 10
    config.logger = get_logger(log_dir=config.log_dir, file_name='train-log')
    config.cl_requires_task_label = True

    config.eval_interval = 25
    config.task_ids = np.arange(num_tasks).tolist()



    # Consists of data collection and optimisation loops
    agent = LLAgent_mp(config)



    config.agent_name = agent.__class__.__name__
    tasks = agent.config.cl_tasks_info
    config.cl_num_learn_blocks = 1
    shutil.copy(env_config_path, config.log_dir + '/env_config.json')
    with open('{0}/tasks_info.bin'.format(config.log_dir), 'wb') as f:
        pickle.dump(tasks, f)
    run_iterations_w_oracle_mp(agent, tasks)
    with open('{0}/tasks_info_after_train.bin'.format(config.log_dir), 'wb') as f:
        pickle.dump(tasks, f)
    # save config
    with open('{0}/config.json'.format(config.log_dir), 'w') as f:
        dict_config = vars(config)
        for k in dict_config.keys():
            if not isinstance(dict_config[k], int) \
            and not isinstance(dict_config[k], float) and dict_config[k] is not None:
                dict_config[k] = str(dict_config[k])
        json.dump(dict_config, f)

def ppo_ll_minigrid_mp(name, args):
    env_config_path = args.env_config_path

    config = Config()
    config.env_name = name
    config.env_config_path = env_config_path
    config.lr = 0.00015
    config.cl_preservation = 'supermask'
    config.seed = 8379
    random_seed(config.seed)
    exp_id = '-seed-{0}'.format(config.seed)
    log_name = name + '-ppo' + '-' + config.cl_preservation + exp_id
    config.log_dir = get_default_log_dir(log_name)
    config.num_workers = 1
    # get num_tasks from env_config
    with open(env_config_path, 'r') as f:
        env_config_ = json.load(f)
    num_tasks = len(env_config_['tasks'])
    del env_config_


    #global task_fn
    #global task_fn_intermediate
    #def task_fn():
    #    MiniGridFlatObs(name, env_config_path, log_dir, config.seed, False)

    #def task_fn_intermediate():
    #    return ParallelizedTask(task_fn, config.num_workers, log_dir=config.log_dir, single_process=False)

    #config.task_fn = task_fn_intermediate
    #dis.dis(config.task_fn)
    ##dis.dis(task_fn)

    task_fn = lambda log_dir: MiniGridFlatObs(name, env_config_path, log_dir, config.seed, False)
    config.task_fn = lambda: ParallelizedTask(task_fn, config.num_workers, log_dir=config.log_dir, single_process=True)
    #dis.dis(task_fn)
    #dis.dis(config.task_fn)

    eval_task_fn = lambda log_dir: MiniGridFlatObs(name, env_config_path, log_dir, config.seed, True)
    config.eval_task_fn = eval_task_fn
    config.optimizer_fn = lambda params, lr: torch.optim.RMSprop(params, lr=lr)
    config.network_fn = lambda state_dim, action_dim, label_dim: CategoricalActorCriticNet_SS(
        state_dim, action_dim, label_dim,
        phi_body=FCBody_SS(state_dim, task_label_dim=label_dim, hidden_units=(200, 200, 200), num_tasks=num_tasks),
        actor_body=DummyBody_CL(200),
        critic_body=DummyBody_CL(200),
        num_tasks=num_tasks)
    config.policy_fn = SamplePolicy
    #config.state_normalizer = ImageNormalizer()
    # rescale state normaliser: suitable for grid encoding of states in minigrid
    config.state_normalizer = RescaleNormalizer(1./10.)
    config.discount = 0.99
    config.use_gae = True
    config.gae_tau = 0.99
    config.entropy_weight = 0.1 #0.75
    config.rollout_length = 128
    config.optimization_epochs = 8
    config.num_mini_batches = 64
    config.ppo_ratio_clip = 0.1
    config.iteration_log_interval = 1
    config.gradient_clip = 5
    config.max_steps = args.max_steps
    config.evaluation_episodes = 10
    config.logger = get_logger(log_dir=config.log_dir, file_name='train-log')
    config.cl_requires_task_label = True

    config.eval_interval = 25
    config.task_ids = np.arange(num_tasks).tolist()
    

    # Initialise the multiprocess agent
    agent = LLAgent_mp(config)
    #agent = LLAgent_mp(config, name, env_config_path)
    #agent.network.share_memory()

    
    config.agent_name = agent.__class__.__name__
    tasks = agent.config.cl_tasks_info
    config.cl_num_learn_blocks = 1
    shutil.copy(env_config_path, config.log_dir + '/env_config.json')
    with open('{0}/tasks_info.bin'.format(config.log_dir), 'wb') as f:
        pickle.dump(tasks, f)


    # Start single agent lifecycle
    run_iterations_w_oracle_mp(agent, tasks)



    with open('{0}/tasks_info_after_train.bin'.format(config.log_dir), 'wb') as f:
        pickle.dump(tasks, f)
    # save config
    with open('{0}/config.json'.format(config.log_dir), 'w') as f:
        dict_config = vars(config)
        for k in dict_config.keys():
            if not isinstance(dict_config[k], int) \
            and not isinstance(dict_config[k], float) and dict_config[k] is not None:
                dict_config[k] = str(dict_config[k])
        json.dump(dict_config, f)
        
def ppo_ll_continualworld_mp(name, args):
    env_config_path = args.env_config_path

    config = Config()
    config.env_name = name
    config.env_config_path = env_config_path
    config.lr = 5e-4
    config.cl_preservation = 'supermask'
    config.seed = 8379
    random_seed(config.seed)
    exp_id = '-seed-{0}'.format(config.seed)
    log_name = name + '-ppo' + '-' + config.cl_preservation + exp_id
    config.log_dir = get_default_log_dir(log_name)
    config.num_workers = 1

    # get num_tasks from env_config
    with open(env_config_path, 'r') as f:
        env_config_ = json.load(f)
    num_tasks = len(env_config_['tasks'])
    del env_config_

    task_fn = lambda log_dir: ContinualWorld(name, env_config_path, log_dir, config.seed)
    config.task_fn = lambda: ParallelizedTask(task_fn, config.num_workers, log_dir=config.log_dir)
    eval_task_fn = lambda log_dir: ContinualWorld(name, env_config_path, log_dir, config.seed)
    config.eval_task_fn = eval_task_fn
    config.optimizer_fn = lambda params, lr: torch.optim.Adam(params, lr=lr)
    config.network_fn = lambda state_dim, action_dim, label_dim: GaussianActorCriticNet_SS(
        state_dim, action_dim, label_dim,
        phi_body=DummyBody_CL(state_dim, task_label_dim=label_dim),
        actor_body=FCBody_SS(state_dim + label_dim, hidden_units=(128, 128), \
            discrete_mask=False, gate=torch.tanh, num_tasks=num_tasks),
        critic_body=FCBody_SS(state_dim + label_dim, hidden_units=(128, 128), \
            discrete_mask=False, gate=torch.tanh, num_tasks=num_tasks),
        num_tasks=num_tasks)
    config.policy_fn = SamplePolicy
    #config.state_normalizer = RescaleNormalizer(1.) # no rescaling
    config.state_normalizer = RunningStatsNormalizer()
    config.reward_normalizer = RewardRunningStatsNormalizer()
    config.discount = 0.99
    config.use_gae = True
    config.gae_tau = 0.97
    config.entropy_weight = 5e-3
    config.rollout_length = 512 * 10
    config.optimization_epochs = 16
    config.num_mini_batches = 160 # with rollout of 5120, 160 mini_batch gives 32 samples per batch
    config.ppo_ratio_clip = 0.2
    config.iteration_log_interval = 1
    config.gradient_clip = 5
    config.max_steps = args.max_steps
    config.evaluation_episodes = 10
    config.logger = get_logger(log_dir=config.log_dir, file_name='train-log')
    config.cl_requires_task_label = True

    config.eval_interval = 200
    config.task_ids = np.arange(num_tasks).tolist()

    agent = LLAgent(config)
    config.agent_name = agent.__class__.__name__
    tasks = agent.config.cl_tasks_info
    config.cl_num_learn_blocks = 1
    shutil.copy(env_config_path, config.log_dir + '/env_config.json')
    with open('{0}/tasks_info.bin'.format(config.log_dir), 'wb') as f:
        pickle.dump(tasks, f)
    run_iterations_w_oracle(agent, tasks)
    with open('{0}/tasks_info_after_train.bin'.format(config.log_dir), 'wb') as f:
        pickle.dump(tasks, f)
    # save config
    with open('{0}/config.json'.format(config.log_dir), 'w') as f:
        dict_config = vars(config)
        for k in dict_config.keys():
            if not isinstance(dict_config[k], int) \
            and not isinstance(dict_config[k], float) and dict_config[k] is not None:
                dict_config[k] = str(dict_config[k])
        json.dump(dict_config, f)

def ppo_ll_minigrid_mpu(name, args):
    env_config_path = args.env_config_path

    config = Config()
    config.env_name = name
    config.env_config_path = env_config_path
    config.lr = 0.00015
    config.cl_preservation = 'supermask'
    config.seed = 8379
    random_seed(config.seed)
    exp_id = '-seed-{0}'.format(config.seed)
    log_name = name + '-ppo' + '-' + config.cl_preservation + exp_id
    config.log_dir = get_default_log_dir(log_name)
    config.num_workers = 4
    # get num_tasks from env_config
    with open(env_config_path, 'r') as f:
        env_config_ = json.load(f)
    num_tasks = len(env_config_['tasks'])
    del env_config_

    # All lambda function definitions
    task_fn = lambda log_dir: MiniGridFlatObs(name, env_config_path, log_dir, config.seed, False)
    config.task_fn = lambda: ParallelizedTask(task_fn, config.num_workers, log_dir=config.log_dir, single_process=False)
    eval_task_fn = lambda log_dir: MiniGridFlatObs(name, env_config_path, log_dir, config.seed, True)
    config.eval_task_fn = eval_task_fn
    config.optimizer_fn = lambda params, lr: torch.optim.RMSprop(params, lr=lr)
    config.network_fn = lambda state_dim, action_dim, label_dim: CategoricalActorCriticNet_SS(
        state_dim, action_dim, label_dim,
        phi_body=FCBody_SS(state_dim, task_label_dim=label_dim, hidden_units=(200, 200, 200), num_tasks=num_tasks),
        actor_body=DummyBody_CL(200),
        critic_body=DummyBody_CL(200),
        num_tasks=num_tasks)



    config.policy_fn = SamplePolicy
    #config.state_normalizer = ImageNormalizer()
    # rescale state normaliser: suitable for grid encoding of states in minigrid
    config.state_normalizer = RescaleNormalizer(1./10.)
    config.discount = 0.99
    config.use_gae = True
    config.gae_tau = 0.99
    config.entropy_weight = 0.1 #0.75
    config.rollout_length = 128
    config.optimization_epochs = 8
    config.num_mini_batches = 64
    config.ppo_ratio_clip = 0.1
    config.iteration_log_interval = 1
    config.gradient_clip = 5
    config.max_steps = args.max_steps
    config.evaluation_episodes = 10
    config.logger = get_logger(log_dir=config.log_dir, file_name='train-log')
    config.cl_requires_task_label = True

    config.eval_interval = 25
    config.task_ids = np.arange(num_tasks).tolist()

    Agent = LLAgent_mpu


    # Start single agent lifecycle
    run_iterations_w_oracle_mpu(Agent, config)



    with open('{0}/tasks_info_after_train.bin'.format(config.log_dir), 'wb') as f:
        pickle.dump(tasks, f)
    # save config
    with open('{0}/config.json'.format(config.log_dir), 'w') as f:
        dict_config = vars(config)
        for k in dict_config.keys():
            if not isinstance(dict_config[k], int) \
            and not isinstance(dict_config[k], float) and dict_config[k] is not None:
                dict_config[k] = str(dict_config[k])
        json.dump(dict_config, f)

if __name__ == '__main__':
    mkdir('log')
    set_one_thread()
    print(torch.cuda.is_initialized())
    #select_device(-1) # -1 is CPU, a positive integer is the index of GPU

    mp.set_start_method('fork', force=True)

    print(mp.get_start_method())
    
    #dill.settings["protocol"] = pickle.HIGHEST_PROTOCOL
    #dill.settings["byref"] = True
    #mp.dill.settings["ignore"] = True


    parser = argparse.ArgumentParser()
    parser.add_argument('--algo', help='algorithm to run')
    parser.add_argument('--env_name', help='name of the evaluation environment. ' \
        'minigrid and ctgraph currently supported', default='minigrid')
    parser.add_argument('--env_config_path', help='path to environment config', \
        default='./env_configs/minigrid_sc_3.json')
    parser.add_argument('--max_steps', help='maximum number of training steps per task.', \
        default=51200*2, type=int)
    args = parser.parse_args()

    if args.env_name == 'minigrid':
        name = Config.ENV_MINIGRID
        if args.algo == 'baseline':
            ppo_baseline_minigrid(name, args)
        elif args.algo == 'll_supermask':
            ppo_ll_minigrid(name, args)
        elif args.algo == 'mp':
            ppo_ll_minigrid_mp(name, args)
        elif args.algo == 'mpu':
            ppo_ll_minigrid_mpu(name, args)
        else:
            raise ValueError('algo {0} not implemented'.format(args.algo))
    elif args.env_name == 'ctgraph':
        name = Config.ENV_METACTGRAPH
        if args.algo == 'baseline':
            ppo_baseline_mctgraph(name, args)
        elif args.algo == 'll_supermask':
            ppo_ll_mctgraph(name, args)
        elif args.algo == 'mp':
            ppo_ll_mctgraph_mp(name, args)
        else:
            raise ValueError('algo {0} not implemented'.format(args.algo))
    elif args.env_name == 'continualworld':
        name = Config.ENV_CONTINUALWORLD
        if args.algo == 'baseline':
            ppo_baseline_continualworld(name, args)
        elif args.algo == 'll_supermask':
            ppo_ll_continualworld(name, args)
        else:
            raise ValueError('algo {0} not implemented'.format(args.algo))
    else:
        raise ValueError('--env_name {0} not implemented'.format(args.env_name))
