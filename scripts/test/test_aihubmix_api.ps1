[CmdletBinding()]
param(
    [string]$BaseUrl = "https://aihubmix.com/v1",
    [string]$Model = "gpt-4o-mini",
    [string]$ApiKey = $env:AIHUBMIX_API_KEY,
    [switch]$ModelsOnly
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($ApiKey)) {
    Write-Error "API Key is empty. Set AIHUBMIX_API_KEY before running this script."
    exit 2
}

$BaseUrl = $BaseUrl.TrimEnd("/")
$headers = @{
    Authorization = "Bearer $ApiKey"
    "Content-Type" = "application/json"
}

function Get-ApiErrorDetails {
    param([System.Management.Automation.ErrorRecord]$ErrorRecord)

    $statusCode = $null
    if ($null -ne $ErrorRecord.Exception.Response) {
        try {
            $statusCode = [int]$ErrorRecord.Exception.Response.StatusCode
        } catch {
            $statusCode = $null
        }
    }

    $responseBody = $ErrorRecord.ErrorDetails.Message
    if ([string]::IsNullOrWhiteSpace($responseBody)) {
        $responseBody = $ErrorRecord.Exception.Message
    }

    [pscustomobject]@{
        StatusCode = $statusCode
        Message = $responseBody
    }
}

function Show-ApiFailure {
    param(
        [string]$Stage,
        [System.Management.Automation.ErrorRecord]$ErrorRecord
    )

    $details = Get-ApiErrorDetails -ErrorRecord $ErrorRecord
    Write-Host "[$Stage] FAILED" -ForegroundColor Red
    if ($null -ne $details.StatusCode) {
        Write-Host "HTTP status: $($details.StatusCode)"
    }
    Write-Host "Response: $($details.Message)"

    $message = [string]$details.Message
    if ($message -match "invalid key|unauthorized") {
        Write-Host "Diagnosis: the API key is missing, invalid, disabled, or sent incorrectly." -ForegroundColor Yellow
    } elseif ($message -match "usage limit|limit has been exhausted") {
        Write-Host "Diagnosis: the key is valid, but its configured usage limit is exhausted." -ForegroundColor Yellow
    } elseif ($details.StatusCode -eq 402 -or $message -match "insufficient.*(balance|credit)|billing") {
        Write-Host "Diagnosis: the account likely has insufficient balance or billing access." -ForegroundColor Yellow
    } elseif ($details.StatusCode -eq 429 -or $message -match "rate limit") {
        Write-Host "Diagnosis: requests are being rate-limited; reduce concurrency or retry later." -ForegroundColor Yellow
    } else {
        Write-Host "Diagnosis: inspect the response above; this may be a network, provider, or request-format issue." -ForegroundColor Yellow
    }
}

Write-Host "Testing provider: $BaseUrl"
Write-Host "Testing model:    $Model"
Write-Host "API key length:   $($ApiKey.Length) (value hidden)"

try {
    $modelsResponse = Invoke-RestMethod `
        -Uri "$BaseUrl/models" `
        -Headers $headers `
        -Method Get `
        -TimeoutSec 30

    $modelIds = @($modelsResponse.data | ForEach-Object { $_.id })
    Write-Host "[models] OK - returned $($modelIds.Count) models" -ForegroundColor Green

    if ($modelIds -contains $Model) {
        Write-Host "[models] '$Model' is listed." -ForegroundColor Green
    } else {
        Write-Host "[models] '$Model' is not listed for this key." -ForegroundColor Yellow
    }
} catch {
    Show-ApiFailure -Stage "models" -ErrorRecord $_
    exit 1
}

if ($ModelsOnly) {
    exit 0
}

$body = @{
    model = $Model
    messages = @(
        @{
            role = "user"
            content = "Reply with exactly: OK"
        }
    )
    max_tokens = 5
    temperature = 0
} | ConvertTo-Json -Depth 6

try {
    $chatResponse = Invoke-RestMethod `
        -Uri "$BaseUrl/chat/completions" `
        -Headers $headers `
        -Method Post `
        -Body $body `
        -TimeoutSec 60

    $content = $chatResponse.choices[0].message.content
    Write-Host "[chat] OK" -ForegroundColor Green
    Write-Host "Model response: $content"
    exit 0
} catch {
    Show-ApiFailure -Stage "chat" -ErrorRecord $_
    exit 1
}
