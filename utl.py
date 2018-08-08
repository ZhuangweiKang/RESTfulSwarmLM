#!/usr/bin/env /usr/local/bin/python
# encoding: utf-8
# Author: Zhuangwei Kang

import os
import sys
import socket
import struct
import re
import tarfile
import shutil
import logging
import cpuinfo

import SystemConstants


def get_logger(logger_name, log_file):
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)

    fl = logging.FileHandler(log_file)
    fl.setLevel(logging.DEBUG)

    cl = logging.StreamHandler()
    cl.setLevel(logging.DEBUG)

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    fl.setFormatter(formatter)
    cl.setFormatter(formatter)

    logger.addHandler(fl)
    logger.addHandler(cl)

    return logger


def get_hostname():
    cmd = 'hostname'
    return os.popen(cmd).read().strip()


def get_username():
    return os.getlogin().strip()


def get_host_ip():
    host_address = os.popen('ip addr show dev ens3 | grep -w inet | awk \'{print $2}\'', 'r').read()
    host_address = host_address.split('/')[0]
    return host_address


def get_work_dir():
    return '/var/lib/docker/tmp'


def go_to_work_dir():
    work_dir = '/var/lib/docker/tmp'
    os.chdir(work_dir)


def tar_files(checkpoint_tar, container_id, checkpoint_name):
    checkpoint_dir = '/var/lib/docker/containers/%s/checkpoints' % container_id
    os.chdir(checkpoint_dir)
    tar_file = tarfile.TarFile.open(name=checkpoint_tar, mode='w')
    checkpoint_tar_file = checkpoint_dir + '/' + checkpoint_name
    tar_file.add(checkpoint_tar_file, arcname=os.path.basename(checkpoint_tar_file))
    tar_file.close()
    shutil.move(checkpoint_tar, get_work_dir())
    go_to_work_dir()


def untar_file(tar_file):
    go_to_work_dir()
    tar = tarfile.TarFile.open(name=tar_file, mode='r')
    tar.extractall()
    tar.close()
    os.remove(tar_file)


# socket
def transfer_file(file_name, dst_address, port, logger):
    try:
        logger.info('Prepare to send tar file to destination host.')
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((dst_address, port))
        logger.info('Connection has been set up.')
    except socket.error as er:
        logger.error(er)
        sys.exit(1)
    if os.path.isfile(file_name):
        fileinfo_size = struct.calcsize('128sl')
        fhead = struct.pack('128sl', os.path.basename(file_name).encode('utf-8'), os.stat(file_name).st_size)
        s.send(fhead)
        fp = open(file_name, 'rb')
        while True:
            data = fp.read(1024)
            if not data:
                break
            s.send(data)
        logger.info('Tar file has been sent.')
        fp.close()
        s.close()
    else:
        logger.error('File %s not exists.' % file_name)
        sys.exit(1)


# socket
def recv_file(logger):
    try:
        recv_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        recv_socket.bind(('', SystemConstants.CONTAINER_LM_PORT))
        recv_socket.listen(20)
        logger.info('Waiting for client to ps_connect...')
        conn, addr = recv_socket.accept()
        logger.info('Client has connected to server...')
        go_to_work_dir()
        fileinfo_size = struct.calcsize('128sl')
        fhead = conn.recv(fileinfo_size)
        fn, file_size = struct.unpack('128sl', fhead)
        file_name = fn.decode('utf-8')
        file_name = file_name.strip('\00')
        logger.info('Received file info: %s' % fn)
        logger.info('File size: ' + str(file_size))
        filenew_name = os.path.join('/var/lib/docker/tmp/', file_name)
        with open(filenew_name, 'wb') as tarFile:
            logger.info('Start receiving file...')
            temp_size = file_size
            while True:
                if temp_size > 1024:
                    data = conn.recv(1024)
                else:
                    data = conn.recv(temp_size)
                if not data:
                    break
                tarFile.write(data)
                temp_size -= len(data)
                if temp_size == 0:
                    break
            logger.info('Receiving file finished, connection will be closed...')
        conn.close()
        recv_socket.close()
        logger.info('Connection has been closed...')
        return file_name
    except Exception as ex:
        logger.error(ex)
        return None


def get_total_cores():
    return cpuinfo.get_cpu_info()['count']


def get_total_mem():
    meminfo = open('/proc/meminfo').read()
    memfree = re.search("MemFree:\s+(\d+)", meminfo)
    memfree = str(memfree.group(0).split()[1]) + 'k'
    return str(memory_size_translator(memfree)) + 'm'


# convert memory size to mB
def memory_size_translator(mem_size):
    '''
    :param mem_size: b/k/m/g
    :return: mem_size: m
    '''
    # remove 'B' and blank from input str
    mem_size = mem_size.replace(' ', '')
    mem_size = mem_size.replace('B', '')
    num = float(re.findall(r"\d+\.?\d*", mem_size)[0])
    unit = mem_size[-1]
    if unit == 'm':
        return num
    elif unit == 'k':
        return num / 1000
    elif unit == 'b':
        return num / 1000 / 1000
    elif unit == 'g':
        return num * 1000