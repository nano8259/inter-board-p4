pd-simple-sketch

pd SwitchIngress_ipv4_static add_entry SwitchIngress_hit hdr_ipv4_dst_addr 10.0.0.2 action_port 1 
pd SwitchIngress_ipv4_static add_entry SwitchIngress_hit hdr_ipv4_dst_addr 10.0.0.1 action_port 0

dump_table SwitchIngress_ipv4_static 
exit

