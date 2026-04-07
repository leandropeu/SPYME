# Acesso Remoto ao DVR com MikroTik sem WireGuard

Quando o MikroTik não suporta `WireGuard`, a alternativa mais prática e compatível é:

- `L2TP/IPsec` no MikroTik
- `DDNS do MikroTik` para localizar o site
- cliente `VPN nativo do Windows`

## Recomendação

Para o seu cenário, a melhor solução é:

1. habilitar `L2TP/IPsec` no MikroTik do site
2. habilitar `IP Cloud DDNS`
3. conectar o notebook por `VPN`
4. acessar o DVR pelo IP interno `10.0.7.251`

## O que NÃO resolve sozinho

### Nuvem do fabricante

Serve para acesso manual em app/web do fabricante, mas não é a melhor base para o SPYGYM.

Motivo:

- o SPYGYM trabalha melhor alcançando o DVR por IP interno
- snapshot, checagem, HLS e automações ficam mais previsíveis via VPN

### DDNS sozinho

Não cria túnel nem segurança.

O DDNS só dá um nome para o IP público do site. Ainda é preciso:

- `VPN`, ou
- abrir portas do DVR para internet, o que eu não recomendo

## Script pronto

Arquivo:

- `deploy/mikrotik-l2tp-ipsec-dvr-site.rsc`

## Como aplicar no MikroTik

1. Abra o arquivo `.rsc`
2. Edite estes campos:

- `WAN_IF`
- `VPN_USER`
- `VPN_PASS`
- `IPSEC_SECRET`

3. Cole o conteúdo no terminal do MikroTik

4. Depois rode:

```rsc
/ip cloud print
```

Anote:

- `dns-name`
- `public-address`

## Como configurar no Windows

No Windows:

1. Abra `Configurações`
2. Vá em `Rede e Internet`
3. Vá em `VPN`
4. Clique em `Adicionar VPN`

Preencha:

- `Provedor de VPN`: `Windows (interno)`
- `Nome da conexão`: `SPYGYM Site DVR`
- `Nome ou endereço do servidor`: `dns-name` do MikroTik
- `Tipo de VPN`: `L2TP/IPsec com chave pré-compartilhada`
- `Chave pré-compartilhada`: valor de `IPSEC_SECRET`
- `Tipo de informações de entrada`: `Nome de usuário e senha`
- `Nome de usuário`: valor de `VPN_USER`
- `Senha`: valor de `VPN_PASS`

Salve.

## Como conectar

1. Clique na VPN criada
2. Clique em `Conectar`

## Como testar

No PowerShell:

```powershell
ping 10.99.99.1
ping 10.0.7.251
```

Depois:

```powershell
start http://10.0.7.251
```

## Quando precisa abrir portas no modem/firewall da operadora

Se houver equipamento antes do MikroTik, encaminhe para o MikroTik:

- `UDP 500`
- `UDP 4500`
- `IP protocol ESP` se o ambiente exigir

Em muitos cenários com NAT-T, `UDP 500` e `UDP 4500` são os principais.

## Quando NÃO vai funcionar só com DDNS

Se o site estiver atrás de `CGNAT`, conexões vindas da internet podem não chegar ao MikroTik.

Nesses casos, as opções mais realistas são:

1. pedir IP público à operadora
2. usar um túnel de saída para VPS
3. usar uma malha overlay como Tailscale/ZeroTier em outro gateway compatível

## Validação final no SPYGYM

Depois da VPN ativa:

1. teste `http://10.0.7.251`
2. abra o SPYGYM
3. rode `Checar` no DVR
4. teste snapshot
5. depois teste visualização ao vivo

## Fontes oficiais usadas

- MikroTik L2TP: https://help.mikrotik.com/docs/display/ROS/L2TP
- MikroTik IPsec: https://help.mikrotik.com/docs/spaces/ROS/pages/11993097/IPsec
- MikroTik Cloud/DDNS: https://help.mikrotik.com/docs/spaces/ROS/pages/97779929/Cloud
