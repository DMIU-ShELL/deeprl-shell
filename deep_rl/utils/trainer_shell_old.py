#######################################################################
# Copyright (C) 2017 Shangtong Zhang(zhangshangtong.cpp@gmail.com)    #
# Permission given to modify the code as long as you keep this        #
# declaration at the top                                              #
#######################################################################



#   __________ .__                              __   .__     .__                                           
#   \______   \|  |    ____    ______  ______ _/  |_ |  |__  |__|  ______   _____    ____    ______  ______
#    |    |  _/|  |  _/ __ \  /  ___/ /  ___/ \   __\|  |  \ |  | /  ___/  /     \ _/ __ \  /  ___/ /  ___/
#    |    |   \|  |__\  ___/  \___ \  \___ \   |  |  |   Y  \|  | \___ \  |  Y Y  \\  ___/  \___ \  \___ \ 
#    |______  /|____/ \___  >/____  >/____  >  |__|  |___|  /|__|/____  > |__|_|  / \___  >/____  >/____  >
#           \/            \/      \/      \/              \/          \/        \/      \/      \/      \/ 
#
#                                                     :')


import numpy as np
import pickle
import os
import time
import datetime
import torch
from .torch_utils import *
from ..shell_modules import *

try:
    # python >= 3.5
    from pathlib import Path
except:
    # python == 2.7
    from pathlib2 import Path


def _shell_itr_log(logger, agent, agent_idx, itr_counter, task_counter, dict_logs):
    logger.info('agent %d, task %d / iteration %d, total steps %d, ' \
    'mean/max/min reward %f/%f/%f' % (agent_idx, task_counter, \
        itr_counter,
        agent.total_steps,
        np.mean(agent.iteration_rewards),
        np.max(agent.iteration_rewards),
        np.min(agent.iteration_rewards)
    ))
    logger.scalar_summary('agent_{0}/last_episode_avg_reward'.format(agent_idx), \
        np.mean(agent.last_episode_rewards))
    logger.scalar_summary('agent_{0}/last_episode_std_reward'.format(agent_idx), \
        np.std(agent.last_episode_rewards))
    logger.scalar_summary('agent_{0}/last_episode_max_reward'.format(agent_idx), \
        np.max(agent.last_episode_rewards))
    logger.scalar_summary('agent_{0}/last_episode_min_reward'.format(agent_idx), \
        np.min(agent.last_episode_rewards))
    logger.scalar_summary('agent_{0}/iteration_avg_reward'.format(agent_idx), \
        np.mean(agent.iteration_rewards))
    logger.scalar_summary('agent_{0}/iteration_std_reward'.format(agent_idx), \
        np.std(agent.iteration_rewards))
    logger.scalar_summary('agent_{0}/iteration_max_reward'.format(agent_idx), \
        np.max(agent.iteration_rewards))
    logger.scalar_summary('agent_{0}/iteration_min_reward'.format(agent_idx), \
        np.min(agent.iteration_rewards))

    prefix = 'agent_{0}_'.format(agent_idx)
    if hasattr(agent, 'layers_output'):
        for tag, value in agent.layers_output:
            value = value.detach().cpu().numpy()
            value_norm = np.linalg.norm(value, axis=-1)
            logger.scalar_summary('{0}debug/{1}_avg_norm'.format(prefix, tag), np.mean(value_norm))
            logger.scalar_summary('{0}debug/{1}_avg'.format(prefix, tag), value.mean())
            logger.scalar_summary('{0}debug/{1}_std'.format(prefix, tag), value.std())
            logger.scalar_summary('{0}debug/{1}_max'.format(prefix, tag), value.max())
            logger.scalar_summary('{0}debug/{1}_min'.format(prefix, tag), value.min())

    for key, value in dict_logs.items():
        logger.scalar_summary('{0}debug_extended/{1}_avg'.format(prefix, key), np.mean(value))
        logger.scalar_summary('{0}debug_extended/{1}_std'.format(prefix, key), np.std(value))
        logger.scalar_summary('{0}debug_extended/{1}_max'.format(prefix, key), np.max(value))
        logger.scalar_summary('{0}debug_extended/{1}_min'.format(prefix, key), np.min(value))

    return

# metaworld/continualworld
def _shell_itr_log_mw(logger, agent, agent_idx, itr_counter, task_counter, dict_logs):
    logger.info('agent %d, task %d / iteration %d, total steps %d, ' \
    'mean/max/min reward %f/%f/%f, mean/max/min success rate %f/%f/%f' % (agent_idx, \
        task_counter,
        itr_counter,
        agent.total_steps,
        np.mean(agent.iteration_rewards),
        np.max(agent.iteration_rewards),
        np.min(agent.iteration_rewards),
        np.mean(agent.iteration_success_rate),
        np.max(agent.iteration_success_rate),
        np.min(agent.iteration_success_rate)
    ))
    logger.scalar_summary('agent_{0}/last_episode_avg_reward'.format(agent_idx), \
        np.mean(agent.last_episode_rewards))
    logger.scalar_summary('agent_{0}/last_episode_std_reward'.format(agent_idx), \
        np.std(agent.last_episode_rewards))
    logger.scalar_summary('agent_{0}/last_episode_max_reward'.format(agent_idx), \
        np.max(agent.last_episode_rewards))
    logger.scalar_summary('agent_{0}/last_episode_min_reward'.format(agent_idx), \
        np.min(agent.last_episode_rewards))
    logger.scalar_summary('agent_{0}/iteration_avg_reward'.format(agent_idx), \
        np.mean(agent.iteration_rewards))
    logger.scalar_summary('agent_{0}/iteration_std_reward'.format(agent_idx), \
        np.std(agent.iteration_rewards))
    logger.scalar_summary('agent_{0}/iteration_max_reward'.format(agent_idx), \
        np.max(agent.iteration_rewards))
    logger.scalar_summary('agent_{0}/iteration_min_reward'.format(agent_idx), \
        np.min(agent.iteration_rewards))

    logger.scalar_summary('agent_{0}/last_episode_avg_success_rate'.format(agent_idx), \
        np.mean(agent.last_episode_success_rate))
    logger.scalar_summary('agent_{0}/last_episode_std_success_rate'.format(agent_idx), \
        np.std(agent.last_episode_success_rate))
    logger.scalar_summary('agent_{0}/last_episode_max_success_rate'.format(agent_idx), \
        np.max(agent.last_episode_success_rate))
    logger.scalar_summary('agent_{0}/last_episode_min_success_rate'.format(agent_idx), \
        np.min(agent.last_episode_success_rate))
    logger.scalar_summary('agent_{0}/iteration_avg_success_rate'.format(agent_idx), \
        np.mean(agent.iteration_success_rate))
    logger.scalar_summary('agent_{0}/iteration_std_success_rate'.format(agent_idx), \
        np.std(agent.iteration_success_rate))
    logger.scalar_summary('agent_{0}/iteration_max_success_rate'.format(agent_idx), \
        np.max(agent.iteration_success_rate))
    logger.scalar_summary('agent_{0}/iteration_min_success_rate'.format(agent_idx), \
        np.min(agent.iteration_success_rate))

    prefix = 'agent_{0}_'.format(agent_idx)
    if hasattr(agent, 'layers_output'):
        for tag, value in agent.layers_output:
            value = value.detach().cpu().numpy()
            value_norm = np.linalg.norm(value, axis=-1)
            logger.scalar_summary('{0}debug/{1}_avg_norm'.format(prefix, tag), np.mean(value_norm))
            logger.scalar_summary('{0}debug/{1}_avg'.format(prefix, tag), value.mean())
            logger.scalar_summary('{0}debug/{1}_std'.format(prefix, tag), value.std())
            logger.scalar_summary('{0}debug/{1}_max'.format(prefix, tag), value.max())
            logger.scalar_summary('{0}debug/{1}_min'.format(prefix, tag), value.min())

    for key, value in dict_logs.items():
        logger.scalar_summary('{0}debug_extended/{1}_avg'.format(prefix, key), np.mean(value))
        logger.scalar_summary('{0}debug_extended/{1}_std'.format(prefix, key), np.std(value))
        logger.scalar_summary('{0}debug_extended/{1}_max'.format(prefix, key), np.max(value))
        logger.scalar_summary('{0}debug_extended/{1}_min'.format(prefix, key), np.min(value))

    return

'''
shell training: single processing, all agents are executed/trained in a single process
with each agent taking turns to execute a training step.

note: task boundaries are explictly given to the agents. this means that each agent
knows when task changes. 
'''
def shell_train(agents, logger):
    num_agents = len(agents)
    shell_done = [False,] * num_agents
    shell_iterations = [0,] * num_agents
    shell_tasks = [agent.config.cl_tasks_info for agent in agents] # tasks for each agent
    shell_task_ids = [agent.config.task_ids for agent in agents]
    shell_task_counter = [0,] * num_agents

    shell_eval_tracker = [False,] * num_agents
    shell_eval_data = []
    num_eval_tasks = len(agents[0].evaluation_env.get_all_tasks())
    shell_eval_data.append(np.zeros((num_agents, num_eval_tasks), dtype=np.float32))
    shell_metric_icr = [] # icr => instant cumulative reward metric
    eval_data_fhs = [open(logger.log_dir + '/eval_metrics_agent_{0}.csv'.format(agent_idx), 'a', \
        buffering=1) for agent_idx in range(num_agents)]

    if agents[0].task.name == agents[0].config.ENV_METAWORLD or \
        agents[0].task.name == agents[0].config.ENV_CONTINUALWORLD:
        itr_log_fn = _shell_itr_log_mw
    else:
        itr_log_fn = _shell_itr_log

    #print()
    logger.info('*****start shell training')

    # set the first task each agent is meant to train on
    for agent_idx, agent in enumerate(agents):
        states_ = agent.task.reset_task(shell_tasks[agent_idx][0])
        agent.states = agent.config.state_normalizer(states_)
        logger.info('*****agent {0} /setting first task (task 0)'.format(agent_idx))
        logger.info('task: {0}'.format(shell_tasks[agent_idx][0]['task']))
        logger.info('task_label: {0}'.format(shell_tasks[agent_idx][0]['task_label']))
        agent.task_train_start(shell_tasks[agent_idx][0]['task_label'])
        #print()
    del states_

    while True:
        for agent_idx, agent in enumerate(agents):
            if shell_done[agent_idx]:
                continue
            dict_logs = agent.iteration()
            shell_iterations[agent_idx] += 1
            # tensorboard log
            if shell_iterations[agent_idx] % agent.config.iteration_log_interval == 0:
                itr_log_fn(logger, agent, agent_idx, shell_iterations[agent_idx], \
                    shell_task_counter[agent_idx], dict_logs)

            # evaluation block
            if (agent.config.eval_interval is not None and \
                shell_iterations[agent_idx] % agent.config.eval_interval == 0):
                logger.info('*****agent {0} / evaluation block'.format(agent_idx))
                _task_ids = shell_task_ids[agent_idx]
                _tasks = shell_tasks[agent_idx]
                _names = [eval_task_info['name'] for eval_task_info in _tasks]
                logger.info('eval tasks: {0}'.format(', '.join(_names)))
                for eval_task_idx, eval_task_info in zip(_task_ids, _tasks):
                    agent.task_eval_start(eval_task_info['task_label'])
                    eval_states = agent.evaluation_env.reset_task(eval_task_info)
                    agent.evaluation_states = eval_states
                    # performance (perf) can be success rate in (meta-)continualworld or
                    # rewards in other environments
                    perf, eps = agent.evaluate_cl(num_iterations=agent.config.evaluation_episodes)
                    agent.task_eval_end()
                    shell_eval_data[-1][agent_idx, eval_task_idx] = np.mean(perf)
                shell_eval_tracker[agent_idx] = True
                # save latest eval data for current agent to csv
                _record = np.concatenate([shell_eval_data[-1][agent_idx, : ], \
                    np.array(time.time()).reshape(1,)])
                np.savetxt(eval_data_fhs[agent_idx], _record.reshape(1, -1),delimiter=',',fmt='%.4f')
                del _record

            # checker for end of task training
            if not agent.config.max_steps:
                raise ValueError('`max_steps` should be set for each agent')
            task_steps_limit = agent.config.max_steps[shell_task_counter[agent_idx]] * \
                (shell_task_counter[agent_idx] + 1)
            if agent.total_steps >= task_steps_limit:
                #print()
                task_counter_ = shell_task_counter[agent_idx]
                logger.info('*****agent {0} / end of training on task {1}'.format(agent_idx, \
                    task_counter_))
                agent.task_train_end()

                task_counter_ += 1
                shell_task_counter[agent_idx] = task_counter_
                if task_counter_ < len(shell_tasks[agent_idx]):
                    logger.info('*****agent {0} / set next task {1}'.format(agent_idx, task_counter_))
                    logger.info('task: {0}'.format(shell_tasks[agent_idx][task_counter_]['task']))
                    logger.info('task_label: {0}'.format(shell_tasks[agent_idx][task_counter_]['task_label']))
                    states_ = agent.task.reset_task(shell_tasks[agent_idx][task_counter_]) # set new task
                    agent.states = agent.config.state_normalizer(states_)
                    agent.task_train_start(shell_tasks[agent_idx][task_counter_]['task_label'])

                    # ping other agents to see if they have knoweledge (mask) of current task
                    logger.info('*****agent {0} / pinging other agents to leverage on existing ' \
                        'knowledge about task'.format(agent_idx))
                    a_idxs = list(range(len(agents)))
                    a_idxs.remove(agent_idx)
                    other_agents = [agents[i] for i in a_idxs]
                    found_knowledge = agent.ping_agents(other_agents)
                    if found_knowledge > 0:
                        logger.info('found knowledge about task from other agents')
                        logger.info('number of task knowledge found: {0}'.format(found_knowledge))
                    else:
                        logger.info('could not find any agent with knowledge about task')
                    del states_
                    #print()
                else:
                    shell_done[agent_idx] = True # training done for all task for agent
                    logger.info('*****agent {0} / end of all training'.format(agent_idx))
                del task_counter_
                    
        if all(shell_eval_tracker):
            _metrics = shell_eval_data[-1]
            # compute icr
            _max_reward = _metrics.max(axis=0) 
            _agent_ids = _metrics.argmax(axis=0).tolist()
            _agent_ids = ', '.join([str(_agent_id) for _agent_id in _agent_ids])
            icr = _max_reward.sum()
            shell_metric_icr.append(icr)
            # log eval to file/screen and tensorboard
            logger.info('*****shell evaluation:')
            logger.info('best agent per task:'.format(_agent_ids))
            logger.info('shell eval ICR: {0}'.format(icr))
            logger.info('shell eval TP: {0}'.format(np.sum(shell_metric_icr)))
            logger.scalar_summary('shell_eval/icr', icr)
            logger.scalar_summary('shell_eval/tpot', np.sum(shell_metric_icr))
            # reset eval tracker
            shell_eval_tracker = [False for _ in shell_eval_tracker]
            # initialise new eval block
            shell_eval_data.append(np.zeros((num_agents, num_eval_tasks), dtype=np.float32))

        if all(shell_done):
            break

    for i in range(len(eval_data_fhs)):
        eval_data_fhs[i].close()
    # discard last eval data entry as it was not used.
    if np.all(shell_eval_data[-1] == 0.):
        shell_eval_data.pop(-1)
    # save eval metrics
    to_save = np.stack(shell_eval_data, axis=0)
    with open(logger.log_dir + '/eval_metrics.npy', 'wb') as f:
        np.save(f, to_save)

    for agent in agents:
        agent.close()
    return

'''
shell training: concurrent processing, all agents are executed/trained in across multiple
processes (either in a single machine, or distributed machines)

note: task boundaries are explictly given to the agents. this means that each agent
knows when task changes. 
'''
def shell_dist_train(agent, comm, agent_id, num_agents):
    logger = agent.config.logger
    #print()
    logger.info('*****start shell training')

    shell_done = False
    shell_iterations = 0
    shell_tasks = agent.config.cl_tasks_info # tasks for agent
    shell_task_ids = agent.config.task_ids
    shell_task_counter = 0


    mask_rewards_dict = dict()


    shell_eval_tracker = False
    shell_eval_data = []
    num_eval_tasks = len(agent.evaluation_env.get_all_tasks())
    shell_eval_data.append(np.zeros((num_eval_tasks, ), dtype=np.float32))
    shell_metric_icr = [] # icr => instant cumulative reward metric. NOTE may be redundant now
    eval_data_fh = open(logger.log_dir + '/eval_metrics_agent_{0}.csv'.format(agent_id), 'a', \
        buffering=1) # buffering=1 means flush data to file after every line written
    shell_eval_end_time = None

    if agent.task.name == agent.config.ENV_METAWORLD or \
        agent.task.name == agent.config.ENV_CONTINUALWORLD:
        itr_log_fn = _shell_itr_log_mw
    else:
        itr_log_fn = _shell_itr_log

    await_response = [False,] * num_agents # flag
    # set the first task each agent is meant to train on
    states_ = agent.task.reset_task(shell_tasks[0])
    agent.states = agent.config.state_normalizer(states_)
    logger.info('*****agent {0} / setting first task (task 0)'.format(agent_id))
    logger.info('task: {0}'.format(shell_tasks[0]['task']))
    logger.info('task_label: {0}'.format(shell_tasks[0]['task_label']))
    agent.task_train_start(shell_tasks[0]['task_label'])
    #print()
    del states_

    msg = None
    while True:
        #print(await_response)
        # listen for and send info (task label or NULL message) to other agents
        other_agents_request = comm.send_receive_request(msg)
        #print(other_agents_request)
        msg = None # reset message

        requests = []
        for req in other_agents_request:
            #print(req)
            if req is None: continue
            req['mask'] = agent.label_to_mask(req['task_label'])
            requests.append(req)
        if len(requests) > 0:
            comm.send_response(requests)

        # if the agent earlier sent a request, check whether response has been sent.
        if any(await_response):
            logger.info('awaiting response: {0}'.format(await_response))
            masks = []
            received_masks = comm.receive_response()
            for i in range(len(await_response)):
                if await_response[i] is False: continue

                if received_masks[i] is False: continue
                elif received_masks[i] is None: await_response[i] = False
                else:
                    masks.append(received_masks[i])
                    await_response[i] = False
            logger.info('number of task knowledge received: {0}'.format(len(masks)))
            # TODO still need to fix how mask is used.
            agent.distil_task_knowledge(masks)
                    
        # agent iteration (training step): collect on policy data and optimise agent
        dict_logs = agent.iteration()
        shell_iterations += 1

        # tensorboard log
        if shell_iterations % agent.config.iteration_log_interval == 0:
            itr_log_fn(logger, agent, agent_id, shell_iterations, shell_task_counter, dict_logs)
            
            # Create a dictionary to store the most recent iteration rewards for a mask. Update in every iteration
            # logging cycle. Take average of all worker averages as the most recent reward score for a given task
            mask_rewards_dict[np.array2string(shell_tasks[shell_task_counter]['task_label'], precision=2, separator=', ', suppress_small=True)] = np.mean(agent.iteration_rewards)
            #print(mask_rewards_dict)


        # evaluation block
        if (agent.config.eval_interval is not None and \
            shell_iterations % agent.config.eval_interval == 0):
            logger.info('*****agent {0} / evaluation block'.format(agent_id))
            _task_ids = shell_task_ids
            _tasks = shell_tasks
            _names = [eval_task_info['name'] for eval_task_info in _tasks]
            logger.info('eval tasks: {0}'.format(', '.join(_names)))
            for eval_task_idx, eval_task_info in zip(_task_ids, _tasks):
                agent.task_eval_start(eval_task_info['task_label'])
                eval_states = agent.evaluation_env.reset_task(eval_task_info)
                agent.evaluation_states = eval_states
                # performance (perf) can be success rate in (meta-)continualworld or
                # rewards in other environments
                perf, eps = agent.evaluate_cl(num_iterations=agent.config.evaluation_episodes)
                agent.task_eval_end()
                shell_eval_data[-1][eval_task_idx] = np.mean(perf)
            shell_eval_tracker = True
            shell_eval_end_time = time.time()

        # end of current task training. move onto next task or end training if last task.
        if not agent.config.max_steps: raise ValueError('`max_steps` should be set for each agent')
        task_steps_limit = agent.config.max_steps[shell_task_counter] * (shell_task_counter + 1)
        if agent.total_steps >= task_steps_limit:
            #print()
            task_counter_ = shell_task_counter
            logger.info('*****agent {0} / end of training on task {1}'.format(agent_id, task_counter_))
            agent.task_train_end()

            task_counter_ += 1
            shell_task_counter = task_counter_
            if task_counter_ < len(shell_tasks):
                # new task
                logger.info('*****agent {0} / set next task {1}'.format(agent_id, task_counter_))
                logger.info('task: {0}'.format(shell_tasks[task_counter_]['task']))
                logger.info('task_label: {0}'.format(shell_tasks[task_counter_]['task_label']))
                states_ = agent.task.reset_task(shell_tasks[task_counter_]) # set new task
                agent.states = agent.config.state_normalizer(states_)
                agent.task_train_start(shell_tasks[task_counter_]['task_label'])

                # set message (task_label) that will be sent to other agent as a request for
                # task knowledge (mask) about current task. this will be sent in the next
                # receive/send request cycle.
                logger.info('*****agent {0} / query other agents using current task label'\
                    .format(agent_id))
                msg = shell_tasks[task_counter_]['task_label']


                



                await_response = [True,] * num_agents
                del states_
                #print()
            else:
                shell_done = True # training done for all task for agent
                logger.info('*****agent {0} / end of all training'.format(agent_id))
            del task_counter_
                    
        if shell_eval_tracker:
            # log the last eval metrics to file
            _record = np.concatenate([shell_eval_data[-1],np.array(shell_eval_end_time).reshape(1,)])
            np.savetxt(eval_data_fh, _record.reshape(1, -1), delimiter=',', fmt='%.4f')
            del _record

            # reset eval tracker and add new buffer to save next eval metrics
            shell_eval_tracker = False
            shell_eval_data.append(np.zeros((num_eval_tasks, ), dtype=np.float32))
        #if all(shell_eval_tracker):
        #    _metrics = shell_eval_data[-1]
        #    # compute icr
        #    _max_reward = _metrics.max(axis=0) 
        #    _agent_ids = _metrics.argmax(axis=0).tolist()
        #    _agent_ids = ', '.join([str(_agent_id) for _agent_id in _agent_ids])
        #    icr = _max_reward.sum()
        #    shell_metric_icr.append(icr)
        #    # log eval to file/screen and tensorboard
        #    logger.info('*****shell evaluation:')
        #    logger.info('best agent per task:'.format(_agent_ids))
        #    logger.info('shell eval ICR: {0}'.format(icr))
        #    logger.info('shell eval TP: {0}'.format(np.sum(shell_metric_icr)))
        #    logger.scalar_summary('shell_eval/icr', icr)
        #    logger.scalar_summary('shell_eval/tpot', np.sum(shell_metric_icr))
        #    # reset eval tracker
        #    shell_eval_tracker = [False for _ in shell_eval_tracker]
        #    # initialise new eval block
        #    shell_eval_data.append(np.zeros((1, num_eval_tasks), dtype=np.float32))


        #print(await_response)

        if shell_done:
            break
        comm.barrier()
    # end of while True

    #eval_data_fh.close()
    # discard last eval data entry as it was not used.
    #if np.all(shell_eval_data[-1] == 0.):
    #    shell_eval_data.pop(-1)
    # save eval metrics
    #to_save = np.stack(shell_eval_data, axis=0)
    #with open(logger.log_dir + '/eval_metrics_agent_{0}.npy'.format(agent_id), 'wb') as f:
    #    np.save(f, to_save)

    agent.close()
    return
    

'''
ShELL distributed trainer using multiprocessing communication. Multiprocessing agent to be
added in the future.
'''
import multiprocess as mp
from colorama import Fore, Back, Style

def shell_dist_train_mp(agent, comm, agent_id, num_agents):
    logger = agent.config.logger
    #print()

    logger.info('*****start shell training')

    shell_done = False
    shell_iterations = 0
    shell_tasks = agent.config.cl_tasks_info # tasks for agent
    shell_task_ids = agent.config.task_ids
    shell_task_counter = 0

    shell_agent_seed = agent.config.seed        # Chris


    shell_eval_tracker = False
    shell_eval_data = []
    num_eval_tasks = len(agent.evaluation_env.get_all_tasks())
    shell_eval_data.append(np.zeros((num_eval_tasks, ), dtype=np.float32))
    shell_metric_icr = [] # icr => instant cumulative reward metric. NOTE may be redundant now
    eval_data_fh = open(logger.log_dir + '/eval_metrics_agent_{0}.csv'.format(agent_id), 'a', \
        buffering=1) # buffering=1 means flush data to file after every line written
    shell_eval_end_time = None

    if agent.task.name == agent.config.ENV_METAWORLD or \
        agent.task.name == agent.config.ENV_CONTINUALWORLD:
        itr_log_fn = _shell_itr_log_mw
    else:
        itr_log_fn = _shell_itr_log

    await_response = [True,] * num_agents # flag
    # set the first task each agent is meant to train on
    states_ = agent.task.reset_task(shell_tasks[0])
    agent.states = agent.config.state_normalizer(states_)
    logger.info('*****agent {0} / setting first task (task 0)'.format(agent_id))
    logger.info('task: {0}'.format(shell_tasks[0]['task']))
    logger.info('task_label: {0}'.format(shell_tasks[0]['task_label']))
    agent.task_train_start(shell_tasks[0]['task_label'])
    #print()
    del states_


    

    # Msg can be embedding or task label.
    # Set msg to first task. The agents will then request knowledge on the first task.
    # this will ensure that other agents are aware that this agent is now working this task
    # until a task change happens.
    #msg = np.zeros(agent.get_task_emb_size)#shell_tasks[0]['task_label']
    msg = None
    
    # Initialize dictionary to store the most up-to-date rewards for a particular embedding/task label.
    mask_rewards_dict = dict()

    # Track which agents are working which tasks. This will be resized every time a new agent is added
    # to the network. Every time there is a communication step 1, we will check if it is none otherwise update
    # this dictionary
    track_tasks = {}#{agent_id: torch.from_numpy(msg)}


    # Agent-Communication interaction queues
    manager = mp.Manager()
    queue_check = manager.Queue()
    queue_mask = manager.Queue()
    queue_label = manager.Queue()
    queue_label_send = manager.Queue()  # Used to send label from comm to agent to convert to mask
    queue_mask_recv = manager.Queue()   # Used to send mask from agent to comm after conversion from label
    queue_loop = manager.Queue()

    # Put in the initial data into the loop queue so that the comm module is not blocking the agent
    # from running.
    queue_loop.put_nowait((track_tasks, mask_rewards_dict, await_response, shell_iterations))

    #detect = detect_module

    # Start the communication module with the initial states and the first task label.
    # Get the mask ahead of the start of the agent iteration loop so that it is available sooner
    # Also pass the queue proxies to enable interaction between the communication module and the agent module
    pcomm = comm.parallel(queue_label, queue_mask, queue_label_send, queue_mask_recv, queue_loop, queue_check) # CHANGE THIS TO GET THE EMBEDDINGS!!!!!!!!!!!

    exchanges = []
    task_times = []
    detect_module_activations = []
    #What is this for? NO NEED TO CHANGE, WAS FOR LOGGIN.
    task_times.append([0, shell_iterations, np.argmax(shell_tasks[0]['task_label'], axis=0), time.time()]) # CHNAGE THIS FORM LABEL TO EMBEDDING!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

    check = queue_check.get()
    #check = True
    if check:
        while True:
            if not pcomm.is_alive():
                pcomm.kill()    # Kill the old process and start a new one
                pcomm = comm.parallel(queue_label, queue_mask, queue_label_send, queue_mask_recv, queue_loop, queue_check) # CHNAGE TO TAKE EMBEDDINGS INSTEAD OF LABELS !!!!!!!!!

            START = time.time()
            #print(Fore.BLUE + 'Msg in this iteration: ', msg)
            # If world size is 1 then act as an individual agent.
            ######################## COMMUNICATION MODULE HANDLING ########################
            '''
            Handles the interaction between the agent and the communication module. The agent can tell the
            communication module to get it masks from the network if available. Agent will continue to function
            regardless of whether the communication module gets a mask or not.
            '''

            print(Fore.BLUE + 'Agent SEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEED:', shell_agent_seed, flush=True)           # Chris

            #time.sleep(1)
            if num_agents > 1:
                try:
                    mask, track_tasks_temp, await_response, best_agent_rw, best_agent_id, received_label = queue_mask.get_nowait() # CHANGE TO TAKE EMBEDDINGS INSTEAD OF LABELS !!!!!!!!!!!!!
                    print(Fore.BLUE + 'Agent received mask from comm for query:', type(mask), mask, flush=True)
                    
                    if mask is not None:
                        #if shell_iterations % mask_interval == 0:
                        # Update the knowledge base with the expected reward
                        mask_rewards_dict.update(best_agent_rw)
                        # Update the network with the mask
                        agent.distil_task_knowledge_single(mask, received_label) # CHANGE SO IT DISTILS KNOWLEDGE BASED ON THE EMBEDDING, NOT LABEL!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
                        print(Fore.BLUE+'KNOWLEDGE DISTILLED TO NETWORK!', flush=True)

                        #print(shell_iterations)
                        #print(best_agent_id)
                        #print(best_agent_rw)
                        #print(len(mask))
                        #print(mask)

                        _tempknowledgebase = {}
                        for key, val in mask_rewards_dict.items():
                            _tempknowledgebase[np.argmax(key, axis=0)] = val

                        exchanges.append([shell_iterations, best_agent_id, np.argmax(received_label, axis=0), _tempknowledgebase, len(mask), mask]) #CHANGE TO USE THE EMBEDDING!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
                        np.savetxt(logger.log_dir + '/exchanges_{0}.csv'.format(agent_id), exchanges, delimiter=',', fmt='%s')
                        #del mask

                        

                    if torch.equal(track_tasks_temp[agent_id], track_tasks[agent_id]):
                        track_tasks = track_tasks_temp
                        del track_tasks_temp

                    else:
                        temp_self_task = track_tasks[agent_id]
                        track_tasks = track_tasks_temp
                        track_tasks[agent_id] = temp_self_task
                        del track_tasks_temp, temp_self_task

                        
                    ##print(Fore.BLUE + 'Agent received from comm: ', mask, track_tasks, mask_rewards_dict, await_response)
                    #print()

                except Empty:
                    print('Get mask failed')
                    pass # continue with the iteration



                # Check if the communication module has sent a label to be converted to a mask
                # convert it and send it back to the agent
                try:
                    #print(Fore.BLUE + 'Agent checking for any label conversion req')
                    to_convert = queue_label_send.get_nowait() #CHANGE TO WORK WITH THE EMBEDDING!!!!!!!!!!!!!!!!!!!!!!!!!
                    _conversions = []
                    for dst_agent_id, comm_label in to_convert.items(): #comm_label SHOULD NOW BE AN EMBEDDING!!!!!!!!!!!!
                        _comm_label = comm_label.detach().cpu().numpy()
                        d = {}
                        d['dst_agent_id'] = dst_agent_id
                        d['label'] = comm_label # REPLACE WITH THE EMBEDDING!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
                        d['mask'] = agent.label_to_mask(_comm_label)
                        _conversions.append(d)
                    queue_mask_recv.put((_conversions))
                except Empty:
                    print(Fore.BLUE + 'No label to convert to mask')
                    pass

                #print(Fore.BLUE + 'START OF ITERATION: ', track_tasks, mask_rewards_dict, await_response)

                # Get the mask when it is available but don't wait on the communication module. Continue
                # with the iteration regardless of mask being available. Once the mask is available in
                # an iteration cycle, then distil the knowledge to the network which should dramatically
                # improve performance.

                
                await_response = [True,] * num_agents
                # Update the communication module with the latest information from this iteration
                queue_loop.put_nowait((track_tasks, mask_rewards_dict, await_response, shell_iterations))
                
                # Send the msg of this iteration. It will be either a task label or NoneType. Eitherway
                # the communication module will do its thing.
                if msg is not None:
                    queue_label.put_nowait(msg)
                #print(Fore.BLUE + "Agent requesting mask for label: ", msg)
                #print()

                
                #msg = None # reset message

            ######################## AGENT ITERATION AND LOGGING ########################
            '''
            The main iteration loop. Handles everything from the actual iteration function (data collection/optimisation),
            iteration logging function, evaluation block, task change function, and the evaluation logging
            TODO: Look to convert the agent iteration loop to a parallel process like the communciation
                    module, to achieve true asynchronisity. Might take heavy refactoring of how the config
                    object is setup with lambda functions.
            '''

            ### AGENT ITERATION (training step): collect on policy data and optimise agent
            '''
            Handles the data collection and optimisation functionalities of the agent.
            TODO: Look into multihreading/multiprocessing the data collection and optimisation of the agent
                    to achieve the continous data collection we want for a real world scenario.
                
                Possibly the optimisation could be made a seperate process parallel to the data collection
                    process, similar to the communication-agent(trainer) architecture. Data collection and the code
                    below would run together in the main loop.
            '''
            dict_logs = agent.iteration() #NOTE WE PERFORM THE TRAINING ITERATION HERE, IT IS WHERE OUR REPLAY BUFFER WILL BE FEELED WITH DATA!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
            shell_iterations += 1

            print("ITERATION NUMBER:", shell_iterations)


            #daf = agent.get_



            activation_flag = detect_module_activation_check(shell_iterations, agent.get_detect_module_activation_frequency(), agent)
            str_task_chng_msg, task_change_flag, emb_dist, emb_bool, new_emb = run_detect_module(agent, activation_flag)

            #Logging of the detect operations!!!
            if activation_flag:
                #print(Fore.GREEN)
                detect_module_activations.append([shell_iterations, activation_flag, agent.detect.get_num_samples(), str_task_chng_msg, task_change_flag, "HI I AM DIST:", emb_dist, "HI I CHECK EQ CURR VS NEW EMB:", emb_bool, "HI I AM EMB:", new_emb])
                np.savetxt(logger.log_dir + '/detect_activations_{0}.csv'.format(agent_id), detect_module_activations, delimiter=',', fmt='%s')

            ### TENSORBOARD LOGGING & SELF TASK REWARD TRACKING
            '''
            Logs metrics to tensorboard log file and updates the embedding, reward pair in this cycle for a particular task
            
            TODO: Modify how the key of the dictionary (the embedding) is compared to the previous embedding and updated
                    We will need to store the embedding from the previous cycle and the new embedding to update the reward
                    tracking. This will continue until the Detect module tells us that there is a task change and we
                    create a new addition to the dictionary.
            '''
            if shell_iterations % agent.config.iteration_log_interval == 0:
                itr_log_fn(logger, agent, agent_id, shell_iterations, shell_task_counter, dict_logs)
                
                # Create a dictionary to store the most recent iteration rewards for a mask. Update in every iteration
                # logging cycle. Take average of all worker averages as the most recent reward score for a given task
                mask_rewards_dict[tuple(shell_tasks[shell_task_counter]['task_label'])] = np.around(np.mean(agent.iteration_rewards), decimals=6)#CHANGE TO USE THE EMBEDDING!!!!!!!!!!!!!!!!!!!!!!!
                #print(Fore.BLUE + '', mask_rewards_dict, flush=True)
                #print(track_tasks)

                # Save agent model
                agent.save(agent.config.log_dir + '/%s-%s-model-%s.bin' % (agent.config.agent_name, agent.config.tag, \
                        agent.task.name))


            ### EVALUATION BLOCK
            '''
            Performs the evaluation block.
            
            TODO: Need to create a flag to activate only evaluation or only iteration. This will allow us
                    to create a dedicated evaluation agent which will need to use fetchall in every task
                    to find the best mask from other agents. This evaluation agent will need to have a 
                    unique identifier so other agents know to ignore it when requesting information but are
                    aware it exists in the network. Other agents will simply need to answer this agents request for
                    task masks.
            '''
            # If we want to stop evaluating then set agent.config.eval_interval to None
            if (agent.config.eval_interval is not None and \
                shell_iterations % agent.config.eval_interval == 0):
                logger.info('*****agent {0} / evaluation block'.format(agent_id))
                _task_ids = shell_task_ids
                _tasks = shell_tasks
                _names = [eval_task_info['name'] for eval_task_info in _tasks]
                logger.info('eval tasks: {0}'.format(', '.join(_names)))
                for eval_task_idx, eval_task_info in zip(_task_ids, _tasks):
                    agent.task_eval_start(eval_task_info['task_label'])
                    eval_states = agent.evaluation_env.reset_task(eval_task_info)
                    agent.evaluation_states = eval_states
                    # performance (perf) can be success rate in (meta-)continualworld or
                    # rewards in other environments
                    perf, eps = agent.evaluate_cl(num_iterations=agent.config.evaluation_episodes)
                    agent.task_eval_end()
                    shell_eval_data[-1][eval_task_idx] = np.mean(perf)
                shell_eval_tracker = True
                shell_eval_end_time = time.time()


            ### TASK CHANGE
            # end of current task training. move onto next task or end training if last task.
            # i.e., Task Change occurs here. For detect module, if the task embedding signifies a task
            # change then that occurs here.
            '''
            If we want to use a Fetch All mode for ShELL then we need to add a commmunication component
            at task change which broadcasts the mask to all other agents currently on the network.

            Otherwise the current implementation is a On Demand mode where each agent requests knowledge
            only when required.
            '''
            if not agent.config.max_steps: raise ValueError('`max_steps` should be set for each agent')
            task_steps_limit = agent.config.max_steps[shell_task_counter] * (shell_task_counter + 1)
            if agent.total_steps >= task_steps_limit:
                #print()
                task_counter_ = shell_task_counter
                logger.info('*****agent {0} / end of training on task {1}'.format(agent_id, task_counter_))
                #MOVE TO PPOagent.task_train_end()

                task_counter_ += 1
                shell_task_counter = task_counter_
                if task_counter_ < len(shell_tasks):
                    task_times.append([task_counter_, shell_iterations, np.argmax(shell_tasks[task_counter_]['task_label'], axis=0), time.time()])#CHANGE TO WORK WITH EMBEDDING !!!!!!!!!!!!!!!!!!!!!!!!!!
                    np.savetxt(logger.log_dir + '/task_changes_{0}.csv'.format(agent_id), task_times, delimiter=',', fmt='%s')


                    # new task
                    logger.info('*****agent {0} / set next task {1}'.format(agent_id, task_counter_))
                    logger.info('task: {0}'.format(shell_tasks[task_counter_]['task']))
                    logger.info('task_label: {0}'.format(shell_tasks[task_counter_]['task_label'])) #CHANGE TO WORK WITH EMBEDDING!!!!!!!!!!!!!!
                    states_ = agent.task.reset_task(shell_tasks[task_counter_]) # set new task
                    agent.states = agent.config.state_normalizer(states_)
                    # SHOULD MOVE TO PPO agent.task_train_start(shell_tasks[task_counter_]['task_label'])# CHANGE TO WORK WITH EMBEDDING!!!!!!!!!!!!!!!!!!!!!!!!

                    # set message (task_label) that will be sent to other agent as a request for
                    # task knowledge (mask) about current task. this will be sent in the next
                    # receive/send request cycle.
                    logger.info('*****agent {0} / query other agents using current task label'\
                        .format(agent_id))

                    # Update the msg, track_tasks dict for this agent and reset await_responses for new task
                    msg = shell_tasks[task_counter_]['task_label'] #CHANGE THIS WITH THE CALUCLATED EMBEDDING OR NONE!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
                    track_tasks[agent_id] = torch.from_numpy(msg)       # remove later
                    await_response = [True,] * num_agents
                    del states_
                    #print()
                else:
                    shell_done = True # training done for all task for agent
                    logger.info('*****agent {0} / end of all training'.format(agent_id))
                del task_counter_


            ### EVALUATION BLOCK LOGGING
            '''
            Logs the evaluation block data and tracks it.
            TODO: This will need to be refactored as part of the evaluation agent refactoring.
            '''
            if shell_eval_tracker:
                # log the last eval metrics to file
                _record = np.concatenate([shell_eval_data[-1],np.array(shell_eval_end_time).reshape(1,)])
                np.savetxt(eval_data_fh, _record.reshape(1, -1), delimiter=',', fmt='%.4f')
                del _record

                # reset eval tracker and add new buffer to save next eval metrics
                shell_eval_tracker = False
                shell_eval_data.append(np.zeros((num_eval_tasks, ), dtype=np.float32))
            
            print()
            END = time.time()-START
            print('***** AGENT ITERATION TIME ELAPSED:', END)

            # If ShELL is finished running all tasks then stop the program
            # this will have to be changed when we deploy so agents never stop working
            # and simply idle if there is nothing to learn.
            if shell_done:
                break
        # end of while True

        #eval_data_fh.close()
        # discard last eval data entry as it was not used.
        #if np.all(shell_eval_data[-1] == 0.):
        #    shell_eval_data.pop(-1)
        # save eval metrics
        #to_save = np.stack(shell_eval_data, axis=0)
        #with open(logger.log_dir + '/eval_metrics_agent_{0}.npy'.format(agent_id), 'wb') as f:
        #    np.save(f, to_save)

        agent.close()
        return

def shell_dist_eval_mp(agent, comm, agent_id, num_agents):
    logger = agent.config.logger
    #print()

    logger.info('*****start shell training')

    shell_done = False
    shell_iterations = 0
    shell_tasks = agent.config.cl_tasks_info # tasks for agent
    shell_task_ids = agent.config.task_ids
    shell_task_counter = 0


    shell_agent_seed = agent.config.seed        # Chris
    agent.config.eval_interval = 1      # Manual overide
    


    _task_ids = shell_task_ids
    _tasks = shell_tasks
    # agent.seen_tasks = {_tasks}
    agent.seen_tasks = {}
    for idx, eval_task_info in enumerate(_tasks):
        agent.seen_tasks[idx] =  eval_task_info['task_label']
    _names = [eval_task_info['name'] for eval_task_info in _tasks]
    eval_task_info = zip(_task_ids, _tasks)

    shell_eval_tracker = False
    shell_eval_data = []
    num_eval_tasks = len(agent.evaluation_env.get_all_tasks())
    shell_eval_data.append(np.zeros((num_eval_tasks, ), dtype=np.float32))
    shell_metric_icr = [] # icr => instant cumulative reward metric. NOTE may be redundant now
    eval_data_fh = open(logger.log_dir + '/eval_metrics_agent_{0}.csv'.format(agent_id), 'a', \
        buffering=1) # buffering=1 means flush data to file after every line written
    shell_eval_end_time = None

    # Evaluation agent likely wont need a iteration logging function
    '''if agent.task.name == agent.config.ENV_METAWORLD or \
        agent.task.name == agent.config.ENV_CONTINUALWORLD:
        itr_log_fn = _shell_itr_log_mw
    else:
        itr_log_fn = _shell_itr_log'''

    # We will still need the await_response list for communication
    await_response = [True,] * num_agents
    
    task_steps_limit = sum(agent.config.max_steps)


    # Msg can be embedding or task label.
    # Set msg to first task. The agents will then request knowledge on the first task.
    # this will ensure that other agents are aware that this agent is now working this task
    # until a task change happens.
    msg = _tasks[0]['task_label'] #Change with EMbeddings!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
    
    # Initialize dictionary to store the most up-to-date rewards for a particular embedding/task label.
    # Not sure we will need this anymore but might be useful to track what knowledge the eval agent has
    # in any given iteration. 
    mask_rewards_dict = dict()

    # Track which agents are working which tasks. This will be resized every time a new agent is added
    # to the network. Every time there is a communication step 1, we will check if it is none otherwise update
    # this dictionary
    # We probably won't need this in the future.
    track_tasks = {agent_id: torch.from_numpy(msg)}


    # Agent-Communication interaction queues
    # Eval agent will still need most of these.
    manager = mp.Manager()
    queue_check = manager.Queue()
    queue_mask = manager.Queue()
    queue_label = manager.Queue()
    queue_label_send = manager.Queue()  # Used to send label from comm to agent to convert to mask
    queue_mask_recv = manager.Queue()   # Used to send mask from agent to comm after conversion from label
    queue_loop = manager.Queue()

    # Put in the initial data into the loop queue so that the comm module is not blocking the agent
    # from running.
    queue_loop.put_nowait((track_tasks, mask_rewards_dict, await_response))

    # Start the communication module with the initial states and the first task label.
    # Get the mask ahead of the start of the agent iteration loop so that it is available sooner
    # Also pass the queue proxies to enable interaction between the communication module and the agent module
    pcomm = comm.parallel(queue_label, queue_mask, queue_label_send, queue_mask_recv, queue_loop, queue_check) # CHNEGE WITH EMBEDDINGS!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!


    #for item in _tasks:
    #    print(item)
    
    exchanges = []
    check = queue_check.get()
    #check = True
    if check:
        while True:
            if not pcomm.is_alive():
                pcomm.kill()    # Kill the old process and start a new one
                pcomm = comm.parallel(queue_label, queue_mask, queue_label_send, queue_mask_recv, queue_loop, queue_check) #CHNEGE WITH EMBEDDINGS!!!!!!!!!!!!!!!!!!!

            print()
            print(shell_iterations, shell_task_counter, agent.total_steps, agent.config.max_steps, task_steps_limit)
            agent.total_steps += agent.config.rollout_length * agent.config.num_workers 

            START = time.time()
            #print(Fore.BLUE + 'Msg in this iteration: ', msg)
            # If world size is 1 then act as an individual agent.
            ######################## COMMUNICATION MODULE HANDLING ########################
            '''
            Handles the interaction between the agent and the communication module. The agent can tell the
            communication module to get it masks from the network if available. Agent will continue to function
            regardless of whether the communication module gets a mask or not.
            '''
            #time.sleep(3) # Try turning this back if we have issues with mask synchronisation with comm module
            
            print(Fore.BLUE + 'Agent SEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEED:', shell_agent_seed, flush=True)         # Chris

            # Agent communication code block. All communication module related interactions are in here
            if num_agents > 1:
                try:
                    mask, track_tasks_temp, await_response, best_agent_rw, best_agent_id, received_label = queue_mask.get_nowait() #CHANGE WITH EMBEDDINGS!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
                    print(Fore.BLUE + 'Agent received mask from comm for query:', type(mask), mask, flush=True)
                    
                    if mask is not None:
                        # Update the knowledge base with the expected reward
                        mask_rewards_dict.update(best_agent_rw)
                        # Update the network with the mask
                        agent.distil_task_knowledge_single_eval(mask, received_label)#CHANGE WITH EMBEDDINGS!!!!!!!!!!!!!!!!!!!!!!!!
                        print(Fore.BLUE+'KNOWLEDGE DISTILLED TO NETWORK!', flush=True)

                        _tempknowledgebase = {}
                        for key, val in mask_rewards_dict.items():
                            _tempknowledgebase[np.argmax(key, axis=0)] = val

                        exchanges.append([shell_iterations, best_agent_id, np.argmax(received_label, axis=0), _tempknowledgebase, len(mask), mask])#CHANGE  WITH EMBEDDINGS!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
                        np.savetxt(logger.log_dir + '/exchanges_{0}.csv'.format(agent_id), exchanges, delimiter=',', fmt='%s')
                        #del mask

                    if torch.equal(track_tasks_temp[agent_id], track_tasks[agent_id]):
                        track_tasks = track_tasks_temp
                        del track_tasks_temp

                    else:
                        temp_self_task = track_tasks[agent_id]
                        track_tasks = track_tasks_temp
                        track_tasks[agent_id] = temp_self_task
                        del track_tasks_temp, temp_self_task

                except Empty:
                    print('Get mask failed')
                    pass
                
                await_response = [True,] * num_agents
                # Update the communication module with the latest information from this iteration
                queue_loop.put_nowait((track_tasks, mask_rewards_dict, await_response))
                
                # Send the msg of this iteration. It will be either a task label or NoneType. Eitherway
                # the communication module will do its thing.
                msg = _tasks[shell_task_counter]['task_label'] #CHANGE WITH EMBEDDINGS!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
                #agent.curr_eval_task_label = msg
                queue_label.put_nowait(msg)


            # Evaluation agent does not need to do data collection and optimisation so we will
            # not need to run the agent.iteration() function here. We will need to increment the shell
            # iterations however.
            #dict_logs = agent.iteration()
            #perf, eps = agent.evaluate_cl(num_iterations=agent.config.evaluation_episodes)
            shell_iterations += 1


            
            ### EVALUATION BLOCK
            '''
            Performs the evaluation block.
            
            TODO: Need to create a flag to activate only evaluation or only iteration. This will allow us
                    to create a dedicated evaluation agent which will need to use fetchall in every task
                    to find the best mask from other agents. This evaluation agent will need to have a 
                    unique identifier so other agents know to ignore it when requesting information but are
                    aware it exists in the network. Other agents will simply need to answer this agents request for
                    task masks.
            '''
            # If we want to stop evaluating then set agent.config.eval_interval to None
            if (agent.config.eval_interval is not None and \
                shell_iterations % agent.config.eval_interval == 0):
                logger.info('*****agent {0} / evaluation block'.format(agent_id))
                _task_ids = shell_task_ids
                _tasks = shell_tasks
                _names = [eval_task_info['name'] for eval_task_info in _tasks]
                logger.info('eval tasks: {0}'.format(', '.join(_names)))
                for eval_task_idx, eval_task_info in zip(_task_ids, _tasks):
                    agent.task_eval_start(eval_task_info['task_label'])
                    eval_states = agent.evaluation_env.reset_task(eval_task_info)
                    agent.evaluation_states = eval_states
                    # performance (perf) can be success rate in (meta-)continualworld or
                    # rewards in other environments
                    perf, eps = agent.evaluate_cl(num_iterations=agent.config.evaluation_episodes)
                    agent.task_eval_end()
                    shell_eval_data[-1][eval_task_idx] = np.mean(perf)
                shell_eval_tracker = True
                shell_eval_end_time = time.time()


            task_counter_ = shell_task_counter
            task_counter_ += 1
            if task_counter_ > len(shell_tasks)-1:
                task_counter_ = 0

            shell_task_counter = task_counter_


            ### EVALUATION BLOCK LOGGING
            '''
            Logs the evaluation block data and tracks it.
            TODO: This will need to be refactored as part of the evaluation agent refactoring.
            '''
            if shell_eval_tracker:
                # log the last eval metrics to file
                _record = np.concatenate([shell_eval_data[-1],np.array(shell_eval_end_time).reshape(1,)])
                np.savetxt(eval_data_fh, _record.reshape(1, -1), delimiter=',', fmt='%.4f')
                del _record

                # reset eval tracker and add new buffer to save next eval metrics
                shell_eval_tracker = False
                shell_eval_data.append(np.zeros((num_eval_tasks, ), dtype=np.float32))


            print('***** AGENT ITERATION TIME ELAPSED:', time.time()-START)

            # If ShELL is finished running all tasks then stop the program
            # this will have to be changed when we deploy so agents never stop working
            # and simply idle if there is nothing to learn.
            if shell_done:
                break
        # end of while True

        eval_data_fh.close()
        # discard last eval data entry as it was not used.
        if np.all(shell_eval_data[-1] == 0.):
            shell_eval_data.pop(-1)
        # save eval metrics
        to_save = np.stack(shell_eval_data, axis=0)
        with open(logger.log_dir + '/eval_metrics_agent_{0}.npy'.format(agent_id), 'wb') as f:
            np.save(f, to_save)

        agent.close()
        return


#########################################################################################################################################
########################################  U T I L I T Y      F U N C T I O N S  #########################################################
#########################################################################################################################################


def detect_module_activation_check(shell_training_iterations, detect_module_activation_frequncy, agent):
    '''Utility function for checking wheter the Detect Module should be activated or not based on the
    shell_training_iterations of the agent and the activation frequncy given from the configuration file.
    It makes sure that the data buffer has the ammount of data necassary for the detect module to sample.'''
    

    print("REPAY_BUFFER_SIZE:", agent.data_buffer.size())
    print("DETECT_MODULE_SAMPLE_SIZE:", agent.detect.get_num_samples())
    #print("ACTUAL_SAMPLES_DETECT_NEEDS:", (agent.detect.get_num_samples() * 64))
    if shell_training_iterations != 0 and shell_training_iterations % detect_module_activation_frequncy == 0 and agent.data_buffer.size() >= (agent.detect.get_num_samples() ):#Times the batch size the Detect Module uses.
        return True
    else:
        return False
        

def run_detect_module(an_agent, activation_check_flag):
    '''Uitility function for running all the necassery methods and function for the detect module
    so the approprate embeddings are generated for each batch of SAR data'''
    
    #Initilize the retun varibles with None values in the case of the detect module not being appropriate to run.
    str_task_chng_msg, task_change_flag, emb_dist, emb_bool, new_emb = None, None, None, None, None
    
    if activation_check_flag:
        sar_data = an_agent.sar_data_extraction()
        print("SAR_DATA_ARR:", sar_data)
        print("SAR SIZE:",sar_data.shape)
        print(sar_data)
        #print("CURR_EMB:", current_embedding)
        new_emb = an_agent.compute_task_embedding(sar_data, an_agent.get_task_action_space_size())
        current_embedding = an_agent.get_current_task_embedding()
        print("CURR_EMB:", current_embedding)
        print("NEW_EMB:", new_emb)
        print("EMBEDDING SIZE:", len(new_emb))
        emb_bool = current_embedding == new_emb
        emb_dist = an_agent.calculate_emb_distance(current_embedding, new_emb)
        emb_dist_thrshld = an_agent.get_emb_dist_threshold()
        str_task_chng_msg, task_change_flag = an_agent.assign_task_emb(new_emb, emb_dist, emb_dist_thrshld)

    return str_task_chng_msg, task_change_flag, emb_dist, emb_bool, new_emb