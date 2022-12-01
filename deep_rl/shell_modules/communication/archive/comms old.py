# -*- coding: utf-8 -*-
'''
_________                                           .__                  __   .__                 
\_   ___ \   ____    _____    _____   __ __   ____  |__|  ____  _____  _/  |_ |__|  ____    ____  
/    \  \/  /  _ \  /     \  /     \ |  |  \ /    \ |  |_/ ___\ \__  \ \   __\|  | /  _ \  /    \ 
\     \____(  <_> )|  Y Y  \|  Y Y  \|  |  /|   |  \|  |\  \___  / __ \_|  |  |  |(  <_> )|   |  \
 \______  / \____/ |__|_|  /|__|_|  /|____/ |___|  /|__| \___  >(____  /|__|  |__| \____/ |___|  /
        \/               \/       \/             \/          \/      \/                        \/ 

                                        TOOL Lateralus: Schism

'''
import os
import copy
import time
import datetime
import numpy as np
import torch
import torch.distributed as dist
import multiprocess as mp
from queue import Empty


######## COMMUNICATION CLASSES
'''
Original communication class. Contains the original implementation of the communication module
fast but at the expense of bandwidth.
'''
class Communication(object):
    META_INF_SZ = 3
    META_INF_IDX_PROC_ID = 0
    META_INF_IDX_MSG_TYPE = 1
    META_INF_IDX_MSG_DATA = 2
    
    # message type (META_INF_IDX_MSG_TYPE) values
    MSG_TYPE_SEND_REQ = 0
    MSG_TYPE_RECV_RESP = 1
    MSG_TYPE_RECV_REQ = 2
    MSG_TYPE_SEND_RESP = 3

    # message data (META_INF_IDX_MSG_DATA) values
    MSG_DATA_NULL = 0 # an empty message
    MSG_DATA_SET = 1

    # number of seconds to sleep/wait
    SLEEP_DURATION = 1

    def __init__(self, agent_id, num_agents, task_label_sz, mask_sz, logger, init_address, init_port):
        super(Communication, self).__init__()
        self.agent_id = agent_id
        self.num_agents = num_agents
        self.task_label_sz = task_label_sz
        self.mask_sz = mask_sz
        self.logger = logger

        if init_address in ['127.0.0.1', 'localhost']:
            os.environ['MASTER_ADDR'] = init_address
            os.environ['MASTER_PORT'] = init_port
            comm_init_str = 'env://'
        else:
            comm_init_str = 'tcp://{0}:{1}'.format(init_address, init_port)

        self.handle_send_recv_req = None
        self.handle_recv_resp = [None, ] * num_agents
        self.handle_send_resp = [None, ] * num_agents

        self.buff_send_recv_req = [torch.ones(Communication.META_INF_SZ + task_label_sz, ) \
            * torch.inf for _ in range(num_agents)]
        self.buff_recv_resp = [torch.ones(Communication.META_INF_SZ + mask_sz, ) * torch.inf \
            for _ in range(num_agents)]
        self.buff_send_resp = [torch.ones(Communication.META_INF_SZ + mask_sz, ) * torch.inf \
            for _ in range(num_agents)]

        logger.info('*****agent {0} / initialising transfer (communication) module'.format(agent_id))
        dist.init_process_group(backend='gloo', init_method=comm_init_str, rank=agent_id, \
            world_size=num_agents, timeout=datetime.timedelta(seconds=30))

    def _null_message(self, msg):
        # check whether message sent denotes or is none.
        if bool(msg[Communication.META_INF_IDX_MSG_DATA] == Communication.MSG_DATA_NULL):
            return True
        else:
            return False

    '''
    method to receive request from other agents (query whether current agent possess knowledge
    about queried task), as well as query (send request to) other agents.
    '''
    def send_receive_request(self, task_label):
        if isinstance(task_label, np.ndarray):
            task_label = torch.tensor(task_label, dtype=torch.float32)
        self.logger.info('send_recv_req, req data: {0}'.format(task_label))
        # from message to send from agent (current node), can be NULL message or a valid
        # request based on given task label
        data = torch.ones_like(self.buff_send_recv_req[0]) * torch.inf
        data[Communication.META_INF_IDX_PROC_ID] = self.agent_id
        data[Communication.META_INF_IDX_MSG_TYPE] = Communication.MSG_TYPE_SEND_REQ
        if task_label is None:
            data[Communication.META_INF_IDX_MSG_DATA] = Communication.MSG_DATA_NULL
        else:
            data[Communication.META_INF_IDX_MSG_DATA] = Communication.MSG_DATA_SET
            data[Communication.META_INF_SZ : ] = task_label # NOTE deepcopy?

        # actual send/receive
        self.handle_send_recv_req = dist.all_gather(tensor_list=self.buff_send_recv_req, \
            tensor=data, async_op=True)
        # briefly wait to see if other agents will send their request
        time.sleep(Communication.SLEEP_DURATION)
        
        # check buffer for incoming requests
        idxs = list(range(len(self.buff_send_recv_req)))
        idxs.remove(self.agent_id)
        ret = []
        for idx in idxs :
            buff = self.buff_send_recv_req[idx]
            if self._null_message(buff):
                ret.append(None)
            else:
                self.logger.info('send_recv_req: request received from agent {0}'.format(idx))
                d = {}
                d['sender_agent_id'] = int(buff[Communication.META_INF_IDX_PROC_ID])
                d['msg_type'] = int(buff[Communication.META_INF_IDX_MSG_TYPE])
                d['msg_data'] = int(buff[Communication.META_INF_IDX_MSG_DATA])
                d['task_label'] = buff[Communication.META_INF_SZ : ]
                ret.append(d)
        return ret

    def send_response(self, requesters):
        self.logger.info('send_resp:')
        for requester in requesters:
            self._send_response(requester)

    def _send_response(self, req_dict):
        requester_agent_id = req_dict['sender_agent_id']
        mask = req_dict['mask']
        buff = self.buff_send_resp[requester_agent_id]
        buff[Communication.META_INF_IDX_PROC_ID] = self.agent_id
        buff[Communication.META_INF_IDX_MSG_TYPE] = Communication.MSG_TYPE_SEND_RESP

        self.logger.info('send_resp: responding to agent {0} query'.format(requester_agent_id))
        self.logger.info('send_resp: mask (response) data type: {0}'.format(type(mask)))

        if mask is None:
            buff[Communication.META_INF_IDX_MSG_DATA] = Communication.MSG_DATA_NULL
            buff[Communication.META_INF_SZ : ] = torch.inf
        else:
            buff[Communication.META_INF_IDX_MSG_DATA] = Communication.MSG_DATA_SET
            buff[Communication.META_INF_SZ : ] = mask # NOTE deepcopy? 

        # actual send
        self.handle_send_resp[requester_agent_id] = dist.isend(tensor=buff, dst=requester_agent_id)
        return

    def receive_response(self):
        self.logger.info('recv_resp:')
        for idx in range(self.num_agents):
            if idx == self.agent_id:
                continue
            if self.handle_recv_resp[idx] is None:
                self.logger.info('recv_resp: set up handle to receive response from agent {0}'.format(idx))
                self.handle_recv_resp[idx] = dist.irecv(tensor=self.buff_recv_resp[idx], src=idx)

        time.sleep(Communication.SLEEP_DURATION)

        # check whether message has been received
        ret = []
        for idx in range(self.num_agents):
            if idx == self.agent_id:
                ret.append(None)
                continue

            msg = self.buff_recv_resp[idx]
            if self._null_message(msg):
                ret.append(None)
                self.logger.info('recv_resp: appending {0} response'.format(None))
            elif msg[Communication.META_INF_IDX_MSG_DATA] == torch.inf:
                ret.append(False)
                self.logger.info('recv_resp: appending False response')
            else:
                mask = copy.deepcopy(msg[Communication.META_INF_SZ : ])
                ret.append(mask)
                self.logger.info('recv_resp: appending {0} response'.format(mask))

            # reset buffer and handle
            self.buff_recv_resp[idx][:] = torch.inf
            self.handle_recv_resp[idx] = None 
        return ret

    def barrier(self):
        dist.barrier()

'''
Revise communication class. Contains the new implementation of the communication module
Improves on the bandwidth efficiency by some margin by reducing the amount of masks
that are communicated over the network, but will likely take longer to complete

Is currently the communication method used in the parallelisation wrapper

TODO: Debug this version of the communication module. Ensure it is working as expected.
probably best to use it in a synchronised setting first before moving to full async mode.
To do this use waits for the handlers etc. The code should work fingers crossed.
'''
class Communication_mp(object):
    # DETECT MODULE CONSTANTS
    # Threshold for embedding/tasklabel distance (similarity)
    THRESHOLD = 0.0

    META_INF_IDX_PROC_ID = 0
    META_INF_IDX_MSG_TYPE = 1
    META_INF_IDX_MSG_DATA = 2

    META_INF_IDX_MSK_RW = 3
    META_INF_IDX_TASK_SZ = 3 # only for the send_recv_request buffer

    META_INF_IDX_DIST = 4
    META_INF_IDX_TASK_SZ_ = 5
    

    META_INF_IDX_MASK_SZ = 6
    
    # message type (META_INF_IDX_MSG_TYPE) values
    MSG_TYPE_SEND_REQ = 0
    MSG_TYPE_RECV_RESP = 1
    MSG_TYPE_RECV_REQ = 2
    MSG_TYPE_SEND_RESP = 3

    # message data (META_INF_IDX_MSG_DATA) values
    MSG_DATA_NULL = 0 # an empty message
    MSG_DATA_TSK = 1
    MSG_DATA_MSK = 2
    MSG_DATA_META = 3

    # number of seconds to sleep/wait
    SLEEP_DURATION = 1

    # Task label size can be replaced with the embedding size.
    def __init__(self, agent_id, num_agents, emb_label_sz, mask_sz, logger, init_address, init_port, queue_agent, queue_comm):
        super(Communication_mp, self).__init__()
        self.agent_id = agent_id
        self.num_agents = num_agents
        self.emb_label_sz = emb_label_sz
        self.mask_sz = mask_sz
        self.logger = logger
        self.queue_agent = queue_agent
        self.queue_comm = queue_comm
        

        if init_address in ['127.0.0.1', 'localhost']:
            os.environ['MASTER_ADDR'] = init_address
            os.environ['MASTER_PORT'] = init_port
            self.comm_init_str = 'env://'
        else:
            self.comm_init_str = 'tcp://{0}:{1}'.format(init_address, init_port)

        self.handle_send_recv_req = None
        self.handle_recv_resp = [None, ] * num_agents
        self.handle_send_resp = [None, ] * num_agents

        self.buff_send_recv_req = [torch.ones(Communication_mp.META_INF_IDX_TASK_SZ + emb_label_sz, ) \
            * torch.inf for _ in range(num_agents)]

        self.buff_send_recv_meta = [torch.ones(Communication_mp.META_INF_IDX_TASK_SZ_ + emb_label_sz, ) \
            * torch.inf for _ in range(num_agents)]

        self.buff_recv_resp_task = [torch.ones(Communication_mp.META_INF_IDX_TASK_SZ_ + emb_label_sz, ) * torch.inf \
            for _ in range(num_agents)]
        self.buff_send_resp_task = [torch.ones(Communication_mp.META_INF_IDX_TASK_SZ_ + emb_label_sz, ) * torch.inf \
            for _ in range(num_agents)]

        self.buff_recv_resp = [torch.ones(Communication_mp.META_INF_IDX_MASK_SZ + mask_sz, ) * torch.inf \
            for _ in range(num_agents)]
        self.buff_send_resp = [torch.ones(Communication_mp.META_INF_IDX_MASK_SZ + mask_sz, ) * torch.inf \
            for _ in range(num_agents)]

        self.buff_send_recv_msk_req = torch.ones(Communication_mp.META_INF_IDX_TASK_SZ + emb_label_sz, ) * torch.inf

    def init_dist(self):
        '''
        Initialise the process group for torch.
        '''
        self.logger.info('*****agent {0} / initialising transfer (communication) module'.format(self.agent_id))
        dist.init_process_group(backend='gloo', init_method=self.comm_init_str, rank=self.agent_id, \
            world_size=self.num_agents, timeout=datetime.timedelta(seconds=30))

    def _null_message(self, msg):
        # check whether message sent denotes or is none.
        if bool(msg[Communication.META_INF_IDX_MSG_DATA] == Communication.MSG_DATA_NULL):
            return True
        else:
            return False

    def send_receive_request(self, emb_label):
        '''
        Setup up the communication buffer with the necessary flags and data.
        Send buffer to all agents in the network.
        Then listen for any requests from other agents and unpack the buffer.
        Return the data to the main process for use in the next process.

        Task label can be interchangeable with the task embedding. Just needs to be a numpy 
        array to be compatible.

        # Data buffer for communication looks like this
        #   task label: [0, 0, 1]
        #   [agentid, communication type, is data or null flag, 0, 0, 1]
        '''
        #### TO DO: Switch task labels with embeddings?
        # or with new idea task labels are made for each embedding cluster?

        if isinstance(emb_label, np.ndarray):
            emb_label = torch.tensor(emb_label, dtype=torch.float32)

            
        self.logger.info('send_recv_req, req data: {0}'.format(emb_label))
        # from message to send from agent (current node), can be NULL message or a valid
        # request based on given task label
        data = torch.ones_like(self.buff_send_recv_req[0]) * torch.inf

        # Send the task label or embedding to the other agents.
        data[Communication_mp.META_INF_IDX_PROC_ID] = self.agent_id
        data[Communication_mp.META_INF_IDX_MSG_TYPE] = Communication_mp.MSG_TYPE_SEND_REQ

        if emb_label is None:
            data[Communication_mp.META_INF_IDX_MSG_DATA] = Communication_mp.MSG_DATA_NULL
        else:
            data[Communication_mp.META_INF_IDX_MSG_DATA] = Communication_mp.MSG_DATA_TSK
            data[Communication_mp.META_INF_IDX_TASK_SZ : ] = emb_label # NOTE deepcopy?


        # actual send/receive
        self.handle_send_recv_req = dist.all_gather(tensor_list=self.buff_send_recv_req, \
            tensor=data, async_op=True)

        self.handle_send_recv_req.wait()


        # briefly wait to see if other agents will send their request
        #time.sleep(Communication_mp.SLEEP_DURATION)
        
        # check buffer for incoming requests
        idxs = list(range(len(self.buff_send_recv_req)))
        idxs.remove(self.agent_id)
        ret = []
        for idx in idxs :
            buff = self.buff_send_recv_req[idx]

            if self._null_message(buff):
                d = {}
                d['sender_agent_id'] = int(buff[Communication_mp.META_INF_IDX_PROC_ID])
                d['msg_data'] = None
                ret.append(d)
            else:
                self.logger.info('send_recv_req: request received from agent {0}'.format(idx))
                d = {}
                d['sender_agent_id'] = int(buff[Communication_mp.META_INF_IDX_PROC_ID])
                d['msg_type'] = int(buff[Communication_mp.META_INF_IDX_MSG_TYPE])
                d['msg_data'] = int(buff[Communication_mp.META_INF_IDX_MSG_DATA])
                d['task_label'] = buff[Communication_mp.META_INF_IDX_TASK_SZ : ]
                ret.append(d)
        return ret

    def send_meta_response(self, requesters):
        '''
        Send response for each requester agent.
        '''
        self.logger.info('send_resp:')
        for requester in requesters:
            if requester is None: continue
            self._send_meta_response(requester)

    def _send_meta_response(self, req_dict):
        '''
        Sends either the mask or meta data to another agent.
        '''
        self.logger.info('send_resp {0}'.format(req_dict))
        dst_agent_id = req_dict['sender_agent_id']

        # Get the mask, mask reward and embedding/tasklabel
        mask_reward = req_dict['mask_reward']
        emb_label = req_dict['resp_task_label']
        distance = req_dict['dist'].item()

        print(mask_reward, emb_label, distance)
        print(type(mask_reward), type(emb_label), type(distance))

        if isinstance(emb_label, np.ndarray):
            emb_label = torch.tensor(emb_label, dtype=torch.float32)


        buff = self.buff_send_resp_task[dst_agent_id]
        buff[Communication_mp.META_INF_IDX_PROC_ID] = self.agent_id
        buff[Communication_mp.META_INF_IDX_MSG_TYPE] = Communication_mp.MSG_TYPE_SEND_RESP

        self.logger.info('send_resp: responding to agent {0} query'.format(dst_agent_id))
        #self.logger.info('send_resp: mask (response) data type: {0}'.format(type(mask)))

        # If mask is none then send back torch.inf
        # otherwise send mask
        if mask_reward is None:
            buff[Communication_mp.META_INF_IDX_MSG_DATA] = Communication_mp.MSG_DATA_NULL

        else:
            # if the mask is none but there is a mask reward, then overwrite the buffer with
            # the meta data. Otherwise don't do anything.
            buff[Communication_mp.META_INF_IDX_MSG_DATA] = Communication_mp.MSG_DATA_META
            buff[Communication_mp.META_INF_IDX_MSK_RW] = mask_reward
            buff[Communication_mp.META_INF_IDX_DIST] = distance
            buff[Communication_mp.META_INF_IDX_TASK_SZ_ :] = emb_label

        print('SEND: ', buff, flush=True)
        # actual send
        self.handle_send_resp[dst_agent_id] = dist.isend(tensor=buff, dst=dst_agent_id)
        self.handle_send_resp[dst_agent_id].wait()
        return

    def receive_meta_response(self):
        '''
        Receives the response from all in the network agents.
        '''
        self.logger.info('recv_resp:')
        for idx in range(self.num_agents):
            if idx == self.agent_id:
                continue
            if self.handle_recv_resp[idx] is None:
                self.logger.info('recv_resp: set up handle to receive response from agent {0}'.format(idx))
                self.handle_recv_resp[idx] = dist.irecv(tensor=self.buff_recv_resp[idx], src=idx)
                self.handle_recv_resp[idx].wait()

        #time.sleep(Communication_mp.SLEEP_DURATION)

        # check whether message has been received
        ret = list()
        for idx in range(self.num_agents):
            if idx == self.agent_id:
                ret.append(None)
                continue

            msg = self.buff_recv_resp_task[idx]
            print(msg)
            if self._null_message(msg):
                ret.append(None)
                self.logger.info('recv_resp: appending {0} response'.format(None))
            
            elif msg[Communication.META_INF_IDX_MSG_DATA] == torch.inf:
                ret.append(False)
                self.logger.info('recv_resp: appending False response')

            elif msg[Communication_mp.META_INF_IDX_MSG_DATA] == Communication_mp.MSG_DATA_META:
                d = {}
                d['agent_id'] = copy.deepcopy(msg[Communication_mp.META_INF_IDX_PROC_ID])
                d['mask_reward'] = copy.deepcopy(msg[Communication_mp.META_INF_IDX_MSK_RW])
                d['dist'] = copy.deepcopy(msg[Communication_mp.META_INF_IDX_DIST])
                d['emb_label'] = copy.deepcopy(msg[Communication_mp.META_INF_IDX_TASK_SZ_ :])
                ret.append(d)

                # Change this at some point to take the original data and not string
                self.logger.info('recv_resp: appending metadata response from agent {0}'. format(ret['agent_id']))

            else:
                pass



            # code for receive response for the mask    
            #elif msg[Communication.META_INF_IDX_MSG_DATA] == MSG_DATA_MSK:
            #    ret['agent_id'] = copy.deepcopy(msg[Communication.META_INF_IDX_PROC_ID])
            #    ret['mask'] = copy.deepcopy(msg[Communication.META_INF_IDX_MSK_SZ : ])
            #    results.append(ret)

                # Change this at some point to take the original data and not string
            #    self.logger.info('recv_resp: appending {0} response'.format('MASK'))

            # reset buffer and handle
            self.buff_recv_resp[idx][:] = torch.inf
            self.handle_recv_resp[idx] = None 
        return results

    def barrier(self):
        dist.barrier()

    def send_mask_request(self, msk_requests, expecting):
        # TODO: Merge this function with the other send_receive_mask function.
        '''
        Sends a request to the top three agents for masks using the their embeddings.
        Checks for similar requests.
        '''

        # For each 
        for agent_id, emb_label in msk_requests.items():
            # Convert embedding label to tensor
            if isinstance(emb_label, np.ndarray):
                emb_label = torch.tensor(emb_label, dtype=torch.float32)

            # Initialise a buffer for one agent embedding/tasklabel
            data = torch.ones_like(self.buff_send_recv_req[0]) * torch.inf

            # Populate the tensor with necessary data
            data[Communication_mp.META_INF_IDX_PROC_ID] = self.agent_id
            data[Communication_mp.META_INF_IDX_MSG_TYPE] = Communication_mp.MSG_TYPE_SEND_REQ
            
            if emb_label is None:
                # If emb_label is none it means we reject the agent
                data[Communication_mp.META_INF_IDX_MSG_DATA] = Communication_mp.MSG_DATA_NULL
                    
            else:
                # Otherwise we want the agent's mask
                data[Communication_mp.META_INF_IDX_MSG_DATA] = Communication_mp.MSG_DATA_TSK
                data[Communication_mp.META_INF_TASK_SZ : ] = emb_label # NOTE deepcopy?

            # Send out the mask request or rejection to each agent that sent metadata
            self.handle_send_recv_req = dist.isend(tensor=data, dst=agent_id)
            self.handle_send_recv_req.wait()
        
    def receive_mask_requests(self, expecting):
        # Check for mask requests from other agents if expecting any requests
        ret = []
        if expecting:
            # If expecting a request for a mask, check for each expected agent id
            for idx in expecting:
                data = torch.ones_like(self.buff_send_recv_req[0]) * torch.inf
                self.handle_send_recv_req = dist.irecv(tensor=data, src=idx)
                time.sleep(Communication_mp.SLEEP_DURATION)

                # If response was null message then this agent has been rejected.
                # If so, remove the idx from expecting and check the next id.
                # if no more idxs then return the list of dictionaries. (can be empty)
                if self._null_message(data):
                    expecting.remove(idx)

                # If not rejected then we need to send the mask to the requester
                else:
                    d = {}
                    d['requester_agent_id'] = int(buff[Communication_mp.META_INF_IDX_PROC_ID])
                    d['msg_type'] = int(buff[Communication_mp.META_INF_IDX_MSG_TYPE])
                    d['msg_data'] = int(buff[Communication_mp.META_INF_IDX_MSG_DATA])
                    d['task_label'] = buff[Communication_mp.META_INF_IDX_TASK_SZ : ]
                    ret.append(d)

        # Return a list of dictionaries for each agent that wants a mask
        return expecting, ret

    def send_mask_response(self, dst_agent_id, mask):
        buff = torch.ones_like(self.buff_send_resp[0]) * torch.inf

        buff[Communication_mp.META_INF_IDX_PROC_ID] = self.agent_id
        buff[Communication_mp.META_INF_IDX_MSG_TYPE] = Communication_mp.MSG_TYPE_SEND_RESP

        if mask is None:
            buff[Communication_mp.META_INF_IDX_MSG_DATA] = Communication_mp.MSG_DATA_NULL
            buff[Communication_mp.META_INF_SZ : ] = torch.inf

        else:
            buff[Communication_mp.META_INF_IDX_MSG_DATA] = Communication_mp.MSG_DATA_MSK
            buff[Communication_mp.META_INF_SZ : ] = mask # NOTE deepcopy?

        # Send the mask to the destination agent id
        req = dist.isend(tensor=buff, dst=dst_agent_id)
        return

    def receive_mask_response(self, best_agent_id):
        buff = torch.ones_like(self.buff_send_resp[0]) * torch.inf

        # Receive the buffer containing the mask. Wait for 10 seconds to make sure mask is received
        req = dist.irecv(tensor=buff, src=best_agent_id)
        time.sleep(Communication_mp.SLEEP_DURATION)

        # If the buffer was a null response (which it shouldn't be)
        # meep
        if self._null_message(buff):
            # Shouldn't reach this hopefully :^)
            return None

        # otherwise return the mask
        elif buff[Communication_mp.META_INF_IDX_MSG_DATA] == Communication_mp.MSG_DATA_MSK:
            if buff[Communication_mp.META_INF_IDX_PROC_ID] == best_agent_id:
                return buff[Communication_mp.META_INF_IDX_MASK_SZ : ]

    def fetch_all(self):
        '''
        Copy the code 
        '''

    def sync_gather_meta(self, agents):
        print('Agents: ', agents)
        new_group = dist.new_group(ranks=agents, backend='gloo')

        data = torch.ones_like(self.buff_send_recv_meta[0]) * torch.inf

        data[Communication_mp.META_INF_IDX_PROC_ID] = self.agent_id
        data[Communication_mp.META_INF_IDX_MSG_TYPE] = Communication_mp.MSG_TYPE_SEND_RESP

        # If mask is none then send back torch.inf
        # otherwise send mask
        if mask_reward is None:
            data[Communication_mp.META_INF_IDX_MSG_DATA] = Communication_mp.MSG_DATA_NULL

        else:
            # if the mask is none but there is a mask reward, then overwrite the buffer with
            # the meta data. Otherwise don't do anything.
            data[Communication_mp.META_INF_IDX_MSG_DATA] = Communication_mp.MSG_DATA_META
            data[Communication_mp.META_INF_IDX_MSK_RW] = mask_reward
            data[Communication_mp.META_INF_IDX_DIST] = distance
            data[Communication_mp.META_INF_IDX_TASK_SZ_ :] = emb_label

        req = dist.all_gather(tensor_list=self.buff_send_recv_meta, tensor=data, async_op=True)
        req.wait()

        # check buffer for incoming requests
        idxs = list(range(len(self.buff_send_recv_meta)))
        idxs.remove(self.agent_id)
        ret = []
        for idx in idxs :
            buff = self.buff_send_recv_meta[idx]

            if self._null_message(buff):
                ret.append(None)
            else:
                self.logger.info('send_recv_req: request received from agent {0}'.format(idx))
                d = {}
                d['agent_id'] = copy.deepcopy(msg[Communication_mp.META_INF_IDX_PROC_ID])
                d['mask_reward'] = copy.deepcopy(msg[Communication_mp.META_INF_IDX_MSK_RW])
                d['dist'] = copy.deepcopy(msg[Communication_mp.META_INF_IDX_DIST])
                d['emb_label'] = copy.deepcopy(msg[Communication_mp.META_INF_IDX_TASK_SZ_ :])
                ret.append(d)
        return ret

    def broadcast_mask(self, src, agents):
        new_group = dist.new_group(ranks=agents, backend='gloo')
        buff = torch.ones_like(self.buff_send_resp[0]) * torch.inf

        buff[Communication_mp.META_INF_IDX_PROC_ID] = self.agent_id
        buff[Communication_mp.META_INF_IDX_MSG_TYPE] = Communication_mp.MSG_TYPE_SEND_RESP

        if mask is None:
            buff[Communication_mp.META_INF_IDX_MSG_DATA] = Communication_mp.MSG_DATA_NULL
            buff[Communication_mp.META_INF_SZ : ] = torch.inf

        else:
            buff[Communication_mp.META_INF_IDX_MSG_DATA] = Communication_mp.MSG_DATA_MSK
            buff[Communication_mp.META_INF_SZ : ] = mask # NOTE deepcopy?

        # Send the mask to the destination agent id
        req = dist.broadcast(tensor=buff, src=src, group=new_group, async_op=True)
        req.wait()

        return buff

    def broadcast_label(self, label):
        #req = dist.broadcast(tensor=label, src=0, )

        #return label
        pass

    def gather_masks(self, mask):
        #gather_list = [torch.ones(2 + mask_sz, ) * torch.inf for _ in range(num_agents)]

        #print(gather_list)
        #tensor = gather_list[0]
        #print(tensor)

        #req = dist.gather(tensor=tensor, gather_list=gather_list, dst=0, group=None, async_op=True)
        #req.wait()

        #if self.agent_id == 0:
        #    ret = []
        #    for idx in len(gather_list):
        #        gather_list[idx]
        #    return gather_list
        pass

    def comm_loop(self, event):
        while True:
            # Alternative is fetchall but it hasn't been implemented yet
            #mode = 'ondemand'

            #if mode == 'ondemand':
            ####################### COMMUNICATION STEP ONE #######################
            # Every agent lets every other agent know what they are working on in this cycle
            # at this point in time.
            
            # To my understanding queue.get() is blocking until item is available from queue.
            # Unsure how this will function in the edge case that the task is constantly changing
            # at a very high frequency. The agent will send out requeusts for useless masks
            # and get backlogged on requests potentially.

            # Wait to receive a tasklabel from the agent to query the network for
            other_agents_request = None
            #try:
            #    print("HERE")
            #    msg = queue_comm.get_nowait()
            #    print("HERE")
            #    other_agents_request = send_receive_request(msg)
            #    del msg

            #except Empty:
            #    pass


            if other_agents_request is not None:

                # send out broadcast request to all other agents for task label

                # gather all masks and rewards pairs for task label

                '''
                # SYCHRONISE LEARNING
                # Iterate through the request
                # Gather the agent ids of similar task labels
                # create a process sub group (new_group) for the agent ids, including self id
                # all agents all_gather on subgroup their reward for the task
                # best agent broadcasts to the subgroup the mask that they have and other agents
                #       will distill the mask to their network and continue training.

                # This all happens every iteration. (Unsure of the communication bandwidth requirements)

                # Go through the requests and take note of what agent is doing what task
                # We will know when an agent is still doing the same task if the update is None
                # otherwise the update will be a new task label request
                for req in other_agents_request:
                    if req['msg_data'] is not None:
                        track_tasks[req['sender_agent_id']] = req['task_label'].detach().cpu().numpy()

                print('TRACK TASKS: ', track_tasks)

                responses = list()
                sync_agents = list()
                for key, value in track_tasks.items():
                    if key == agent_id: continue
                    if key == None: continue

                    # Change to distance calculation later
                    if np.array_equal(value, shell_tasks[0]['task_label']):
                        sync_agents.append(key)

                if sync_agents:
                    sync_agents.append(agent_id)
                    responses = self.sync_gather_meta(sync_agents)


                print('RESPONSES: ', responses)
                if responses:
                    print("SENDING MASKS")
                    # Check if responses reward is greater than this agents reward
                    sorted_responses = sorted(responses, key=lambda d: d['mask_reward'])

                    # If the first 
                    if sorted_responses[0]['sender_agent_id'] == agent_id:
                        # If the best agent is this one then send mask to all other agents
                        mask = agent.label_to_mask(shell_tasks[0]['task_label'])
                        for i in sync_agents():
                            if i == agent_id: continue
                            self.send_mask_response(i, mask)
                    else:
                        # except a mask from the best agent
                        best_agent = sorted_responses[0]['sender_agent_id']
                        mask = self.receive_mask_response(best_agent)
                        agent.distil_task_knowledge_single(mask)'''


                ####################### COMMUNICATION STEP TWO #######################
                # Respond to received queries with metadata.
                # Meta data contains the reward for the similar task, distance and the similar 
                # tasklabel/embedding.

                # Go through each request from the network of agents
                responses = []
                for req in other_agents_request:
                    # If the req is none, which it usually will be, just skip.
                    if req['msg_data'] is None: continue
                    
                    # If the message is None then the agent has already requested and begun
                    # working the task. So there is no need to update this agents task tracking dictionary
                    # If the other agents do task change then they will do a fresh request. This will make the
                    # request not None and this agent can update their task track.
                    track_tasks[req['sender_agent_id']] = req['task_label']

                    # If this agent has not learned anything yet, then respond with nothing
                    if not mask_rewards_dict:
                        continue

                    # Otherwise send what it knows if appropriate

                    # Compute the embedding distance. Maybe there is a better way to achieve this
                    req_label_as_np = req['task_label'].detach().cpu().numpy()
                    print('Requested label from agent {0}: {1}'.format(req['sender_agent_id'], req_label_as_np))
                    print('Current knowledge base for this agent: ', mask_rewards_dict)

                    # For each embedding/tasklabel reward pair, calculate the distance to the
                    # requested embedding/tasklabel.
                    # If the distance is below the THRESHOLD then send it back
                    # otherwise send nothing back.
                    for key, val in mask_rewards_dict.items():
                        print(np.asarray(key), val)
                        dist = np.sum(abs(np.subtract(req_label_as_np, np.asarray(key))))
                        print(dist)

                        # If the distance of the knowledge is below THRESHOLD then the embedding/tasklabels
                        # are similar enough to send.
                        if dist <= Communication_mp.THRESHOLD:
                            print('Distance is good. Adding to dictionary')
                            # Send the reward, distance and the embedding/tasklabel from this agent
                            # note this will likely be different to the requested embedding/tasklabel
                            # We send this agents embedding/tasklabel so that the requester can send
                            # a mask request if required.
                            req['mask_reward'] = val
                            req['dist'] = dist
                            req['resp_task_label'] = np.asarray(key)

                            # Append the requester agent id. We use this to listen for a mask request
                            # or to get rejected.
                            expecting.append(req['sender_agent_id'])
                            print(expecting)
                            
                            # Append the response to the requests to the 
                            responses.append(req)

                        # Otherwise send nothing and do nothing
                        else:
                            responses.append(None)

                # Do a check and send out the responses to requests for knowledge
                if len(responses) > 0:
                    # Send out the metadata for the embedding/tasklabel query
                    self.send_meta_response(responses)


                ####################### COMMUNICATION STEP THREE #######################
                # Receive metadata response from other agents for a embedding/tasklabel request from 
                # this agent.
                start_time = time.time()
                
                send_msk_request = dict()


                received_mask = None
                # Listen for any responses from other agents (containing the metadata)
                # if the agent earlier sent a request, check whether response has been sent.
                if any(await_response):
                    logger.info('awaiting response: {0}'.format(await_response))
                    results = self.receive_meta_response()

                    print('METADATA RESPONSE', results)

                    # Sort received meta data by smallest distance (primary) and highest reward (secondary),
                    # using full bidirectional multikey sorting (fancy words for such a simple concept)
                    results = sorted(results, key=lambda d: (d['dist'], -d['mask_reward']))


                    # Iterate through the await_response list. Upon task change this is an array
                    # [True,] * num_agents
                    selected = False
                    for idx in range(len(await_response)):
                        # Do some checks to remove to useless results
                        if await_response[idx] is False: continue
                        if results[idx] is False: continue
                        elif results[idx] is None: await_response[idx] = False

                        # Otherwise unpack the metadata
                        else:
                            recv_agent_id = results[idx]['agent_id']
                            recv_msk_rw = results[idx]['mask_reward']
                            recv_label = results[idx]['emb_label']
                            recv_dist = results[idx]['dist']

                            # If the received distance is below the THRESHOLD and the agent
                            # hasn't selected a best agent yet then select this response
                            if recv_dist <= Communication_mp.THRESHOLD and selected == False:
                                # Add the agent id and embedding/tasklabel from the agent
                                # to a dictionary to send requests/rejections out to.
                                send_msk_request[recv_agent_id] = recv_label

                                # Make a note of the best agent id in memory of this agent
                                # We will use this later to check the response from the best agent
                                best_agent_id = recv_agent_id

                                # Make the selected flag true so we don't pick anymore to send
                                selected = True

                            # If best selected or doesn't meet criteria, then send rejection
                            # i.e., None
                            else:
                                send_msk_request[recv_agent_id] = None

                            # We have checked the response so set it to False until the next task change
                            # and request loop begins
                            await_response[idx] = False

                    # Need to fix this logging message
                    logger.info('meta data received from other agents')

                print('STEP THREE ', time.time() - start_time)

                ####################### COMMUNICATION STEP FOUR #######################
                # Send a response back to each agent that sent this agent metadata. Tell them to either
                # send mask or move on.

                start_time = time.time()

                msk_requests = None
                if send_msk_request:
                    self.send_mask_request(send_msk_request)

                # Also receive the same response from other agents. If other agents want a mask from this
                # agent, then msk_requests will be populated with a dictionary for each request.
                if expecting:
                    expecting, msk_requests = self.receive_mask_requests(expecting)

                # Now the agent needs to send a mask to each agent in the msk_requests list
                # if it is not empty.
                if msk_requests:
                    # Iterate through the requests
                    for req in msk_requests:
                        # Send a mask to the requesting agent
                        agent_id = req['requester_agent_id']
                        mask = agent.label_to_mask(req['task_label'])
                        self.send_mask_response((agent_id, mask))

                # Expecting a response from the best agent id
                if best_agent_id:
                    # We want to get the mask from the best agent
                    received_mask = self.receive_mask_response(best_agent_id)

                    # Reset the best agent id for the next request
                    best_agent_id = None

                    print('STEP FOUR ', time.time() - start_time)

                # Take the singular best mask and apply it to the agent network
                # A modified version of the original code. Found in deep_rl/shell_modules/mmn/ssmask_utils.py
                return (received_mask, track_tasks, mask_rewards_dict, expecting, best_agent_id, await_response)

                #elif mode == 'fetchall':
                #    raise ValueError('{0} communication mode has not been implemented!'.format(mode))

                #else:
                #    raise ValueError('{0} communication mode has not been implemented!'.format(mode))

    def run(self, msg):
        if msg is not None:
            p = mp.Process(target=self.comm_loop, args=(msg,))
            p.start()
            p.join()

"""
'''
Communication Module for the revised communication algortihm with added communication methods
for synchronised learning.
'''
class Communication_mp_v2(object):
    META_INF_IDX_PROC_ID = 0
    META_INF_IDX_MSG_TYPE = 1
    META_INF_IDX_MSG_DATA = 2

    META_INF_IDX_MSK_RW = 3
    META_INF_IDX_TASK_SZ = 3 # only for the send_recv_request buffer

    META_INF_IDX_DIST = 4
    META_INF_IDX_TASK_SZ_ = 5
    

    META_INF_IDX_MASK_SZ = 6
    
    # message type (META_INF_IDX_MSG_TYPE) values
    MSG_TYPE_SEND_REQ = 0
    MSG_TYPE_RECV_RESP = 1
    MSG_TYPE_RECV_REQ = 2
    MSG_TYPE_SEND_RESP = 3

    # message data (META_INF_IDX_MSG_DATA) values
    MSG_DATA_NULL = 0 # an empty message
    MSG_DATA_TSK = 1
    MSG_DATA_MSK = 2
    MSG_DATA_META = 3

    # number of seconds to sleep/wait
    SLEEP_DURATION = 1

    # Task label size can be replaced with the embedding size.
    def __init__(self, agent_id, num_agents, emb_label_sz, mask_sz, logger, init_address, init_port):
        super(Communication_mp, self).__init__()
        self.agent_id = agent_id
        self.num_agents = num_agents
        self.emb_label_sz = emb_label_sz
        self.mask_sz = mask_sz
        self.logger = logger
        

        if init_address in ['127.0.0.1', 'localhost']:
            os.environ['MASTER_ADDR'] = init_address
            os.environ['MASTER_PORT'] = init_port
            self.comm_init_str = 'env://'
        else:
            self.comm_init_str = 'tcp://{0}:{1}'.format(init_address, init_port)

        self.handle_send_recv_req = None
        self.handle_recv_resp = [None, ] * num_agents
        self.handle_send_resp = [None, ] * num_agents

        self.buff_send_recv_req = [torch.ones(Communication_mp.META_INF_IDX_TASK_SZ + emb_label_sz, ) \
            * torch.inf for _ in range(num_agents)]

        self.buff_recv_resp = [torch.ones(Communication_mp.META_INF_IDX_MASK_SZ + mask_sz, ) * torch.inf \
            for _ in range(num_agents)]
        self.buff_send_resp = [torch.ones(Communication_mp.META_INF_IDX_MASK_SZ + mask_sz, ) * torch.inf \
            for _ in range(num_agents)]

        self.buff_send_recv_msk_req = torch.ones(Communication_mp.META_INF_IDX_TASK_SZ + emb_label_sz, ) * torch.inf

    def init_dist(self):
        '''
        Initialise the process group for torch.
        '''
        self.logger.info('*****agent {0} / initialising transfer (communication) module'.format(self.agent_id))
        dist.init_process_group(backend='gloo', init_method=self.comm_init_str, rank=self.agent_id, \
            world_size=self.num_agents, timeout=datetime.timedelta(seconds=30))

    def _null_message(self, msg):
        # check whether message sent denotes or is none.
        if bool(msg[Communication.META_INF_IDX_MSG_DATA] == Communication.MSG_DATA_NULL):
            return True
        else:
            return False
    '''
    method to receive request from other agents (query whether current agent possess knowledge
    about queried task), as well as query (send request to) other agents.
    '''
    def send_receive_labels(self, label):
        '''
        Setup up the communication buffer with the necessary flags and data.
        Send buffer to all agents in the network.
        Then listen for any requests from other agents and unpack the buffer.
        Return the data to the main process for use in the next process.

        Task label can be interchangeable with the task embedding. Just needs to be a numpy 
        array to be compatible.

        # Data buffer for communication looks like this
        #   task label: [0, 0, 1]
        #   [agentid, communication type, is data or null flag, 0, 0, 1]
        '''
        #### TO DO: Switch task labels with embeddings?
        # or with new idea task labels are made for each embedding cluster?

        if isinstance(label, np.ndarray):
            label = torch.tensor(label, dtype=torch.float32)

            
        self.logger.info('send_recv_label, meta data: {0}'.format(label))
        # from message to send from agent (current node), can be NULL message or a valid
        # request based on given task label
        data = torch.ones_like(self.buff_send_recv_req[0]) * torch.inf

        # Send the task label or embedding to the other agents.
        data[Communication_mp.META_INF_IDX_PROC_ID] = self.agent_id
        data[Communication_mp.META_INF_IDX_MSG_TYPE] = Communication_mp.MSG_TYPE_SEND_REQ
        data[Communication_mp.META_INF_IDX_MSG_DATA] = Communication_mp.MSG_DATA_TSK
        data[Communication_mp.META_INF_IDX_TASK_SZ : ] = label # NOTE deepcopy?


        # actual send/receive
        self.handle_send_recv_req = dist.all_gather(tensor_list=self.buff_send_recv_req, \
            tensor=data, async_op=True)

        self.handle_send_recv_req.wait()


        # briefly wait to see if other agents will send their request
        #time.sleep(Communication_mp.SLEEP_DURATION)
        
        # check buffer for incoming requests
        idxs = list(range(len(self.buff_send_recv_req)))
        idxs.remove(self.agent_id)
        ret = []
        for idx in idxs :
            buff = self.buff_send_recv_req[idx]
            self.logger.info('send_recv_req: request received from agent {0}'.format(idx))
            d = {}
            d['sender_agent_id'] = int(buff[Communication_mp.META_INF_IDX_PROC_ID])
            d['msg_type'] = int(buff[Communication_mp.META_INF_IDX_MSG_TYPE])
            d['msg_data'] = int(buff[Communication_mp.META_INF_IDX_MSG_DATA])
            d['label'] = buff[Communication_mp.META_INF_IDX_TASK_SZ : ]
            ret.append(d)
        return ret

    def send_meta_request(self, req_dict):
        self.logger.info('send_req: requesting metadata from agent {0}'.format(agent_id))

        agent_id = req['agent_id']
        label = req['label']
        if isinstance(label, np.ndarray):
            label = torch.tensor(label, dtype=torch.float32)

        buff = self.buff_send_resp[dst_agent_id]
        buff[Communication_mp_v2.META_INF_IDX_PROC_ID] = self.agent_id
        buff[Communication_mp_v2.META_INF_IDX_MSG_TYPE] = Communication_mp_v2.MSG_TYPE_SEND_REQ
        buff[Communication_mp_v2.META_INF_IDX_MSG_DATA] = Communication_mp_v2.MSG_DATA_META
        buff[Communication_mp_v2.META_INF_IDX_TASK_SZ : ] = label

        self.handle_send_req[agent_id] = dist.isend(tensor=buff, dst=agent_id)
        return
    
    def recv_meta_request(self, expecting):
        ret = []
        for idx in expecting:
            data = torch.ones_like(self.buff_send_recv_req[0]) * torch.inf
            recv = dist.irecv(tensor=data, src=idx)
            time.sleep(Communication_mp_v2.SLEEP_DURATION)

            


    def send_meta_response(self, requesters):
        '''
        Send response for each requester agent.
        '''
        self.logger.info('send_resp:')
        for requester in requesters:
            self._send_meta_response(requester)

    def _send_meta_response(self, req_dict):
        '''
        Sends either the mask or meta data to another agent.
        '''
        dst_agent_id = req_dict['sender_agent_id']

        # Get the mask, mask reward and embedding/tasklabel
        mask_reward = req_dict['mask_reward']
        emb_label = req_dict['resp_task_label']
        distance = req_dict['dist']

        print(type(mask_reward), type(emb_label), type(distance))

        if isinstance(emb_label, np.ndarray):
            emb_label = torch.tensor(emb_label, dtype=torch.float32)


        buff = self.buff_send_resp[dst_agent_id]
        buff[Communication_mp.META_INF_IDX_PROC_ID] = self.agent_id
        buff[Communication_mp.META_INF_IDX_MSG_TYPE] = Communication_mp.MSG_TYPE_SEND_RESP

        self.logger.info('send_resp: responding to agent {0} query'.format(dst_agent_id))
        #self.logger.info('send_resp: mask (response) data type: {0}'.format(type(mask)))

        # If mask is none then send back torch.inf
        # otherwise send mask
        if mask_reward is None:
            buff[Communication_mp.META_INF_IDX_MSG_DATA] = Communication_mp.MSG_DATA_NULL

        else:
            # if the mask is none but there is a mask reward, then overwrite the buffer with
            # the meta data. Otherwise don't do anything.
            buff[Communication_mp.META_INF_IDX_MSG_DATA] = Communication_mp.MSG_DATA_META
            buff[Communication_mp.META_INF_IDX_MSK_RW] = mask_reward
            buff[Communication_mp.META_INF_IDX_DIST] = distance
            buff[Communication_mp.META_INF_IDX_TASK_SZ_ :] = emb_label

        # actual send
        self.handle_send_resp[dst_agent_id] = dist.isend(tensor=buff, dst=dst_agent_id)
        return

    def receive_meta_response(self):
        '''
        Receives the response from all in the network agents.
        '''
        self.logger.info('recv_resp:')
        for idx in range(self.num_agents):
            if idx == self.agent_id:
                continue
            if self.handle_recv_resp[idx] is None:
                self.logger.info('recv_resp: set up handle to receive response from agent {0}'.format(idx))
                self.handle_recv_resp[idx] = dist.irecv(tensor=self.buff_recv_resp[idx], src=idx)
                self.handle_recv_resp[idx].wait()

        #time.sleep(Communication_mp.SLEEP_DURATION)

        # check whether message has been received
        results = list()
        ret = dict()
        for idx in range(self.num_agents):
            if idx == self.agent_id:
                results.append(None)
                continue

            msg = self.buff_recv_resp[idx]
            if self._null_message(msg):
                results.append(None)
                self.logger.info('recv_resp: appending {0} response'.format(None))

            elif msg[Communication_mp.META_INF_IDX_MSG_DATA] == MSG_DATA_META:
                ret['agent_id'] = copy.deepcopy(msg[Communication_mp.META_INF_IDX_PROC_ID])
                ret['mask_reward'] = copy.deepcopy(msg[Communication_mp.META_INF_IDX_MSK_RW])
                ret['dist'] = copy.deepcopy(msg[Communication_mp.META_INF_IDX_DIST])
                ret['emb_label'] = copy.deepcopy(msg[Communication_mp.META_INF_IDX_TASK_SZ_ :])
                results.append(ret)

                # Change this at some point to take the original data and not string
                self.logger.info('recv_resp: appending {0} response'. format('META DATA'))

            else:
                pass



            # code for receive response for the mask    
            #elif msg[Communication.META_INF_IDX_MSG_DATA] == MSG_DATA_MSK:
            #    ret['agent_id'] = copy.deepcopy(msg[Communication.META_INF_IDX_PROC_ID])
            #    ret['mask'] = copy.deepcopy(msg[Communication.META_INF_IDX_MSK_SZ : ])
            #    results.append(ret)

                # Change this at some point to take the original data and not string
            #    self.logger.info('recv_resp: appending {0} response'.format('MASK'))

            # reset buffer and handle
            self.buff_recv_resp[idx][:] = torch.inf
            self.handle_recv_resp[idx] = None 
        return results

    def barrier(self):
        dist.barrier()

    def send_mask_request(self, msk_requests, expecting):
        # TODO: Merge this function with the other send_receive_mask function.
        '''
        Sends a request to the top three agents for masks using the their embeddings.
        Checks for similar requests.
        '''

        # For each 
        for agent_id, emb_label in msk_requests.items():
            # Convert embedding label to tensor
            if isinstance(emb_label, np.ndarray):
                emb_label = torch.tensor(emb_label, dtype=torch.float32)

            # Initialise a buffer for one agent embedding/tasklabel
            data = torch.ones_like(self.buff_send_recv_req[0]) * torch.inf

            # Populate the tensor with necessary data
            data[Communication_mp.META_INF_IDX_PROC_ID] = self.agent_id
            data[Communication_mp.META_INF_IDX_MSG_TYPE] = Communication_mp.MSG_TYPE_SEND_REQ
            
            if emb_label is None:
                # If emb_label is none it means we reject the agent
                data[Communication_mp.META_INF_IDX_MSG_DATA] = Communication_mp.MSG_DATA_NULL
                    
            else:
                # Otherwise we want the agent's mask
                data[Communication_mp.META_INF_IDX_MSG_DATA] = Communication_mp.MSG_DATA_TSK
                data[Communication_mp.META_INF_TASK_SZ : ] = emb_label # NOTE deepcopy?

            # Send out the mask request or rejection to each agent that sent metadata
            self.handle_send_recv_req = dist.isend(tensor=data, dst=agent_id)
        
    def receive_mask_requests(self, expecting):
        # Check for mask requests from other agents if expecting any requests
        ret = []
        if expecting:
            # If expecting a request for a mask, check for each expected agent id
            for idx in expecting:
                data = torch.ones_like(self.buff_send_recv_req[0]) * torch.inf
                self.handle_send_recv_req = dist.irecv(tensor=data, src=idx)
                time.sleep(Communication_mp.SLEEP_DURATION)

                # If response was null message then this agent has been rejected.
                # If so, remove the idx from expecting and check the next id.
                # if no more idxs then return the list of dictionaries. (can be empty)
                if self._null_message(data):
                    expecting.remove(idx)

                # If not rejected then we need to send the mask to the requester
                else:
                    d = {}
                    d['requester_agent_id'] = int(buff[Communication_mp.META_INF_IDX_PROC_ID])
                    d['msg_type'] = int(buff[Communication_mp.META_INF_IDX_MSG_TYPE])
                    d['msg_data'] = int(buff[Communication_mp.META_INF_IDX_MSG_DATA])
                    d['task_label'] = buff[Communication_mp.META_INF_IDX_TASK_SZ : ]
                    ret.append(d)

        # Return a list of dictionaries for each agent that wants a mask
        return expecting, ret

    def send_mask_response(self, dst_agent_id, mask):
        buff = torch.ones_like(self.buff_send_resp[0]) * torch.inf

        buff[Communication_mp.META_INF_IDX_PROC_ID] = self.agent_id
        buff[Communication_mp.META_INF_IDX_MSG_TYPE] = Communication_mp.MSG_TYPE_SEND_RESP

        if mask is None:
            buff[Communication_mp.META_INF_IDX_MSG_DATA] = Communication_mp.MSG_DATA_NULL
            buff[Communication_mp.META_INF_SZ : ] = torch.inf

        else:
            buff[Communication_mp.META_INF_IDX_MSG_DATA] = Communication_mp.MSG_DATA_MSK
            buff[Communication_mp.META_INF_SZ : ] = mask # NOTE deepcopy?

        # Send the mask to the destination agent id
        req = dist.isend(tensor=buff, dst=dst_agent_id)
        return

    def receive_mask_response(self, best_agent_id):
        buff = torch.ones_like(self.buff_send_resp[0]) * torch.inf

        # Receive the buffer containing the mask. Wait for 10 seconds to make sure mask is received
        req = dist.irecv(tensor=buff, src=best_agent_id)
        time.sleep(Communication_mp.SLEEP_DURATION)

        # If the buffer was a null response (which it shouldn't be)
        # meep
        if self._null_message(buff):
            # Shouldn't reach this hopefully :^)
            return None

        # otherwise return the mask
        elif buff[Communication_mp.META_INF_IDX_MSG_DATA] == Communication_mp.MSG_DATA_MSK:
            if buff[Communication_mp.META_INF_IDX_PROC_ID] == best_agent_id:
                return buff[Communication_mp.META_INF_IDX_MASK_SZ : ]

    def fetch_all(self):
        '''
        We can use the original code with some modifications here
        '''

"""

######## PARALLELISATION WRAPPERS
'''
Communication parallelisation wrapper. These handle the parallelisation of the selected
communication module, and provide interface methods to call the functions. Interfacing
methods must match the ones inside the communication module implementation used.

TODO: Need to modify the communication interfacing methods in these to match the ones used in
the revised communication module Communication_mp.
'''
class CommProcess(mp.Process):
    SR_REQ= 0
    S_META_RESP = 1
    R_META_RESP = 2
    BARRIER = 3
    INIT = 4
    S_MASK_REQ = 5
    R_MASK_REQ = 6
    S_MASK_RESP = 7
    R_MASK_RESP = 8
    SYNC_META = 9
    DO_COMM = 10

    def __init__(self, pipe, agent_id, num_agents, task_label_sz, mask_sz, logger, init_address, init_port, queue_agent, queue_comm):
        mp.Process.__init__(self)
        self.pipe = pipe
        self.comm = Communication_mp(agent_id, num_agents, task_label_sz, mask_sz, logger, init_address, init_port, queue_agent, queue_comm)

    def run(self):
        while True:
            op, data = self.pipe.recv()
            if op == self.SR_REQ:
                self.pipe.send(self.comm.send_receive_request(data))

            elif op == self.S_META_RESP:
                self.comm.send_meta_response(data)

            elif op == self.R_META_RESP:
                self.pipe.send(self.comm.receive_meta_response())

            elif op == self.BARRIER:
                self.comm.barrier()

            elif op == self.INIT:
                self.comm.init_dist()

            elif op == self.S_MASK_REQ:
                self.comm.send_mask_request(data)

            elif op == self.R_MASK_REQ:
                self.pipe.send(self.comm.receive_mask_requests(data))

            elif op == self.S_MASK_RESP:
                self.comm.send_mask_response(data)

            elif op == self.R_MASK_RESP:
                self.pipe.send(self.comm.receive_mask_response(data))

            elif op == self.SYNC_META:
                self.pipe.send(self.comm.sync_gather_meta(data))

            elif op == self.DO_COMM:
                event, msg = data
                self.pipe.send(self.comm.comm_loop(event, msg))
                
            else:
                raise Exception('Unknown command')
                
class ParallelizedComm:
    def __init__(self, agent_id, num_agents, task_label_sz, mask_sz, logger, init_address, init_port, queue_agent, queue_comm):
        self.pipe, worker_pipe = mp.Pipe([True])
        self.worker = CommProcess(worker_pipe, agent_id, num_agents, task_label_sz, mask_sz, logger, init_address, init_port, queue_agent, queue_comm)
        self.worker.start()

    def send_receive_request(self, data):
        self.pipe.send([CommProcess.SR_REQ, data])
        return self.pipe.recv()

    def send_meta_response(self, data):
        self.pipe.send([CommProcess.S_META_RESP, data])

    def receive_meta_response(self):
        self.pipe.send([CommProcess.R_META_RESP, None])
        return self.pipe.recv()

    def barrier(self):
        self.pipe.send([CommProcess.BARRIER, None])

    def init_dist(self):
        self.pipe.send([CommProcess.INIT, None])

    def send_mask_request(self, data):
        self.pipe.send([CommProcess.S_MASK_REQ, data])

    def receive_mask_requests(self, data):
        self.pipe.send([CommProcess.R_MASK_REQ, data])
        return self.pipe.recv()

    def send_mask_response(self, data):
        self.pipe.send([CommProcess.S_MASK_RESP, data])
        
    def receive_mask_response(self, data):
        self.pipe.send([CommProcess.R_MASK_RESP, data])
        return self.pipe.recv()

    def sync_gather_meta(self, data):
        self.pipe.send([CommProcess.SYNC_META, data])
        return self.pipe.recv()

    def comm_loop(self, data):
        self.pipe.send([CommProcess.DO_COMM, data])
        return self.pipe.recv()


"""
'''
Using communication client-server paradigm with multiprocessing. The concept is that each agent will
have a client sending requests out and a server receiving responses.
'''

class CommClient_v2(mp.Process):
    SR_REQ= 0
    S_META_RESP = 1
    R_META_RESP = 2
    BARRIER = 3
    INIT = 4
    S_MASK_REQ = 5
    R_MASK_REQ = 6
    S_MASK_RESP = 7
    R_MASK_RESP = 8

    def __init__(self, pipe, agent_id, num_agents, task_label_sz, mask_sz, logger, init_address, init_port):
        mp.Process.__init__(self)
        self.pipe = pipe
        self.self = Communication_mp(agent_id, num_agents, task_label_sz, mask_sz, logger, init_address, init_port)

    def run(self):
        while True:
            op, data = self.pipe.recv()
            if op == self.SR_REQ:
                self.pipe.send(self.self.send_receive_request(data))

            elif op == self.S_META_RESP:
                self.self.send_meta_response(data)

            elif op == self.R_META_RESP:
                self.pipe.send(self.self.receieve_meta_response())

            elif op == self.BARRIER:
                self.self.barrier()

            elif op == self.INIT:
                self.self.init_dist()

            elif op == self.S_MASK_REQ:
                self.self.send_mask_request(data)

            elif op == self.R_MASK_REQ:
                self.pipe.send(self.self.receive_mask_requests(data))

            elif op == self.S_MASK_RESP:
                self.self.send_mask_response(data)

            elif op == self.R_MASK_RESP:
                self.pipe.send(self.self.receive_mask_response(data))
            else:
                raise Exception('Unknown command')

class CommProcess_v2(mp.Process):
    SR_REQ= 0
    S_META_RESP = 1
    R_META_RESP = 2
    BARRIER = 3
    INIT = 4
    S_MASK_REQ = 5
    R_MASK_REQ = 6
    S_MASK_RESP = 7
    R_MASK_RESP = 8

    def __init__(self, pipe, agent_id, num_agents, task_label_sz, mask_sz, logger, init_address, init_port):
        mp.Process.__init__(self)
        self.pipe = pipe
        self.self = Communication_mp(agent_id, num_agents, task_label_sz, mask_sz, logger, init_address, init_port)

    def run(self):
        while True:
            op, data = self.pipe.recv()
            if op == self.SR_REQ:
                self.pipe.send(self.self.send_receive_labels(data))

            elif op == self.S_META_RESP:
                self.self.send_meta_response(data)

            elif op == self.R_META_RESP:
                self.pipe.send(self.self.receieve_meta_response())

            elif op == self.BARRIER:
                self.self.barrier()

            elif op == self.INIT:
                self.self.init_dist()

            elif op == self.S_MASK_REQ:
                self.self.send_mask_request(data)

            elif op == self.R_MASK_REQ:
                self.pipe.send(self.self.receive_mask_requests(data))

            elif op == self.S_MASK_RESP:
                self.self.send_mask_response(data)

            elif op == self.R_MASK_RESP:
                self.pipe.send(self.self.receive_mask_response(data))
            else:
                raise Exception('Unknown command')
   
class ParallelizedComm_v2:
    def __init__(self, agent_id, num_agents, task_label_sz, mask_sz, logger, init_address, init_port):
        self.pipe, worker_pipe = mp.Pipe([True])
        self.worker = CommProcess_v2(worker_pipe, agent_id, num_agents, task_label_sz, mask_sz, logger, init_address, init_port)
        self.worker.start()

    def send_receive_labels(self, data):
        self.pipe.send([CommProcess_v2.SR_REQ, data])
        return self.pipe.recv()

    def send_meta_response(self, data):
        self.pipe.send([CommProcess_v2.S_META_RESP, data])

    def receive_meta_response(self):
        self.pipe.send([CommProcess_v2.R_META_RESP, None])
        return self.pipe.recv()

    def barrier(self):
        self.pipe.send([CommProcess_v2.BARRIER, None])

    def init_dist(self):
        self.pipe.send([CommProcess_v2.INIT, None])

    def send_mask_request(self, data):
        self.pipe.send([CommProcess_v2.S_MASK_REQ, data])

    def receive_mask_requests(self, data):
        self.pipe.send([CommProcess_v2.R_MASK_REQ, data])
        return self.pipe.recv()

    def send_mask_response(self, data):
        self.pipe.send([CommProcess_v2.S_MASK_RESP, data])
        
    def receive_mask_response(self, data):
        self.pipe.send([CommProcess_v2.R_MASK_RESP, data])
        return self.pipe.recv()

"""