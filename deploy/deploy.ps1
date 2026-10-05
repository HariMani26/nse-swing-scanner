#requires -Version 5.1
<#
  Rebuilds the combined image in ACR and redeploys it to the Azure Web App.
  Usage: ./deploy/deploy.ps1
#>
param(
    [string]$ResourceGroup = "nse-swing-scanner-rg",
    [string]$AcrName       = "nseswingscannercr",
    [string]$ImageName     = "nse-swing-scanner",
    [string]$ImageTag      = "latest",
    [string]$WebAppName    = "nse-swing-scanner-app"
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot

Write-Host "==> Building and pushing image via ACR Tasks (cloud build, no local Docker)..." -ForegroundColor Cyan
az acr build `
    --registry $AcrName `
    --image "${ImageName}:${ImageTag}" `
    --file "$repoRoot/Dockerfile.appservice" `
    "$repoRoot"

Write-Host "==> Restarting Web App to pull the new image..." -ForegroundColor Cyan
az webapp restart --resource-group $ResourceGroup --name $WebAppName

Write-Host "==> Deployed. Checking health endpoint..." -ForegroundColor Cyan
$healthUrl = "https://$WebAppName.azurewebsites.net/api/health"
$ok = $false
for ($i = 1; $i -le 10; $i++) {
    try {
        $resp = Invoke-WebRequest -Uri $healthUrl -UseBasicParsing -TimeoutSec 10
        if ($resp.StatusCode -eq 200) {
            Write-Host "Healthy: $($resp.Content)" -ForegroundColor Green
            $ok = $true
            break
        }
    } catch {
        Start-Sleep -Seconds 10
    }
}

if (-not $ok) {
    Write-Warning "Health check did not succeed after retries. Check logs with: az webapp log tail -g $ResourceGroup -n $WebAppName"
} else {
    Write-Host "App live at: https://$WebAppName.azurewebsites.net" -ForegroundColor Green
}
