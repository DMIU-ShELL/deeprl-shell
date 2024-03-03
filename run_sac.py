import json
import shutil
import matplotlib
matplotlib.use("Pdf")
import multiprocessing as mp
from deep_rl.utils.misc import mkdir, get_default_log_dir, run_episodes
from deep_rl.utils.torch_utils import set_one_thread, random_seed, select_device
from deep_rl.utils.config import Config
from deep_rl.component.policy import SamplePolicy
from deep_rl.component.replay import Replay
from deep_rl.component.random_process import GaussianProcess, OrnsteinUhlenbeckProcess
from deep_rl.utils.normalizer import ImageNormalizer, RescaleNormalizer, RunningStatsNormalizer, RewardRunningStatsNormalizer
from deep_rl.utils.logger import get_logger
from deep_rl.utils.trainer_shell import trainer_learner, trainer_evaluator, trainer_learner_eps
from deep_rl.utils.trainer_ll import run_iterations_w_oracle
from deep_rl.utils.schedule import LinearSchedule
from deep_rl.agent.SAC_agent import SACAgent, SACContinualLearnerAgent, SACBaseAgent, SACLLAgent, SACShellAgent, SACDetectShell
from deep_rl.component.task import ParallelizedTask, MiniGridFlatObs, MetaCTgraphFlatObs, ContinualWorld, PendulumWrapper
from deep_rl.network.network_heads import SACNet, CategoricalActorCriticNet_SS, GaussianActorCriticNet_SS, DeterministicActorCriticNet
from deep_rl.network.network_bodies import FCBody, FCBody_SS, DummyBody_CL, TwoLayerFCBodyWithAction
from deep_rl.shell_modules.communication.comms_detect import ParallelCommDetect, ParallelCommDetectEval
from deep_rl.shell_modules.detect.detect import Detect
import argparse
import torch
import random
import torch.nn.functional as F



def global_config(config, name):
    # ctgraph config
    config.env_name = name
    config.env_config_path = None
    config.lr = 0.0003 #0.00015
    config.cl_preservation = 'supermask'
    config.seed = 9157
    random_seed(config.seed)
    config.log_dir = None
    config.logger = None 
    config.num_workers = 1
    config.optimizer_fn = lambda params, lr: torch.optim.RMSprop(params, lr=lr)

    config.policy_fn = SamplePolicy
    config.state_normalizer = ImageNormalizer()
    config.discount = 0.99
    config.use_gae = True
    config.gae_tau = 0.99
    config.entropy_weight = 0.00015 #0.75
    config.rollout_length = 128
    config.optimization_epochs = 8
    config.num_mini_batches = 64
    config.ppo_ratio_clip = 0.1
    config.iteration_log_interval = 1
    config.gradient_clip = 5
    config.max_steps = 25600
    config.evaluation_episodes = 25
    config.cl_requires_task_label = True
    config.task_fn = None
    config.eval_task_fn = None
    config.network_fn = None 
    config.eval_interval = None#1
    return config

def sac_baseline(name, args, shell_config):
    env_config_path = shell_config['env']['env_config_path']
    config_seed = shell_config['seed']

    config = Config()
    config = global_config(config, name)
    env_config_path = shell_config['env']['env_config_path']
    config_seed = shell_config['seed']
    config.backbone_seed = 9157
    config.init_port = args.port

    config.state_normalizer = RescaleNormalizer()
    config.reward_normalizer = RescaleNormalizer()

    config.seed = 9157

    ###############################################################################
    # Curriculum setup. TODO: Check how much of this is needed. Remove unnecessary stuff
    num_tasks = len(set(shell_config['curriculum']['task_ids']))
    config.cl_num_tasks = num_tasks
    config.task_ids = shell_config['curriculum']['task_ids']
    if isinstance(shell_config['curriculum']['max_steps'], list):
        config.max_steps = shell_config['curriculum']['max_steps']
    else:
        config.max_steps = [shell_config['curriculum']['max_steps'], ] * len(shell_config['curriculum']['task_ids'])

    ###############################################################################
    # Logging
    exp_id = '{0}-seed-{1}'.format(args.exp_id, config_seed)
    path_name = '{0}-shell-dist-{1}/agent_{2}'.format(name, exp_id, args.curriculum_id)
    log_dir = get_default_log_dir(path_name)
    logger = get_logger(log_dir=log_dir, file_name='train-log')
    config.logger = logger
    config.log_dir = log_dir

    # save shell config and env config
    #shutil.copy(shell_config_path, log_dir)
    with open(log_dir + '/shell_config.json', 'w') as f:
        json.dump(shell_config, f, indent=4)
    shutil.copy(env_config_path, log_dir)

    # create/initialise agent
    logger.info('*****initialising agent {0}'.format(args.curriculum_id))

    '''num_tasks = len(set(shell_config['curriculum']['task_ids']))
    config.cl_num_tasks = num_tasks
    config.task_ids = shell_config['curriculum']['task_ids']
    if isinstance(shell_config['curriculum']['max_steps'], list):
        config.max_steps = shell_config['curriculum']['max_steps']
    else:
        config.max_steps = [shell_config['curriculum']['max_steps'], ] * len(shell_config['curriculum']['task_ids'])'''

    #config.max_steps = int(1e6)#config.max_steps[0]
    config.max_steps = int(1e6)
    config.episode_limit = int(1e6)
    task_fn = lambda log_dir: PendulumWrapper(name, env_config_path, log_dir)
    config.task_fn = lambda: ParallelizedTask(task_fn,config.num_workers,log_dir=config.log_dir, single_process=True)
    
    eval_task_fn = lambda log_dir: PendulumWrapper(name, env_config_path, log_dir)
    config.eval_task_fn = eval_task_fn

    config.network_fn = lambda state_dim, action_dim: SACNet(
        action_dim,
        actor_body_fn  = lambda: FCBody(state_dim, (400, 300), gate=F.relu),
        critic_body_fn = lambda: FCBody(state_dim+action_dim, (400, 300), gate=F.relu),
        value_body_fn  = lambda: FCBody(state_dim, (400, 300), gate=F.relu),
        actor_opt_fn   = lambda params: torch.optim.Adam(params, lr=1e-3),
        critic_opt_fn  = lambda params: torch.optim.Adam(params, lr=1e-3),
        value_opt_fn   = lambda params: torch.optim.Adam(params, lr=1e-3))
    
    config.seed = config_seed
    #config.use_task_label = False
    #config.cl_requires_task_label = True

    config.replay_fn = lambda: Replay(memory_size=int(1e6), batch_size=64)
    config.discount = 0.99 # Gamma value
    config.random_process_fn = lambda action_dim: GaussianProcess(
        size=(action_dim,), std=LinearSchedule(0.1))
    #config.td3_noise = 0.2
    #config.td3_noise_clip = 0.5
    #config.td3_delay = 2
    config.alpha = 0.1
    config.warm_up = int(1e4)
    config.min_memory_size = int(1e4)
    config.target_network_mix = 5e-3

    agent = SACAgent(config)
    #config.agent_name = agent.__class__.__name__
    #tasks = agent.config.cl_tasks_info
    #config.cl_num_learn_blocks = 1
    run_episodes(agent)

def sac_detect(name, args, shell_config):
    config = Config()
    config = global_config(config, name)
    
    env_config_path = shell_config['env']['env_config_path']
    config_seed = shell_config['seed']
    config.backbone_seed = 9157
    config.init_port = args.port


    ###############################################################################
    # Detect Module
    config.detect_reference_num = shell_config['detect_reference_num']
    config.detect_num_samples = shell_config['detect_num_samples']
    config.emb_dist_threshold = shell_config['emb_dist_threshold']
    config.detect_module_activation_frequency = shell_config['detect_module_activation_frequency']


    ###############################################################################
    # Logging
    exp_id = '{0}-seed-{1}'.format(args.exp_id, config_seed)
    path_name = '{0}-shell-dist-{1}/agent_{2}'.format(name, exp_id, args.curriculum_id)
    log_dir = get_default_log_dir(path_name)
    logger = get_logger(log_dir=log_dir, file_name='train-log')
    config.logger = logger
    config.log_dir = log_dir

    # save shell config and env config
    #shutil.copy(shell_config_path, log_dir)
    with open(log_dir + '/shell_config.json', 'w') as f:
        json.dump(shell_config, f, indent=4)
    shutil.copy(env_config_path, log_dir)

    # create/initialise agent
    logger.info('*****initialising agent {0}'.format(args.curriculum_id))


    ###############################################################################
    # Curriculum setup. TODO: Check how much of this is needed. Remove unnecessary stuff
    num_tasks = len(set(shell_config['curriculum']['task_ids']))
    config.cl_num_tasks = num_tasks
    config.task_ids = shell_config['curriculum']['task_ids']
    if isinstance(shell_config['curriculum']['max_steps'], list):
        config.max_steps = shell_config['curriculum']['max_steps']
    else:
        config.max_steps = [shell_config['curriculum']['max_steps'], ] * len(shell_config['curriculum']['task_ids'])


    ###############################################################################
    # SAC specific hyperparameters and functions
    #config.max_steps = int(1e6)#config.max_steps[0]
    #config.max_steps = None
    config.episode_limit = int(1e6)
    config.replay_fn = lambda: Replay(memory_size=int(1e6), batch_size=64)
    config.discount = 0.99 # Gamma value
    config.random_process_fn = lambda action_dim: GaussianProcess(
        size=(action_dim,), std=LinearSchedule(0.1))
    #config.td3_noise = 0.2
    #config.td3_noise_clip = 0.5
    #config.td3_delay = 2
    config.alpha = 0.1
    config.warm_up = int(1e4)
    config.min_memory_size = int(1e4)
    config.target_network_mix = 5e-3


    ###############################################################################
    # Environment and Network

    # Training task function
    task_fn = lambda log_dir: PendulumWrapper(name, env_config_path, log_dir)
    config.task_fn = lambda: ParallelizedTask(task_fn, config.num_workers, log_dir=config.log_dir, single_process=True)
    
    # Evaluation task function
    eval_task_fn = lambda log_dir: PendulumWrapper(name, env_config_path, log_dir)
    config.eval_task_fn = eval_task_fn

    # Network function
    config.network_fn = lambda state_dim, action_dim: SACNet(
        action_dim,
        actor_body_fn  = lambda: FCBody(state_dim, (400, 300), gate=F.relu),
        critic_body_fn = lambda: FCBody(state_dim+action_dim, (400, 300), gate=F.relu),
        value_body_fn  = lambda: FCBody(state_dim, (400, 300), gate=F.relu),
        actor_opt_fn   = lambda params: torch.optim.Adam(params, lr=1e-3),
        critic_opt_fn  = lambda params: torch.optim.Adam(params, lr=1e-3),
        value_opt_fn   = lambda params: torch.optim.Adam(params, lr=1e-3))
    
    #config.seed = config_seed


    config.use_task_label = False


    ###############################################################################
    # Setup detect module
    #Passing the Detect Module in the config object of the Agent OPTIONAL COULD BE USED BY THE TRAINER ONLY
    config.detect_fn = lambda reference_num, input_dim, num_samples: Detect(reference_num, input_dim, num_samples, one_hot=False, normalized=False)


    ###############################################################################
    # Initialise Manager() for handling shared variables over an internal server
    config.manager = mp.Manager()
    config.seen_tasks = config.manager.dict()
    config.mode = config.manager.Value('b', args.omni)


    ###############################################################################
    # Setup agent module
    agent = SACDetectShell(config)
    config.agent_name = agent.__class__.__name__ + '_{0}'.format(args.curriculum_id)

    # Communication frequency. TODO: This will need a rework if we don't know the length of task encounters.
    config.querying_frequency = (config.max_steps[0]/(config.rollout_length * config.num_workers)) / args.comm_interval


    ###############################################################################
    # Read the reference ip-port pairs to enter a collective. Setup the parallelised
    # communication module.
    addresses, ports = [], []
    reference_file = open(args.reference, 'r')
    lines = reference_file.readlines()
    for line in lines:
        line = line.strip('\n').split(', ')
        addresses.append(line[0])
        ports.append(int(line[1]))

    comm = ParallelCommDetect(agent.get_task_emb_size(), agent.model_mask_dim, config.logger, config.init_port, zip(addresses, ports), config.seen_tasks, config.manager, args.localhost, config.mode, args.dropout, config.emb_dist_threshold)
    
    # Start training
    trainer_learner_eps(agent, comm, args.curriculum_id, config.manager, config.querying_frequency, config.mode)

if __name__ == '__main__':
    mkdir('log')
    set_one_thread()

    mp.set_start_method('fork', force=True)


    parser = argparse.ArgumentParser()
    parser.add_argument('curriculum_id', help='rank: the process id or machine id of the agent', type=int)                   # NOTE: REQUIRED Used to create the logging filepath and select a specific curriculum from the shell configuration JSON.
    parser.add_argument('port', help='port to use for this agent', type=int)                                            # NOTE: REQUIRED Port for the listening server.
    parser.add_argument('--num_agents', help='world: total number of agents', type=int, default=1)                      # Will eventually be deprecated. Currently used to set the communication module initial world size.
    parser.add_argument('--shell_config_path', help='shell config', default='./shell_configs/sac_pendulum_test.json')                       # File path to your chosen shell.json configuration file. Changing the default here might save you some time.
    parser.add_argument('--exp_id', help='id of the experiment. useful for setting '\
        'up structured directory of experiment results/data', default='upz', type=str)                                  # Experiment ID. Can be useful for setting up directories for logging results/data.
    parser.add_argument('--eval', '--e', '-e', help='launches agent in evaluation mode', action='store_true')           # Flag used to start the system in evaluation agent mode. By default the system will run in learning mode.
    parser.add_argument('--omni', '--o', '-o', help='launches agetn in omniscient mode. omniscient agents use the '\
        'gather all querying method to gather all knowledge from the network while still operating as a functional '\
            'learning agent', action='store_true')                                                                      # Flag used to start the system in omniscient agent mode. By default the system will run in learning mode.
                                                                                                                        # Omnisicient agent mode cannot be combined with evaluation mode.

    parser.add_argument('--localhost', '--ls', '-ls', help='used to run DMIU in localhost mode', action='store_true')   # Flag used to start the system using localhost instead of public IP. Can be useful for debugging network related problems.
    parser.add_argument('--shuffle', '--s', '-s', help='randomise the task curriculum', action='store_true')            # Not required. If you want to randomise the order of tasks in the curriculum then you can change to 1
    parser.add_argument('--comm_interval', '--i', '-i', help='integer value indicating the number of communications '\
        'to perform per task', type= int, default=5)                                                                    # Configures the communication interval used to test and take advantage of the lucky agent phenomenon. We found that a value of 5 works well. 
                                                                                                                        # Please do not modify this value unless you know what you're doing as it may cause unexpected results.

    parser.add_argument('--quick_start', '--qs', '-qs', help='use this to take advantage of the quick start method ' \
        'for the reference table', action='store_true')                                                                 # Quick start allows you to use a complete reference table across all your agents, to quickly start localised experimentation. To use this
                                                                                                                        # you will need to simply put every address of all agents you intend to run on your system and use the same file on all your agents at launch.
                                                                                                                        # Then you must use the unique values for your agents using the curriculum_id argument and start each agent sequentially. I.e., for 16 agents you 
                                                                                                                        # should have agents with ids 0 ~ 15. This will make each agent populate its known peers lists with all agents that have been started up to that point.
                                                                                                                        # Was implemented just to make internal testing easier during development.

    parser.add_argument('--device', help='select device 1 for GPU or 0 for CPU. default is GPU', type=int, default=1)   # Used to select device. By default system will try to use the GPU. Currently PyTorch is only compatible with NVIDIA GPUs or Apple M Series processors.
    parser.add_argument('--reference', '--r', '-r', help='reference.csv file path', type=str, default='reference.csv')
    parser.add_argument('--dropout', '--d', '-d', help='Communication dropout parameter', type=float, default=0.0)
    parser.add_argument('--amnesia', '--a', '-a', help='probability of total memory loss', type=float, default = 0.0)
    args = parser.parse_args()

    with open(args.shell_config_path, 'r') as f:
        # Load shell configuration JSON
        shell_config = json.load(f)
        shell_config['curriculum'] = shell_config['agents'][args.curriculum_id]

        # Randomise the curriculum if shuffle raised and not in evaluation mode
        #if args.shuffle and not args.eval: random.shuffle(shell_config['curriculum']['task_ids'])

        # Handle seeds
        shell_config['seed'] = shell_config['seed'][args.curriculum_id]      # Chris
        del shell_config['agents'][args.curriculum_id]


    name = 'Pendulum'
    #name = 'Simulation'

    #sac_baseline(name, args, shell_config) # Without lifelong learning
    sac_detect(name, args, shell_config)    # With lifelong learning + detect module