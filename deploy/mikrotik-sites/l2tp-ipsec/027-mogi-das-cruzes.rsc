# SPYGYM - Acesso remoto L2TP/IPsec por unidade
# Unidade: Mogi das Cruzes | Codigo: 27 | Cidade: Mogi das Cruzes/SP
# Alternativa compativel ao mesmo padrao operacional da Homero thon.
# Pendencias para revisar antes de aplicar: LAN_CIDR, DVR_IP

:local WAN_IF "ether1"
:local LAN_CIDR "REVISAR_LAN_CIDR"
:local DVR_IP "REVISAR_DVR_IP"
:local VPN_POOL_NAME "spygym-pool-27"
:local VPN_PROFILE "spygym-profile-27"
:local VPN_USER "spygym27"
:local VPN_PASS "PREENCHER_SENHA_FORTE"
:local IPSEC_SECRET "PREENCHER_SEGREDO_IPSEC"

/ip cloud
set ddns-enabled=yes update-time=yes

/ip pool
add name=$VPN_POOL_NAME ranges=10.99.27.10-10.99.27.20

/ppp profile
add name=$VPN_PROFILE local-address=10.99.27.1 remote-address=$VPN_POOL_NAME dns-server=1.1.1.1,8.8.8.8 use-encryption=required only-one=yes change-tcp-mss=yes

/ppp secret
add name=$VPN_USER password=$VPN_PASS service=l2tp profile=$VPN_PROFILE

/interface l2tp-server server
set enabled=yes authentication=mschap2 default-profile=$VPN_PROFILE use-ipsec=required ipsec-secret=$IPSEC_SECRET

/ip/firewall/filter
add chain=input action=accept in-interface=$WAN_IF protocol=udp dst-port=500,4500 comment="SPYGYM IPsec 27"
add chain=input action=accept in-interface=$WAN_IF protocol=ipsec-esp comment="SPYGYM ESP 27"
add chain=input action=accept in-interface=$WAN_IF ipsec-policy=in,ipsec protocol=udp dst-port=1701 comment="SPYGYM L2TP 27 somente em IPsec"
add chain=input action=drop in-interface=$WAN_IF protocol=udp dst-port=1701 comment="SPYGYM bloqueia L2TP sem IPsec 27"

/ip/firewall/filter
add chain=forward action=accept src-address=10.99.27.0/24 dst-address=$DVR_IP comment="SPYGYM VPN 27 -> DVR"
add chain=forward action=accept src-address=$DVR_IP dst-address=10.99.27.0/24 comment="SPYGYM DVR 27 -> VPN"

# Opcional: liberar acesso da VPN a toda a LAN da unidade
# /ip/firewall/filter
# add chain=forward action=accept src-address=10.99.27.0/24 dst-address=$LAN_CIDR comment="SPYGYM VPN 27 -> LAN"
# add chain=forward action=accept src-address=$LAN_CIDR dst-address=10.99.27.0/24 comment="SPYGYM LAN 27 -> VPN"

# Opcional: NAT se o DVR/LAN nao devolverem trafego para a VPN
# /ip/firewall/nat
# add chain=srcnat action=masquerade src-address=10.99.27.0/24 dst-address=$DVR_IP comment="SPYGYM NAT 27"
