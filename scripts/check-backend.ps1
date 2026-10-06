# Windows host commands; exec commands run Python/pytest in the Linux API container.
$ErrorActionPreference = 'Stop'
$backendCheckRoot = Split-Path -Parent $PSScriptRoot
$backendCheckProject = 'siv-check-' + [Guid]::NewGuid().ToString('N')
$backendCheckEnvFile = Join-Path ([System.IO.Path]::GetTempPath()) ($backendCheckProject + '.env')
$backendCheckPassword = [Guid]::NewGuid().ToString('N') + [Guid]::NewGuid().ToString('N')
$backendCheckArguments = @(
    '--project-directory', $backendCheckRoot,
    '--env-file', $backendCheckEnvFile,
    '--project-name', $backendCheckProject,
    '-f', (Join-Path $backendCheckRoot 'compose.yaml'),
    '-f', (Join-Path $backendCheckRoot 'compose.ci.yaml')
)
$backendCheckSavedEnvironment = @{}
$backendCheckSettings = @{
    POSTGRES_DB = 'siv_ci'
    POSTGRES_USER = 'siv_ci'
    POSTGRES_PASSWORD = $backendCheckPassword
}
$backendCheckFailed = $false

function Invoke-BackendCheckCompose {
    param([string[]]$CheckArguments)
    & docker compose @backendCheckArguments @CheckArguments
    if ($LASTEXITCODE -ne 0) {
        throw "Disposable Compose check failed: $($CheckArguments -join ' ')"
    }
}

try {
    # Explicitly use generated values instead of any local database environment.
    foreach ($backendCheckKey in $backendCheckSettings.Keys) {
        $backendCheckSavedEnvironment[$backendCheckKey] = [Environment]::GetEnvironmentVariable($backendCheckKey, 'Process')
        [Environment]::SetEnvironmentVariable($backendCheckKey, $backendCheckSettings[$backendCheckKey], 'Process')
    }
    $backendCheckEnvContents = @(
        'POSTGRES_DB=siv_ci'
        'POSTGRES_USER=siv_ci'
        "POSTGRES_PASSWORD=$backendCheckPassword"
    )
    Set-Content -LiteralPath $backendCheckEnvFile -Value $backendCheckEnvContents -Encoding ASCII
    Write-Host "Checking disposable Compose project $backendCheckProject"
    Invoke-BackendCheckCompose -CheckArguments @('config', '--quiet')
    Invoke-BackendCheckCompose -CheckArguments @('up', '--build', '--detach', '--wait', '--wait-timeout', '90')
    Invoke-BackendCheckCompose -CheckArguments @('exec', '-T', 'api', 'python', 'scripts/check_endpoints.py', '--timeout', '60')
    Invoke-BackendCheckCompose -CheckArguments @('exec', '-T', 'api', 'pytest', '-q')
    Invoke-BackendCheckCompose -CheckArguments @('stop', '--timeout', '10', 'db', 'redis')
    Invoke-BackendCheckCompose -CheckArguments @('exec', '-T', 'api', 'python', 'scripts/check_endpoints.py', '--expect-unavailable', '--timeout', '60')
    Invoke-BackendCheckCompose -CheckArguments @('start', 'db', 'redis')
    Invoke-BackendCheckCompose -CheckArguments @('exec', '-T', 'api', 'python', 'scripts/check_endpoints.py', '--timeout', '60')
} catch {
    $backendCheckFailed = $true
    Write-Error -Message $_ -ErrorAction Continue
    if (Test-Path -LiteralPath $backendCheckEnvFile) {
        & docker compose @backendCheckArguments ps --all
        & docker compose @backendCheckArguments logs --no-color --tail 200
    }
} finally {
    if (Test-Path -LiteralPath $backendCheckEnvFile) {
        & docker compose @backendCheckArguments down --volumes --remove-orphans --timeout 10
        if ($LASTEXITCODE -ne 0) { $backendCheckFailed = $true }
        Remove-Item -LiteralPath $backendCheckEnvFile
    }
    foreach ($backendCheckKey in $backendCheckSavedEnvironment.Keys) {
        [Environment]::SetEnvironmentVariable($backendCheckKey, $backendCheckSavedEnvironment[$backendCheckKey], 'Process')
    }
}

if ($backendCheckFailed) { exit 1 }
