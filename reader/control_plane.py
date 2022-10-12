import enum
from lib2to3.pgen2.token import OP
from ssl import OP_ALL
import bfrt_grpc.client as gc
from typing import List
import logging

import pd_base_tests
from bfruntime_client_base_tests import BfRuntimeTest

import bfrt_grpc.bfruntime_pb2 as bfruntime_pb2

import ptf.testutils as testutils

from tm_api_rpc.ttypes import *

# import sys

# print(sys.executable)

from prettytable import PrettyTable

logger = logging.getLogger('Test')
if not len(logger.handlers):
    logger.addHandler(logging.StreamHandler())

p4_name = "inter-board"

# the list of Port
ports = []
q_num = 1

# queue
CONTROL_QID = 0
OQ_QID = 0
CQ1_QID = 2
CQ2_QID = 3
CQ1_NEW_QID = 4

# Parameters in experiment
XON_THRESHOLD_GHOST = 300
XOFF_THRESHOLD_GHOST = 600
QLENGTH_CELL = 1200


class Port:
    def __init__(self, name, dp, speed="100G", fec="BF_FEC_TYP_NONE", peer_addr = None, peer_mac = None):
        if speed in ["100G", "400G"]:
            # if the port rate is 100G or 400G, the FEC should be RS
            fec = "BF_FEC_TYP_RS"
            # 100G and 400G port should be only added on lane0
            if dp % 8 != 0:
                print("100G and 40G port should be only added on lane0")
        else: 
            fec = "BF_FEC_TYP_NONE"
            
        self.name = name
        self.pipe = dp >> 7
        self.dp = dp
        self.speed = speed
        self.fec = fec
        # the ip addr of host which the port is connected to 
        self.peer_addr = peer_addr
        self.peer_mac = peer_mac

g_is_tofino = testutils.test_param_get("arch") == "tofino"
g_is_tofino2 = testutils.test_param_get("arch") == "tofino2"
assert g_is_tofino or g_is_tofino2

class Controller(BfRuntimeTest):
    def __init__(self):
        BfRuntimeTest.__init__(self)
        self.p4_name = p4_name
        
        self.ports = []
        self.ports.append(Port("1/0", 392, "10G", "BF_FEC_TYP_NONE", "172.16.100.2", 0xec0d9abfdf75))
        # self.ports.append(Port("2/0", 400, "10G", "BF_FEC_TYP_NONE", "172.16.100.12", 0xec0d9aa418ff))
        self.ports.append(Port("9/0", 64, "10G", "BF_FEC_TYP_NONE", "172.16.100.14", 0xec0d9abfdcbd))
        self.ports.append(Port("10/0", 56, "10G", "BF_FEC_TYP_NONE", "172.16.100.6", 0xec0d9abfdcb5))
        self.ports.append(Port("11/0", 48, "10G", "BF_FEC_TYP_NONE", "172.16.100.13", 0x043f72c0639e))
        self.ports.append(Port("12/0", 40, "10G", "BF_FEC_TYP_NONE", "172.16.100.14", 0x043f72c0656e))
        # self.ports.append(Port("13/0", 32, "10G", "BF_FEC_TYP_NONE", "172.16.100.15", 0xec0d9abfd92c))
        self.ports.append(Port("17/0", 136, "10G", "BF_FEC_TYP_NONE", "172.16.100.19", 0xec0d9aa4190f))
        self.ports.append(Port("18/0", 144, "10G", "BF_FEC_TYP_NONE", "172.16.100.20", 0x043f72c060e6))
        
        self.inner_ports = []
        for lp in [312, 320, 296, 304, 288, 280]:
            self.inner_ports.append(Port("0/0", lp, "10G", "BF_FEC_TYP_NONE", "0.0.0.0"))
        
    
    def setUp(self):
        self.client_id = 0
        self.dev = 0
        # self.dev_tgt = gc.Target(device_id=self.dev, pipe_id=0xffff)
        self.grpc_setup(p4_name = self.p4_name)
        # BfRuntimeTest.setUp(self, self.client_id, self.p4_name)
        # self.bfrt_info = self.interface.bfrt_info_get()
        # self.target = gc.Target(device_id=0, pipe_id=0xffff)
        
        self.tidp = pd_base_tests.ThriftInterfaceDataPlane([self.p4_name])
        self.tidp.setUp()
        # This try-except block is required since unittest does not seem
        # to be able to handle Thrift exceptions correctly.
        try:
            self.tidp.shdl = self.tidp.conn_mgr.client_init()
        except Exception as exc:
            raise Exception("Failed to initialize ThriftInterfaceDataPlane") from exc
        
        # drop count: [{switch, src_addr, dst_addr, tm_drop_count, random_drop_count}]
        self.drop_count = []
        self.read_drop_count()
        self.print_drop_count()
        
    def runTest(self):
        print("runTest")
        pass
    
    def tearDown(self):
        pass

    def grpc_setup(self, client_id=0, p4_name=None):
        '''
        Set up connection to gRPC server and bind
        Args: 
         - client_id Client ID
         - p4_name Name of P4 program
        '''
        self.bfrt_info = None

        grpc_addr = 'localhost:50052'        

        self.interface = gc.ClientInterface(grpc_addr, client_id=client_id,
                device_id=0, notifications=None, perform_subscribe=True)
        self.interface.bind_pipeline_config(p4_name)
        self.bfrt_info = self.interface.bfrt_info_get()

        self.target = gc.Target(device_id=0, pipe_id=0xffff)
        
    def safe_entry_add(self, table, target, keys, datas):
        '''
        try to del the entry before add the entry
        incase of ALREADY_EXISTS error
        '''
        try:
            table.entry_del(
                target, 
                keys
            )
        except:
            pass
        table.entry_add(
            target,
            keys,
            datas
        )
        
    def read_drop_count(self):
        ig_tbl_packet_count = self.bfrt_info.table_get("SwitchIngress.tbl_ig_packet_count")
        eg_tbl_packet_count = self.bfrt_info.table_get("SwitchEgress.tbl_eg_packet_count")
        tbl_random_drop_count = self.bfrt_info.table_get("SwitchEgress.tbl_random_drop_count")
        ig_tbl_packet_count.info.key_field_annotation_add("hdr.ipv4.src_addr", "ipv4")
        ig_tbl_packet_count.info.key_field_annotation_add("hdr.ipv4.dst_addr", "ipv4")
        eg_tbl_packet_count.info.key_field_annotation_add("hdr.ipv4.src_addr", "ipv4")
        eg_tbl_packet_count.info.key_field_annotation_add("hdr.ipv4.dst_addr", "ipv4")
        tbl_random_drop_count.info.key_field_annotation_add("hdr.ipv4.src_addr", "ipv4")
        tbl_random_drop_count.info.key_field_annotation_add("hdr.ipv4.dst_addr", "ipv4")
        
        self.mpu_port = self.ports[0]
        self.lpu_port = self.ports[1:]
        lsw0_port = {
            'up_port': self.mpu_port,
            'down_port': self.inner_ports[0]
        }
        lsw1_port = {
            'up_port': self.inner_ports[1],
            'down_port': [self.inner_ports[2],
                          self.inner_ports[4]]
        }
        lsw2_port = {
            'up_port': self.inner_ports[3],
            'down_port': self.lpu_port[:4]
        }
        lsw3_port = {
            'up_port': self.inner_ports[5],
            'down_port': self.lpu_port[4:]
        }
        
        # route for mpu->lpu
        # for simplity, we use other addr in forword
        routes_mpu = [
            # the first hop
            {
                'switch' : "lsw0",
                'dst_addr': (0, 0),  # value and mask
                'ig_port': lsw0_port['up_port'],
                'eg_port': lsw0_port['down_port']
            }
        ] + [
            # the second hop
            {
                'switch' : "lsw1",
                'dst_addr': (p.peer_addr, 0x1FF),
                'ig_port': lsw1_port['up_port'],
                'eg_port': lsw1_port['down_port'][0]  # forward to lsw2
            } for p in lsw2_port['down_port']
        ] + [
            {
                'switch' : "lsw1",
                'dst_addr': (p.peer_addr, 0x1FF),
                'ig_port': lsw1_port['up_port'],
                'eg_port': lsw1_port['down_port'][1]  # forward to lsw3
            } for p in lsw3_port['down_port']
        ] + [
            {
                'switch' : "lsw2",
                'dst_addr': (p.peer_addr, 0x1FF),
                'ig_port': lsw2_port['up_port'],
                'eg_port': p  # forward hosts
            } for p in lsw2_port['down_port']
        ] + [
            {
                'switch' : "lsw3",
                'dst_addr': (p.peer_addr, 0x1FF),
                'ig_port': lsw3_port['up_port'],
                'eg_port': p  # forward hosts
            } for p in lsw3_port['down_port']
        ]
        
        # lpu->mpu
        for r in routes_mpu:
            if r['dst_addr'][0] == 0:
                for lp in self.lpu_port:
                    self.drop_count.append(
                        self.read_drop_count_once(ig_tbl_packet_count, eg_tbl_packet_count, tbl_random_drop_count, r['switch'], 
                                              r['eg_port'].dp, r['ig_port'].dp, lp.peer_addr, self.mpu_port.peer_addr))
            else:
                self.drop_count.append(
                    self.read_drop_count_once(ig_tbl_packet_count, eg_tbl_packet_count, tbl_random_drop_count, r['switch'], 
                                              r['eg_port'].dp, r['ig_port'].dp, r['dst_addr'][0], self.mpu_port.peer_addr))
        # mpu->lpu
        for r in routes_mpu:
            if r['dst_addr'][0] == 0:
                for lp in self.lpu_port:
                    self.drop_count.append(
                        self.read_drop_count_once(ig_tbl_packet_count, eg_tbl_packet_count, tbl_random_drop_count, r['switch'], 
                                              r['ig_port'].dp, r['eg_port'].dp, self.mpu_port.peer_addr, lp.peer_addr))
            else:
                self.drop_count.append(
                    self.read_drop_count_once(ig_tbl_packet_count, eg_tbl_packet_count, tbl_random_drop_count, r['switch'], 
                                              r['ig_port'].dp, r['eg_port'].dp, self.mpu_port.peer_addr, r['dst_addr'][0]))
        
    def read_drop_count_once(self, ig_tbl_packet_count, eg_tbl_packet_count, tbl_random_drop_count, switch, ig_port, eg_port, src_addr, dst_addr):
        ig_count = 0
        eg_count = 0
        rand_count = 0
        resp_ig = ig_tbl_packet_count.entry_get(
            self.target,
            [ig_tbl_packet_count.make_key([gc.KeyTuple('ig_intr_md.ingress_port', ig_port),
                                        gc.KeyTuple('hdr.ipv4.src_addr', src_addr),
                                        gc.KeyTuple('hdr.ipv4.dst_addr', dst_addr)])],
            {"from_hw": True}
        )
        resp_eg = eg_tbl_packet_count.entry_get(
            self.target,
            [eg_tbl_packet_count.make_key([gc.KeyTuple('eg_intr_md.egress_port', eg_port),
                                        gc.KeyTuple('hdr.ipv4.src_addr', src_addr),
                                        gc.KeyTuple('hdr.ipv4.dst_addr', dst_addr)])],
            {"from_hw": True}
        )
        resp_rand = tbl_random_drop_count.entry_get(
            self.target,
            [tbl_random_drop_count.make_key([gc.KeyTuple('eg_intr_md.egress_port', eg_port),
                                        gc.KeyTuple('hdr.ipv4.src_addr', src_addr),
                                        gc.KeyTuple('hdr.ipv4.dst_addr', dst_addr)])],
            {"from_hw": True}
        )
        
        # only one entry in this generator
        # print(ig_port, eg_port, src_addr, dst_addr)
        for data, key in resp_ig:
            # print(data, key)
            data_fields = data.to_dict()
            ig_count = data_fields['SwitchIngress.reg_ig_packet_count.f1'][get_pipe(ig_port)]
        for data, key in resp_eg:
            data_fields = data.to_dict()
            eg_count = data_fields['SwitchEgress.reg_eg_packet_count.f1'][get_pipe(eg_port)]
        for data, key in resp_rand:
            data_fields = data.to_dict()
            rand_count = data_fields['SwitchEgress.reg_random_drop_count.f1'][get_pipe(eg_port)]
            
        # drop count: [{switch, src_addr, dst_addr, tm_drop_count, random_drop_count}]
        return {
            'switch': switch,
            'src_addr': src_addr,
            'dst_addr': dst_addr,
            'tm_drop_count': ig_count - eg_count,
            'random_drop_count': rand_count,
            'random_drop_ratio': float(rand_count) / float(eg_count) if eg_count != 0 else 0
        }
        
    def print_drop_count(self):
        table = PrettyTable(['Flow','Switch','TM drop count','Random drop count', 'Random drop ratio'])
        for dc in self.drop_count:
            table.add_row([dc['src_addr'] + "->" + dc['dst_addr'], dc['switch'], dc['tm_drop_count'], dc['random_drop_count'], '%.3e' % dc['random_drop_ratio']])
            # print("Flow from " + dc['src_addr'] + "\tto " + dc['dst_addr'] + " at " + dc['switch'] + ":\tdrops " + str(dc['tm_drop_count']) + \
            #     "\tpackets at tm and randomly drops " + str(dc['random_drop_count']) + "\tpackets with " +  '%.3e' % dc['random_drop_ratio'] + " drop ratio")
        print(table)
            
        
# Type transformation functions
def make_port(pipe, local_port):
    assert pipe >= 0 and pipe < 4
    assert local_port >= 0 and local_port < 72
    return pipe << 7 | local_port

def port_to_pipe(port):
    return port >> 7

def toInt8(n):
    n = n & 0xff
    return (n ^ 0x80) - 0x80

def toInt16(n):
    n = n & 0xffff
    return (n ^ 0x8000) - 0x8000

def toInt32(n):
    n = n & 0xffffffff
    return (n ^ 0x80000000) - 0x80000000

def get_pipe(n):
    return (n >> 7)