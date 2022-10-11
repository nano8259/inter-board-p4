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
    udp_h udp;
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
        transition select(hdr.ipv4.protocol){
            IP_PROTOCOLS_ICMP : parse_icmp;
            IP_PROTOCOLS_TCP: parse_tcp;
			IP_PROTOCOLS_UDP: parse_udp;
            default: reject;
        }
    }

    state parse_tcp {
        pkt.extract(hdr.tcp);
        transition accept;
    }

    state parse_udp {
        pkt.extract(hdr.udp);
        transition accept;
    }
    
    state parse_icmp {
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
        size = 1024;
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
    }

    DirectRegister<bit<32>>() reg_ig_packet_count;
    DirectRegisterAction<bit<32>, bit<32>>(reg_ig_packet_count) regact_ig_packet_count_inc = {
        void apply(inout bit<32> val) {
            val = val + 1;
        }
    };
    action act_ig_packet_count_inc() {
        regact_ig_packet_count_inc.execute();
    }
    
    table tbl_ig_packet_count {
        key = {
            ig_intr_md.ingress_port : exact;
            hdr.ipv4.dst_addr : exact;
        }
        actions = {
            act_ig_packet_count_inc;
        }
        size = 1024;      
        registers = reg_ig_packet_count;
    }

    apply {
        if (hdr.arp.isValid()){
            arp_proxy.apply();
        }
        if (hdr.ipv4.isValid()) {
            forward.apply();
        }
        if (hdr.udp.isValid()){
            tbl_ig_packet_count.apply();
        }
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
        transition select(hdr.ipv4.protocol){
            IP_PROTOCOLS_ICMP : parse_icmp;
            IP_PROTOCOLS_TCP: parse_tcp;
			IP_PROTOCOLS_UDP: parse_udp;
            default: reject;
        }
    }

    state parse_tcp {
        pkt.extract(hdr.tcp);
        transition accept;
    }

    state parse_udp {
        pkt.extract(hdr.udp);
        transition accept;
    }
    
    state parse_icmp {
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

    DirectRegister<bit<32>>() reg_eg_packet_count;
    DirectRegisterAction<bit<32>, bit<32>>(reg_eg_packet_count) regact_eg_packet_count_inc = {
        void apply(inout bit<32> val) {
            val = val + 1;
        }
    };
    action act_eg_packet_count_inc() {
        regact_eg_packet_count_inc.execute();
    }
    
    table tbl_eg_packet_count {
        key = {
            eg_intr_md.egress_port : exact;
            hdr.ipv4.dst_addr : exact;
        }
        actions = {
            act_eg_packet_count_inc;
        }
        size = 1024;
        registers = reg_eg_packet_count;
    }

    apply{
        tbl_max_queue_length.apply();
        tbl_eg_packet_count.apply();
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
