# SPYGYM - Acesso remoto WireGuard por unidade
# Unidade: HeliÃ³polis | Codigo: 17 | Cidade: Sao Paulo/SP
# Mesmo padrao operacional da Homero thon, com faixa VPN dedicada por unidade para evitar conflito entre sites.
# Pendencias para revisar antes de aplicar: LAN_CIDR, DVR_IP

:local WGNAME "wg-spygym-17"
:local WGPORT 52017
:local WG_ROUTER_ADDR "10.99.17.1/24"
:local WG_CLIENT_ADDR "10.99.17.2/32"
:local LAN_CIDR "REVISAR_LAN_CIDR"
:local DVR_IP "REVISAR_DVR_IP"
:local CLIENTPUBKEY "PREENCHER_CHAVE_PUBLICA_CLIENTE"

/interface/wireguard
add name=$WGNAME listen-port=$WGPORT mtu=1420 comment="SPYGYM acesso remoto 17"

/ip/address
add address=$WG_ROUTER_ADDR interface=$WGNAME comment="SPYGYM WireGuard gateway 17"

/interface/wireguard/peers
add interface=$WGNAME public-key=$CLIENTPUBKEY allowed-address=$WG_CLIENT_ADDR persistent-keepalive=25 comment="SPYGYM cliente remoto 17"

/ip/firewall/filter
add chain=input action=accept protocol=udp dst-port=$WGPORT comment="SPYGYM WG 17 UDP"
add chain=forward action=accept src-address=10.99.17.2 dst-address=$DVR_IP comment="SPYGYM WG 17 -> DVR"
add chain=forward action=accept src-address=$DVR_IP dst-address=10.99.17.2 comment="SPYGYM DVR 17 -> WG"

# Opcional: liberar acesso da VPN a toda a LAN da unidade
# /ip/firewall/filter
# add chain=forward action=accept src-address=10.99.17.2 dst-address=$LAN_CIDR comment="SPYGYM WG 17 -> LAN"
# add chain=forward action=accept src-address=$LAN_CIDR dst-address=10.99.17.2 comment="SPYGYM LAN 17 -> WG"

# Opcional: NAT se o DVR/LAN nao devolverem trafego para o tunel
# /ip/firewall/nat
# add chain=srcnat action=masquerade src-address=10.99.17.2 dst-address=$DVR_IP comment="SPYGYM WG NAT 17"

# Depois de aplicar:
# 1. confirme a chave publica do MikroTik em /interface/wireguard/print detail
# 2. use a porta UDP 52017 no modem/roteador anterior, se existir
# 3. valide ping no DVR REVISAR_DVR_IP e a interface web do equipamento
