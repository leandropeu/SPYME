# Guia de VPN Windows e VPS

Este guia resume o caminho recomendado para o SPYGYM funcionar como ponte de acesso tecnico entre a central e os equipamentos da unidade.

## 1. Modelo recomendado

- cadastrar cada unidade no SPYGYM com seus parametros de VPN
- cadastrar cada DVR/NVR/camera/roteador/AP/maquina em `Ativos de rede`
- nunca expor DVR ou roteador direto na internet
- usar VPN ate a rede interna da unidade
- acessar equipamentos sempre pelo IP interno da LAN

## 2. Como preencher no SPYGYM

Em `Unidades`:

- `Tipo de VPN`: `l2tp-ipsec` ou `wireguard`
- `Host VPN`: IP publico ou DNS do site
- `Porta VPN`: normalmente `500/4500` no L2TP/IPsec ou `51820` no WireGuard
- `Usuario VPN`
- `Senha VPN`
- `PSK/IPsec` quando a unidade usar L2TP/IPsec
- `Rede remota VPN`: ex. `10.0.7.0/24`
- `Nome da conexao Windows`: ex. `SPYGYM Unidade Centro`

Em `Ativos de rede`:

- registrar um item para cada DVR, NVR, camera IP, access point, roteador e maquina
- definir `Host/IP` interno do equipamento
- definir `Protocolo`: `https`, `ssh`, `rdp`, `rtsp`, `winbox`
- salvar usuario e senha do equipamento quando houver

## 3. Configurar VPN nativa do Windows

### L2TP/IPsec

1. Abra `Configuracoes > Rede e Internet > VPN`.
2. Clique em `Adicionar VPN`.
3. Provedor: `Windows (interno)`.
4. Nome da conexao: use o mesmo nome salvo no SPYGYM.
5. Nome ou endereco do servidor: IP publico ou DNS da unidade.
6. Tipo de VPN: `L2TP/IPsec com chave pre-compartilhada`.
7. Chave pre-compartilhada: use o `PSK/IPsec`.
8. Tipo de informacao de entrada: `Nome de usuario e senha`.
9. Preencha usuario e senha.
10. Salve.

Depois:

1. Abra `Alterar opcoes de adaptador`.
2. Clique com o botao direito na VPN e entre em `Propriedades`.
3. Na aba `Rede`, deixe IPv4 habilitado.
4. Em `IPv4 > Avancado`, marque ou desmarque `Usar gateway padrao na rede remota` conforme o seu cenario:
   - marque se todo o trafego deve passar pela unidade
   - desmarque se quiser split tunnel
5. Se usar split tunnel, adicione rota para a rede da unidade com:

```powershell
route -p add 10.0.7.0 mask 255.255.255.0 10.99.99.1
```

Substitua:

- `10.0.7.0` pela rede da unidade
- `10.99.99.1` pelo gateway entregue pela VPN

### NAT-T para L2TP/IPsec

Em alguns cenarios do Windows atras de NAT, pode ser necessario habilitar NAT-T:

```powershell
reg add HKLM\SYSTEM\CurrentControlSet\Services\PolicyAgent /v AssumeUDPEncapsulationContextOnSendRule /t REG_DWORD /d 2 /f
```

Depois reinicie o Windows.

## 4. Validacao

Depois de conectar a VPN:

```powershell
ping 10.0.7.251
Test-NetConnection 10.0.7.251 -Port 80
Test-NetConnection 10.0.7.251 -Port 554
```

Se responder:

- abra o DVR no navegador
- rode `Checar` no SPYGYM
- rode `Sincronizar cameras`
- valide `Ativos de rede` copiando o destino de conexao

## 5. VPS

Para publicar em VPS, o caminho recomendado e:

- VPS Linux com Docker e Nginx
- backend FastAPI atras de proxy reverso HTTPS
- frontend buildado e servido pelo Nginx
- volume persistente para `backend/data`

### Estrutura esperada

Se voce vai subir em:

- `192.252.231.6`
- caminho remoto informado: `/root/Documents/CUNHADO/SPYGYM`

entao a estrutura final deve ficar parecida com:

```text
/root/Documents/CUNHADO/SPYGYM/
  backend/
  frontend/
  deploy/
  docs/
```

### Dados que ainda faltam para eu configurar de forma remota

Para eu configurar a VPS de verdade, ainda preciso de:

- forma real de acesso SSH: senha ou chave privada
- confirmar se o caminho correto e Linux mesmo, porque o texto `ip: 192.252.231.6/root/...` mistura host e path
- dominio ou subdominio publico
- certificado TLS desejado
- quais portas a VPS pode expor

### Exemplo de acesso SSH

Use este formato:

```bash
ssh root@192.252.231.6
cd /root/Documents/CUNHADO/SPYGYM
```

Se preferir outro usuario:

```bash
ssh spygym@192.252.231.6
```

## 6. Enderecos recomendados

- URL publica do sistema: `https://spygym.seudominio.com`
- API: `https://spygym.seudominio.com/api`
- WebSocket: `wss://spygym.seudominio.com/ws`

Na rede da unidade, manter enderecos internos como:

- DVR/NVR: `10.x.x.x`
- roteadores e APs: `10.x.x.x`
- maquinas Windows: `10.x.x.x`

## 7. Observacao importante

Eu nao consigo configurar a VPN do Windows da sua maquina nem entrar na VPS sozinho sem as credenciais reais e sem liberacao explicita de acesso remoto. O que eu deixei pronto aqui foi a aplicacao para armazenar e operar esses acessos com mais organizacao e seguranca.
