param(
  [string]$ApiBaseUrl = 'http://127.0.0.1:8010/api'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Read-DotEnvValue {
  param(
    [string]$Path,
    [string]$Key,
    [string]$DefaultValue
  )

  if (-not (Test-Path -LiteralPath $Path)) {
    return $DefaultValue
  }

  $line = Get-Content -LiteralPath $Path | Where-Object { $_ -match "^$([regex]::Escape($Key))=" } | Select-Object -First 1
  if (-not $line) {
    return $DefaultValue
  }

  return ($line -split '=', 2)[1].Trim()
}

function Invoke-Step {
  param(
    [string]$Name,
    [scriptblock]$Action
  )

  try {
    return & $Action
  } catch {
    $message = $_.Exception.Message
    if ($_.ErrorDetails -and $_.ErrorDetails.Message) {
      $message = $_.ErrorDetails.Message
    }
    return [pscustomobject]@{
      step = $Name
      error = $message
    }
  }
}

$envFile = 'C:\Users\Admin\X\SPYGYM\backend\.env'
$adminEmail = Read-DotEnvValue -Path $envFile -Key 'SPYGYM_ADMIN_EMAIL' -DefaultValue 'admin@spygym.local'
$adminPassword = Read-DotEnvValue -Path $envFile -Key 'SPYGYM_ADMIN_PASSWORD' -DefaultValue 'Admin@123'

$loginBody = @{
  email = $adminEmail
  password = $adminPassword
} | ConvertTo-Json

$session = Invoke-RestMethod -Method Post -Uri "$ApiBaseUrl/auth/login" -ContentType 'application/json' -Body $loginBody
$headers = @{ Authorization = "Bearer $($session.token)" }

$units = Invoke-RestMethod -Uri "$ApiBaseUrl/units" -Headers $headers
$baseUnit = $units | Where-Object { $_.code -eq '07' } | Select-Object -First 1
if (-not $baseUnit) {
  throw 'Unidade base 07 não encontrada para o smoke test.'
}

$summary = [ordered]@{}
$summary['health'] = Invoke-RestMethod -Uri "$ApiBaseUrl/health"
$overviewBefore = Invoke-RestMethod -Uri "$ApiBaseUrl/dashboard/overview" -Headers $headers
$summary['overview_before'] = [pscustomobject]@{
  totals = $overviewBefore.totals
  critical_events = @($overviewBefore.critical_events).Count
  latest_backups = @($overviewBefore.latest_backups).Count
}
$summary['list_users_before'] = @((Invoke-RestMethod -Uri "$ApiBaseUrl/users" -Headers $headers)).Count
$summary['list_dvrs_before'] = @((Invoke-RestMethod -Uri "$ApiBaseUrl/dvrs" -Headers $headers)).Count
$summary['list_cameras_before'] = @((Invoke-RestMethod -Uri "$ApiBaseUrl/cameras" -Headers $headers)).Count
$summary['list_cloud_accounts_before'] = @((Invoke-RestMethod -Uri "$ApiBaseUrl/cloud-accounts" -Headers $headers)).Count
$summary['list_backups_before'] = @((Invoke-RestMethod -Uri "$ApiBaseUrl/backups" -Headers $headers)).Count
$summary['list_events_before'] = @((Invoke-RestMethod -Uri "$ApiBaseUrl/events?limit=25" -Headers $headers)).Count

$summary['run_monitor'] = Invoke-Step -Name 'run_monitor' -Action { Invoke-RestMethod -Method Post -Uri "$ApiBaseUrl/monitor/run" -Headers $headers }
$summary['run_backup'] = Invoke-Step -Name 'run_backup' -Action { Invoke-RestMethod -Method Post -Uri "$ApiBaseUrl/backups/run" -Headers $headers }

$tempCloud = Invoke-RestMethod -Method Post -Uri "$ApiBaseUrl/cloud-accounts" -Headers $headers -ContentType 'application/json' -Body (@{
  name = 'Smoke Cloud'
  vendor = 'hikvision'
  email = 'smoke-cloud@local.test'
  password = 'SmokeCloud123'
  notes = 'Criado pelo smoke test de integracao.'
} | ConvertTo-Json)

$tempCloudUpdated = Invoke-RestMethod -Method Put -Uri "$ApiBaseUrl/cloud-accounts/$($tempCloud.id)" -Headers $headers -ContentType 'application/json' -Body (@{
  notes = 'Conta cloud atualizada pelo smoke test.'
} | ConvertTo-Json)

$revealedPassword = Invoke-RestMethod -Uri "$ApiBaseUrl/cloud-accounts/$($tempCloud.id)/reveal-password" -Headers $headers

$tempUser = Invoke-RestMethod -Method Post -Uri "$ApiBaseUrl/users" -Headers $headers -ContentType 'application/json' -Body (@{
  full_name = 'Smoke Operator'
  email = 'smoke-operator@local.test'
  role = 'operator'
  is_active = $true
  password = 'SmokeUser123'
} | ConvertTo-Json)

$tempUserUpdated = Invoke-RestMethod -Method Put -Uri "$ApiBaseUrl/users/$($tempUser.id)" -Headers $headers -ContentType 'application/json' -Body (@{
  full_name = 'Smoke Operator Updated'
  email = 'smoke-operator@local.test'
  role = 'viewer'
  is_active = $true
} | ConvertTo-Json)

$tempDvr = Invoke-RestMethod -Method Post -Uri "$ApiBaseUrl/dvrs" -Headers $headers -ContentType 'application/json' -Body (@{
  unit_id = $baseUnit.id
  name = 'SMOKE-DVR'
  vendor = 'hikvision'
  model = 'Smoke'
  serial_number = 'SMOKE-SERIAL'
  device_serial = 'SMOKE-CLOUD-SERIAL'
  host = '192.0.2.10'
  port = 80
  protocol = 'http'
  username = 'admin'
  password = 'SmokeDvr123'
  channel_count = 4
  cloud_account_id = $tempCloud.id
  is_active = $true
  notes = 'Criado pelo smoke test.'
} | ConvertTo-Json)

$tempDvrUpdated = Invoke-RestMethod -Method Put -Uri "$ApiBaseUrl/dvrs/$($tempDvr.id)" -Headers $headers -ContentType 'application/json' -Body (@{
  unit_id = $baseUnit.id
  name = 'SMOKE-DVR-UPDATED'
  vendor = 'hikvision'
  model = 'Smoke 2'
  serial_number = 'SMOKE-SERIAL-2'
  device_serial = 'SMOKE-CLOUD-SERIAL'
  host = '192.0.2.11'
  port = 8080
  protocol = 'http'
  username = 'admin'
  channel_count = 4
  cloud_account_id = $tempCloud.id
  is_active = $true
  notes = 'Atualizado pelo smoke test.'
} | ConvertTo-Json)

$tempCamera = Invoke-RestMethod -Method Post -Uri "$ApiBaseUrl/cameras" -Headers $headers -ContentType 'application/json' -Body (@{
  unit_id = $baseUnit.id
  dvr_id = $tempDvr.id
  name = 'SMOKE-CAMERA'
  vendor = 'hikvision'
  channel_number = 1
  location = 'Recepcao'
  resolution = '1920x1080'
  snapshot_path = '/ISAPI/Streaming/channels/101/picture'
  stream_path = '/Streaming/Channels/101'
  notes = 'Criada pelo smoke test.'
  is_active = $true
} | ConvertTo-Json)

$tempCameraUpdated = Invoke-RestMethod -Method Put -Uri "$ApiBaseUrl/cameras/$($tempCamera.id)" -Headers $headers -ContentType 'application/json' -Body (@{
  unit_id = $baseUnit.id
  dvr_id = $tempDvr.id
  name = 'SMOKE-CAMERA-UPDATED'
  vendor = 'hikvision'
  channel_number = 1
  location = 'Sala de musculacao'
  resolution = '1280x720'
  snapshot_path = '/ISAPI/Streaming/channels/101/picture'
  stream_path = '/Streaming/Channels/101'
  notes = 'Atualizada pelo smoke test.'
  is_active = $true
} | ConvertTo-Json)

$realDvrs = Invoke-RestMethod -Uri "$ApiBaseUrl/dvrs" -Headers $headers
$realDvr = $realDvrs | Where-Object { $_.name -ne $tempDvrUpdated.name } | Select-Object -First 1
if ($realDvr) {
  $summary['check_real_dvr'] = Invoke-Step -Name 'check_real_dvr' -Action { Invoke-RestMethod -Method Post -Uri "$ApiBaseUrl/dvrs/$($realDvr.id)/check" -Headers $headers }
  $summary['sync_real_dvr'] = Invoke-Step -Name 'sync_real_dvr' -Action { Invoke-RestMethod -Method Post -Uri "$ApiBaseUrl/dvrs/$($realDvr.id)/sync-cameras" -Headers $headers }
}

Invoke-Step -Name 'cleanup_camera' -Action { Invoke-RestMethod -Method Delete -Uri "$ApiBaseUrl/cameras/$($tempCamera.id)" -Headers $headers | Out-Null } | Out-Null
Invoke-Step -Name 'cleanup_dvr' -Action { Invoke-RestMethod -Method Delete -Uri "$ApiBaseUrl/dvrs/$($tempDvr.id)" -Headers $headers | Out-Null } | Out-Null
Invoke-Step -Name 'cleanup_cloud' -Action { Invoke-RestMethod -Method Delete -Uri "$ApiBaseUrl/cloud-accounts/$($tempCloud.id)" -Headers $headers | Out-Null } | Out-Null
Invoke-Step -Name 'cleanup_user' -Action { Invoke-RestMethod -Method Delete -Uri "$ApiBaseUrl/users/$($tempUser.id)" -Headers $headers | Out-Null } | Out-Null

$summary['cloud_account_created'] = $tempCloud
$summary['cloud_account_updated'] = $tempCloudUpdated
$summary['cloud_account_revealed'] = $revealedPassword
$summary['user_created'] = $tempUser
$summary['user_updated'] = $tempUserUpdated
$summary['dvr_created'] = $tempDvr
$summary['dvr_updated'] = $tempDvrUpdated
$summary['camera_created'] = $tempCamera
$summary['camera_updated'] = $tempCameraUpdated
$summary['list_users_after'] = @((Invoke-RestMethod -Uri "$ApiBaseUrl/users" -Headers $headers)).Count
$summary['list_dvrs_after'] = @((Invoke-RestMethod -Uri "$ApiBaseUrl/dvrs" -Headers $headers)).Count
$summary['list_cameras_after'] = @((Invoke-RestMethod -Uri "$ApiBaseUrl/cameras" -Headers $headers)).Count
$summary['list_cloud_accounts_after'] = @((Invoke-RestMethod -Uri "$ApiBaseUrl/cloud-accounts" -Headers $headers)).Count
$summary['list_backups_after'] = @((Invoke-RestMethod -Uri "$ApiBaseUrl/backups" -Headers $headers)).Count
$summary['list_events_after'] = @((Invoke-RestMethod -Uri "$ApiBaseUrl/events?limit=25" -Headers $headers)).Count

$summary | ConvertTo-Json -Depth 8
