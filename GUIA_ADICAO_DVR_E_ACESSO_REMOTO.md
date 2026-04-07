# Guia de Adição de DVR e Acesso Remoto no SPYGYM

Este documento reúne o passo a passo para:

- cadastrar um novo DVR no SPYGYM
- preparar rede, firewall e roteador da operadora
- configurar VPN quando o DVR está fora da rede da máquina
- validar visualização ao vivo, snapshot e reprodução
- usar o sistema em outra máquina, quando necessário

## 1. O que é necessário antes de começar

Tenha em mãos:

- nome da unidade no SPYGYM
- nome do DVR
- fabricante: `hikvision` ou `intelbras`
- IP interno do DVR na LAN do site
- porta HTTP/HTTPS do DVR
- usuário e senha do DVR
- quantidade máxima de canais do equipamento
- informação sobre a rede do site:
  - faixa LAN, por exemplo `10.0.7.0/24`
  - IP do DVR, por exemplo `10.0.7.251`
  - existência de MikroTik no site
  - existência de modem/roteador da operadora antes do MikroTik

## 2. O que precisa existir na máquina

Para a máquina que vai rodar o SPYGYM completo:

- Windows com Python 3 instalado
- Node.js com `npm`
- `ffmpeg` instalado
- acesso à API e ao frontend do SPYGYM
- VPN ativa até a rede do site, quando o DVR não estiver na mesma rede

Checklist local:

- backend no ar: `http://127.0.0.1:8010/api/health`
- frontend no ar: `http://127.0.0.1:5174`
- `ffmpeg` instalado
- VPN conectada, se o DVR estiver fora da rede local

Observação:

- o `ffmpeg` é obrigatório para o modo `Ao vivo` no navegador
- se o DVR entregar stream corrompido, verde ou inválido, o app não conseguirá reproduzir corretamente até corrigir o stream no próprio DVR

## 3. Cadastro do DVR no SPYGYM

Na tela de DVRs, preencher:

- `Unidade`
- `Nome do DVR`
- `Fabricante`
- `Host/IP`
- `Porta`
- `Protocolo`
- `Usuário`
- `Senha`
- `Canais`

Regra importante:

- o campo `Canais` representa a capacidade do equipamento
- ele não significa que todos os canais possuem câmera física instalada

Depois do cadastro:

1. salvar o DVR
2. clicar em `Checar`
3. clicar em `Sincronizar câmeras`

Comportamento atual do sistema:

- a sincronização usa a capacidade do DVR como limite máximo
- mas só mantém no aplicativo as câmeras com stream realmente válido
- canais sem vídeo útil podem ser ocultados da malha de câmeras

## 4. Regras de rede do site

O cenário mais seguro é:

- nunca expor o DVR diretamente na internet
- usar VPN até a rede interna do site
- acessar o DVR pelo IP interno, por exemplo `10.0.7.251`

### 4.1 Se a máquina já estiver na mesma LAN do DVR

Não é necessário VPN.

Basta garantir:

- a máquina alcança o IP do DVR
- a porta do DVR responde
- o SPYGYM aponta para o IP interno do DVR

### 4.2 Se a máquina estiver fora da rede do DVR

Será necessário:

- VPN
- ou outra rota segura até a LAN do site

Recomendação do projeto:

- MikroTik com `WireGuard`, quando disponível
- `L2TP/IPsec`, quando o MikroTik não tiver WireGuard

## 5. Firewall e roteador da operadora

Se houver modem/roteador da operadora antes do MikroTik, ele precisa encaminhar a VPN para o MikroTik.

### 5.1 Para WireGuard

Encaminhar no modem:

- `UDP 51820` para o IP WAN do MikroTik

### 5.2 Para L2TP/IPsec

Encaminhar no modem:

- `UDP 500` para o IP WAN do MikroTik
- `UDP 4500` para o IP WAN do MikroTik

Se existir opção, habilitar:

- `IPSec Pass-Through`

Observação:

- em alguns cenários, usar `DMZ` temporária para o MikroTik ajuda no diagnóstico
- depois do teste, o ideal é voltar ao encaminhamento somente das portas necessárias

## 6. VPN recomendada

## 6.1 Opção preferencial: WireGuard no MikroTik

Usar quando o MikroTik suporta `RouterOS v7+` com WireGuard.

Documentos já prontos no projeto:

- [ACESSO_REMOTO_DVR_MIKROTIK.md](/C:/Users/Admin/X/SPYGYM/docs/ACESSO_REMOTO_DVR_MIKROTIK.md)
- [mikrotik-wireguard-dvr-site.rsc](/C:/Users/Admin/X/SPYGYM/deploy/mikrotik-wireguard-dvr-site.rsc)

## 6.2 Opção compatível: L2TP/IPsec no MikroTik

Usar quando o MikroTik não suporta WireGuard.

Documentos já prontos no projeto:

- [ACESSO_REMOTO_DVR_L2TP_IPSEC_MIKROTIK.md](/C:/Users/Admin/X/SPYGYM/docs/ACESSO_REMOTO_DVR_L2TP_IPSEC_MIKROTIK.md)
- [mikrotik-l2tp-ipsec-dvr-site.rsc](/C:/Users/Admin/X/SPYGYM/deploy/mikrotik-l2tp-ipsec-dvr-site.rsc)

Observações para Windows no cenário `L2TP/IPsec`:

- pode ser necessário habilitar NAT-T via registro
- o split tunnel costuma ser necessário para não derrubar a internet da máquina
- em alguns casos é preciso adicionar rota para a LAN remota

Exemplos:

- rota para a LAN do site: `10.0.7.0/24`
- gateway VPN remoto: `10.99.99.1`

## 7. Passo a passo recomendado para inserir outro DVR

1. Confirmar se o DVR está acessível pelo IP interno da rede do site.
2. Validar usuário, senha, protocolo e porta.
3. Confirmar se a máquina do operador alcança a rede do site.
4. Se não alcançar, subir a VPN.
5. No SPYGYM, cadastrar o DVR com o IP interno.
6. Rodar `Checar`.
7. Rodar `Sincronizar câmeras`.
8. Abrir a tela de `Câmeras`.
9. Validar se só aparecem os canais realmente com vídeo útil.
10. Testar o modal `Ao vivo`.
11. Testar `Reprodução` pela interface web do DVR.

## 8. Como validar se a VPN está correta

Na máquina do operador:

1. testar o IP da VPN
2. testar o IP do DVR
3. abrir a interface web do DVR no navegador

Checklist:

- `ping` para o gateway da VPN
- `ping` para o DVR
- abrir `http://IP_DO_DVR`

Se o navegador não abrir o DVR:

- revisar a VPN
- revisar o encaminhamento no modem da operadora
- revisar firewall do MikroTik
- confirmar se existe CGNAT no link da operadora

## 9. Como usar o SPYGYM em outra máquina

Existem dois cenários.

### 9.1 Outra máquina só para operar o sistema

Se o SPYGYM já estiver rodando em uma máquina principal, a outra máquina precisa apenas:

- acesso ao frontend/backend publicados
- VPN até a rede do site, quando necessário

Nesse cenário, a outra máquina não precisa:

- rodar banco local
- rodar backend local
- instalar ambiente de desenvolvimento completo

Mas precisa:

- alcançar a URL do SPYGYM
- alcançar a rede do DVR, direta ou via VPN, se a arquitetura exigir

### 9.2 Outra máquina para rodar o SPYGYM completo

Nesse caso, a outra máquina precisa:

- código do projeto
- Python
- Node.js
- `ffmpeg`
- banco de dados do projeto ou acesso ao banco correto
- VPN, se o DVR estiver fora da rede

Depois:

1. subir backend
2. subir frontend
3. conectar VPN
4. acessar o app
5. testar o DVR

## 10. Como validar um novo DVR dentro do app

### 10.1 Checagem básica

- `Checar` o DVR
- confirmar `online`
- confirmar latência e última checagem

### 10.2 Câmeras instaladas

- rodar `Sincronizar câmeras`
- confirmar quantas câmeras ativas foram detectadas
- validar se a lista do sistema bate com o que existe fisicamente no equipamento

### 10.3 Ao vivo

- abrir uma câmera
- entrar em `Ao vivo`
- confirmar se o HLS sobe

### 10.4 Reprodução

- abrir a aba `Reprodução`
- usar `Abrir interface`
- consultar playback no próprio DVR

## 11. Problemas comuns

### 11.1 Snapshot 403

Significa, em geral:

- o DVR não libera snapshot HTTP naquele endpoint

Impacto:

- o preview por imagem pode não funcionar
- isso não significa necessariamente que o stream ao vivo esteja indisponível

### 11.2 Vídeo verde ou corrompido

Significa, em geral:

- o próprio stream RTSP do DVR está saindo inválido
- codec, GOP, substream, firmware ou sinal podem estar incorretos

Revisar no DVR:

- codec do substream
- resolução
- FPS
- bitrate
- integridade do canal
- se a câmera realmente está conectada e com imagem

### 11.3 Todos os canais aparecem como instalados, mas não existem fisicamente

O comportamento esperado agora é:

- a capacidade do DVR continua cadastrada
- mas a malha de câmeras deve mostrar só as câmeras realmente com stream útil

Se um canal sem câmera ainda aparecer:

- rodar novamente `Sincronizar câmeras`
- rodar `Checar`

### 11.4 DVR acessível no navegador, mas não no app

Verificar:

- se o SPYGYM está usando o IP interno correto
- se a máquina tem VPN ativa
- se o `ffmpeg` está instalado
- se o stream RTSP da câmera está íntegro

## 12. Padrão recomendado para novos sites

Sempre que possível:

- cadastrar o DVR com IP interno da LAN
- manter MikroTik como ponto central de acesso remoto
- usar VPN em vez de exposição direta do DVR
- liberar somente as portas da VPN no modem da operadora
- manter `ffmpeg` instalado na máquina que roda o backend do SPYGYM

## 13. Checklist final

Antes de concluir um novo DVR:

- DVR cadastrado
- IP interno correto
- credenciais corretas
- VPN validada, se necessária
- `Checar` executado
- `Sincronizar câmeras` executado
- câmeras reais conferidas
- `Ao vivo` testado
- `Reprodução` testada via interface do DVR
- documentação da rede salva

