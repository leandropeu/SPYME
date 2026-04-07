# Acesso Remoto ao DVR via MikroTik

Este guia prepara acesso remoto seguro ao DVR `10.0.7.251` usando `WireGuard` no MikroTik do site.

## Arquivos gerados

- `deploy/mikrotik-wireguard-dvr-site.rsc`
- `deploy/wireguard-client-spygym.conf.example`

## Premissas

- MikroTik com `RouterOS v7+`
- DVR na rede interna `10.0.7.0/24`
- DVR em `10.0.7.251`
- porta da VPN `UDP 51820`
- rede do túnel `10.99.99.0/24`

## Ordem recomendada

1. Instale o cliente WireGuard no notebook remoto.
2. Gere um par de chaves no cliente.
3. Copie a chave pública do cliente.
4. Edite `deploy/mikrotik-wireguard-dvr-site.rsc` e substitua `CLIENTPUBKEY`.
5. Cole o script no terminal do MikroTik.
6. Rode no MikroTik:

```rsc
/interface/wireguard/print detail
```

7. Copie a chave pública do MikroTik.
8. Edite `deploy/wireguard-client-spygym.conf.example` com:
   - chave privada do cliente
   - chave pública do MikroTik
   - IP público ou DDNS do site
9. Ative o túnel no cliente.
10. Teste conectividade:

```powershell
ping 10.99.99.1
ping 10.0.7.251
```

11. Teste acesso web:

```powershell
start http://10.0.7.251
```

12. Depois valide o SPYGYM novamente.

## Quando precisa de regra de firewall

Sim. Você precisa de:

- regra de `input` para receber `UDP 51820` no próprio MikroTik
- regra de `forward` para permitir tráfego do IP VPN até o DVR

Você normalmente **não** precisa expor o DVR na internet com `dst-nat`.

## Quando precisa de NAT adicional

Somente se:

- o DVR não responder de volta ao túnel
- a rota de retorno da LAN for problemática

Nesse caso, descomente a regra opcional de `masquerade` no arquivo `.rsc`.

## Se houver modem antes do MikroTik

Encaminhe `UDP 51820` no modem para o IP WAN do MikroTik.

## Se o site estiver atrás de CGNAT

Entradas vindas da internet podem não funcionar.

Alternativas:

- DDNS não resolve sozinho se houver CGNAT
- usar um túnel de saída para um VPS
- usar Tailscale/ZeroTier
- usar VPN site-to-cloud com endpoint público intermediário

## Validação final no SPYGYM

Depois da VPN ativa:

1. confirme que o DVR cadastrado está com host `10.0.7.251`
2. rode a checagem no SPYGYM
3. sincronize câmeras se necessário
4. teste snapshot da câmera 1
5. se quiser vídeo ao vivo no navegador, confirme também a instalação do `ffmpeg` no servidor do backend
