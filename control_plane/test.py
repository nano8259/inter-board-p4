#################################################################################################
# BAREFOOT NETWORKS CONFIDENTIAL & PROPRIETARY
#
# Copyright (c) 2019-present Barefoot Networks, Inc.
#
# All Rights Reserved.
#
# NOTICE: All information contained herein is, and remains the property of
# Barefoot Networks, Inc. and its suppliers, if any. The intellectual and
# technical concepts contained herein are proprietary to Barefoot Networks, Inc.
# and its suppliers and may be covered by U.S. and Foreign Patents, patents in
# process, and are protected by trade secret or copyright law.  Dissemination of
# this information or reproduction of this material is strictly forbidden unless
# prior written permission is obtained from Barefoot Networks, Inc.
#
# No warranty, explicit or implicit is provided, unless granted under a written
# agreement with Barefoot Networks, Inc.
#
################################################################################

import logging
import random

from ptf import config
from collections import namedtuple
import ptf.testutils as testutils
from bfruntime_client_base_tests import BfRuntimeTest
import bfrt_grpc.client as gc
import grpc

logger = logging.getLogger('Test')
if not len(logger.handlers):
    logger.addHandler(logging.StreamHandler())

swports = [13, 14]
# for device, port, ifname in config["interfaces"]:
#     swports.append(port)
#     swports.sort()

if swports == []:
    swports = list(range(9))


class SketchTest(BfRuntimeTest):
    """@brief Basic test for my sketch.
    """

    def setUp(self):
        client_id = 0
        p4_name = "simple_sketch"
        BfRuntimeTest.setUp(self, client_id, p4_name)

    def runTest(self):
        ig_port = swports[0]
        eg_port = swports[1]

        # Get bfrt_info and set it as part of the test
        bfrt_info = self.interface.bfrt_info_get("simple_sketch")

        forward_table = bfrt_info.table_get("SwitchIngress.ipv4_static")
        forward_table.info.key_field_annotation_add("hdr.ipv4.dst_addr", "ipv4")

        target = gc.Target(device_id=0, pipe_id=0xffff)
        # forward_table.entry_add(
        #     target,
        #     [forward_table.make_key([gc.KeyTuple('hdr.ipv4.dst_addr', "10.0.0.1")])],
        #     [forward_table.make_data([gc.DataTuple('port', eg_port)],'SwitchIngress.hit')]
        # )

        forward_table.entry_add(
            target,
            [forward_table.make_key([gc.KeyTuple('ig_intr_md.ingress_port', ig_port)])],
            [forward_table.make_data([gc.DataTuple('port', eg_port)],'SwitchIngress.hit')]
        )

        forward_table.entry_add(
            target,
            [forward_table.make_key([gc.KeyTuple('ig_intr_md.ingress_port', eg_port)])],
            [forward_table.make_data([gc.DataTuple('port', ig_port)],'SwitchIngress.hit')]
        )
        
        pkt = testutils.simple_tcp_packet(ip_dst="10.0.0.1")
        exp_pkt = pkt
        logger.info("Sending packet on port %d", ig_port)
        testutils.send_packet(self, ig_port, pkt)

        logger.info("Expecting packet on port %d", eg_port)  # Change this --> eg_port[0]
        testutils.verify_packets(self, exp_pkt, [eg_port])

        # check get
       
        resp = forward_table.entry_get(
            target,
            [forward_table.make_key([gc.KeyTuple('hdr.ipv4.dst_addr', "10.0.0.1")])],
            {"from_hw": True})

        data_dict = next(resp)[0].to_dict()
        recv_port = data_dict["port"]
        if (recv_port != eg_port):
            logger.error("Error! port sent = %s received port = %s", str(eg_port), str(recv_port))
            assert 0

        # delete all entries
 
        forward_table.entry_del(
            target,
            [forward_table.make_key([gc.KeyTuple('hdr.ipv4.dst_addr', "10.0.0.1")])])

        # send pkt and verify dropped
        pkt = testutils.simple_tcp_packet(ip_dst="10.0.0.1")
        logger.info("Sending packet on port %d", ig_port)
        testutils.send_packet(self, ig_port, pkt)
        logger.info("Packet is expected to get dropped.")
        testutils.verify_no_other_packets(self)
