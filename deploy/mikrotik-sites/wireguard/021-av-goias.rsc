# SPYGYM - Acesso remoto WireGuard por unidade
# Unidade: Av Goias | Codigo: 21 | Cidade: Sao Caetano do Sul/SP
# Mesmo padrao operacional da Homero thon, com faixa VPN dedicada por unidade para evitar conflito entre sites.
# Pendencias para revisar antes de aplicar: LAN_CIDR, DVR_IP

:local WGNAME "wg-spygym-21"
:local WGPORT 52021
:local WG_ROUTER_ADDR "10.99.21.1/24"
:local WG_CLIENT_ADDR "10.99.21.2/32"
:local LAN_CIDR "REVISAR_LAN_CIDR"
:local DVR_IP "REVISAR_DVR_IP"
:local CLIENTPUBKEY "PREENCHER_CHAVE_PUBLICA_CLIENTE"

/interface/wireguard
add name=$WGNAME listen-port=$WGPORT mtu=1420 comment="SPYGYM acesso remoto 21"

/ip/address
add address=$WG_ROUTER_ADDR interface=$WGNAME comment="SPYGYM WireGuard gateway 21"

/interface/wireguard/peers
add interface=$WGNAME public-key=$CLIENTPUBKEY allowed-address=$WG_CLIENT_ADDR persistent-keepalive=25 comment="SPYGYM cliente remoto 21"

/ip/firewall/filter
add chain=input action=accept protocol=udp dst-port=$WGPORT comment="SPYGYM WG 21 UDP"
add chain=forward action=accept src-address=10.99.21.2 dst-address=$DVR_IP comment="SPYGYM WG 21 -> DVR"
add chain=forward action=accept src-address=$DVR_IP dst-address=10.99.21.2 comment="SPYGYM DVR 21 -> WG"

# Opcional: liberar acesso da VPN a toda a LAN da unidade
# /ip/firewall/filter
# add chain=forward action=accept src-address=10.99.21.2 dst-address=$LAN_CIDR comment="SPYGYM WG 21 -> LAN"
# add chain=forward action=accept src-address=$LAN_CIDR dst-address=10.99.21.2 comment="SPYGYM LAN 21 -> WG"

# Opcional: NAT se o DVR/LAN nao devolverem trafego para o tunel
# /ip/firewall/nat
# add chain=srcnat action=masquerade src-address=10.99.21.2 dst-address=$DVR_IP comment="SPYGYM WG NAT 21"

# Depois de aplicar:
# 1. confirme a chave publica do MikroTik em /interface/wireguard/print detail
# 2. use a porta UDP 52021 no modem/roteador anterior, se existir
# 3. valide ping no DVR REVISAR_DVR_IP e a interface web do equipamento
