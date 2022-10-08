/*******************************************************************************
 * BAREFOOT NETWORKS CONFIDENTIAL & PROPRIETARY
 *
 * Copyright (c) 2019-present Barefoot Networks, Inc.
 *
 * All Rights Reserved.
 *
 * NOTICE: All information contained herein is, and remains the property of
 * Barefoot Networks, Inc. and its suppliers, if any. The intellectual and
 * technical concepts contained herein are proprietary to Barefoot Networks, Inc.
 * and its suppliers and may be covered by U.S. and Foreign Patents, patents in
 * process, and are protected by trade secret or copyright law.  Dissemination of
 * this information or reproduction of this material is strictly forbidden unless
 * prior written permission is obtained from Barefoot Networks, Inc.
 *
 * No warranty, explicit or implicit is provided, unless granted under a written
 * agreement with Barefoot Networks, Inc.
 *
 ******************************************************************************/

#include <core.p4>
#include <t2na.p4>

#include "common/headers.p4"
#include "common/util.p4"

#if __TARGET_TOFINO__ == 1
typedef bit<3> mirror_type_t;
#else
typedef bit<4> mirror_type_t;
#endif

struct headers_t {
    ethernet_h ethernet;
    arp_h arp;
    ipv4_h ipv4;
    tcp_h tcp;
}

struct ingress_metadata_t {}

struct egress_metadata_t {}

// ---------------------------------------------------------------------------
// Ingress parser
// ---------------------------------------------------------------------------
parser SwitchIngressParser(
        packet_in pkt,
        out headers_t hdr,
        out ingress_metadata_t ig_md,
        out ingress_intrinsic_metadata_t ig_intr_md) {

    TofinoIngressParser() tofino_parser;

    state start {
        tofino_parser.apply(pkt, ig_intr_md);
        transition parse_ethernet;
    }

    state parse_ethernet {
        pkt.extract(hdr.ethernet);
        transition select(hdr.ethernet.ether_type){
            ETHERTYPE_IPV4: parse_ipv4;
			ETHERTYPE_ARP: parse_arp;
            default: reject;
        }
    }

    state parse_ipv4 {
        pkt.extract(hdr.ipv4);
        transition parse_tcp;
    }

    state parse_tcp {
        pkt.extract(hdr.tcp);
        transition accept;
    }

    state parse_arp {
		pkt.extract(hdr.arp);
		transition accept;
	}
}

// ---------------------------------------------------------------------------
// Switch Ingress MAU
// ---------------------------------------------------------------------------
// ingress bloom filter, is able to set bloom filter's content and check whether hit
// only one action
control SwitchIngress(
        inout headers_t hdr,
        inout ingress_metadata_t ig_md,
        in ingress_intrinsic_metadata_t ig_intr_md,
        in ingress_intrinsic_metadata_from_parser_t ig_intr_prsr_md,
        inout ingress_intrinsic_metadata_for_deparser_t ig_intr_dprsr_md,
        inout ingress_intrinsic_metadata_for_tm_t ig_intr_tm_md) {

    action hit(PortId_t port, QueueId_t qid, bit<3> ingress_cos) {
        ig_intr_tm_md.ucast_egress_port = port;
        ig_intr_tm_md.qid = qid;
        ig_intr_tm_md.ingress_cos = ingress_cos;
    }

    action miss() {
        ig_intr_dprsr_md.drop_ctl = 0x1; // Drop packet.
    }

    table forward {
        key = {
            hdr.ipv4.dst_addr : ternary;
            ig_intr_md.ingress_port : ternary;
        }
        actions = {
            hit;
            miss;
        }
        const default_action = miss;
        size = 64;
    }

    action reply_arp(mac_addr_t reply_mac, bit<32> reply_ip){
        hdr.arp.dstMacAddr = hdr.arp.srcMacAddr;
        hdr.arp.dstIPAddr = hdr.arp.srcIPAddr;
        hdr.arp.srcMacAddr = reply_mac;
        hdr.arp.srcIPAddr = reply_ip;
        hdr.arp.opcode = 16w2;

        hdr.ethernet.dst_addr = hdr.ethernet.src_addr;
        hdr.ethernet.src_addr = reply_mac;
        ig_intr_tm_md.ucast_egress_port = ig_intr_md.ingress_port;
    }

    table arp_proxy {
        key = {
            hdr.arp.dstIPAddr : exact;
        }
        actions = {
            reply_arp;
            @defaultonly miss;
        }
        size = 64;
        const default_action = miss;
        const entries = {
            32w0xAC106401: reply_arp(48w0xec0d9abfdf75, 0xAC106401);
			// 32w0xAC106402: reply_arp(48w0xec0d9abfdd0d, 0xAC106402);
            32w0xAC106402: reply_arp(48w0xec0d9aa418ff, 0xAC106402);
            // Note that the 172.16.100.7 is the 609-3
            // We exchange the MAC here
            // 32w0xAC106403: reply_arp(48w0xec0d9abfdcb5, 0xAC106403);
			// 32w0xAC106407: reply_arp(48w0xec0d9abfdcbd, 0xAC106407);
            32w0xAC106403: reply_arp(48w0xec0d9abfdcbd, 0xAC106403);
			32w0xAC106407: reply_arp(48w0xec0d9abfdcb5, 0xAC106407);
			32w0xAC10640A: reply_arp(48w0xec0d9aa4190f, 0xAC10640A);
            32w0xAC106414: reply_arp(48w0x043f72c060e6, 0xAC106414);
		}
    }

    apply {
        if (hdr.arp.isValid()){
            arp_proxy.apply();
        }
        if (hdr.ipv4.isValid()) {
            forward.apply();
        }        
        // No need for egress processing, skip it and use empty controls for egress.
        // ig_intr_tm_md.bypass_egress = 1w1;
    }
}

// ---------------------------------------------------------------------------
// Ingress Deparser
// ---------------------------------------------------------------------------
control SwitchIngressDeparser(
        packet_out pkt,
        inout headers_t hdr,
        in ingress_metadata_t ig_md,
        in ingress_intrinsic_metadata_for_deparser_t ig_intr_dprsr_md) {

    apply {
        pkt.emit(hdr);
    }
}

// ---------------------------------------------------------------------------
// Egress parser
// ---------------------------------------------------------------------------
parser SwitchEgressParser(
        packet_in pkt,
        out headers_t hdr,
        out egress_metadata_t eg_md,
        out egress_intrinsic_metadata_t eg_intr_md) {

    TofinoEgressParser() tofino_parser; 

    state start {
        tofino_parser.apply(pkt, eg_intr_md);
        transition parse_ethernet;
    }

    state parse_ethernet {
        pkt.extract(hdr.ethernet);
        transition select(hdr.ethernet.ether_type){
            ETHERTYPE_IPV4: parse_ipv4;
			ETHERTYPE_ARP: parse_arp;
            default: reject;
        }
    }

    state parse_ipv4 {
        pkt.extract(hdr.ipv4);
        transition parse_tcp;
    }

    state parse_tcp {
        pkt.extract(hdr.tcp);
        transition accept;
    }

    state parse_arp {
		pkt.extract(hdr.arp);
		transition accept;
	}
}

control SwitchEgress(
        inout headers_t hdr,
        inout egress_metadata_t eg_md,
        in    egress_intrinsic_metadata_t                 eg_intr_md,
        in    egress_intrinsic_metadata_from_parser_t     eg_prsr_md,
        inout egress_intrinsic_metadata_for_deparser_t    eg_dprsr_md,
        inout egress_intrinsic_metadata_for_output_port_t eg_oport_md) {

    DirectRegister<bit<32>>() reg_max_queue_length;
    DirectRegisterAction<bit<32>, bit<32>>(reg_max_queue_length) regact_max_queue_length_set = {
        void apply(inout bit<32> val, out bit<32> read_value) {
            if (eg_intr_md.deq_qdepth > (bit<19>)val){
                val = (bit<32>)eg_intr_md.deq_qdepth;
            }
            read_value = val;
        }
    };
    action act_max_queue_length_set() {
        regact_max_queue_length_set.execute();
    }
    
    table tbl_max_queue_length {
        key = {
            eg_intr_md.egress_port : exact;
            eg_intr_md.egress_qid : exact;
        }
        actions = {
            act_max_queue_length_set;
        }
        size = 1024;      
        registers = reg_max_queue_length;
    }

    apply{
        tbl_max_queue_length.apply();
    }
}


// ---------------------------------------------------------------------------
// Egress Deparser
// ---------------------------------------------------------------------------
control SwitchEgressDeparser(
        packet_out pkt,
        inout headers_t hdr,
        in egress_metadata_t eg_md,
        in egress_intrinsic_metadata_for_deparser_t eg_dprsr_md) {

    Mirror() mirror;

    apply {
        pkt.emit(hdr);
    }
}

Pipeline(SwitchIngressParser(),
         SwitchIngress(),
         SwitchIngressDeparser(),
         SwitchEgressParser(),
         SwitchEgress(),
         SwitchEgressDeparser()) pipe;

Switch(pipe) main;
