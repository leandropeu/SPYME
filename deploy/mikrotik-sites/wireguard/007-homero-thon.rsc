# SPYGYM - Acesso remoto WireGuard por unidade
# Unidade: Homero thon | Codigo: 07 | Cidade: Santo Andre/SP
# Mesmo padrao operacional da Homero thon, com faixa VPN dedicada por unidade para evitar conflito entre sites.
# Pronto para aplicar assim que a chave publica do cliente for informada.

:local WGNAME "wg-spygym-07"
:local WGPORT 52007
:local WG_ROUTER_ADDR "10.99.7.1/24"
:local WG_CLIENT_ADDR "10.99.7.2/32"
:local LAN_CIDR "10.0.7.0/24"
:local DVR_IP "10.0.7.251"
:local CLIENTPUBKEY "PREENCHER_CHAVE_PUBLICA_CLIENTE"

/interface/wireguard
add name=$WGNAME listen-port=$WGPORT mtu=1420 comment="SPYGYM acesso remoto 07"

/ip/address
add address=$WG_ROUTER_ADDR interface=$WGNAME comment="SPYGYM WireGuard gateway 07"

/interface/wireguard/peers
add interface=$WGNAME public-key=$CLIENTPUBKEY allowed-address=$WG_CLIENT_ADDR persistent-keepalive=25 comment="SPYGYM cliente remoto 07"

/ip/firewall/filter
add chain=input action=accept protocol=udp dst-port=$WGPORT comment="SPYGYM WG 07 UDP"
add chain=forward action=accept src-address=10.99.7.2 dst-address=$DVR_IP comment="SPYGYM WG 07 -> DVR"
add chain=forward action=accept src-address=$DVR_IP dst-address=10.99.7.2 comment="SPYGYM DVR 07 -> WG"

# Opcional: liberar acesso da VPN a toda a LAN da unidade
# /ip/firewall/filter
# add chain=forward action=accept src-address=10.99.7.2 dst-address=$LAN_CIDR comment="SPYGYM WG 07 -> LAN"
# add chain=forward action=accept src-address=$LAN_CIDR dst-address=10.99.7.2 comment="SPYGYM LAN 07 -> WG"

# Opcional: NAT se o DVR/LAN nao devolverem trafego para o tunel
# /ip/firewall/nat
# add chain=srcnat action=masquerade src-address=10.99.7.2 dst-address=$DVR_IP comment="SPYGYM WG NAT 07"

# Depois de aplicar:
# 1. confirme a chave publica do MikroTik em /interface/wireguard/print detail
# 2. use a porta UDP 52007 no modem/roteador anterior, se existir
# 3. valide ping no DVR 10.0.7.251 e a interface web do equipamento
