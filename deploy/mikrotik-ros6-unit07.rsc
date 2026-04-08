# Ajuste o nome do certificado do cliente se, apos o import, o RouterOS nao usar exatamente "07_0".
# Confira em: /certificate print

/interface ovpn-client
add name=spygym-ros6-07 connect-to=191.252.212.6 port=1195 mode=ip user=07 password=teste123 profile=default certificate=07_0 auth=sha1 cipher=aes256 add-default-route=no use-peer-dns=no disabled=no

# Validacao
# /interface ovpn-client print detail
# /interface ovpn-client monitor 0
# /ping 10.45.0.1
