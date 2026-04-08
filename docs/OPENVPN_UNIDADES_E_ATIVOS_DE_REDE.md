# OpenVPN para unidades e ativos de rede

Este fluxo foi pensado para o SPYGYM acessar, a partir da VPS:

- `MikroTiks`
- `Access Points`
- `catracas`
- `faciais`
- `roteadores atras do MikroTik`
- `roteadores da operadora`
- `computadores por RDP`
- `DVRs`, `NVRs`, `cameras` e `alarmes`

## Desenho recomendado

```text
Operador -> VPS SPYGYM -> OpenVPN -> Unidade -> MikroTik/roteador -> ativos internos
```

Quando a unidade nao tiver MikroTik:

```text
Operador -> VPS SPYGYM -> OpenVPN -> roteador operadora -> ativos internos
```

## Estrategia pratica

1. A VPS concentra o `OpenVPN Server`.
2. Cada unidade entra como cliente `OpenVPN`.
3. O SPYGYM usa o cadastro da unidade para guardar:
   - `vpn_type`
   - `vpn_host`
   - `vpn_port`
   - `vpn_username`
   - `vpn_network_cidr`
4. Cada equipamento interno entra em `Ativos de rede`.
5. O campo `Ativo pai / uplink` desenha o mapa da unidade.

## Ordem sugerida de cadastro

1. `Roteador operadora` ou `MikroTik`
2. `Switch`
3. `Access Points`
4. `catracas` e `faciais`
5. `computadores`
6. `DVRs`, `NVRs`, `alarmes`

## Protocolos tecnicos suportados no cadastro

- `HTTPS`
- `HTTP`
- `SSH`
- `RDP`
- `WinBox`
- `RTSP`

## Templates no projeto

- servidor OpenVPN: [openvpn-server.conf.example](/C:/Users/Admin/X/SPYGYM/deploy/openvpn-server.conf.example)
- cliente base por unidade: [openvpn-client-unit.ovpn.example](/C:/Users/Admin/X/SPYGYM/deploy/openvpn-client-unit.ovpn.example)
- gerador de perfis: [generate_openvpn_unit_profiles.py](/C:/Users/Admin/X/SPYGYM/scripts/generate_openvpn_unit_profiles.py)
- gerador de rotas e CCD: [generate_openvpn_routing_artifacts.py](/C:/Users/Admin/X/SPYGYM/scripts/generate_openvpn_routing_artifacts.py)
- gerador de bundles finais `.ovpn`: [build_openvpn_client_bundles.py](/C:/Users/Admin/X/SPYGYM/scripts/build_openvpn_client_bundles.py)
- importador de ativos: [import_network_assets_from_csv.py](/C:/Users/Admin/X/SPYGYM/scripts/import_network_assets_from_csv.py)

## Geracao de perfis por unidade

Execute:

```powershell
py -3 scripts\generate_openvpn_unit_profiles.py
```

Saida:

- pasta `deploy/openvpn-units`
- um `.ovpn` por unidade
- inventario `openvpn-units-inventory.csv`

## Mapa e status offline

A aba `Ativos de rede` agora:

- mostra o mapa da unidade por hierarquia
- destaca ativos offline em vermelho
- permite copiar acessos tecnicos
- valida por teste manual ou monitoramento automatico

## Observacao importante

O OpenVPN resolve o caminho ate a unidade, mas o acesso real continua dependendo de:

- rota correta ate a sub-rede interna
- firewall liberando portas
- credenciais corretas dos equipamentos
- cadastro correto do `host`, `porta`, `protocolo` e `uplink`
