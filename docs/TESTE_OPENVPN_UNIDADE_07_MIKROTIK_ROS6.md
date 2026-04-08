# Teste da Unidade 07 com MikroTik RouterOS 6

Este roteiro existe porque a unidade `07` está em `RouterOS 6.49.16`, que nao suporta o perfil OpenVPN moderno usado no servidor principal.

## Servidor legado

Na VPS, o servidor compatível com RouterOS 6 ficará assim:

- IP: `191.252.212.6`
- Porta: `1195`
- Protocolo: `TCP`
- Cipher: `AES-256-CBC`
- Auth: `SHA1`
- Sem `tls-crypt`

## Arquivos esperados para a unidade 07

- `ca.crt`
- `07.crt`
- `07.key`
- `mikrotik-ros6-unit07.rsc`

## Importação no MikroTik

Suba os três arquivos de certificado e o script `.rsc` em `Files`.

No terminal:

```rsc
/certificate import file-name=ca.crt
/certificate import file-name=07.crt
/certificate import file-name=07.key
```

Depois confira os nomes dos certificados:

```rsc
/certificate print
```

No script `.rsc`, o campo `certificate=` deve apontar para o nome do certificado do cliente importado.

## Validação

Depois de aplicar o script:

```rsc
/interface ovpn-client print detail
/interface ovpn-client monitor 0
/ping 10.45.0.1
```

Se ficar `running`, valide pela VPS:

```bash
ping -c 4 10.0.7.1
ping -c 4 10.0.7.2
ping -c 4 10.0.7.20
ping -c 4 10.0.7.30
```
