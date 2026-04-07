# SPYGYM - Acesso remoto L2TP/IPsec por unidade
# Unidade: Homero thon | Codigo: 07 | Cidade: Santo Andre/SP
# Alternativa compativel ao mesmo padrao operacional da Homero thon.
# Pronto para aplicar apos preencher usuario, senha e segredo IPsec.

:local WAN_IF "ether1"
:local LAN_CIDR "10.0.7.0/24"
:local DVR_IP "10.0.7.251"
:local VPN_POOL_NAME "spygym-pool-07"
:local VPN_PROFILE "spygym-profile-07"
:local VPN_USER "spygym07"
:local VPN_PASS "PREENCHER_SENHA_FORTE"
:local IPSEC_SECRET "PREENCHER_SEGREDO_IPSEC"

/ip cloud
set ddns-enabled=yes update-time=yes

/ip pool
add name=$VPN_POOL_NAME ranges=10.99.7.10-10.99.7.20

/ppp profile
add name=$VPN_PROFILE local-address=10.99.7.1 remote-address=$VPN_POOL_NAME dns-server=1.1.1.1,8.8.8.8 use-encryption=required only-one=yes change-tcp-mss=yes

/ppp secret
add name=$VPN_USER password=$VPN_PASS service=l2tp profile=$VPN_PROFILE

/interface l2tp-server server
set enabled=yes authentication=mschap2 default-profile=$VPN_PROFILE use-ipsec=required ipsec-secret=$IPSEC_SECRET

/ip/firewall/filter
add chain=input action=accept in-interface=$WAN_IF protocol=udp dst-port=500,4500 comment="SPYGYM IPsec 07"
add chain=input action=accept in-interface=$WAN_IF protocol=ipsec-esp comment="SPYGYM ESP 07"
add chain=input action=accept in-interface=$WAN_IF ipsec-policy=in,ipsec protocol=udp dst-port=1701 comment="SPYGYM L2TP 07 somente em IPsec"
add chain=input action=drop in-interface=$WAN_IF protocol=udp dst-port=1701 comment="SPYGYM bloqueia L2TP sem IPsec 07"

/ip/firewall/filter
add chain=forward action=accept src-address=10.99.7.0/24 dst-address=$DVR_IP comment="SPYGYM VPN 07 -> DVR"
add chain=forward action=accept src-address=$DVR_IP dst-address=10.99.7.0/24 comment="SPYGYM DVR 07 -> VPN"

# Opcional: liberar acesso da VPN a toda a LAN da unidade
# /ip/firewall/filter
# add chain=forward action=accept src-address=10.99.7.0/24 dst-address=$LAN_CIDR comment="SPYGYM VPN 07 -> LAN"
# add chain=forward action=accept src-address=$LAN_CIDR dst-address=10.99.7.0/24 comment="SPYGYM LAN 07 -> VPN"

# Opcional: NAT se o DVR/LAN nao devolverem trafego para a VPN
# /ip/firewall/nat
# add chain=srcnat action=masquerade src-address=10.99.7.0/24 dst-address=$DVR_IP comment="SPYGYM NAT 07"
