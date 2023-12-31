import toml
from utils import pairing
import ipaddress
import os
import jinja2

DO_SAVE = True

def main():
    # Reading the configuration file
    with open('config.toml', 'r') as f:
        config = toml.load(f)

    self_id: int = config['id']
    private_key: str = config['private_key']
    self_asn: int = config['asn']

    assert 0 < self_id <= 253, "Invalid id"

    # Ips
    ipv4 = ipaddress.IPv4Address("10.30.255.0") + self_id
    ipv6 = ipaddress.IPv6Address("fc00:ffff:30::") + self_id

    frr_peers = ""
    frr_rules = ""

    orion_network_conf: str = ""
    orion_wireguard_conf: str = ""
    orion_wireguard_conf += f"[Interface]\n"
    orion_wireguard_conf += f"Address = {ipv4}/24,{ipv6}/120\n"
    orion_wireguard_conf += f"PrivateKey = {private_key}\n"
    orion_wireguard_conf += f"Table = off\n"

    self_listening = 'listen' in config
    # If we need to listen, we simply add it to the wireguard config
    if self_listening:
        orion_wireguard_conf += f"ListenPort = {config['listen']}\n"

    groups = {}
    peers = []

    # For each peer we have
    for peer in config['peers']:
        peer_public_key: str = peer['public_key']
        peer_id: int = peer['id']
        peer_asn: int = peer['asn']

        # Name of the interface for the tunnel
        interface_name: str = f"orion{peer_id}"

        # We compute the interconnect id
        interconnect_id = pairing(peer_id, self_id)

        # All the Orion interconnect networks are in 172.30.0.0/15
        # From (172.30.0.0 - 172.31.255.255). We need a /15 network because the subnet id
        # is 16 bits long and we need anoter bit for two computers (/31 network point-to-point)
        subnet_v4 = ipaddress.IPv4Address(
            "172.30.0.0") + (interconnect_id << 1)
        subnet_v6 = ipaddress.IPv6Address(
            "fc00:ffff:30:1::") + (interconnect_id << 1)

        # To ensure consistency, we choose the peer with the highest id for the higest ip
        self_address_v4 = subnet_v4 if peer_id > self_id else subnet_v4 + 1
        self_address_v6 = subnet_v6 if peer_id > self_id else subnet_v6 + 1

        other_address_v4 = subnet_v4 + 1 if peer_id > self_id else subnet_v4

        mtu = 1368

        peer_ipv4 = ipaddress.IPv4Address("10.30.255.0") + peer_id
        # peer_ipv6 = ipaddress.IPv6Address("fc00:ffff:30::") + peer_id

        if not (peer_asn in groups):
            groups[peer_asn] = {
                'asn': peer_asn
            }

        peers.append({
            'address': other_address_v4,
            'asn': peer_asn
        })

        orion_network_conf += f"auto {interface_name}\n"
        orion_network_conf += f"iface {interface_name} inet tunnel\n"
        orion_network_conf += f"	mode gre\n"
        orion_network_conf += f"	address {self_address_v4}\n"
        orion_network_conf += f"	netmask 255.255.255.254\n"
        orion_network_conf += f"	local 10.30.255.{self_id}\n"
        orion_network_conf += f"	endpoint 10.30.255.{peer_id}\n"
        orion_network_conf += f"	post-up ip link set dev {interface_name} group 2\n"
        orion_network_conf += f"	mtu {mtu}\n"

        orion_wireguard_conf += f"[Peer]\n"
        orion_wireguard_conf += f"PublicKey = {peer_public_key}\n"
        orion_wireguard_conf += f"AllowedIPs = {peer_ipv4}/32\n"
        orion_wireguard_conf += f"PersistentKeepalive = 25\n"

        if 'endpoint' in peer:
            orion_wireguard_conf += f"Endpoint = {peer['endpoint']}\n"
        elif not self_listening:
            raise TypeError(
                'Cannot connect to a peer without endpoint without being a listener')

    template = './templ/frr.conf'

    if os.path.exists('./templ/frr.user.conf'):
        template = './templ/frr.user.conf'

    env = jinja2.Environment()
    f = open(template, 'r')
    template = env.from_string(f.read(), {
        'asn': self_asn,
        'orion_id': self_id,
        'peers': peers,
        'groups': list(groups.values())
    })

    frr_config = template.render()

    if DO_SAVE:
        with open('/etc/frr/frr.conf', 'w') as frrconf:
            frrconf.truncate(0)
            frrconf.write(frr_config)
            frrconf.close()
        with open('/etc/network/interfaces.d/01-orion.conf', 'w') as networkfile:
            networkfile.truncate(0)
            networkfile.write(orion_network_conf)
            networkfile.close()

        with open('/etc/wireguard/orion.conf', 'w') as wireguard:
            wireguard.truncate(0)
            wireguard.write(orion_wireguard_conf)
            wireguard.close()
    else:
        print(frr_config)


if __name__ == "__main__":
    main()
