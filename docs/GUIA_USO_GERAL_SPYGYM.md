# Guia Geral de Uso do SPYGYM

Este guia resume como usar o aplicativo no dia a dia, do login ao acompanhamento de unidades, DVRs, câmeras, eventos e backups.

## 1. Objetivo do sistema

O `SPYGYM` centraliza o cadastro e a operação de monitoramento das academias:

- unidades
- DVRs
- câmeras
- eventos operacionais
- backups do banco
- acesso rápido ao visualizador ao vivo e à interface dos DVRs

## 2. Acesso ao aplicativo

1. Abra o frontend no navegador.
2. Informe e-mail e senha.
3. Após o login, verifique o indicador de conexão no topo.

Leituras do indicador:

- `Online`: frontend conectado ao backend
- `Offline`: frontend sem comunicação com o backend em tempo real

## 3. Visão geral do menu

As páginas principais ficam na barra lateral:

- `Dashboard`
- `Unidades`
- `DVRs`
- `Câmeras`
- `Eventos`
- `Backups`
- `Usuários`
- `Contas cloud`, quando aplicável

## 4. Dashboard

O `Dashboard` é a leitura rápida da operação.

Ali você acompanha:

- total de unidades cadastradas
- DVRs online versus total
- câmeras online versus total
- incidentes abertos
- backups recentes

Uso recomendado:

1. olhar os indicadores gerais
2. identificar unidades com alerta ou offline
3. abrir a página correspondente para ação operacional

## 5. Página de Unidades

A página `Unidades` concentra o cadastro mestre das academias.

Campos mais importantes:

- `Nome`
- `Código`
- `Cidade`
- `Estado`
- `Rede`
- `Endereço`
- `Responsável`
- `Telefone`
- `Observações`

Uso recomendado:

1. cadastrar ou revisar os dados da unidade
2. preencher `Rede` com a sub-rede local, por exemplo `10.0.7.0/24`
3. usar `Observações` para particularidades operacionais

Leitura visual:

- unidade `Online`: todos os DVRs vinculados estão online
- unidade `Alerta`: parte dos DVRs está online
- unidade `Offline`: todos os DVRs vinculados estão offline
- unidade `Indefinido`: ainda não há DVR vinculado

## 6. Página de DVRs

A página `DVRs` é a base técnica do gravador.

Campos principais:

- `Unidade`
- `Nome do DVR`
- `Fabricante`
- `Host/IP`
- `Porta`
- `Usuário`
- `Senha`
- `Canais`
- `Conta cloud`
- `Observações`

Ações disponíveis:

- `Console`
- `Checar`
- `Sincronizar`
- `Editar`
- `Excluir`

### 6.1 Testar conexão

Use `Checar` quando quiser validar o acesso ao equipamento sem esperar a rotina automática.

Esse teste serve para confirmar:

- host acessível
- resposta básica do DVR
- credencial válida para integração

### 6.2 Sincronizar câmeras

Use `Sincronizar` após cadastrar o DVR ou alterar sua topologia.

Esse processo:

- consulta os canais do equipamento
- cria ou atualiza as câmeras vinculadas ao DVR
- preserva o cadastro já existente quando possível

### 6.3 Console do DVR

O modal `Console` reúne a operação técnica do gravador:

- status atual
- host e última checagem
- conta cloud vinculada
- acesso à interface web
- canais detectados
- busca de gravações
- reinício remoto, para administradores

Fluxo recomendado:

1. abrir `Console`
2. usar `Testar conexão`
3. usar `Sincronizar câmeras`
4. validar canais e gravações
5. abrir a interface nativa do DVR se precisar de configuração avançada

## 7. Página de Câmeras

A página `Câmeras` organiza a malha de vídeo por DVR.

Você pode usar em dois modos:

- `Cards`: visão operacional por gravador
- `Lista`: visão resumida

Cada card mostra:

- DVR e unidade
- host do gravador
- quantidade de câmeras
- capacidade total
- última checagem

### 7.1 Visualizador

O botão `Abrir visualizador` abre o modal de operação do canal.

Recursos do modal:

- troca rápida de canal
- leitura de ocupação do canal
- `Ao vivo`
- `Reprodução`
- link para interface web do DVR

### 7.2 Modo Ao vivo

No modo `Ao vivo`, o backend tenta converter o RTSP do DVR para HLS e reproduzir no navegador.

Se não abrir:

- valide `usuário/senha`
- valide `RTSP`
- confirme `stream principal` e `substream` em `H.264`
- teste no `VLC`

### 7.3 Modo Reprodução

No modo `Reprodução`, o sistema direciona para o playback do próprio DVR, que é mais estável para consulta histórica em muitos modelos.

## 8. Página de Eventos

A página `Eventos` mostra incidentes operacionais gerados pelo monitoramento.

Exemplos:

- DVR offline
- câmera sem resposta
- falha de integração

Uso recomendado:

1. ordenar os eventos por criticidade
2. identificar reincidência por unidade
3. atuar primeiro nos incidentes críticos

## 9. Página de Backups

A página `Backups` registra os backups automáticos e manuais do banco.

Ali você acompanha:

- horário da execução
- tamanho do arquivo
- status
- histórico recente

Uso recomendado:

1. confirmar se a política automática está rodando
2. verificar falhas
3. disparar backup manual antes de alterações sensíveis

## 10. Padrão visual de status

Os principais cadastros usam a mesma lógica visual:

- `Verde`: online
- `Amarelo`: alerta ou parcial
- `Vermelho`: offline
- `Cinza/Azul neutro`: indefinido ou sem vínculo suficiente

Quando um equipamento aparece em vermelho, a prioridade é:

1. validar conectividade
2. validar credenciais
3. confirmar acesso ao equipamento fora do sistema, se necessário

## 11. Fluxo operacional recomendado

Para cadastrar uma nova unidade com monitoramento:

1. criar ou revisar a unidade
2. preencher a rede da unidade
3. cadastrar o DVR
4. testar conexão
5. sincronizar câmeras
6. abrir o visualizador
7. validar ao vivo e reprodução
8. revisar eventos e registrar observações

## 12. Acesso remoto com MikroTik

Quando a unidade usa MikroTik, o padrão recomendado do projeto é:

- `WireGuard` como primeira opção
- `L2TP/IPsec` quando o equipamento não suporta WireGuard

Arquivos úteis:

- [ACESSO_REMOTO_DVR_MIKROTIK.md](/C:/Users/Admin/X/SPYGYM/docs/ACESSO_REMOTO_DVR_MIKROTIK.md)
- [ACESSO_REMOTO_DVR_L2TP_IPSEC_MIKROTIK.md](/C:/Users/Admin/X/SPYGYM/docs/ACESSO_REMOTO_DVR_L2TP_IPSEC_MIKROTIK.md)
- [generate_mikrotik_site_scripts.ps1](/C:/Users/Admin/X/SPYGYM/scripts/generate_mikrotik_site_scripts.ps1)

## 13. Problemas comuns

### DVR online no cadastro, mas sem vídeo ao vivo

Normalmente indica:

- RTSP indisponível
- credencial sem permissão de preview
- stream principal ou substream incompatível

### WebSocket desconectando

Normalmente indica:

- backend reiniciando
- token vencido
- instabilidade entre frontend e backend

### Unidade sem status confiável

Normalmente indica:

- DVR ainda não vinculado
- checagem ainda não executada
- dados da unidade incompletos

## 14. Boas práticas de operação

- manter `rede`, `host` e `porta` sempre atualizados
- preencher observações relevantes nos cadastros
- usar usuários dedicados nos DVRs quando possível
- validar o acesso remoto antes de depender de suporte externo
- acompanhar eventos e backups diariamente
