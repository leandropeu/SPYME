# Guia Passo a Passo de Implantacao OpenVPN

Este guia cobre, um a um, os pontos necessarios para o SPYGYM operar a rede das unidades:

1. `servidor OpenVPN na VPS`
2. `certificados e chaves`
3. `rotas das sub-redes das unidades`
4. `clientes OpenVPN nas unidades`
5. `cadastro dos ativos com uplink correto`

## 1. Servidor OpenVPN na VPS

Na VPS Ubuntu:

```bash
cd /opt/spygym
sudo bash scripts/bootstrap_openvpn_server_ubuntu.sh
```

Depois copie a configuracao base:

```bash
sudo cp deploy/openvpn-server.conf.example /etc/openvpn/server/spygym.conf
```

Edite:

```bash
sudo nano /etc/openvpn/server/spygym.conf
```

Acrescente estas linhas ao final:

```conf
client-config-dir /etc/openvpn/server/spygym/ccd
ccd-exclusive
```

Depois inclua as rotas geradas em `server-routes.conf`.

## 2. Certificados e chaves

Na VPS:

```bash
cd /opt/spygym
sudo bash scripts/create_openvpn_pki_ubuntu.sh
```

Para emitir um cliente por unidade:

```bash
cd /opt/spygym
sudo bash scripts/issue_openvpn_client_cert.sh 007-homero-thon
sudo bash scripts/issue_openvpn_client_cert.sh 008-portugal
```

Arquivos principais gerados:

- `ca.crt`
- `issued/server.crt`
- `private/server.key`
- `tls-crypt.key`
- um `crt/key` por unidade

## 3. Rotas das sub-redes das unidades

No cadastro da unidade, preencha:

- `Tipo de VPN = openvpn`
- `Host VPN = IP ou dominio da VPS`
- `Porta VPN = 1194`
- `Rede remota VPN = exemplo 10.7.251.0/24`
- `Usuario VPN = CN sugerido do cliente`

Depois gere os artefatos:

```bash
cd /opt/spygym
py -3 scripts/generate_openvpn_routing_artifacts.py
```

Saidas:

- `deploy/openvpn-routing/server-routes.conf`
- `deploy/openvpn-routing/ccd/<cliente>`
- `deploy/openvpn-routing/openvpn-routing-inventory.csv`

Copie os CCDs para:

```bash
sudo cp deploy/openvpn-routing/ccd/* /etc/openvpn/server/spygym/ccd/
```

E aplique as rotas no `server.conf`.

Exemplo:

```conf
route 10.7.251.0 255.255.255.0
route 10.8.10.0 255.255.255.0
```

## 4. Clientes OpenVPN nas unidades

Gere os perfis base:

```bash
cd /opt/spygym
py -3 scripts/generate_openvpn_unit_profiles.py
```

Para cada unidade:

1. Abra o `.ovpn` correspondente em `deploy/openvpn-units`
2. Troque os placeholders:
   - `COLE_A_CA_AQUI`
   - `COLE_O_CERTIFICADO_DO_CLIENTE_AQUI`
   - `COLE_A_CHAVE_DO_CLIENTE_AQUI`
   - `COLE_A_CHAVE_TLS_CRYPT_AQUI`

Ou gere tudo automaticamente:

```bash
cd /opt/spygym
python3 scripts/build_openvpn_client_bundles.py
```

### Em unidade com MikroTik

Recomendacao: use o MikroTik como cliente principal da VPN.

Depois da VPN subir, crie rota de saida e firewall liberando acesso da VPS para:

- `8291` WinBox
- `22` SSH
- `80/443` Web
- `3389` RDP
- `554` RTSP

### Em unidade sem MikroTik

Use:

- roteador da operadora com cliente OpenVPN, se suportar
- ou um mini PC/PC local com OpenVPN e rotas para a rede interna

## 5. Cadastro dos ativos com uplink correto

Use a aba `Ativos de rede` no sistema ou importe em lote.

Template CSV:

- [network-assets-import-template.csv](/C:/Users/Admin/X/SPYGYM/deploy/network-assets-import-template.csv)

Importacao:

```bash
cd /opt/spygym
py -3 scripts/import_network_assets_from_csv.py
```

Ou informe outro arquivo:

```bash
py -3 scripts/import_network_assets_from_csv.py C:\caminho\meus-ativos.csv
```

### Como modelar o uplink

Cadastre nesta ordem:

1. `roteador operadora`
2. `mikrotik`
3. `switch`
4. `access point`
5. `catraca`
6. `facial`
7. `computador`
8. `dvr`, `nvr`, `alarme`

No campo `Ativo pai / uplink`:

- MikroTik aponta para o roteador da operadora, se existir
- switch aponta para o MikroTik
- AP, facial, catraca e PC apontam para o switch ou MikroTik
- DVR e NVR apontam para o switch ou MikroTik

Assim o mapa fica fiel e o offline em vermelho aparece no ponto certo da cadeia.

## 6. Subindo o servico

Quando tudo estiver pronto:

```bash
sudo systemctl enable openvpn-server@spygym
sudo systemctl restart openvpn-server@spygym
sudo systemctl status openvpn-server@spygym
```

## 7. Testes finais

Na VPS:

```bash
ip a
ip route
ping 10.7.251.1
curl -k https://10.7.251.1
```

No SPYGYM:

1. rodar monitoramento
2. abrir `Ativos de rede`
3. testar um MikroTik
4. testar um computador por RDP
5. testar um DVR
6. verificar mapa e status offline
