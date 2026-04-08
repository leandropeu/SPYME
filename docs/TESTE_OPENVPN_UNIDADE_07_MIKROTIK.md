# Teste OpenVPN da Unidade 07 no MikroTik

Este roteiro valida a primeira unidade antes de replicar o modelo para as demais.

## Arquivos gerados

Na VPS:

- `/root/Documents/CUNHADO/spygym/deploy/deploy/openvpn-bundles/07-homero-thon.ovpn`
- `/root/Documents/CUNHADO/spygym/deploy/deploy/openvpn-routeros/07-homero-thon.ovpn`
- `/root/Documents/CUNHADO/spygym/deploy/deploy/openvpn-client-bundles-20260407.tar.gz`

Use preferencialmente o arquivo de `openvpn-routeros`.

## Pré-requisitos

- RouterOS 7 atualizado
- Unidade com saída para Internet
- Porta UDP `1194` liberada para a VPS `191.252.212.6`
- Rede local da unidade: `10.0.7.0/24`

## Importação no MikroTik

Envie o arquivo `07-homero-thon.ovpn` para o roteador.

No terminal do MikroTik:

```rsc
/interface/ovpn-client/import-ovpn-configuration file-name=07-homero-thon.ovpn
```

Depois confira a interface criada:

```rsc
/interface/ovpn-client/print detail
```

## Validação de conexão

Verifique se a interface ficou conectada:

```rsc
/interface/ovpn-client/monitor 0
```

Se a interface estiver `running`, valide tráfego:

```rsc
/ping 10.44.0.1
```

## Validação a partir da VPS

Na VPS:

```bash
ping -c 4 10.0.7.1
ping -c 4 10.0.7.2
ping -c 4 10.0.7.20
ping -c 4 10.0.7.30
```

## Validação no aplicativo

Quando a VPN estiver conectada:

1. Abrir a aba de ativos de rede.
2. Filtrar pela unidade `07`.
3. Rodar teste manual nos ativos.
4. Confirmar que o mapa mostra a cadeia:
   `Operadora -> MikroTik -> Switch -> Facial / PC`

## Próximo passo

Depois que a unidade `07` estiver estável:

1. preencher `vpn_network_cidr` das demais unidades
2. cadastrar os ativos de cada unidade
3. regenerar rotas e bundles
4. replicar o mesmo padrão de importação
