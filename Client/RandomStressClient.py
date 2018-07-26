#!/usr/bin/env /usr/local/bin/python
# encoding: utf-8
# Author: Zhuangwei Kang

import json
import random
from Client.Client import StressClient


class RandomStressClient(StressClient):
    def __init__(self, lower_bound, upper_bound):
        super(StressClient).__init__()
        self.lower_bound = lower_bound
        self.upper_bound = upper_bound

    def feed_func(self, time_stamp):
        return random.randint(self.lower_bound, self.upper_bound)


if __name__ == '__main__':
    # parser = argparse.ArgumentParser()
    # parser.add_argument('-a', '--address', type=str, help='Front end node address.')
    # parser.add_argument('-p', '--port', type=str, default='5001', help='Front end node port number.')
    # args = parser.parse_args()
    # fe_addr = args.address
    # fe_port = args.port

    try:
        json_path = 'RandomStressClientInfo.json'
        with open(json_path, 'r') as f:
            data = json.load(f)
        client = RandomStressClient(lower_bound=data['lower_bound'], upper_bound=data['upper_bound'])
        client.feed_jobs()
    except ValueError as er:
        print(er)