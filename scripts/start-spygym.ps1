Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$backendDir = Join-Path $root 'backend'
$frontendDir = Join-Path $root 'frontend'
$backendPort = 8010
$frontendPort = 5174
$backendUrl = "http://127.0.0.1:$backendPort/api/health"
$frontendUrl = "http://127.0.0.1:$frontendPort/"

function Write-Step {
    param([string] $Message)
    Write-Host "[SPYGYM] $Message" -ForegroundColor Cyan
}

function Test-PortOpen {
    param([int] $Port)

    try {
        $client = [System.Net.Sockets.TcpClient]::new()
        $async = $client.BeginConnect('127.0.0.1', $Port, $null, $null)
        $connected = $async.AsyncWaitHandle.WaitOne(400)
        if (-not $connected) {
            $client.Close()
            return $false
        }

        $client.EndConnect($async)
        $client.Close()
        return $true
    } catch {
        return $false
    }
}

function Wait-HttpReady {
    param(
        [string] $Url,
        [int] $Attempts = 45,
        [int] $DelaySeconds = 2
    )

    for ($attempt = 1; $attempt -le $Attempts; $attempt++) {
        try {
            Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 5 | Out-Null
            return $true
        } catch {
            Start-Sleep -Seconds $DelaySeconds
        }
    }

    return $false
}

function Resolve-BackendPython {
    $candidates = @(
        (Join-Path $backendDir '.venv\Scripts\python.exe'),
        (Join-Path $backendDir 'venv\Scripts\python.exe')
    )

    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) {
            return $candidate
        }
    }

    return $null
}

function Get-PythonLauncher {
    return Get-Command py.exe -ErrorAction SilentlyContinue
}

function Ensure-BackendVenv {
    $pythonExe = Resolve-BackendPython
    if ($pythonExe) {
        return $pythonExe
    }

    $pyLauncher = Get-PythonLauncher
    if (-not $pyLauncher) {
        throw 'Nao encontrei Python instalado nem um ambiente virtual pronto em backend\.venv ou backend\venv.'
    }

    Write-Step 'Criando ambiente virtual do backend...'
    & $pyLauncher.Source -3 -m venv (Join-Path $backendDir '.venv')
    return Resolve-BackendPython
}

function Ensure-BackendDependencies {
    $requirements = Join-Path $backendDir 'requirements.txt'
    Write-Step 'Instalando dependencias do backend...'

    $pyLauncher = Get-PythonLauncher
    if ($pyLauncher) {
        & $pyLauncher.Source -3 -m pip install -r $requirements
        return
    }

    $pythonExe = Ensure-BackendVenv
    & $pythonExe -m pip install -r $requirements
}

function Ensure-FrontendDependencies {
    $npm = Get-Command npm.cmd -ErrorAction SilentlyContinue
    if (-not $npm) {
        throw 'Nao encontrei o npm.cmd no sistema. Instale o Node.js para subir o frontend.'
    }

    Write-Step 'Instalando dependencias do frontend...'
    & cmd.exe /c 'npm install' | Out-Host
}

function Start-Backend {
    if (Test-PortOpen -Port $backendPort) {
        Write-Step "Backend ja esta respondendo na porta $backendPort."
        return
    }

    $pyLauncher = Get-PythonLauncher
    if ($pyLauncher) {
        Write-Step 'Abrindo janela do backend...'
        $command = "cd /d `"$backendDir`" && py -3 -m uvicorn app.main:app --host 0.0.0.0 --port $backendPort"
        Start-Process -FilePath 'cmd.exe' -WorkingDirectory $backendDir -ArgumentList '/k', $command | Out-Null
        return
    }

    $pythonExe = Ensure-BackendVenv
    Write-Step 'Abrindo janela do backend...'
    $command = "cd /d `"$backendDir`" && `"$pythonExe`" -m uvicorn app.main:app --host 0.0.0.0 --port $backendPort"
    Start-Process -FilePath 'cmd.exe' -WorkingDirectory $backendDir -ArgumentList '/k', $command | Out-Null
}

function Start-Frontend {
    if (Test-PortOpen -Port $frontendPort) {
        Write-Step "Frontend ja esta respondendo na porta $frontendPort."
        return
    }

    Write-Step 'Abrindo janela do frontend...'
    $command = "cd /d `"$frontendDir`" && cmd /c npm install && cmd /c npm run dev -- --host 0.0.0.0 --port $frontendPort --strictPort"
    Start-Process -FilePath 'cmd.exe' -WorkingDirectory $frontendDir -ArgumentList '/k', $command | Out-Null
}

Ensure-BackendDependencies
Ensure-FrontendDependencies
Start-Backend
Start-Frontend

Write-Step 'Aguardando backend ficar pronto...'
$backendReady = Wait-HttpReady -Url $backendUrl
if (-not $backendReady) {
    throw "O backend nao respondeu em $backendUrl."
}

Write-Step 'Aguardando frontend ficar pronto...'
$frontendReady = Wait-HttpReady -Url $frontendUrl
if (-not $frontendReady) {
    throw "O frontend nao respondeu em $frontendUrl."
}

Write-Step 'Abrindo painel web do SPYGYM...'
Start-Process $frontendUrl | Out-Null

Write-Host ''
Write-Host 'SPYGYM no ar.' -ForegroundColor Green
Write-Host "Frontend: $frontendUrl"
Write-Host "Backend:  $backendUrl"
