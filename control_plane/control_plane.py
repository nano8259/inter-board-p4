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

from tm_types import *

from tm_api_rpc.ttypes import *

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

# random drop
MAX_RANDOM_NUMBER = 0xFFFF
DROP_RATIO = 0


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
        self.ports.append(Port("2/0", 400, "10G", "BF_FEC_TYP_NONE", "172.16.100.12", 0xec0d9aa418ff))
        self.ports.append(Port("9/0", 64, "10G", "BF_FEC_TYP_NONE", "172.16.100.14", 0xec0d9abfdcbd))
        self.ports.append(Port("10/0", 56, "10G", "BF_FEC_TYP_NONE", "172.16.100.6", 0xec0d9abfdcb5))
        self.ports.append(Port("11/0", 48, "10G", "BF_FEC_TYP_NONE", "172.16.100.13", 0x043f72c0639e))
        self.ports.append(Port("12/0", 40, "10G", "BF_FEC_TYP_NONE", "172.16.100.14", 0x043f72c0656e))
        self.ports.append(Port("13/0", 32, "10G", "BF_FEC_TYP_NONE", "172.16.100.15", 0xec0d9abfd92c))
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
        
        self.setup_ports()        
        self.setup_l3_forward()
        self.setup_max_qlenth()
        self.setup_packet_count()
        self.setup_random_drop()
        
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
        
    def setup_ports(self):
        port_table = self.bfrt_info.table_get("$PORT")
        for p in self.ports:
            port_table.entry_add(
                self.target,
                [port_table.make_key([gc.KeyTuple('$DEV_PORT', p.dp)])],
                [port_table.make_data([gc.DataTuple('$SPEED', str_val="BF_SPEED_"+p.speed),
                                            gc.DataTuple('$FEC', str_val=p.fec),
                                            gc.DataTuple('$PORT_ENABLE', bool_val=True),
                                            gc.DataTuple('$TX_PFC_EN_MAP', 0xff),
                                            gc.DataTuple('$RX_PFC_EN_MAP', 0xff)])])
        
        for ip in self.inner_ports:
            port_table.entry_add(
                self.target,
                [port_table.make_key([gc.KeyTuple('$DEV_PORT', ip.dp)])],
                [port_table.make_data([gc.DataTuple('$SPEED', str_val="BF_SPEED_"+ip.speed),
                                            gc.DataTuple('$FEC', str_val=ip.fec),
                                            gc.DataTuple('$PORT_ENABLE', bool_val=True),
                                            gc.DataTuple('$TX_PFC_EN_MAP', 0xff),
                                            gc.DataTuple('$RX_PFC_EN_MAP', 0xff)])])
            
        # q_count = 128
        # for p in self.ports:
        #     self.tidp.tm.tm_set_port_q_mapping_adv(self.dev, p.dp, q_count, list(range(q_count)))
            
        # self.tidp.tm.tm_complete_operations(self.dev)
        
    def setup_l3_forward(self):
        forward_table = self.bfrt_info.table_get("SwitchIngress.forward")
        arp_table = self.bfrt_info.table_get("SwitchIngress.arp_proxy")
        forward_table.info.key_field_annotation_add("hdr.ipv4.dst_addr", "ipv4")
        arp_table.info.key_field_annotation_add("hdr.arp.dstIPAddr", "ipv4")
        arp_table.info.data_field_annotation_add("reply_ip", "SwitchIngress.reply_arp", "ipv4")
        
        # 
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
        
        # route for lpu->mpu
        routes_lpu = [
            # the first hop
            {
                'ig_port': p,
                'eg_port': lsw2_port['up_port']
            } for p in lsw2_port['down_port']
        ] + [
            {
                'ig_port': p,
                'eg_port': lsw3_port['up_port']
            } for p in lsw3_port['down_port']
        ] + [
            # the second hop
            {
                'ig_port': p,
                'eg_port': lsw1_port['up_port']
            } for p in lsw1_port['down_port']
        ] + [
            # the third hop
            {
                'ig_port': lsw0_port['down_port'],
                'eg_port': lsw0_port['up_port']
            }
        ]
        for r in routes_lpu:
            self.safe_entry_add(
                forward_table,
                self.target,
                [forward_table.make_key([gc.KeyTuple('$MATCH_PRIORITY', 10),
                                        gc.KeyTuple('hdr.ipv4.dst_addr', self.mpu_port.peer_addr, 0xFFFF),
                                        gc.KeyTuple('ig_intr_md.ingress_port', r['ig_port'].dp, 0x1FF)])],
                [forward_table.make_data([gc.DataTuple('port', r['eg_port'].dp),
                                        gc.DataTuple('qid', OQ_QID),
                                        gc.DataTuple('ingress_cos', 0)],
                                        'SwitchIngress.hit')])
        
        # route for mpu->lpu
        # for simplity, we use other addr in forword
        routes_mpu = [
            # the first hop
            {
                'dst_addr': (0, 0),  # value and mask
                'ig_port': lsw0_port['up_port'],
                'eg_port': lsw0_port['down_port']
            }
        ] + [
            # the second hop
            {
                'dst_addr': (p.peer_addr, 0x1FF),
                'ig_port': lsw1_port['up_port'],
                'eg_port': lsw1_port['down_port'][0]  # forward to lsw2
            } for p in lsw2_port['down_port']
        ] + [
            {
                'dst_addr': (p.peer_addr, 0x1FF),
                'ig_port': lsw1_port['up_port'],
                'eg_port': lsw1_port['down_port'][1]  # forward to lsw3
            } for p in lsw3_port['down_port']
        ] + [
            {
                'dst_addr': (p.peer_addr, 0x1FF),
                'ig_port': lsw2_port['up_port'],
                'eg_port': p  # forward hosts
            } for p in lsw2_port['down_port']
        ] + [
            {
                'dst_addr': (p.peer_addr, 0x1FF),
                'ig_port': lsw3_port['up_port'],
                'eg_port': p  # forward hosts
            } for p in lsw3_port['down_port']
        ]
        for r in routes_mpu:
            self.safe_entry_add(
                forward_table,
                self.target,
                [forward_table.make_key([gc.KeyTuple('$MATCH_PRIORITY', 20),
                                        gc.KeyTuple('hdr.ipv4.dst_addr', r['dst_addr'][0], r['dst_addr'][1]),
                                        gc.KeyTuple('ig_intr_md.ingress_port', r['ig_port'].dp, 0x1FF)])],
                [forward_table.make_data([gc.DataTuple('port', r['eg_port'].dp),
                                        gc.DataTuple('qid', OQ_QID),
                                        gc.DataTuple('ingress_cos', 0)],
                                        'SwitchIngress.hit')])
            
        # default route to every host
        for p in self.ports:
            self.safe_entry_add(
                forward_table,
                self.target,
                [forward_table.make_key([gc.KeyTuple('$MATCH_PRIORITY', 30),
                                        gc.KeyTuple('hdr.ipv4.dst_addr', p.peer_addr, 0xFFFF),
                                        gc.KeyTuple('ig_intr_md.ingress_port', 0, 0)])],
                [forward_table.make_data([gc.DataTuple('port', p.dp),
                                        gc.DataTuple('qid', OQ_QID),
                                        gc.DataTuple('ingress_cos', 0)],
                                        'SwitchIngress.hit')])
            
        # ARP table
        for p in self.ports:
            self.safe_entry_add(
                arp_table,
                self.target,
                [arp_table.make_key([gc.KeyTuple('hdr.arp.dstIPAddr', p.peer_addr)])],
                [arp_table.make_data([gc.DataTuple('reply_mac', p.peer_mac),
                                      gc.DataTuple('reply_ip', p.peer_addr)],
                                     'SwitchIngress.reply_arp')])
            
        # forward drop indicate packet
        for p in self.port + self.inner_ports:
            self.safe_entry_add(
                forward_table,
                self.target,
                [forward_table.make_key([gc.KeyTuple('$MATCH_PRIORITY', 5),
                                        gc.KeyTuple('hdr.ipv4.dst_addr', (0b111100 << 9 + p.dp) << 16, 0xFE00),
                                        gc.KeyTuple('ig_intr_md.ingress_port', 0, 0)])],
                [forward_table.make_data([gc.DataTuple('port', p.dp),
                                        gc.DataTuple('qid', OQ_QID),
                                        gc.DataTuple('ingress_cos', 0)],
                                        'SwitchIngress.hit')])
            
    def setup_max_qlenth(self):
        tbl_max_queue_length = self.bfrt_info.table_get("SwitchEgress.tbl_max_queue_length")
        for p in self.ports + self.inner_ports:
            for q in range(q_num):
                self.safe_entry_add(
                    tbl_max_queue_length,
                    self.target,
                    [tbl_max_queue_length.make_key([gc.KeyTuple('eg_intr_md.egress_port', p.dp),
                                                gc.KeyTuple('eg_intr_md.egress_qid', q)])],
                    [tbl_max_queue_length.make_data([gc.DataTuple('SwitchEgress.reg_max_queue_length.f1', 0)],
                                                'SwitchEgress.act_max_queue_length_set')])
                
    def setup_packet_count(self):
        ig_tbl_packet_count = self.bfrt_info.table_get("SwitchIngress.tbl_ig_packet_count")
        eg_tbl_packet_count = self.bfrt_info.table_get("SwitchEgress.tbl_eg_packet_count")
        ig_tbl_packet_count.info.key_field_annotation_add("hdr.ipv4.src_addr", "ipv4")
        ig_tbl_packet_count.info.key_field_annotation_add("hdr.ipv4.dst_addr", "ipv4")
        eg_tbl_packet_count.info.key_field_annotation_add("hdr.ipv4.src_addr", "ipv4")
        eg_tbl_packet_count.info.key_field_annotation_add("hdr.ipv4.dst_addr", "ipv4")
        for p in self.ports + self.inner_ports:
            for lp in self.lpu_port:
                # flows form mpu to lpus
                self.safe_entry_add(
                    ig_tbl_packet_count,
                    self.target,
                    [ig_tbl_packet_count.make_key([gc.KeyTuple('ig_intr_md.ingress_port', p.dp),
                                                   gc.KeyTuple('hdr.ipv4.src_addr', self.mpu_port.peer_addr),
                                                   gc.KeyTuple('hdr.ipv4.dst_addr', lp.peer_addr)])],
                    [ig_tbl_packet_count.make_data([gc.DataTuple('SwitchIngress.reg_ig_packet_count.f1', 0)],
                                                   'SwitchIngress.act_ig_packet_count_inc')])
                self.safe_entry_add(
                    eg_tbl_packet_count,
                    self.target,
                    [eg_tbl_packet_count.make_key([gc.KeyTuple('eg_intr_md.egress_port', p.dp),
                                                   gc.KeyTuple('hdr.ipv4.src_addr', self.mpu_port.peer_addr),
                                                   gc.KeyTuple('hdr.ipv4.dst_addr', lp.peer_addr)])],
                    [eg_tbl_packet_count.make_data([gc.DataTuple('SwitchEgress.reg_eg_packet_count.f1', 0)],
                                                   'SwitchEgress.act_eg_packet_count_inc')])
                # flows form lpus to mpu
                self.safe_entry_add(
                    ig_tbl_packet_count,
                    self.target,
                    [ig_tbl_packet_count.make_key([gc.KeyTuple('ig_intr_md.ingress_port', p.dp),
                                                   gc.KeyTuple('hdr.ipv4.src_addr', lp.peer_addr),
                                                   gc.KeyTuple('hdr.ipv4.dst_addr', self.mpu_port.peer_addr)])],
                    [ig_tbl_packet_count.make_data([gc.DataTuple('SwitchIngress.reg_ig_packet_count.f1', 0)],
                                                   'SwitchIngress.act_ig_packet_count_inc')])
                self.safe_entry_add(
                    eg_tbl_packet_count,
                    self.target,
                    [eg_tbl_packet_count.make_key([gc.KeyTuple('eg_intr_md.egress_port', p.dp),
                                                   gc.KeyTuple('hdr.ipv4.src_addr', lp.peer_addr),
                                                   gc.KeyTuple('hdr.ipv4.dst_addr', self.mpu_port.peer_addr)])],
                    [eg_tbl_packet_count.make_data([gc.DataTuple('SwitchEgress.reg_eg_packet_count.f1', 0)],
                                                   'SwitchEgress.act_eg_packet_count_inc')])
                
    def setup_random_drop(self):
        tbl_drop_determine = self.bfrt_info.table_get("SwitchEgress.tbl_drop_determine")
        tbl_random_drop_count = self.bfrt_info.table_get("SwitchEgress.tbl_random_drop_count")
        tbl_random_drop_count.info.key_field_annotation_add("hdr.ipv4.src_addr", "ipv4")
        tbl_random_drop_count.info.key_field_annotation_add("hdr.ipv4.dst_addr", "ipv4")
        # random drop determine
        self.safe_entry_add(
            tbl_drop_determine,
            self.target,
            [tbl_drop_determine.make_key([gc.KeyTuple('eg_md.rand_num', low=0, high=int(MAX_RANDOM_NUMBER * DROP_RATIO))])],
            [tbl_drop_determine.make_data([],'SwitchEgress.set_is_drop')])
        # random drop count
        for p in self.ports + self.inner_ports:
            for lp in self.lpu_port:
                # flows form mpu to lpus
                self.safe_entry_add(
                    tbl_random_drop_count,
                    self.target,
                    [tbl_random_drop_count.make_key([gc.KeyTuple('eg_intr_md.egress_port', p.dp),
                                                   gc.KeyTuple('hdr.ipv4.src_addr', self.mpu_port.peer_addr),
                                                   gc.KeyTuple('hdr.ipv4.dst_addr', lp.peer_addr)])],
                    [tbl_random_drop_count.make_data([gc.DataTuple('SwitchEgress.reg_random_drop_count.f1', 0)],
                                                   'SwitchEgress.act_random_drop_count_inc')])
                # flows form lpus to mpu
                self.safe_entry_add(
                    tbl_random_drop_count,
                    self.target,
                    [tbl_random_drop_count.make_key([gc.KeyTuple('eg_intr_md.egress_port', p.dp),
                                                   gc.KeyTuple('hdr.ipv4.src_addr', lp.peer_addr),
                                                   gc.KeyTuple('hdr.ipv4.dst_addr', self.mpu_port.peer_addr)])],
                    [tbl_random_drop_count.make_data([gc.DataTuple('SwitchEgress.reg_random_drop_count.f1', 0)],
                                                   'SwitchEgress.act_random_drop_count_inc')])
        
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