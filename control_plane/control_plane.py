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
CQ1_QID = 2
CQ2_QID = 3
CQ1_NEW_QID = 4

# Parameters in experiment
XON_THRESHOLD_GHOST = 300
XOFF_THRESHOLD_GHOST = 600
QLENGTH_CELL = 1200


class Port:
    def __init__(self, name, dp, speed="100G", fec="BF_FEC_TYP_NONE", peer_addr = None):
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

g_is_tofino = testutils.test_param_get("arch") == "tofino"
g_is_tofino2 = testutils.test_param_get("arch") == "tofino2"
assert g_is_tofino or g_is_tofino2

class Controller(BfRuntimeTest):
    def __init__(self):
        BfRuntimeTest.__init__(self)
        self.p4_name = p4_name
        
        self.ports = []
        self.ports.append(Port("1/0", 392, "100G", "BF_FEC_TYP_RS", "172.16.100.1"))
        self.ports.append(Port("2/0", 400, "100G", "BF_FEC_TYP_RS", "172.16.100.2"))
        self.ports.append(Port("9/0", 64, "100G", "BF_FEC_TYP_RS", "172.16.100.3"))
        self.ports.append(Port("10/0", 56, "100G", "BF_FEC_TYP_RS", "172.16.100.7"))
        self.ports.append(Port("17/0", 136, "100G", "BF_FEC_TYP_RS", "172.16.100.10"))
        self.ports.append(Port("18/0", 144, "100G", "BF_FEC_TYP_RS", "172.16.100.20"))
        
        self.inner_ports = []
        inner_ports = [424, 32, 168, 312, 320, 296] \
                    + [432, 24, 176, 288, 280, 264]
        for ip in inner_ports:
            self.inner_ports.append(Port("0/0", ip, "100G", "BF_FEC_TYP_RS", "0.0.0.0"))
        
    
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
        forward_table.info.key_field_annotation_add("hdr.ipv4.dst_addr", "ipv4")
        # for p in self.ports:
        #     self.safe_entry_add(
        #         forward_table,
        #     # forward_table.entry_add(
        #         self.target,
        #         [forward_table.make_key([gc.KeyTuple('$MATCH_PRIORITY', 10),
        #                                  gc.KeyTuple('hdr.ipv4.dst_addr', p.peer_addr, 0xFFFF),
        #                                  gc.KeyTuple('ig_intr_md.ingress_port', 0, 0)])],
        #         [forward_table.make_data([gc.DataTuple('port', p.dp),
        #                                   gc.DataTuple('qid', OQ_QID),
        #                                   gc.DataTuple('ingress_cos', 0)],
        #                                   'SwitchIngress.hit')])
        # spine leaf topology
        spine_pipeline = {
            'pipe_id': 2,
            'ports_low': [312, 320, 296],
            'ports_high': [288, 280, 264]
        }
        leaf_pipelines =[
            {
                'pipe_id': 3,
                'uplink_port_low': 424,
                'uplink_port_high': 432,
                'downlink_ports': self.ports[0:2]
            },
            {
                'pipe_id': 0,
                'uplink_port_low': 32,
                'uplink_port_high': 24,
                'downlink_ports': self.ports[2:4]
            },
            {
                'pipe_id': 1,
                'uplink_port_low': 168,
                'uplink_port_high': 176,
                'downlink_ports': self.ports[4:6]
            }
        ]
        
        for i in range(len(leaf_pipelines)):
            # leaf to spine (low)
            self.safe_entry_add(
                forward_table,
                self.target,
                [forward_table.make_key([gc.KeyTuple('$MATCH_PRIORITY', 5),
                                        gc.KeyTuple('hdr.ipv4.dst_addr', 0, 0),
                                        gc.KeyTuple('ig_intr_md.ingress_port', leaf_pipelines[i]['pipe_id']<<7, 0x180)])],
                [forward_table.make_data([gc.DataTuple('port', leaf_pipelines[i]['uplink_port_low']),
                                        gc.DataTuple('qid', OQ_QID),
                                        gc.DataTuple('ingress_cos', 0)],
                                        'SwitchIngress.hit')])
            
            for p in leaf_pipelines[i]['downlink_ports']:
                # leaf to itself
                self.safe_entry_add(
                    forward_table,
                    self.target,
                    [forward_table.make_key([gc.KeyTuple('$MATCH_PRIORITY', 1),
                                            gc.KeyTuple('hdr.ipv4.dst_addr', p.peer_addr, 0xFFFFFFFF),
                                            gc.KeyTuple('ig_intr_md.ingress_port', leaf_pipelines[i]['pipe_id']<<7, 0x180)])],
                    [forward_table.make_data([gc.DataTuple('port', p.dp),
                                            gc.DataTuple('qid', OQ_QID),
                                            gc.DataTuple('ingress_cos', 0)],
                                            'SwitchIngress.hit')])
                # spine to leaf (low)
                self.safe_entry_add(
                    forward_table, 
                    self.target,
                    [forward_table.make_key([gc.KeyTuple('$MATCH_PRIORITY', 5),
                                            gc.KeyTuple('hdr.ipv4.dst_addr', p.peer_addr, 0xFFFFFFFF),
                                            gc.KeyTuple('ig_intr_md.ingress_port', port_low, 0x1FF)])
                                            for port_low in spine_pipeline['ports_low']],
                    [forward_table.make_data([gc.DataTuple('port', spine_pipeline['ports_low'][i]),
                                            gc.DataTuple('qid', OQ_QID),
                                            gc.DataTuple('ingress_cos', 0)],
                                            'SwitchIngress.hit')
                                            for port_low in spine_pipeline['ports_low']])
                # spine to leaf (high)
                self.safe_entry_add(
                    forward_table, 
                    self.target,
                    [forward_table.make_key([gc.KeyTuple('$MATCH_PRIORITY', 5),
                                            gc.KeyTuple('hdr.ipv4.dst_addr', p.peer_addr, 0xFFFFFFFF),
                                            gc.KeyTuple('ig_intr_md.ingress_port', port_high, 0x1FF)])
                                            for port_high in spine_pipeline['ports_high']],
                    [forward_table.make_data([gc.DataTuple('port', spine_pipeline['ports_high'][i]),
                                            gc.DataTuple('qid', OQ_QID),
                                            gc.DataTuple('ingress_cos', 0)],
                                            'SwitchIngress.hit')
                                            for port_high in spine_pipeline['ports_high']])
            
        # Specify the route of specific flows
        # We only need to specify the first hop
        flows = [
            {
                'ingress_port': 392,
                'dst_addr': 0xAC10640A,
                'egress_port': 432
            },
            {
                'ingress_port': 400,
                'dst_addr': 0xAC10640A,
                'egress_port': 424
            },
            {
                'ingress_port': 64,
                'dst_addr': 0xAC10640A,
                'egress_port': 24
            },
            # victim flow
            {
                'ingress_port': 56,
                'dst_addr': 0xAC106414,
                'egress_port': 32
            }
        ]
        # the flows data pkts should go the same way with its ack pkts
        reverse_flows = [
            {
                'ingress_port': 136,
                'dst_addr': 0xAC106401,
                'egress_port': 176
            },
            {
                'ingress_port': 136,
                'dst_addr': 0xAC106402,
                'egress_port': 168
            },
            {
                'ingress_port': 136,
                'dst_addr': 0xAC106403,
                'egress_port': 176
            },
            # victim flow
            {
                'ingress_port': 144,
                'dst_addr': 0xAC106407,
                'egress_port': 168
            }
        ]
        for f in flows:
            self.safe_entry_add(
                forward_table,
                self.target,
                [forward_table.make_key([gc.KeyTuple('$MATCH_PRIORITY', 1),
                                        gc.KeyTuple('hdr.ipv4.dst_addr', f['dst_addr'], 0xFFFFFFFF),
                                        gc.KeyTuple('ig_intr_md.ingress_port', f['ingress_port'], 0x1FF)])],
                [forward_table.make_data([gc.DataTuple('port', f['egress_port']),
                                        gc.DataTuple('qid', OQ_QID),
                                        gc.DataTuple('ingress_cos', 0)],
                                        'SwitchIngress.hit')])
        for f in reverse_flows:
            self.safe_entry_add(
                forward_table,
                self.target,
                [forward_table.make_key([gc.KeyTuple('$MATCH_PRIORITY', 1),
                                        gc.KeyTuple('hdr.ipv4.dst_addr', f['dst_addr'], 0xFFFFFFFF),
                                        gc.KeyTuple('ig_intr_md.ingress_port', f['ingress_port'], 0x1FF)])],
                [forward_table.make_data([gc.DataTuple('port', f['egress_port']),
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