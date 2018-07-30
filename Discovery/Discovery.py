#!/usr/bin/env /usr/local/bin/python
# encoding: utf-8
# Author: Zhuangwei Kang


import os, sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import MongoDBHelper as mg
import ZMQHelper as zmq
import json
import utl
import argparse
import time


class Discovery:
    def __init__(self, db_addr, db_port, discovery_port='4000'):
        db_client = mg.get_client(address=db_addr, port=db_port)
        self.db = mg.get_db(db_client, 'RESTfulSwarmDB')
        self.workers_info = mg.get_col(self.db, 'WorkersInfo')
        self.workers_resource_info = mg.get_col(self.db, 'WorkersResourceInfo')
        self.socket = zmq.csBind(discovery_port)
        self.logger = utl.doLog('DiscoveryLogger', 'DiscoveryLog.log')

    def discovery(self):
        while True:
            msg = self.socket.recv_string()
            self.logger.info('Recv msg: %s' % msg)
            self.socket.send_string('Ack')
            worker_host = msg.split()[0]
            msg = msg.split()[1]
            task_name = msg
            job_name = msg.split('_')[0]
            job_col = mg.get_col(self.db, job_name)

            # update job collection -- task status
            filter_key = 'job_info.tasks.%s.container_name' % task_name
            target_key = 'job_info.tasks.%s.status' % task_name
            mg.update_doc(job_col, filter_key, task_name, target_key, 'Down')

            # update job status if necessary
            job_details = mg.find_col(job_col)[0]
            flag = True
            for job in job_details['job_info']['tasks']:
                if job_details['job_info']['tasks'][job]['status'] != 'Down':
                    flag = False
            if flag:
                mg.update_doc(job_col, 'job_name', job_name, 'status', 'Down')
                mg.update_doc(job_col, 'job_name', job_name, 'end_time', time.time())

            self.logger.info('Updating Job collection.')

            # get the resource utilization of the 'Down' container
            job_info = mg.find_col(job_col)[0]
            cores = job_info['job_info']['tasks'][task_name]['cpuset_cpus']
            cores = cores.split(',')
            memory = job_info['job_info']['tasks'][task_name]['mem_limit']
            self.logger.info('Collecting resources from down containers.')

            # update WorkersInfo collection
            # update cores info
            for core in cores:
                target_key = 'CPUs.%s' % core
                print(target_key)
                mg.update_doc(self.workers_info, 'hostname', worker_host, target_key, False)
                self.logger.info('Release core %s status in worker %s' % (target_key, worker_host))

            # update memory info
            worker_info = mg.filter_col(self.workers_info, 'hostname', worker_host)
            free_memory = worker_info['MemFree']
            memory = float(memory.split('m')[0])
            free_memory = float(free_memory.split('m')[0])
            updated_memory = memory + free_memory
            updated_memory = str(updated_memory) + 'm'
            mg.update_doc(self.workers_info, 'hostname', worker_host, 'MemFree', updated_memory)
            self.logger.info('Updating memory resources in WorkersInfo collection.')

            # update worker resource collection
            mg.update_workers_resource_col(self.workers_info, worker_host, self.workers_resource_info)
            self.logger.info('Updated WorkersResourceInfo collection, because some cores are released.')

            # update job collection -- cpuset_cpus
            target_key = 'job_info.tasks.%s.cpuset_cpus' % task_name
            mg.update_doc(job_col, filter_key, task_name, target_key, '')
            self.logger.info('Updated Job collection. Released used cores.')

            # update job collection -- mem_limit
            target_key = 'job_info.tasks.%s.mem_limit' % task_name
            mg.update_doc(job_col, filter_key, task_name, target_key, '')
            self.logger.info('Updated Job collection. Released used memory.')


def main():
    os.chdir('/home/%s/RESTfulSwarmLM/Discovery' % utl.getUserName())

    try:
        with open('DiscoveryInit.json') as f:
            data = json.load(f)
        mongo_addr = data['mongo_addr']
        mongo_port = data['mongo_port']

        discovery = Discovery(mongo_addr, mongo_port)
        discovery.logger.info('Initialized Discovery block.')

        discovery.discovery()

        os.chdir('/home/%s/RESTfulSwarmLM/ManagementEngine' % utl.getUserName())
    except Exception as ex:
        with open('debug.txt', 'w') as f:
            f.write(ex)


if __name__ == '__main__':
    # parser = argparse.ArgumentParser()
    # parser.add_argument('-ma', '--mongo_addr', type=str, help='Mongodb server address.')
    # parser.add_argument('-mp', '--mongo_port', type=str, default='27017', help='Mongodb server port.')
    # args = parser.parse_args()
    # mongo_addr = args.mongo_addr
    # mongo_port = args.mongo_port

    main()