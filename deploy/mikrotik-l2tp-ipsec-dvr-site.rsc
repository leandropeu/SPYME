# SPYGYM - Acesso remoto seguro ao DVR via L2TP/IPsec no MikroTik
# Indicado para equipamentos sem WireGuard, tipicamente RouterOS v6/v7 antigos.
#
# Premissas:
# - DVR Hikvision na LAN: 10.0.7.251
# - LAN do site: 10.0.7.0/24
# - Pool VPN: 10.99.99.10-10.99.99.20
# - Cliente Windows usando VPN nativa L2TP/IPsec
#
# Edite antes de aplicar:
# - VPN_USER
# - VPN_PASS
# - IPSEC_SECRET

:local WAN_IF "ether1"
:local LAN_CIDR "10.0.7.0/24"
:local DVR_IP "10.0.7.251"
:local VPN_POOL_NAME "spygym-vpn-pool"
:local VPN_PROFILE "spygym-vpn-profile"
:local VPN_USER "spygymremoto"
:local VPN_PASS "TroqueEstaSenhaAgora"
:local IPSEC_SECRET "TroqueEstaChaveIPsecAgora"

# DDNS do MikroTik para localizar o site mesmo com IP dinâmico
/ip cloud
set ddns-enabled=yes update-time=yes

# Pool de IPs da VPN
/ip pool
add name=$VPN_POOL_NAME ranges=10.99.99.10-10.99.99.20

# Perfil PPP da VPN
/ppp profile
add name=$VPN_PROFILE local-address=10.99.99.1 remote-address=$VPN_POOL_NAME dns-server=1.1.1.1,8.8.8.8 use-encryption=required only-one=yes change-tcp-mss=yes

# Usuário do acesso remoto
/ppp secret
add name=$VPN_USER password=$VPN_PASS service=l2tp profile=$VPN_PROFILE

# L2TP/IPsec server
/interface l2tp-server server
set enabled=yes authentication=mschap2 default-profile=$VPN_PROFILE use-ipsec=required ipsec-secret=$IPSEC_SECRET

# Firewall de entrada para IPsec/L2TP
/ip firewall filter
add chain=input action=accept in-interface=$WAN_IF protocol=udp dst-port=500,4500 comment="SPYGYM IKE/IPsec"
add chain=input action=accept in-interface=$WAN_IF protocol=ipsec-esp comment="SPYGYM IPsec ESP"
add chain=input action=accept in-interface=$WAN_IF ipsec-policy=in,ipsec protocol=udp dst-port=1701 comment="SPYGYM L2TP somente dentro do IPsec"
add chain=input action=drop in-interface=$WAN_IF protocol=udp dst-port=1701 comment="SPYGYM bloqueia L2TP sem IPsec"

# Tráfego do cliente VPN apenas para o DVR
/ip firewall filter
add chain=forward action=accept src-address=10.99.99.0/24 dst-address=$DVR_IP comment="SPYGYM VPN -> DVR"
add chain=forward action=accept src-address=$DVR_IP dst-address=10.99.99.0/24 comment="SPYGYM DVR -> VPN"

# Opcional: acesso à LAN inteira do site
# /ip firewall filter
# add chain=forward action=accept src-address=10.99.99.0/24 dst-address=$LAN_CIDR comment="SPYGYM VPN -> LAN"
# add chain=forward action=accept src-address=$LAN_CIDR dst-address=10.99.99.0/24 comment="SPYGYM LAN -> VPN"

# Opcional: NAT se o DVR/LAN não devolver tráfego corretamente para a VPN
# /ip firewall nat
# add chain=srcnat action=masquerade src-address=10.99.99.0/24 dst-address=$DVR_IP comment="SPYGYM NAT opcional para DVR"

# Após aplicar:
# /ip cloud print
# Verifique o dns-name gerado e use-o no cliente Windows.
