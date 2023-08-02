## Build iptables rules

# Setting up ipsets
ipset add orion-routed 10.30.0.0/16
ipset add orion-routed 172.16.0.0/15

# Create a subchain
iptables -N ext-orion

# We accept incoming traffic from orion.
iptables -A ext-orion -m set --match-set orion-routed dst -j ACCEPT

# Allow conns that wera already established.
iptables -A ext-orion -m state --state ESTABLISHED -j ACCEPT
iptables -A ext-orion -j DROP

# We apply our rule to all the orion interfaces.
iptables -A FORWARD -j ext-orion
# We drop all other forwards.
iptables -A FORWARD -j DROP

# Traffic to orion that is not in an orion subnet should be nat translated
# This uses the 10.30.1.1 ip for all outoing connections.
iptables -t nat -A POSTROUTING \
    -m set ! --match-set orion-routed src \
    -m set --match-set orion-routed dst \
    -m devgroup --dst-group 2 \
    -j SNAT --to-source 10.30.1.1

# In order to deploy a service, you simply need to add theses two lines
# Where $LOCAL_IP is the local service you want to deploy
# And $ORION_IP is the external orion ip to deploy to.

# ipset add orion-routed $LOCAL_IP/32
# iptables -t nat -A PREROUTING \
#     -d $ORION_IP/32 \
#     -p tcp \
#     -j DNAT --to-destination $LOCAL_IP
