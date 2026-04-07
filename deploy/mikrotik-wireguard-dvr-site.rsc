# SPYGYM - Acesso remoto seguro ao DVR via WireGuard no MikroTik
# Premissas:
# - RouterOS v7+
# - DVR Hikvision na LAN: 10.0.7.251
# - Sub-rede interna do site: 10.0.7.0/24
# - Túnel WireGuard: 10.99.99.0/24
# - Porta UDP da VPN: 51820
#
# Antes de aplicar:
# 1. Gere a chave pública do notebook/cliente WireGuard
# 2. Substitua CLIENTPUBKEY abaixo
# 3. Se a LAN do site não for 10.0.7.0/24, ajuste LAN_CIDR
# 4. Se houver modem na frente do MikroTik, encaminhe UDP/51820 para ele

:local WGNAME "wg-dvr-remoto"
:local WGPORT 51820
:local WG_ROUTER_ADDR "10.99.99.1/24"
:local WG_CLIENT_ADDR "10.99.99.2/32"
:local LAN_CIDR "10.0.7.0/24"
:local DVR_IP "10.0.7.251"
:local CLIENTPUBKEY "OxTMQN00PjOzL67Wfwe8XMf0B10pWmSzEcFmE6nOckQ="

/interface/wireguard
add name=$WGNAME listen-port=$WGPORT mtu=1420 comment="SPYGYM acesso remoto DVR"

/ip/address
add address=$WG_ROUTER_ADDR interface=$WGNAME comment="SPYGYM WireGuard gateway"

/interface/wireguard/peers
add interface=$WGNAME public-key=$CLIENTPUBKEY allowed-address=$WG_CLIENT_ADDR persistent-keepalive=25 comment="SPYGYM cliente remoto"

# Entrada da VPN no roteador
/ip/firewall/filter
add chain=input action=accept protocol=udp dst-port=$WGPORT comment="SPYGYM WireGuard UDP"

# Tráfego entre o cliente VPN e o DVR
/ip/firewall/filter
add chain=forward action=accept src-address=10.99.99.2 dst-address=$DVR_IP comment="SPYGYM WG -> DVR"
add chain=forward action=accept src-address=$DVR_IP dst-address=10.99.99.2 comment="SPYGYM DVR -> WG"

# Opcional: liberar acesso do cliente VPN a toda a sub-rede do site
# /ip/firewall/filter
# add chain=forward action=accept src-address=10.99.99.2 dst-address=$LAN_CIDR comment="SPYGYM WG -> LAN"
# add chain=forward action=accept src-address=$LAN_CIDR dst-address=10.99.99.2 comment="SPYGYM LAN -> WG"

# Opcional: NAT apenas se o DVR ou a LAN não devolverem tráfego corretamente ao túnel
# /ip/firewall/nat
# add chain=srcnat action=masquerade src-address=10.99.99.2 dst-address=$DVR_IP comment="SPYGYM WG NAT para DVR"

# Depois de aplicar, confira a chave pública do MikroTik com:
# /interface/wireguard/print detail
