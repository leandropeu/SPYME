param(
  [string]$ApiBaseUrl = 'http://127.0.0.1:8010/api',
  [string]$OutputDir = 'C:\Users\Admin\X\SPYGYM\deploy\mikrotik-sites'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Read-DotEnv {
  param([string]$Path)

  $values = @{}
  if (-not (Test-Path -LiteralPath $Path)) {
    return $values
  }

  foreach ($line in Get-Content -LiteralPath $Path) {
    $trimmed = $line.Trim()
    if (-not $trimmed -or $trimmed.StartsWith('#') -or -not $trimmed.Contains('=')) {
      continue
    }

    $key, $value = $trimmed -split '=', 2
    $values[$key.Trim()] = $value.Trim()
  }

  return $values
}

function Get-NumericSiteCode {
  param([string]$Code)

  $digits = ($Code -replace '\D', '')
  if (-not $digits) {
    throw "Codigo de unidade invalido para gerar VPN: $Code"
  }

  return [int]$digits
}

function Get-Slug {
  param([string]$Value)

  $normalized = $Value.Normalize([Text.NormalizationForm]::FormD)
  $builder = New-Object System.Text.StringBuilder

  foreach ($char in $normalized.ToCharArray()) {
    $category = [Globalization.CharUnicodeInfo]::GetUnicodeCategory($char)
    if ($category -ne [Globalization.UnicodeCategory]::NonSpacingMark) {
      [void]$builder.Append($char)
    }
  }

  return (($builder.ToString().ToLowerInvariant() -replace '[^a-z0-9]+', '-') -replace '(^-+|-+$)', '')
}

function New-WireGuardScript {
  param(
    [object]$Unit,
    [string]$Code,
    [int]$SiteNumber,
    [string]$LanCidr,
    [string]$DvrIp,
    [string[]]$PendingFields
  )

  $slug = Get-Slug $Unit.name
  $routerAddress = "10.99.$SiteNumber.1/24"
  $clientAddress = "10.99.$SiteNumber.2/32"
  $vpnPort = 52000 + $SiteNumber
  $pendingComment = if ($PendingFields.Count) {
    "# Pendencias para revisar antes de aplicar: $($PendingFields -join ', ')"
  } else {
    '# Pronto para aplicar assim que a chave publica do cliente for informada.'
  }

  return @"
# SPYGYM - Acesso remoto WireGuard por unidade
# Unidade: $($Unit.name) | Codigo: $Code | Cidade: $($Unit.city)/$($Unit.state)
# Mesmo padrao operacional da Homero thon, com faixa VPN dedicada por unidade para evitar conflito entre sites.
$pendingComment

:local WGNAME "wg-spygym-$Code"
:local WGPORT $vpnPort
:local WG_ROUTER_ADDR "$routerAddress"
:local WG_CLIENT_ADDR "$clientAddress"
:local LAN_CIDR "$LanCidr"
:local DVR_IP "$DvrIp"
:local CLIENTPUBKEY "PREENCHER_CHAVE_PUBLICA_CLIENTE"

/interface/wireguard
add name=`$WGNAME listen-port=`$WGPORT mtu=1420 comment="SPYGYM acesso remoto $Code"

/ip/address
add address=`$WG_ROUTER_ADDR interface=`$WGNAME comment="SPYGYM WireGuard gateway $Code"

/interface/wireguard/peers
add interface=`$WGNAME public-key=`$CLIENTPUBKEY allowed-address=`$WG_CLIENT_ADDR persistent-keepalive=25 comment="SPYGYM cliente remoto $Code"

/ip/firewall/filter
add chain=input action=accept protocol=udp dst-port=`$WGPORT comment="SPYGYM WG $Code UDP"
add chain=forward action=accept src-address=10.99.$SiteNumber.2 dst-address=`$DVR_IP comment="SPYGYM WG $Code -> DVR"
add chain=forward action=accept src-address=`$DVR_IP dst-address=10.99.$SiteNumber.2 comment="SPYGYM DVR $Code -> WG"

# Opcional: liberar acesso da VPN a toda a LAN da unidade
# /ip/firewall/filter
# add chain=forward action=accept src-address=10.99.$SiteNumber.2 dst-address=`$LAN_CIDR comment="SPYGYM WG $Code -> LAN"
# add chain=forward action=accept src-address=`$LAN_CIDR dst-address=10.99.$SiteNumber.2 comment="SPYGYM LAN $Code -> WG"

# Opcional: NAT se o DVR/LAN nao devolverem trafego para o tunel
# /ip/firewall/nat
# add chain=srcnat action=masquerade src-address=10.99.$SiteNumber.2 dst-address=`$DVR_IP comment="SPYGYM WG NAT $Code"

# Depois de aplicar:
# 1. confirme a chave publica do MikroTik em /interface/wireguard/print detail
# 2. use a porta UDP $vpnPort no modem/roteador anterior, se existir
# 3. valide ping no DVR $DvrIp e a interface web do equipamento
"@
}

function New-L2tpScript {
  param(
    [object]$Unit,
    [string]$Code,
    [int]$SiteNumber,
    [string]$LanCidr,
    [string]$DvrIp,
    [string[]]$PendingFields
  )

  $poolStart = "10.99.$SiteNumber.10"
  $poolEnd = "10.99.$SiteNumber.20"
  $routerAddress = "10.99.$SiteNumber.1"
  $pendingComment = if ($PendingFields.Count) {
    "# Pendencias para revisar antes de aplicar: $($PendingFields -join ', ')"
  } else {
    '# Pronto para aplicar apos preencher usuario, senha e segredo IPsec.'
  }

  return @"
# SPYGYM - Acesso remoto L2TP/IPsec por unidade
# Unidade: $($Unit.name) | Codigo: $Code | Cidade: $($Unit.city)/$($Unit.state)
# Alternativa compativel ao mesmo padrao operacional da Homero thon.
$pendingComment

:local WAN_IF "ether1"
:local LAN_CIDR "$LanCidr"
:local DVR_IP "$DvrIp"
:local VPN_POOL_NAME "spygym-pool-$Code"
:local VPN_PROFILE "spygym-profile-$Code"
:local VPN_USER "spygym$Code"
:local VPN_PASS "PREENCHER_SENHA_FORTE"
:local IPSEC_SECRET "PREENCHER_SEGREDO_IPSEC"

/ip cloud
set ddns-enabled=yes update-time=yes

/ip pool
add name=`$VPN_POOL_NAME ranges=$poolStart-$poolEnd

/ppp profile
add name=`$VPN_PROFILE local-address=$routerAddress remote-address=`$VPN_POOL_NAME dns-server=1.1.1.1,8.8.8.8 use-encryption=required only-one=yes change-tcp-mss=yes

/ppp secret
add name=`$VPN_USER password=`$VPN_PASS service=l2tp profile=`$VPN_PROFILE

/interface l2tp-server server
set enabled=yes authentication=mschap2 default-profile=`$VPN_PROFILE use-ipsec=required ipsec-secret=`$IPSEC_SECRET

/ip/firewall/filter
add chain=input action=accept in-interface=`$WAN_IF protocol=udp dst-port=500,4500 comment="SPYGYM IPsec $Code"
add chain=input action=accept in-interface=`$WAN_IF protocol=ipsec-esp comment="SPYGYM ESP $Code"
add chain=input action=accept in-interface=`$WAN_IF ipsec-policy=in,ipsec protocol=udp dst-port=1701 comment="SPYGYM L2TP $Code somente em IPsec"
add chain=input action=drop in-interface=`$WAN_IF protocol=udp dst-port=1701 comment="SPYGYM bloqueia L2TP sem IPsec $Code"

/ip/firewall/filter
add chain=forward action=accept src-address=10.99.$SiteNumber.0/24 dst-address=`$DVR_IP comment="SPYGYM VPN $Code -> DVR"
add chain=forward action=accept src-address=`$DVR_IP dst-address=10.99.$SiteNumber.0/24 comment="SPYGYM DVR $Code -> VPN"

# Opcional: liberar acesso da VPN a toda a LAN da unidade
# /ip/firewall/filter
# add chain=forward action=accept src-address=10.99.$SiteNumber.0/24 dst-address=`$LAN_CIDR comment="SPYGYM VPN $Code -> LAN"
# add chain=forward action=accept src-address=`$LAN_CIDR dst-address=10.99.$SiteNumber.0/24 comment="SPYGYM LAN $Code -> VPN"

# Opcional: NAT se o DVR/LAN nao devolverem trafego para a VPN
# /ip/firewall/nat
# add chain=srcnat action=masquerade src-address=10.99.$SiteNumber.0/24 dst-address=`$DVR_IP comment="SPYGYM NAT $Code"
"@
}

$projectRoot = 'C:\Users\Admin\X\SPYGYM'
$envMap = Read-DotEnv -Path (Join-Path $projectRoot 'backend\.env')
$adminEmail = if ($env:SPYGYM_ADMIN_EMAIL) { $env:SPYGYM_ADMIN_EMAIL } elseif ($envMap.ContainsKey('SPYGYM_ADMIN_EMAIL')) { $envMap['SPYGYM_ADMIN_EMAIL'] } else { 'admin@spygym.local' }
$adminPassword = if ($env:SPYGYM_ADMIN_PASSWORD) { $env:SPYGYM_ADMIN_PASSWORD } elseif ($envMap.ContainsKey('SPYGYM_ADMIN_PASSWORD')) { $envMap['SPYGYM_ADMIN_PASSWORD'] } else { 'Admin@123' }

$wireGuardDir = Join-Path $OutputDir 'wireguard'
$l2tpDir = Join-Path $OutputDir 'l2tp-ipsec'

New-Item -ItemType Directory -Force -Path $wireGuardDir | Out-Null
New-Item -ItemType Directory -Force -Path $l2tpDir | Out-Null

$loginBody = @{
  email = $adminEmail
  password = $adminPassword
} | ConvertTo-Json

$session = Invoke-RestMethod -Method Post -Uri "$ApiBaseUrl/auth/login" -ContentType 'application/json' -Body $loginBody
$headers = @{ Authorization = "Bearer $($session.token)" }
$units = Invoke-RestMethod -Uri "$ApiBaseUrl/units" -Headers $headers
$dvrs = Invoke-RestMethod -Uri "$ApiBaseUrl/dvrs" -Headers $headers

$inventory = foreach ($unit in $units | Sort-Object @{
  Expression = {
    $digits = ($_.code -replace '\D', '')
    if ($digits) { [int]$digits } else { 0 }
  }
}, code) {
  $code = [string]$unit.code
  $siteNumber = Get-NumericSiteCode -Code $code
  $slug = Get-Slug $unit.name
  $unitDvrs = @($dvrs | Where-Object { $_.unit_name -eq $unit.name })
  $primaryDvr = $unitDvrs | Select-Object -First 1

  $pendingFields = @()
  $lanCidr = if ($unit.network_label) { [string]$unit.network_label } else { $pendingFields += 'LAN_CIDR'; 'REVISAR_LAN_CIDR' }
  $dvrIp = if ($primaryDvr -and $primaryDvr.host) { [string]$primaryDvr.host } else { $pendingFields += 'DVR_IP'; 'REVISAR_DVR_IP' }
  $ready = $pendingFields.Count -eq 0
  $fileBase = '{0}-{1}' -f $code.PadLeft(3, '0'), $slug

  $wireGuardPath = Join-Path $wireGuardDir "$fileBase.rsc"
  $l2tpPath = Join-Path $l2tpDir "$fileBase.rsc"

  Set-Content -LiteralPath $wireGuardPath -Encoding UTF8 -Value (New-WireGuardScript -Unit $unit -Code $code -SiteNumber $siteNumber -LanCidr $lanCidr -DvrIp $dvrIp -PendingFields $pendingFields)
  Set-Content -LiteralPath $l2tpPath -Encoding UTF8 -Value (New-L2tpScript -Unit $unit -Code $code -SiteNumber $siteNumber -LanCidr $lanCidr -DvrIp $dvrIp -PendingFields $pendingFields)

  [pscustomobject]@{
    code = $code
    unit = $unit.name
    city = $unit.city
    state = $unit.state
    network_label = $unit.network_label
    dvr_ip = if ($primaryDvr) { $primaryDvr.host } else { $null }
    dvr_name = if ($primaryDvr) { $primaryDvr.name } else { $null }
    wireguard_file = $wireGuardPath
    l2tp_file = $l2tpPath
    ready_to_apply = $ready
    pending_fields = ($pendingFields -join ', ')
  }
}

$inventoryPath = Join-Path $OutputDir 'mikrotik-sites-inventory.csv'
$inventory | Export-Csv -LiteralPath $inventoryPath -NoTypeInformation -Encoding UTF8

[pscustomobject]@{
  output_dir = $OutputDir
  total_units = $inventory.Count
  ready_to_apply = @($inventory | Where-Object { $_.ready_to_apply }).Count
  pending_review = @($inventory | Where-Object { -not $_.ready_to_apply }).Count
  inventory = $inventoryPath
} | ConvertTo-Json -Depth 4
